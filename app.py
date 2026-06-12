import os
import json
import threading
import time
import logging
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Optional, List
from queue import Queue

from flask import Flask, render_template, request, jsonify, send_file, redirect
from flask_socketio import SocketIO, emit

# 延迟导入以加快初次启动
import torch
import numpy as np
import pandas as pd
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from torchvision import datasets, transforms
import collections

from ml.designer import parse_graph_to_plan, build_model_from_plan, build_optim_loss_from_plan
from ml.code_generator import generate_pytorch_script, generate_inference_script
from ml.data_loader import get_dataset
from ml.visualization import plot_confusion_matrix, plot_predictions, plot_loss_curve

# ── SOTA Arena imports ────────────────────────────────────────
from arena.models import db
from arena.leaderboard import leaderboard_bp
from arena.achievements import seed_achievements
from arena.datasets import seed_datasets
from arena.hardware import detect_hardware, recommend_batch_size, get_device

# 导入所有 Model 子类，确保 db.create_all() 创建它们的表
import arena.season       # noqa: F401 — registers Season, SeasonSnapshot, SeasonBadge
import arena.challenges   # noqa: F401 — registers DailyChallenge, ChallengeSubmission

def print_progress_bar(current, total, prefix='', suffix='', length=50):
    """Simple progress bar for console output"""
    percent = current / total
    filled_length = int(length * percent)
    bar = '█' * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent:.1%} {suffix}', end='', flush=True)
    if current == total:
        print()  # New line when complete


app = Flask(__name__, template_folder="templates", static_folder="static")
socketio = SocketIO(app, cors_allowed_origins="*")

# ── SOTA Arena 数据库配置 ───────────────────────────────────────
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.environ.get('ARENA_DB_PATH', os.path.join(os.getcwd(), 'data', 'arena.db'))}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# 日志队列和处理器
log_queue = Queue()

class SocketIOLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'level': record.levelname,
            'message': self.format(record),
            'module': record.name
        }
        log_queue.put(log_entry)
        socketio.emit('log', log_entry)

# 设置日志
logger = logging.getLogger('training')
logger.setLevel(logging.INFO)
handler = SocketIOLogHandler()
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
logger.addHandler(console_handler)


# 简易内存存储
GRAPH_STORE_PATH = os.path.join(os.getcwd(), "graph.json")


@dataclass
class TrainState:
    running: bool = False
    stop_requested: bool = False
    epoch: int = 0
    total_epochs: int = 0
    loss: float = 0.0
    train_acc: float = 0.0
    val_loss: float = 0.0
    val_acc: float = 0.0
    best_val_acc: float = 0.0
    best_val_loss: float = 1e9
    best_model_path: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)


state = TrainState()
state_lock = threading.Lock()


@app.route("/api/save_graph", methods=["POST"])
def save_graph():
    # 客户端操作，不再需要服务器保存
    return jsonify({"ok": True})


@app.route("/api/load_graph", methods=["GET"]) 
def load_graph():
    # 客户端操作，不再需要服务器加载
    return jsonify({"graph": None})


