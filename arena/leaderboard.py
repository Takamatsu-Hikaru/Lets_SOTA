"""
排行榜 API — Flask Blueprint
"""

from flask import Blueprint, jsonify, request
from .models import db, TrainingRun, Dataset, Player, EpochLog
from sqlalchemy import desc

leaderboard_bp = Blueprint("leaderboard", __name__, url_prefix="/api/arena")


@leaderboard_bp.route("/leaderboard/<dataset_id>")
def get_leaderboard(dataset_id):
    """
    获取某个数据集的排行榜

    Query params:
    - tier: 硬件分级过滤 (cpu / gpu-low / gpu-mid / gpu-high / all)
    - limit: 返回条数 (默认 50)
    - metric: 排名依据 (accuracy / loss / speed)
    """
    tier = request.args.get("tier", "all")
    limit = min(int(request.args.get("limit", 50)), 200)
    metric = request.args.get("metric", "accuracy")

    query = (
        db.session.query(TrainingRun, Player)
        .join(Player)
        .filter(TrainingRun.dataset_id == dataset_id)
        .filter(TrainingRun.final_accuracy.isnot(None))
    )

    if tier != "all":
        query = query.filter(TrainingRun.hardware_tier == tier)

    # 排序
    if metric == "accuracy":
        query = query.order_by(desc(TrainingRun.best_accuracy))
    elif metric == "loss":
        query = query.order_by(TrainingRun.final_loss)
    elif metric == "speed":
        # 达到 95%+ accuracy 最快
        query = (
            query
            .filter(TrainingRun.best_accuracy >= 95.0)
            .order_by(TrainingRun.train_duration_seconds)
        )

    results = query.limit(limit).all()

    leaderboard = []
    for i, (run, player) in enumerate(results, 1):
        leaderboard.append({
            "rank": i,
            "player_name": player.name,
            "model_name": run.model_name,
            "accuracy": round(run.best_accuracy, 4) if run.best_accuracy else 0,
            "loss": round(run.final_loss, 6) if run.final_loss else None,
            "epochs": run.epochs,
            "duration": run.train_duration_seconds,
            "hardware_tier": run.hardware_tier,
            "device": run.device_used,
            "submitted_at": run.finished_at.isoformat() if run.finished_at else None,
            "run_id": run.id,
            "is_sota": (i == 1),
        })

    # 当前 SOTA
    dataset = Dataset.query.get(dataset_id)
    sota = {
        "accuracy": dataset.current_sota_accuracy if dataset else 0,
        "total_runs": query.count(),
    }

    return jsonify({"leaderboard": leaderboard, "sota": sota, "dataset_id": dataset_id})


