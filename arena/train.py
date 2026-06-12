"""
Arena 训练桥接
将 Arena 的"开始训练"接入 CortexNodus 实际的训练引擎
"""

import json
import threading
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger('arena.train')


class ArenaTrainer:
    """
    Arena 训练管理器
    接收 Arena 提交的训练参数，调用 CortexNodus 训练引擎，
    训练完成后自动提交结果到排行榜
    """

    def __init__(self):
        self._training_lock = threading.Lock()
        self._active_train: Optional[dict] = None
        self._progress: dict = {}
        self._last_result: Optional[dict] = None

    def get_progress(self) -> dict:
        """返回当前训练进度（供前端轮询）"""
        with self._training_lock:
            if not self._active_train:
                return {"running": False, "progress": 0}
            return {**self._progress, "running": True}

    def get_result(self) -> Optional[dict]:
        """返回最近完成的训练结果"""
        return self._last_result

    def start_training(self, params: dict) -> dict:
        """
        开始训练
        Args:
            params: {
                "dataset": "mnist",
                "learning_rate": 0.001,
                "batch_size": 64,
                "epochs": 5,
                "optimizer": "Adam",
                "graph_json": ...  # 可选
                "model_name": "My Model",
                "player_name": "NeuroNinja",
                "graph_source": "preset",  # "preset" | "workshop"
            }
        """
        with self._training_lock:
            if self._active_train:
                return {"error": "Training already in progress"}
            self._active_train = params
            self._progress = {"epoch": 0, "total_epochs": params.get("epochs", 5), "status": "starting", "message": "Initializing..."}

        thread = threading.Thread(target=self._run_training, args=(params,), daemon=True)
        thread.start()
        return {"ok": True, "message": "Training started"}

    def _run_training(self, params):
        """实际的训练循环"""
        try:
            import torch
            from torch import nn
            from torch.utils.data import DataLoader
            from ml.designer import parse_graph_to_plan, build_model_from_plan, build_optim_loss_from_plan

            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            dataset_id = params.get("dataset", "mnist")
            batch_size = params.get("batch_size", 64)

            # Normalize dataset name for ml.data_loader
            DATASET_NAME_MAP = {
                "mnist": "MNIST",
                "fashion-mnist": "Fashion-MNIST",
                "cifar10": "CIFAR-10",
                "cifar100": "CIFAR-100",
                "svhn": "SVHN",
                "imagenet-tiny": "TinyImageNet",
            }
            dl_dataset_name = DATASET_NAME_MAP.get(dataset_id, dataset_id)

            from ml.data_loader import get_dataset as _get_dataset_old
            try:
                train_loader, test_loader, in_channels, num_classes = _get_dataset_old(dl_dataset_name, batch_size, {})
            except (ValueError, KeyError, AttributeError) as e:
                # Fall back to Arena's dataset loader for SVHN, Tiny ImageNet etc.
                logger.info(f"Old loader failed ({e}), trying Arena dataset loader...")
                from arena.datasets import get_dataloaders as _get_dataset_arena
                train_loader, test_loader = _get_dataset_arena(dataset_id, batch_size, num_workers=0)
                if dataset_id == "svhn":
                    in_channels, num_classes = 3, 10
                elif dataset_id == "imagenet-tiny":
                    in_channels, num_classes = 3, 200
                elif dataset_id == "cifar100":
                    in_channels, num_classes = 3, 100
                else:
                    in_channels, num_classes = 3, 10

            # 构建模型
            graph_json = params.get("graph_json")
            if graph_json:
                graph_data = json.loads(graph_json) if isinstance(graph_json, str) else graph_json
                plan = parse_graph_to_plan(graph_data)
                model = build_model_from_plan(plan, in_channels=in_channels, num_classes=num_classes).to(device)
                optimizer, criterions = build_optim_loss_from_plan(plan, model)
            else:
                # Build a Sequential CNN model directly — DO NOT use nn.Sequential.add_module pattern
                layers = [
                    nn.Conv2d(in_channels if in_channels <= 3 else 1, 32, 3, padding=1),
                    nn.ReLU(),
                    nn.MaxPool2d(2),
                    nn.Conv2d(32, 64, 3, padding=1),
                    nn.ReLU(),
                    nn.MaxPool2d(2),
                    nn.AdaptiveAvgPool2d((4, 4)),
                    nn.Flatten(),
                    nn.Linear(64 * 4 * 4, 128),
                    nn.ReLU(),
                    nn.Linear(128, num_classes),
                ]
                model = nn.Sequential(*layers)
                model.to(device)
                lr = float(params.get("learning_rate", 0.001))
                optimizer = torch.optim.Adam(model.parameters(), lr=lr)
                criterions = {0: nn.CrossEntropyLoss()}
                logger.info(f"Built fallback Sequential model with {sum(p.numel() for p in model.parameters())} params")

            main_crit = next(iter(criterions.values())) if criterions else nn.CrossEntropyLoss()

            total_epochs = int(params.get("epochs", 5))
            lr = float(params.get("learning_rate", 0.001))

            if isinstance(optimizer, torch.optim.Optimizer):
                for param_group in optimizer.param_groups:
                    param_group['lr'] = lr

            self._update_progress({"status": "training", "message": "Training..."})
            logger.info(f"[Arena] Training {dataset_id}, {total_epochs} epochs, lr={lr}, device={device}")

            start_time = time.time()
            epoch_logs = []
            best_accuracy = 0.0
            best_epoch = 0

            for epoch in range(1, total_epochs + 1):
                model.train()
                epoch_loss = 0.0
                train_correct = 0
                train_total = 0

                # Helper: from model output dict, pick the tensor matching num_classes
                def _pick_pred(outputs, num_classes):
                    if not isinstance(outputs, dict):
                        return outputs
                    # Prefer the tensor with last dim == num_classes
                    for v in outputs.values():
                        if isinstance(v, torch.Tensor) and v.shape[-1] == num_classes:
                            return v
                    # Fallback: last tensor in the dict
                    last = None
                    for v in outputs.values():
                        if isinstance(v, torch.Tensor):
                            last = v
                    return last

                for x, y in train_loader:
                    x, y = x.to(device), y.to(device)
                    optimizer.zero_grad()
                    outputs = model(x)
                    pred = _pick_pred(outputs, num_classes)
                    if pred is None:
                        raise RuntimeError("Model produced no usable output tensor")

                    loss = main_crit(pred, y) if len(pred.shape) <= 2 else main_crit(pred.reshape(-1, pred.size(-1)), y.reshape(-1))
                    loss.backward()
                    optimizer.step()
                    epoch_loss += loss.item()
                    p = pred.argmax(dim=1) if len(pred.shape) > 1 else pred
                    if len(p.shape) > 1: p = p.reshape(-1)
                    yf = y.reshape(-1) if len(y.shape) > 1 else y
                    train_correct += (p == yf).sum().item() if len(p.shape) == 1 else 0
                    train_total += yf.size(0)

                # 验证
                model.eval()
                correct = total = val_loss_sum = val_batches = 0
                with torch.no_grad():
                    for x, y in test_loader:
                        x, y = x.to(device), y.to(device)
                        outputs = model(x)
                        pred = _pick_pred(outputs, num_classes)
                        if pred is None: continue
                        l = main_crit(pred, y) if len(pred.shape) <= 2 else main_crit(pred.reshape(-1, pred.size(-1)), y.reshape(-1))
                        val_loss_sum += l.item(); val_batches += 1
                        p = pred.argmax(dim=1) if len(pred.shape) > 1 else pred
                        if len(p.shape) > 1: p = p.reshape(-1)
                        yf = y.reshape(-1) if len(y.shape) > 1 else y
                        correct += (p == yf).sum().item() if len(p.shape) == 1 else 0
                        total += yf.size(0)

                val_loss = val_loss_sum / max(val_batches, 1)
                val_acc = correct / max(total, 1) * 100
                train_acc = train_correct / max(train_total, 1) * 100

                if val_acc > best_accuracy:
                    best_accuracy = val_acc; best_epoch = epoch

                epoch_data = {
                    "epoch": epoch, "train_loss": round(epoch_loss / max(len(train_loader), 1), 6),
                    "val_loss": round(val_loss, 6), "train_accuracy": round(train_acc, 4),
                    "val_accuracy": round(val_acc, 4),
                }
                epoch_logs.append(epoch_data)
                logger.info(f"  Epoch {epoch}/{total_epochs} — loss: {epoch_loss/len(train_loader):.4f} — val_acc: {val_acc:.2f}%")
                self._update_progress({"epoch": epoch, "total_epochs": total_epochs, "status": "training", "message": f"Epoch {epoch}/{total_epochs} - {val_acc:.2f}%", "last_epoch": epoch_data})

            # 完成
            duration = int(time.time() - start_time)
            self._last_result = {
                "type": "done",
                "dataset_id": dataset_id,
                "model_name": params.get("model_name", "Arena Model"),
                "best_accuracy": best_accuracy,
                "best_epoch": best_epoch,
                "learning_rate": lr, "batch_size": batch_size,
                "epochs": total_epochs, "optimizer": params.get("optimizer", "Adam"),
                "duration_seconds": duration,
                "epoch_logs": epoch_logs,
                "player_name": params.get("player_name", "Anonymous"),
                "hardware_info": {
                    "has_gpu": torch.cuda.is_available(),
                    "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                    "gpu_vram_gb": round(torch.cuda.get_device_properties(0).total_mem / (1024**3), 1) if torch.cuda.is_available() else None,
                    "tier": "gpu-high" if (torch.cuda.is_available() and torch.cuda.get_device_properties(0).total_mem / (1024**3) >= 12)
                            else "gpu-mid" if (torch.cuda.is_available() and torch.cuda.get_device_properties(0).total_mem / (1024**3) >= 6)
                            else "gpu-low" if torch.cuda.is_available() else "cpu",
                },
                "device": "cuda" if torch.cuda.is_available() else "cpu",
            }
            logger.info(f"[Arena] Training complete! Best: {best_accuracy:.2f}%")
            self._update_progress({"status": "done", "progress": 100, "message": f"Complete! {best_accuracy:.2f}%"})

        except Exception as e:
            logger.error(f"[Arena] Training error: {e}")
            import traceback; traceback.print_exc()
            self._last_result = {"type": "error", "error": str(e)}
            self._update_progress({"status": "error", "message": f"Error: {e}"})
        finally:
            with self._training_lock:
                self._active_train = None

    def _update_progress(self, updates: dict):
        with self._training_lock:
            self._progress.update(updates)

    def _build_default_plan(self, dataset_id: str, num_classes: int, params: dict) -> dict:
        lr = params.get("learning_rate", 0.001)
        epochs = params.get("epochs", 5)
        optimizer = params.get("optimizer", "Adam")
        return {
            "data": {"dataset": dataset_id, "batch_size": params.get("batch_size", 64)},
            "model": {"connections": {}},
            "train": [{"node_id": "loss_1", "epochs": epochs, "lr": lr, "optimizer": optimizer, "kind": "CrossEntropy", "target": "Label", "weight": 1.0}],
        }

    def stop_training(self):
        with self._training_lock:
            self._active_train = None


arena_trainer = ArenaTrainer()
