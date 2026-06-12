"""
赛季系统 (Seasons)
每月/每两周一个赛季，冻结排行榜快照，发放赛季徽章
"""

import datetime
from .models import db


class Season(db.Model):
    """赛季定义"""
    __tablename__ = "seasons"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)          # "S1: Genesis", "S2: Evolution"
    slug = db.Column(db.String(16), unique=True, nullable=False)  # "s1", "s2"
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)


class SeasonSnapshot(db.Model):
    """赛季结束时排行榜快照"""
    __tablename__ = "season_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)

    # 快照数据
    rank = db.Column(db.Integer)
    dataset_id = db.Column(db.String(32))
    best_accuracy = db.Column(db.Float)
    total_runs = db.Column(db.Integer)
    hardware_tier = db.Column(db.String(16))

    # 赛季结算称号
    title = db.Column(db.String(64))  # "S1 MNIST Champion"

    season = db.relationship("Season", backref="snapshots")
    player = db.relationship("Player", backref="season_snapshots")


class SeasonBadge(db.Model):
    """赛季徽章"""
    __tablename__ = "season_badges"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=False)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    badge_type = db.Column(db.String(32))  # "champion", "top3", "top10", "participant"
    awarded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


# ============================================================
#  赛季逻辑
# ============================================================

SEASON_DURATION_DAYS = 30  # 一个月一个赛季

# 赛季名称生成
SEASON_NAMES = [
    "Genesis", "Evolution", "Breakout", "Rebalance",
    "Surge", "Precision", "Velocity", "Quantum",
    "Horizon", "Nexus", "Apex", "Zenith",
]


def get_or_create_current_season():
    """获取当前赛季，如果无活跃赛季则创建一个"""
    now = datetime.datetime.utcnow()
    active = Season.query.filter_by(is_active=True).first()
    if active:
        return active

    # 创建新赛季
    count = Season.query.count()
    season_num = count + 1
    name = f"S{season_num}: {SEASON_NAMES[(season_num - 1) % len(SEASON_NAMES)]}"
    slug = f"s{season_num}"

    season = Season(
        name=name,
        slug=slug,
        started_at=now,
        is_active=True,
    )
    db.session.add(season)
    db.session.commit()
    return season


def end_season(season: Season):
    """
    结束某个赛季：
    1. 从 TrainingRun 排行榜取前 10 名（每个数据集）
    2. 创建 SeasonSnapshot
    3. 颁发徽章
    4. 标记赛季结束
    """
    from .models import Player, TrainingRun
    from sqlalchemy import desc

    now = datetime.datetime.utcnow()
    datasets = Dataset.query.all()

    for dataset in datasets:
        top_runs = (
            TrainingRun.query
            .filter(TrainingRun.dataset_id == dataset.id)
            .filter(TrainingRun.best_accuracy.isnot(None))
            .order_by(desc(TrainingRun.best_accuracy))
            .limit(10)
            .all()
        )

        titles = ["Champion", "Runner-up", "3rd Place", "4th", "5th", "6th", "7th", "8th", "9th", "10th"]

        for i, run in enumerate(top_runs):
            snapshot = SeasonSnapshot(
                season_id=season.id,
                player_id=run.player_id,
                rank=i + 1,
                dataset_id=dataset.id,
                best_accuracy=run.best_accuracy,
                total_runs=Player.query.get(run.player_id).total_runs,
                hardware_tier=run.hardware_tier,
                title=f"S{season.id} {dataset.id.title()} {titles[i]}",
            )
            db.session.add(snapshot)

            # 颁发徽章
            badge_type = "champion" if i == 0 else ("top3" if i < 3 else ("top10" if i < 10 else "participant"))
            badge = SeasonBadge(
                player_id=run.player_id,
                season_id=season.id,
                badge_type=badge_type,
            )
            db.session.add(badge)

    season.is_active = False
    season.ended_at = now
    db.session.commit()


def get_player_season_badges(player_id: int):
    """获取玩家的赛季徽章"""
    badges = SeasonBadge.query.filter_by(player_id=player_id).all()
    result = []
    for b in badges:
        season = Season.query.get(b.season_id)
        result.append({
            "season": season.name if season else "Unknown",
            "season_slug": season.slug if season else "",
            "badge_type": b.badge_type,
            "awarded_at": b.awarded_at.isoformat() if b.awarded_at else "",
        })
    return result
