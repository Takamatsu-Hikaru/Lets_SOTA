"""
数据模型 — SQLAlchemy + SQLite
所有竞技数据的持久化层
"""

import datetime
import json
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Player(db.Model):
    """玩家"""
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    hardware_fingerprint = db.Column(db.String(12))
    hardware_tier = db.Column(db.String(16), default="cpu")
    hardware_info = db.Column(db.Text)  # JSON: 完整硬件档案

    # 统计缓存（定期更新，避免每次聚合查询）
    total_runs = db.Column(db.Integer, default=0)
    best_accuracy = db.Column(db.Float, default=0.0)
    total_train_seconds = db.Column(db.Integer, default=0)

    runs = db.relationship("TrainingRun", backref="player", lazy="dynamic")
    achievements = db.relationship("PlayerAchievement", backref="player", lazy="dynamic")


class Dataset(db.Model):
    """注册的数据集"""
    __tablename__ = "datasets"

    id = db.Column(db.String(32), primary_key=True)  # "mnist", "cifar10" 等
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    input_shape = db.Column(db.String(32))            # "1,28,28"
    num_classes = db.Column(db.Integer)
    train_size = db.Column(db.Integer)
    test_size = db.Column(db.Integer)

    # SOTA 追踪
    current_sota_accuracy = db.Column(db.Float, default=0.0)
    current_sota_run_id = db.Column(db.Integer, db.ForeignKey("training_runs.id"), nullable=True)


class TrainingRun(db.Model):
    """一次训练记录"""
    __tablename__ = "training_runs"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    dataset_id = db.Column(db.String(32), db.ForeignKey("datasets.id"), nullable=False)

    # 模型信息
    model_name = db.Column(db.String(128))
    model_hash = db.Column(db.String(16))             # 模型结构 hash（判断重复）
    graph_json = db.Column(db.Text)                    # LiteGraph 完整节点图
    generated_code = db.Column(db.Text)                # 生成的 PyTorch 代码

    # 训练参数
    learning_rate = db.Column(db.Float)
    batch_size = db.Column(db.Integer)
    epochs = db.Column(db.Integer)
    optimizer = db.Column(db.String(32))

    # 结果
    final_accuracy = db.Column(db.Float)
    final_loss = db.Column(db.Float)
    best_accuracy = db.Column(db.Float)               # 所有 epoch 中最好的
    best_epoch = db.Column(db.Integer)

    # 时间
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    train_duration_seconds = db.Column(db.Integer)

    # 硬件上下文
    hardware_tier = db.Column(db.String(16))
    device_used = db.Column(db.String(16))            # "cuda", "cpu", "mps"

    # 回放数据路径
    replay_path = db.Column(db.String(256))

    # 验证状态（防作弊）
    is_verified = db.Column(db.Boolean, default=False)
    verification_hash = db.Column(db.String(64))      # 训练过程 checksum

    dataset = db.relationship("Dataset", foreign_keys=[dataset_id])


class EpochLog(db.Model):
    """每个 epoch 的详细记录（用于回放和图表）"""
    __tablename__ = "epoch_logs"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("training_runs.id"), nullable=False)
    epoch = db.Column(db.Integer, nullable=False)

    train_loss = db.Column(db.Float)
    train_accuracy = db.Column(db.Float)
    val_loss = db.Column(db.Float)
    val_accuracy = db.Column(db.Float)

    learning_rate = db.Column(db.Float)               # 如果有 scheduler
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # 可选：每 epoch 的混淆矩阵（JSON）
    confusion_matrix = db.Column(db.Text)

    run = db.relationship("TrainingRun", backref=db.backref("epoch_logs", order_by="EpochLog.epoch"))


class Achievement(db.Model):
    """成就定义"""
    __tablename__ = "achievements"

    id = db.Column(db.String(32), primary_key=True)   # "first_blood", "99_club" 等
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(256))
    icon = db.Column(db.String(32))                    # Tabler icon name
    category = db.Column(db.String(32))                # "milestone", "speed", "mastery"
    rarity = db.Column(db.String(16), default="common")  # common/rare/epic/legendary

    # 解锁条件（JSON，由 achievements.py 解析执行）
    condition = db.Column(db.Text)


class PlayerAchievement(db.Model):
    """玩家已解锁的成就"""
    __tablename__ = "player_achievements"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    achievement_id = db.Column(db.String(32), db.ForeignKey("achievements.id"), nullable=False)
    unlocked_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    unlocked_by_run_id = db.Column(db.Integer, db.ForeignKey("training_runs.id"), nullable=True)

    achievement = db.relationship("Achievement")
