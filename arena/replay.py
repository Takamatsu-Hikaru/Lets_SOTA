"""
训练回放系统
记录和播放训练过程中的各项指标
"""

import json
import os
import datetime
from typing import Dict, List, Optional


class ReplayRecorder:
    """
    训练回放记录器
    记录每个 epoch 的指标，保存为 JSON 文件
    """

    def __init__(self, replay_dir: str = None):
        if replay_dir is None:
            replay_dir = os.environ.get(
                "REPLAY_DIR",
                os.path.join(os.getcwd(), "data", "replays")
            )
        self.replay_dir = replay_dir
        os.makedirs(self.replay_dir, exist_ok=True)
        self.data = {
            "meta": {},
            "epochs": [],
        }

    def set_meta(self, **kwargs):
        """设置回放元数据"""
        self.data["meta"].update(kwargs)

    def record_epoch(self, epoch: int, train_loss: float, val_loss: float,
                     train_accuracy: float = None, val_accuracy: float = None,
                     learning_rate: float = None, **extra):
        """记录一个 epoch 的数据"""
        entry = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "train_accuracy": train_accuracy,
            "val_accuracy": val_accuracy,
            "learning_rate": learning_rate,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
        entry.update(extra)
        self.data["epochs"].append(entry)

    def save(self, run_id: int) -> str:
        """保存回放到文件，返回文件路径"""
        filename = f"run_{run_id}.json"
        path = os.path.join(self.replay_dir, filename)
        with open(path, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        return path

    @staticmethod
    def load(path: str) -> Dict:
        """从文件加载回放数据"""
        with open(path, "r") as f:
            return json.load(f)
