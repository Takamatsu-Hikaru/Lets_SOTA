"""
成就系统
每次训练结束后检查是否解锁新成就
"""

from .models import db, Achievement, PlayerAchievement, TrainingRun, Player
from typing import List, Dict


# ============================================================
#  成就定义（首次启动时写入数据库）
# ============================================================

ACHIEVEMENTS = [
    # --- 里程碑 ---
    {
        "id": "first_blood",
        "name": "First blood",
        "description": "完成第一次训练",
        "icon": "ti-trophy",
        "category": "milestone",
        "rarity": "common",
    },
    {
        "id": "10_runs",
        "name": "Warm up",
        "description": "完成 10 次训练",
        "icon": "ti-flame",
        "category": "milestone",
        "rarity": "common",
    },
    {
        "id": "50_runs",
        "name": "Grinder",
        "description": "完成 50 次训练",
        "icon": "ti-repeat",
        "category": "milestone",
        "rarity": "rare",
    },
    {
        "id": "100_runs",
        "name": "No life",
        "description": "完成 100 次训练",
        "icon": "ti-24-hours",
        "category": "milestone",
        "rarity": "epic",
    },

    # --- 精度 ---
    {
        "id": "90_club",
        "name": "90% club",
        "description": "在任意数据集上突破 90% accuracy",
        "icon": "ti-target",
        "category": "accuracy",
        "rarity": "common",
    },
    {
        "id": "95_club",
        "name": "95% club",
        "description": "在任意数据集上突破 95% accuracy",
        "icon": "ti-target",
        "category": "accuracy",
        "rarity": "rare",
    },
    {
        "id": "99_club",
        "name": "99% club",
        "description": "在任意数据集上突破 99% accuracy",
        "icon": "ti-target",
        "category": "accuracy",
        "rarity": "epic",
    },

    # --- 速度 ---
    {
        "id": "speedrunner",
        "name": "Speedrunner",
        "description": "在 60 秒内达到 98%+ accuracy",
        "icon": "ti-cpu",
        "category": "speed",
        "rarity": "epic",
    },
    {
        "id": "one_epoch_wonder",
        "name": "One epoch wonder",
        "description": "只用 1 个 epoch 达到 90%+ accuracy",
        "icon": "ti-bolt",
        "category": "speed",
        "rarity": "rare",
    },

    # --- 多样性 ---
    {
        "id": "polyglot",
        "name": "Polyglot",
        "description": "在 3 个不同数据集上提交过",
        "icon": "ti-arrows-shuffle",
        "category": "diversity",
        "rarity": "rare",
    },
    {
        "id": "all_datasets",
        "name": "Completionist",
        "description": "在所有可用数据集上都提交过",
        "icon": "ti-circle-check",
        "category": "diversity",
        "rarity": "epic",
    },

    # --- 竞争 ---
    {
        "id": "sota_breaker",
        "name": "SOTA breaker",
        "description": "在任意数据集上拿到第 1 名",
        "icon": "ti-crown",
        "category": "competition",
        "rarity": "legendary",
    },
    {
        "id": "top3",
        "name": "Podium finish",
        "description": "在任意数据集上进入前 3",
        "icon": "ti-medal",
        "category": "competition",
        "rarity": "rare",
    },
    {
        "id": "dethrone",
        "name": "Dethroned",
        "description": "打破别人保持的 SOTA 记录",
        "icon": "ti-sword",
        "category": "competition",
        "rarity": "legendary",
    },

    # --- 架构 ---
    {
        "id": "architect",
        "name": "Architect",
        "description": "设计一个 10 层以上的模型",
        "icon": "ti-brain",
        "category": "mastery",
        "rarity": "rare",
    },
    {
        "id": "minimalist",
        "name": "Minimalist",
        "description": "用不超过 3 层达到 95%+ accuracy",
        "icon": "ti-feather",
        "category": "mastery",
        "rarity": "epic",
    },
    {
        "id": "transformer_user",
        "name": "Attention is all you need",
        "description": "使用 Transformer 组件完成一次训练",
        "icon": "ti-eye",
        "category": "mastery",
        "rarity": "rare",
    },

    # --- 隐藏 ---
    {
        "id": "overfit_king",
        "name": "Overfit king",
        "description": "训练 loss 降到 0.001 以下但测试 accuracy 不到 80%",
        "icon": "ti-chart-dots",
        "category": "hidden",
        "rarity": "rare",
    },
    {
        "id": "night_owl",
        "name": "Night owl",
        "description": "在凌晨 2-5 点提交训练",
        "icon": "ti-moon",
        "category": "hidden",
        "rarity": "common",
    },
]


def seed_achievements():
    """初始化成就表"""
    for ach_data in ACHIEVEMENTS:
        if not Achievement.query.get(ach_data["id"]):
            db.session.add(Achievement(**ach_data))
    db.session.commit()


def check_achievements(player: Player, run: TrainingRun) -> List[Dict]:
    """
    检查并解锁成就
    返回新解锁的成就列表
    """
    unlocked = []
    already = {
        pa.achievement_id
        for pa in PlayerAchievement.query.filter_by(player_id=player.id).all()
    }

    def unlock(achievement_id: str):
        if achievement_id not in already:
            pa = PlayerAchievement(
                player_id=player.id,
                achievement_id=achievement_id,
                unlocked_by_run_id=run.id,
            )
            db.session.add(pa)
            ach = Achievement.query.get(achievement_id)
            if ach:
                unlocked.append({
                    "id": ach.id,
                    "name": ach.name,
                    "description": ach.description,
                    "icon": ach.icon,
                    "rarity": ach.rarity,
                })

    # --- 里程碑 ---
    if player.total_runs >= 1:
        unlock("first_blood")
    if player.total_runs >= 10:
        unlock("10_runs")
    if player.total_runs >= 50:
        unlock("50_runs")
    if player.total_runs >= 100:
        unlock("100_runs")

    # --- 精度 ---
    acc = run.best_accuracy or 0
    if acc >= 90:
        unlock("90_club")
    if acc >= 95:
        unlock("95_club")
    if acc >= 99:
        unlock("99_club")

    # --- 速度 ---
    duration = run.train_duration_seconds or 9999
    if acc >= 98 and duration <= 60:
        unlock("speedrunner")
    if run.best_epoch == 1 and acc >= 90:
        unlock("one_epoch_wonder")

    # --- 多样性 ---
    distinct_datasets = (
        db.session.query(TrainingRun.dataset_id)
        .filter(TrainingRun.player_id == player.id)
        .distinct()
        .count()
    )
    if distinct_datasets >= 3:
        unlock("polyglot")
    from .models import Dataset as DatasetModel
    total_datasets = DatasetModel.query.count()
    if distinct_datasets >= total_datasets and total_datasets > 0:
        unlock("all_datasets")

    # --- 竞争 ---
    from .leaderboard import _get_rank
    rank = _get_rank(run)
    if rank == 1:
        unlock("sota_breaker")
    if rank <= 3:
        unlock("top3")

    # --- 隐藏：overfit ---
    if run.final_loss and run.final_loss < 0.001 and acc < 80:
        unlock("overfit_king")

    # --- 隐藏：night owl ---
    if run.finished_at:
        hour = run.finished_at.hour
        if 2 <= hour < 5:
            unlock("night_owl")

    db.session.commit()
    return unlocked