def get_model_filename_from_graph(filename=None):
    """从graph.json文件生成模型文件名"""
    try:
        if filename:
            # 如果提供了文件名，使用它
            base_name = filename.replace('.json', '')
        else:
            # 默认使用graph.json
            if os.path.exists(GRAPH_STORE_PATH):
                with open(GRAPH_STORE_PATH, "r", encoding="utf-8") as f:
                    graph = json.load(f)
                
                # 尝试从graph中获取名称，如果没有则使用默认名称
                graph_name = graph.get("name", "model")
                # 清理文件名，移除不合法字符
                graph_name = "".join(c for c in graph_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                if not graph_name:
                    graph_name = "model"
                base_name = graph_name
            else:
                base_name = "model"
        
        return f"{base_name}.pt"
    except Exception:
        return "model.pt"

def run_training_thread(plan: Dict[str, Any], filename: str = None):
    global state
    
    # 立即设置运行状态
    with state_lock:
        state.running = True
        state.stop_requested = False
        state.epoch = 0
        # total_epochs 稍后更新
        state.best_val_acc = 0.0
        state.best_val_loss = 1e9
        state.best_model_path = None
        state.history = []
        
    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 确保training_results文件夹存在
        training_results_dir = os.path.join(os.getcwd(), "training_results")
        if not os.path.exists(training_results_dir):
            os.makedirs(training_results_dir)

        # Data
        batch_size = plan.get("data", {}).get("batch_size", 64)
        dataset_name = plan.get("data", {}).get("dataset", "MNIST")
        data_props = plan.get("data", {})

        # Check if it's a node-based dataset
        data_nodes = [n for n in plan.get("nodes", []) if n.get("type") in ["MNIST", "Fashion-MNIST", "CIFAR-10", "WikiText-2", "WikiText-103", "PennTreebank", "CustomData"]]
        if data_nodes:
            dataset_name = data_nodes[0]["type"]
            batch_size = data_nodes[0]["properties"].get("batch_size", batch_size)
            # Merge properties
            data_props.update(data_nodes[0]["properties"])

        train_loader, test_loader, in_channels, num_classes = get_dataset(dataset_name, batch_size, data_props)

        # Model
        model = build_model_from_plan(plan, in_channels=in_channels, num_classes=num_classes).to(device)

        # Optimizer & Loss
        # criterion is now a dict: {node_id: loss_fn}
        optimizer, criterions = build_optim_loss_from_plan(plan, model)
        
        # Train Configs
        train_configs = plan.get("train", [])
        if not train_configs:
            raise ValueError("No training configuration found")
            
        # Use the first config for global settings like epochs
        main_config = train_configs[0]
        total_epochs = int(main_config.get("epochs", 3))

        with state_lock:
            state.total_epochs = total_epochs

        logger.info(f"🚀 开始训练 {total_epochs} 个周期，使用 {dataset_name} 数据集")
        for epoch in range(1, total_epochs + 1):
            if state.stop_requested:
                logger.info("🛑 训练已停止")
                break
                
            model.train()
            epoch_loss = 0.0
            train_correct = 0
            train_total = 0
            total_batches = len(train_loader)
            
            # Main head config for training accuracy
            main_head_cfg = train_configs[0]
            main_nid = str(main_head_cfg["node_id"])
            main_target_type = main_head_cfg.get("target", "Label")
            main_src_id = str(plan['model']['connections'].get(main_nid, [])[0])

            # Try to find the main criterion for the primary train config.
            # build_optim_loss_from_plan can store criterions with int or str keys,
            # so try both. Fallback to first available criterion or CrossEntropyLoss.
            main_crit = None
            try:
                main_nid_raw = main_head_cfg.get("node_id")
                # Try exact type first
                main_crit = criterions.get(main_nid_raw)
                if main_crit is None:
                    # Try string form
                    main_crit = criterions.get(str(main_nid_raw))
                if main_crit is None and len(criterions) > 0:
                    main_crit = next(iter(criterions.values()))
            except Exception:
                main_crit = nn.CrossEntropyLoss()

            # Extract underlying test dataset object (for classes etc.)
            test_ds = None
            try:
                test_ds_obj = test_loader.dataset
                from torch.utils.data.dataset import Subset
                if isinstance(test_ds_obj, Subset) and hasattr(test_ds_obj, 'dataset'):
                    test_ds = test_ds_obj.dataset
                else:
                    test_ds = test_ds_obj
            except Exception:
                test_ds = None

            for batch_idx, (x, y) in enumerate(train_loader):
                if state.stop_requested:
                    break
                    
                x, y = x.to(device), y.to(device)
                optimizer.zero_grad()
                
                # Forward pass returns dict of outputs
                outputs = model(x)
                
                total_batch_loss = 0.0
                head_losses = {}
                
                # Calculate loss for each head
                for cfg in train_configs:
                    nid = cfg["node_id"]
                    target_type = cfg.get("target", "Label")
                    weight = cfg.get("weight", 1.0)
                    crit = criterions[nid]
                    
                    loss_node_inputs = plan['model']['connections'].get(str(nid), [])
                    if not loss_node_inputs:
                        continue
                        
                    src_id = str(loss_node_inputs[0])
                    pred = outputs.get(src_id)
                    
                    if pred is None:
                        continue
                        
                    if target_type == "Input":
                        target = x
                    else:
                        target = y
                    
                    # Handle sequence outputs (for language modeling)
                    if len(pred.shape) == 3:  # (batch, seq_len, vocab_size)
                        # Reshape for CrossEntropyLoss
                        pred_reshaped = pred.reshape(-1, pred.size(-1))  # (batch*seq_len, vocab_size)
                        if len(target.shape) == 2:  # (batch, seq_len)
                            target_reshaped = target.reshape(-1)  # (batch*seq_len,)
                        else:
                            target_reshaped = target
                        l = crit(pred_reshaped, target_reshaped)
                    else:
                        l = crit(pred, target)
                        
                    total_batch_loss += l * weight
                    head_losses[nid] = l.item()
                
                if isinstance(total_batch_loss, torch.Tensor):
                    total_batch_loss.backward()
                    optimizer.step()
                    epoch_loss += total_batch_loss.item()
                
                # Calculate training accuracy (approximate based on main head)
                if main_target_type != "Input":
                    pred = outputs.get(main_src_id)
                    if pred is not None:
                        if len(pred.shape) == 3:
                            pred_flat = pred.reshape(-1, pred.size(-1))
                            y_flat = y.reshape(-1) if len(y.shape) == 2 else y
                            p = pred_flat.argmax(dim=1)
                            train_correct += (p == y_flat).sum().item()
                            train_total += y_flat.size(0)
                        else:
                            p = pred.argmax(dim=1)
                            train_correct += (p == y).sum().item()
                            train_total += y.size(0)

                # Update progress bar every 10 batches or at the end
                current_loss = total_batch_loss.item() if isinstance(total_batch_loss, torch.Tensor) else 0.0
                if batch_idx % 10 == 0 or batch_idx == total_batches - 1:
                    progress = (batch_idx + 1) / total_batches
                    filled_length = int(50 * progress)
                    bar = '█' * filled_length + '-' * (50 - filled_length)
                    print(f'\rEpoch {epoch} |{bar}| {progress:.1%} Loss: {current_loss:.4f}', end='', flush=True)
                    if batch_idx == total_batches - 1:
                        print()  # New line when epoch complete

                if batch_idx % 50 == 0:
                    current_loss = total_batch_loss.item() if isinstance(total_batch_loss, torch.Tensor) else 0.0
                    logger.info(f"📊 Epoch {epoch}, Batch {batch_idx}/{total_batches}, Loss: {current_loss:.4f}")
                    
                    # If multi-head, add details
                    if len(train_configs) > 1:
                        details = []
                        for i, cfg in enumerate(train_configs):
                            nid = cfg["node_id"]
                            loss_val = head_losses.get(nid, 0.0)
                            details.append(f"Head{i+1}: {loss_val:.4f}")
                        logger.info(f"   多头损失详情: {', '.join(details)}")

            # Eval
            model.eval()
            correct = 0
            total = 0
            val_loss_sum = 0.0
            val_batches = 0
            
            # For visualization
            all_preds = []
            all_targets = []
            sample_images = None
            sample_preds = None
            sample_targets = None
            
            with torch.no_grad():
                for batch_idx, (x, y) in enumerate(test_loader):
                    x, y = x.to(device), y.to(device)
                    outputs = model(x)
                    pred = outputs.get(main_src_id)
                    
                    if pred is None: continue
                    
                    # Calculate validation loss (using main head)
                    if main_target_type == "Input":
                        target = x
                    else:
                        target = y
                        
                    if len(pred.shape) == 3:
                        pred_reshaped = pred.reshape(-1, pred.size(-1))
                        target_reshaped = target.reshape(-1) if len(target.shape) == 2 else target
                        l = main_crit(pred_reshaped, target_reshaped)
                    else:
                        l = main_crit(pred, target)
                    
                    val_loss_sum += l.item()
                    val_batches += 1
                    
                    if main_target_type == "Input":
                        total += 1 # Count batches for metric
                    else:
                        # Handle sequence outputs for classification
                        if len(pred.shape) == 3:
                            pred_flat = pred.reshape(-1, pred.size(-1))
                            y_flat = y.reshape(-1) if len(y.shape) == 2 else y
                            p = pred_flat.argmax(dim=1)
                            correct += (p == y_flat).sum().item()
                            total += y_flat.size(0)
                        else:
                            p = pred.argmax(dim=1)
                            correct += (p == y).sum().item()
                            total += y.size(0)
                            
                            # Collect for visualization (only for classification tasks)
                            if epoch == total_epochs: # Only last epoch to save time
                                all_preds.extend(p.cpu().numpy())
                                all_targets.extend(y.cpu().numpy())
                                
                                if sample_images is None:
                                    sample_images = x[:16]
                                    sample_preds = p[:16]
                                    sample_targets = y[:16]
            
            val_loss = val_loss_sum / max(val_batches, 1)
            
            if main_target_type == "Input":
                val_metric = val_loss
                metric_name = "val_loss"
                train_metric = 0.0 # No accuracy for input reconstruction usually
            else:
                val_metric = correct / max(total, 1)
                metric_name = "val_acc"
                train_metric = train_correct / max(train_total, 1)

            with state_lock:
                state.epoch = epoch
                state.loss = float(epoch_loss / max(len(train_loader), 1))
                state.train_acc = float(train_metric)
                state.val_loss = float(val_loss)
                state.val_acc = float(val_metric)
                
                state.history.append({
                    "epoch": epoch,
                    "loss": state.loss,
                    "train_acc": state.train_acc,
                    "val_loss": state.val_loss,
                    "val_acc": state.val_acc
                })
                
                if main_target_type == "Input":
                    logger.info(f"✅ Epoch {epoch} 完成, 验证损失: {val_metric:.4f}")
                else:
                    logger.info(f"✅ Epoch {epoch} 完成, 验证准确率: {val_metric:.4f}")
                
                if main_target_type == "Input":
                    if val_metric < state.best_val_loss:
                        state.best_val_loss = float(val_metric)
                        model_filename = get_model_filename_from_graph(filename)
                        best_path = os.path.join(training_results_dir, model_filename)
                        torch.save(model.state_dict(), best_path)
                        state.best_model_path = best_path
                        logger.info(f"💾 保存最佳模型到 training_results/{model_filename} (验证损失: {val_metric:.4f})")
                elif val_metric > state.best_val_acc:
                    state.best_val_acc = float(val_metric)
                    model_filename = get_model_filename_from_graph(filename)
                    best_path = os.path.join(training_results_dir, model_filename)
                    torch.save(model.state_dict(), best_path)
                    state.best_model_path = best_path
                    logger.info(f"💾 保存最佳模型到 training_results/{model_filename} (验证准确率: {val_metric:.4f})")

            # Visualization (Last Epoch)
            if epoch == total_epochs:
                plots_dir = os.path.join(app.static_folder, "plots")
                if not os.path.exists(plots_dir):
                    os.makedirs(plots_dir)
                
                # 1. Loss Curve
                plot_loss_curve(state.history, os.path.join(plots_dir, "loss_curve.png"))
                socketio.emit('update_plots', {'type': 'loss_curve', 'url': '/static/plots/loss_curve.png?t=' + str(time.time())})
                
                # 2. Confusion Matrix & Predictions (Classification only)
                if main_target_type != "Input" and all_preds:
                    classes = test_ds.classes if hasattr(test_ds, 'classes') else [str(i) for i in range(num_classes)]
                    
                    plot_confusion_matrix(all_targets, all_preds, classes, os.path.join(plots_dir, "confusion_matrix.png"))
                    socketio.emit('update_plots', {'type': 'confusion_matrix', 'url': '/static/plots/confusion_matrix.png?t=' + str(time.time())})
                    
                    if sample_images is not None:
                        plot_predictions(sample_images, sample_targets, sample_preds, classes, os.path.join(plots_dir, "predictions.png"))
                        socketio.emit('update_plots', {'type': 'predictions', 'url': '/static/plots/predictions.png?t=' + str(time.time())})

        logger.info("🎉 训练完成！")
        
    except Exception as e:
        logger.error(f"❌ 训练出错: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        with state_lock:
            state.running = False


@app.route("/api/stop", methods=["POST"])
def stop_training():
    with state_lock:
        if state.running:
            state.stop_requested = True
            logger.info("🛑 收到停止训练请求...")
    return jsonify({"ok": True})


@app.route("/api/run", methods=["POST"]) 
def run_training():
    try:
        data = request.get_json(force=True)
        filename = data.get("filename")
        graph = data.get("graph", data)  # 兼容旧格式
        plan = parse_graph_to_plan(graph)
        t = threading.Thread(target=run_training_thread, args=(plan, filename,), daemon=True)
        t.start()
        return jsonify({"ok": True})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Internal Error: {str(e)}"}), 500


@socketio.on('connect')
def handle_connect():
    logger.info("📡 前端已连接")

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("🔌 前端已断开连接")

@socketio.on('request_logs')
def handle_request_logs():
    # 发送最近的日志历史
    logs = []
    while not log_queue.empty() and len(logs) < 100:  # 最多发送100条最近日志
        logs.append(log_queue.get())
    emit('log_history', logs)

@app.route("/api/status", methods=["GET"]) 
def status():
    with state_lock:
        return jsonify(asdict(state))


@app.route("/api/generate_script", methods=["POST"]) 
def generate_script():
    try:
        data = request.get_json(force=True)
        filename = data.get("filename")
        graph = data.get("graph", data)  # 兼容旧格式
        plan = parse_graph_to_plan(graph)
        
        # 生成基于graph名称的脚本文件名
        script_filename = get_model_filename_from_graph(filename).replace('.pt', '.py')

        # Generate standalone PyTorch script
        code = generate_pytorch_script(plan)

        return jsonify({"ok": True, "code": code, "filename": script_filename})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/export_app", methods=["POST"])
def export_app():
    try:
        data = request.get_json(force=True)
        filename = data.get("filename")
        graph = data.get("graph", data)
        plan = parse_graph_to_plan(graph)
        
        script_filename = get_model_filename_from_graph(filename).replace('.pt', '_app.py')
        
        code = generate_inference_script(plan)
        
        return jsonify({"ok": True, "code": code, "filename": script_filename})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/subgraphs", methods=["GET"])
def list_subgraphs():
    subgraphs_dir = os.path.join(os.getcwd(), "subgraphs")
    if not os.path.exists(subgraphs_dir):
        os.makedirs(subgraphs_dir)
    files = [f for f in os.listdir(subgraphs_dir) if f.endswith(".json")]
    return jsonify({"files": files})

@app.route("/api/subgraphs/<name>", methods=["GET"])
def get_subgraph(name):
    subgraphs_dir = os.path.join(os.getcwd(), "subgraphs")
    path = os.path.join(subgraphs_dir, name)
    if not os.path.exists(path):
        return jsonify({"error": "Not found"}), 404
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/api/subgraphs/<name>", methods=["POST"])
def save_subgraph(name):
    subgraphs_dir = os.path.join(os.getcwd(), "subgraphs")
    if not os.path.exists(subgraphs_dir):
        os.makedirs(subgraphs_dir)
    path = os.path.join(subgraphs_dir, name)
    data = request.get_json(force=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})

@app.route("/api/subgraphs/<name>", methods=["DELETE"])
def delete_subgraph(name):
    subgraphs_dir = os.path.join(os.getcwd(), "subgraphs")
    path = os.path.join(subgraphs_dir, name)
    if not os.path.exists(path):
        return jsonify({"error": "Not found"}), 404
    try:
        os.remove(path)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Marketplace proxy routes ───────────────────────────────────────────────────

MARKET_SERVER_URL = os.environ.get("MARKET_SERVER_URL", "https://cortexnodus.streetartist.top")

@app.route("/api/market_config", methods=["GET"])
def market_config():
    """告知前端市场服务器的地址"""
    return jsonify({"url": MARKET_SERVER_URL})


# ── SOTA Arena 路由 ─────────────────────────────────────────────

# 注册蓝图
app.register_blueprint(leaderboard_bp)


# 硬件检测 API
@app.route("/api/arena/hardware")
def api_hardware():
    profile = detect_hardware()
    return json.dumps(profile.__dict__)


# ── 主页面路由 ──────────────────────────────────────────────
@app.route("/")
def arena_page():
    """Let's SOTA!!!!! — 主页（竞技面板）"""
    return render_template("arena.html")


@app.route("/workshop")
def workshop_page():
    """模型搭建工坊（LiteGraph 编辑器）"""
    return render_template("workshop.html")


@app.route("/arena")
def arena_redirect():
    return redirect("/")


# 成就 API
@app.route("/api/arena/achievements/<player_name>")
def api_achievements(player_name):
    from arena.models import Player, Achievement, PlayerAchievement
    player = Player.query.filter_by(name=player_name).first()
    unlocked = set()
    if player:
        unlocked = {
            pa.achievement_id
            for pa in PlayerAchievement.query.filter_by(player_id=player.id).all()
        }
    all_ach = Achievement.query.all()
    return json.dumps({
        "achievements": [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "icon": a.icon,
                "category": a.category,
                "rarity": a.rarity,
            }
            for a in all_ach
        ],
        "unlocked": list(unlocked),
    }, ensure_ascii=False)


