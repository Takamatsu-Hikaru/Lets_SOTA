"""
ELO / 段位系统 & 效率分数
"""

import math
from .models import db, Player, TrainingRun


# ============================================================
#  段位系统
# ============================================================

RANK_TIERS = [
    {"id": "bronze", "name": "Bronze", "min_acc": 0, "icon": "ti-circle", "color": "#CD7F32"},
    {"id": "silver", "name": "Silver", "min_acc": 90, "icon": "ti-circle", "color": "#C0C0C0"},
    {"id": "gold", "name": "Gold", "min_acc": 95, "icon": "ti-star", "color": "#FFD700"},
    {"id": "platinum", "name": "Platinum", "min_acc": 98, "icon": "ti-diamond", "color": "#E5E4E2"},
    {"id": "diamond", "name": "Diamond", "min_acc": 99, "icon": "ti-diamond", "color": "#B9F2FF"},
    {"id": "sota_champion", "name": "SOTA Champion", "min_acc": 99.5, "icon": "ti-crown", "color": "#FF1493"},
]


def get_rank_tier(accuracy: float) -> dict:
    """根据 accuracy 返回对应的段位"""
    tier = RANK_TIERS[0]  # default bronze
    for t in reversed(RANK_TIERS):
        if accuracy >= t["min_acc"]:
            tier = t
            break
    return tier


def get_player_rank_info(player: Player) -> dict:
    """获取玩家的段位和排名信息"""
    from sqlalchemy import desc

    tier = get_rank_tier(player.best_accuracy or 0)

    # 全局排名
    global_rank = (
        Player.query
        .filter(Player.best_accuracy > (player.best_accuracy or 0))
        .count() + 1
    )

    total_players = Player.query.count()

    return {
        "player_name": player.name,
        "best_accuracy": player.best_accuracy,
        "tier": tier,
        "global_rank": global_rank,
        "total_players": total_players,
        "total_runs": player.total_runs,
    }


# ============================================================
#  ELO 分数计算
# ============================================================

INITIAL_ELO = 1200


def calculate_elo_change(runner_elo: float, opponent_elo: float, runner_won: bool, K: int = 32) -> int:
    """
    计算 ELO 变化
    runner_won: True 如果 runner 的 accuracy 更高
    K: K-factor (32 标准, 16 稳定)
    """
    expected = 1.0 / (1.0 + 10.0 ** ((opponent_elo - runner_elo) / 400.0))
    actual = 1.0 if runner_won else 0.0
    return round(K * (actual - expected))


def update_player_elo_after_submit(player: Player, run_accuracy: float):
    """
    提交新训练后更新玩家 ELO
    与同数据集的已有提交进行"比较"
    """
    if not hasattr(player, 'elo'):
        player.elo = INITIAL_ELO

    # 找同数据集的其他玩家
    peers = (
        Player.query
        .join(TrainingRun)
        .filter(TrainingRun.dataset_id == run.dataset_id)
        .filter(Player.id != player.id)
        .filter(TrainingRun.best_accuracy.isnot(None))
        .distinct()
        .all()
    )

    total_change = 0
    for peer in peers:
        peer_elo = getattr(peer, 'elo', INITIAL_ELO)
        peer_best = (
            TrainingRun.query
            .filter_by(player_id=peer.id, dataset_id=run.dataset_id)
            .order_by(TrainingRun.best_accuracy.desc())
            .first()
        )
        peer_acc = peer_best.best_accuracy if peer_best else 0
        won = run_accuracy >= peer_acc
        change = calculate_elo_change(player.elo, peer_elo, won)
        total_change += change

    player.elo = max(400, min(3000, player.elo + total_change))
    return player.elo


# ============================================================
#  参数效率分数
# ============================================================

def calculate_efficiency_score(accuracy: float, param_count: int = 100000, train_time_seconds: int = 60) -> float:
    """
    计算模型效率分数
    efficiency = accuracy / log(param_count + 1) / log(train_time + 1)
    鼓励小模型、快速训练
    """
    if accuracy <= 0 or param_count <= 0 or train_time_seconds <= 0:
        return 0.0
    param_factor = math.log(param_count + 1)
    time_factor = math.log(train_time_seconds + 1)
    score = accuracy / param_factor / time_factor
    return round(score * 100, 4)


def format_param_count(count: int) -> str:
    """格式化参数数量显示"""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1_000:
        return f"{count / 1_000:.0f}K"
    return str(count)