@leaderboard_bp.route("/submit", methods=["POST"])
def submit_run():
    """
    提交训练结果

    POST body (JSON):
    {
        "player_name": "NeuroNinja",
        "dataset_id": "mnist",
        "model_name": "My CNN-4",
        "graph_json": "...",
        "generated_code": "...",
        "learning_rate": 0.001,
        "batch_size": 64,
        "epochs": 10,
        "optimizer": "Adam",
        "epoch_logs": [
            {"epoch": 1, "train_loss": 0.5, "val_loss": 0.4, "val_accuracy": 92.1},
            ...
        ],
        "hardware_info": {...}
    }
    """
    data = request.json

    # 获取或创建玩家
    player = Player.query.filter_by(name=data["player_name"]).first()
    if not player:
        player = Player(
            name=data["player_name"],
            hardware_fingerprint=data.get("hardware_info", {}).get("fingerprint", ""),
            hardware_tier=data.get("hardware_info", {}).get("tier", "cpu"),
        )
        db.session.add(player)
        db.session.flush()

    # 创建训练记录
    epoch_logs = data.get("epoch_logs", [])
    best_epoch_data = max(epoch_logs, key=lambda e: e.get("val_accuracy", 0)) if epoch_logs else {}
    final_epoch = epoch_logs[-1] if epoch_logs else {}

    run = TrainingRun(
        player_id=player.id,
        dataset_id=data["dataset_id"],
        model_name=data.get("model_name", "Unnamed"),
        graph_json=data.get("graph_json"),
        generated_code=data.get("generated_code"),
        learning_rate=data.get("learning_rate"),
        batch_size=data.get("batch_size"),
        epochs=data.get("epochs"),
        optimizer=data.get("optimizer"),
        final_accuracy=final_epoch.get("val_accuracy"),
        final_loss=final_epoch.get("val_loss"),
        best_accuracy=best_epoch_data.get("val_accuracy", 0),
        best_epoch=best_epoch_data.get("epoch", 0),
        train_duration_seconds=data.get("duration_seconds", 0),
        hardware_tier=data.get("hardware_info", {}).get("tier", "cpu"),
        device_used=data.get("device", "cpu"),
    )
    db.session.add(run)
    db.session.flush()

    # 写入 epoch 日志
    for log in epoch_logs:
        db.session.add(EpochLog(
            run_id=run.id,
            epoch=log["epoch"],
            train_loss=log.get("train_loss"),
            train_accuracy=log.get("train_accuracy"),
            val_loss=log.get("val_loss"),
            val_accuracy=log.get("val_accuracy"),
        ))

    # 更新 SOTA
    dataset = Dataset.query.get(data["dataset_id"])
    if dataset and run.best_accuracy > dataset.current_sota_accuracy:
        dataset.current_sota_accuracy = run.best_accuracy
        dataset.current_sota_run_id = run.id

    # 更新玩家统计
    player.total_runs += 1
    if run.best_accuracy > player.best_accuracy:
        player.best_accuracy = run.best_accuracy
    player.total_train_seconds += run.train_duration_seconds or 0

    db.session.commit()

    # 触发成就检查
    from .achievements import check_achievements
    new_achievements = check_achievements(player, run)

    return jsonify({
        "run_id": run.id,
        "rank": _get_rank(run),
        "is_new_sota": run.id == dataset.current_sota_run_id if dataset else False,
        "new_achievements": new_achievements,
    })


@leaderboard_bp.route("/run/<int:run_id>")
def get_run_detail(run_id):
    """获取单次训练的完整信息（用于回放）"""
    run = TrainingRun.query.get_or_404(run_id)
    player = Player.query.get(run.player_id)
    epochs = EpochLog.query.filter_by(run_id=run_id).order_by(EpochLog.epoch).all()

    return jsonify({
        "run": {
            "id": run.id,
            "player_name": player.name,
            "model_name": run.model_name,
            "dataset_id": run.dataset_id,
            "graph_json": run.graph_json,
            "generated_code": run.generated_code,
            "best_accuracy": run.best_accuracy,
            "final_loss": run.final_loss,
            "epochs": run.epochs,
            "duration": run.train_duration_seconds,
            "hardware_tier": run.hardware_tier,
        },
        "epoch_logs": [
            {
                "epoch": e.epoch,
                "train_loss": e.train_loss,
                "val_loss": e.val_loss,
                "train_accuracy": e.train_accuracy,
                "val_accuracy": e.val_accuracy,
            }
            for e in epochs
        ],
    })


@leaderboard_bp.route("/stats")
def get_global_stats():
    """全局统计"""
    total_players = Player.query.count()
    total_runs = TrainingRun.query.count()
    datasets = Dataset.query.all()

    return jsonify({
        "total_players": total_players,
        "total_runs": total_runs,
        "datasets": [
            {
                "id": d.id,
                "name": d.name,
                "sota_accuracy": d.current_sota_accuracy,
                "total_runs": TrainingRun.query.filter_by(dataset_id=d.id).count(),
            }
            for d in datasets
        ],
    })


def _get_rank(run):
    """计算某次训练在其数据集中的排名"""
    better_count = (
        TrainingRun.query
        .filter(TrainingRun.dataset_id == run.dataset_id)
        .filter(TrainingRun.best_accuracy > run.best_accuracy)
        .count()
    )
    return better_count + 1


# Model Zoo routes kept in app.py to avoid blueprint routing issues