# Model Zoo API
ZOO_DIR = os.path.join(os.getcwd(), "model_zoo")

@app.route("/api/zoo")
def api_zoo_list():
    try:
        models = []
        p = os.path.join(ZOO_DIR, "registry.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                models = json.load(f)
        return jsonify(models)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/zoo/<model_id>")
def api_zoo_detail(model_id):
    try:
        graph_path = os.path.join(ZOO_DIR, model_id, "graph.json")
        meta_path = os.path.join(ZOO_DIR, model_id, "meta.json")
        result = {}
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                result["meta"] = json.load(f)
        if os.path.exists(graph_path):
            with open(graph_path, "r", encoding="utf-8") as f:
                result["graph"] = json.load(f)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


# ── Season API ────────────────────────────────────────────────────
@app.route("/api/arena/season")
def api_season():
    from arena.season import get_or_create_current_season, Season, SeasonBadge
    season = get_or_create_current_season()
    badges = SeasonBadge.query.all()
    return json.dumps({
        "id": season.id,
        "name": season.name,
        "slug": season.slug,
        "started_at": season.started_at.isoformat() if season.started_at else "",
        "is_active": season.is_active,
        "total_badges_awarded": len(badges),
    }, ensure_ascii=False)


@app.route("/api/arena/season/leaderboard")
def api_season_leaderboard():
    """赛季排行榜（仅展示本赛季提交）"""
    from arena.models import TrainingRun, Player
    from arena.season import get_or_create_current_season
    from sqlalchemy import desc

    season = get_or_create_current_season()
    dataset = request.args.get("dataset", "mnist")
    limit = min(int(request.args.get("limit", 20)), 100)

    runs = (
        TrainingRun.query
        .join(Player)
        .filter(TrainingRun.dataset_id == dataset)
        .filter(TrainingRun.final_accuracy.isnot(None))
        .filter(TrainingRun.finished_at >= season.started_at)
        .order_by(desc(TrainingRun.best_accuracy))
        .limit(limit)
        .all()
    )

    results = []
    for i, run in enumerate(runs, 1):
        player = Player.query.get(run.player_id)
        results.append({
            "rank": i,
            "player_name": player.name if player else "Unknown",
            "model_name": run.model_name,
            "accuracy": round(run.best_accuracy, 4) if run.best_accuracy else 0,
            "duration": run.train_duration_seconds,
            "hardware_tier": run.hardware_tier,
            "submitted_at": run.finished_at.isoformat() if run.finished_at else "",
            "season_name": season.name,
        })
    return json.dumps({"leaderboard": results, "season": season.name})


@app.route("/api/arena/player/<player_name>/badges")
def api_player_badges(player_name):
    from arena.models import Player
    from arena.season import get_player_season_badges
    player = Player.query.filter_by(name=player_name).first()
    if not player:
        return json.dumps({"badges": []})
    badges = get_player_season_badges(player.id)
    return json.dumps({"badges": badges})


# ── Daily Challenge API ──────────────────────────────────────────
@app.route("/api/arena/challenge")
def api_challenge():
    from arena.challenges import get_today_challenge, DailyChallenge
    challenge = get_today_challenge()
    if not challenge:
        return json.dumps({"error": "No challenge today"})

    # 解析约束
    try:
        constraints = json.loads(challenge.constraints) if isinstance(challenge.constraints, str) else challenge.constraints
    except Exception:
        constraints = {}

    return json.dumps({
        "id": challenge.id,
        "date": challenge.date.isoformat() if challenge.date else "",
        "title": challenge.title,
        "description": challenge.description,
        "constraints": constraints,
        "target_dataset": challenge.target_dataset,
        "target_metric": challenge.target_metric,
        "target_threshold": challenge.target_threshold,
    }, ensure_ascii=False)


# ── Player Ranking API ───────────────────────────────────────────
@app.route("/api/arena/rankings")
def api_rankings():
    """获取所有玩家排名"""
    from arena.models import Player
    from arena.ranking import get_rank_tier
    from sqlalchemy import desc

    players = Player.query.order_by(desc(Player.best_accuracy)).all()
    rankings = []
    for i, p in enumerate(players, 1):
        tier = get_rank_tier(p.best_accuracy or 0)
        rankings.append({
            "rank": i,
            "player_name": p.name,
            "best_accuracy": p.best_accuracy,
            "total_runs": p.total_runs,
            "tier": tier["id"],
            "tier_name": tier["name"],
            "tier_icon": tier["icon"],
            "tier_color": tier["color"],
        })
    return json.dumps(rankings, ensure_ascii=False)


@app.route("/api/arena/player/<player_name>/rank")
def api_player_rank(player_name):
    from arena.models import Player
    from arena.ranking import get_player_rank_info
    player = Player.query.filter_by(name=player_name).first()
    if not player:
        return json.dumps({"error": "Player not found"})
    info = get_player_rank_info(player)
    return json.dumps(info, ensure_ascii=False)


# ── Arena Training API ───────────────────────────────────────────
from arena.train import arena_trainer


@app.route("/api/arena/train", methods=["POST"])
def api_arena_train():
    data = request.json
    result = arena_trainer.start_training(
        params=data,
    )
    return jsonify(result)


@app.route("/api/arena/train/progress")
def api_arena_train_progress():
    """获取当前训练进度"""
    progress = arena_trainer.get_progress()
    return jsonify(progress)


@app.route("/api/arena/train/result")
def api_arena_train_result():
    """获取最近完成的训练结果"""
    result = arena_trainer.get_result()
    return jsonify(result if result else {"status": "no_result"})


@app.route("/api/arena/debug")
def api_debug():
    """Debug: test model creation in process"""
    import torch
    import torch.nn as nn
    try:
        model = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d((4, 4)), nn.Flatten(),
            nn.Linear(64 * 4 * 4, 128), nn.ReLU(), nn.Linear(128, 10),
        )
        params = sum(p.numel() for p in model.parameters())
        opt = torch.optim.Adam(model.parameters(), lr=0.001)
        return jsonify({"params": int(params), "optimizer": str(type(opt).__name__), "success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 初始化 Arena 数据库
def init_arena_db():
    """在应用上下文中初始化数据库和种子数据"""
    with app.app_context():
        db.create_all()
        seed_datasets()
        seed_achievements()
        from arena.season import get_or_create_current_season
        season = get_or_create_current_season()
        print(f"  [OK] SOTA Arena database initialized")
        print(f"  [Season] Active season: {season.name}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # 在训练过程中禁用调试模式以避免文件变化导致的自动重启
    # 可以通过环境变量 FLASK_DEBUG=1 来启用调试模式
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    
    if debug_mode:
        # 在调试模式下，忽略training_results文件夹的变化
        import werkzeug.serving
        original_is_changed = werkzeug.serving._is_changed
        
        def patched_is_changed(filename):
            # 忽略training_results文件夹中的文件变化
            if 'training_results' in str(filename):
                return False
            return original_is_changed(filename)
        
        werkzeug.serving._is_changed = patched_is_changed
    
    # 初始化 Arena 数据库
    init_arena_db()

    url = f"http://localhost:{port}"
    print(f"""
  +--------------------------------------------+
  |         Let's SOTA!!!!!                     |
  |         AI Model Arena                      |
  +--------------------------------------------+
  |  Main  : {url:<39s}|
  |  Studio: {url + '/workshop':<38s}|
  +--------------------------------------------+
  Press Ctrl+C to quit.
""")
    socketio.run(app, host="0.0.0.0", port=port, debug=debug_mode, allow_unsafe_werkzeug=True)
