"""
每日挑战系统 (Daily Challenges)
每天生成随机约束条件，玩家在约束下训练并提交
"""

import datetime
import random
from .models import db


class DailyChallenge(db.Model):
    """每日挑战定义"""
    __tablename__ = "daily_challenges"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)      # 挑战日期
    title = db.Column(db.String(128), nullable=False)            # 标题
    description = db.Column(db.Text)                             # 详细描述
    constraints = db.Column(db.Text)                             # JSON: 约束条件

    # 挑战目标
    target_dataset = db.Column(db.String(32))
    target_metric = db.Column(db.String(16), default="accuracy")  # accuracy / loss
    target_threshold = db.Column(db.Float, default=0.0)           # 目标值

    is_active = db.Column(db.Boolean, default=True)


class ChallengeSubmission(db.Model):
    """玩家对每日挑战的提交"""
    __tablename__ = "challenge_submissions"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("daily_challenges.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    run_id = db.Column(db.Integer, db.ForeignKey("training_runs.id"), nullable=True)

    achieved_metric = db.Column(db.Float)
    passed = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    challenge = db.relationship("DailyChallenge", backref="submissions")
    player = db.relationship("Player", backref="challenge_submissions")


# ============================================================
#  挑战模板
# ============================================================

CHALLENGE_TEMPLATES = [
    {
        "title": "Layer Limit",
        "description": "用不超过 {max_layers} 层达到 {dataset} 最高 accuracy",
        "constraints": {"max_layers": 3},
        "target_dataset": "mnist",
        "target_metric": "accuracy",
        "target_threshold": 95.0,
    },
    {
        "title": "Batch Blitz",
        "description": "batch size 固定为 {batch_size}，在 {dataset} 上谁能最快到 {threshold}%？",
        "constraints": {"batch_size": 8},
        "target_dataset": "fashion-mnist",
        "target_metric": "accuracy",
        "target_threshold": 88.0,
    },
    {
        "title": "No Conv, No Cry",
        "description": "在 {dataset} 上使用纯 MLP 架构（不用卷积层）达到 {threshold}% accuracy",
        "constraints": {"no_conv": True},
        "target_dataset": "cifar10",
        "target_metric": "accuracy",
        "target_threshold": 40.0,
    },
    {
        "title": "Speed Demon",
        "description": "在 {dataset} 上 30 秒内达到最高 accuracy",
        "constraints": {"max_time": 30},
        "target_dataset": "mnist",
        "target_metric": "speed",
        "target_threshold": 90.0,
    },
    {
        "title": "Tiny Model",
        "description": "用不超过 {param_limit} 参数在 {dataset} 上达到最高 accuracy",
        "constraints": {"param_limit": "50K"},
        "target_dataset": "mnist",
        "target_metric": "accuracy",
        "target_threshold": 95.0,
    },
    {
        "title": "CIFAR Challenge",
        "description": "在 CIFAR-10 上用 {optimizer} 优化器达到最高 accuracy",
        "constraints": {"optimizer": "SGD"},
        "target_dataset": "cifar10",
        "target_metric": "accuracy",
        "target_threshold": 60.0,
    },
    {
        "title": "One Epoch Wonder",
        "description": "只用 1 个 epoch 在 {dataset} 上达到最高 accuracy",
        "constraints": {"epochs": 1},
        "target_dataset": "fashion-mnist",
        "target_metric": "accuracy",
        "target_threshold": 80.0,
    },
    {
        "title": "Dropout Master",
        "description": "在 {dataset} 上使用 Dropout 层达到 {threshold}%+ accuracy",
        "constraints": {"use_dropout": True},
        "target_dataset": "cifar10",
        "target_metric": "accuracy",
        "target_threshold": 65.0,
    },
]


def generate_daily_challenge():
    """
    生成今日挑战
    如果当天已有挑战则返回现有挑战
    """
    today = datetime.date.today()
    existing = DailyChallenge.query.filter_by(date=today).first()
    if existing:
        return existing

    # 随机选择一个模板并填充
    template = random.choice(CHALLENGE_TEMPLATES)
    dataset_choices = ["mnist", "fashion-mnist", "cifar10", "cifar100"]
    ds = template.get("target_dataset")
    if ds == "random":
        ds = random.choice(dataset_choices)

    # 填充模板变量
    title = template["title"]
    desc = template["description"]
    constraints = template["constraints"]

    # 根据数据集调整阈值
    threshold = template["target_threshold"]
    if ds == "cifar100":
        threshold = max(threshold - 20, 20)

    challenge = DailyChallenge(
        date=today,
        title=title,
        description=desc.format(
            dataset=ds.upper(),
            threshold=threshold,
            **constraints
        ),
        constraints=str(constraints),
        target_dataset=ds,
        target_metric=template["target_metric"],
        target_threshold=threshold,
        is_active=True,
    )
    db.session.add(challenge)
    db.session.commit()
    return challenge


def check_challenge_submission(challenge: DailyChallenge, run) -> bool:
    """检查一次训练提交是否满足每日挑战要求"""
    from .models import TrainingRun

    metric = challenge.target_metric
    threshold = challenge.target_threshold

    if metric == "accuracy":
        achieved = (run.best_accuracy or 0) >= threshold
    elif metric == "speed":
        achieved = (run.best_accuracy or 0) >= threshold and (run.train_duration_seconds or 999) <= challenge.constraints.get("max_time", 60)
    else:
        achieved = False

    return achieved


def get_today_challenge():
    """获取今日挑战"""
    today = datetime.date.today()
    challenge = DailyChallenge.query.filter_by(date=today).first()
    if not challenge:
        challenge = generate_daily_challenge()
    return challenge
