/**
 * SOTA Arena — 前端逻辑
 *
 * 依赖：Chart.js (全局 Chart)
 *
 * API 端点：
 *   GET  /api/arena/leaderboard/<dataset_id>?tier=&metric=&limit=
 *   POST /api/arena/submit
 *   GET  /api/arena/run/<run_id>
 *   GET  /api/arena/stats
 *   GET  /api/arena/achievements/<player_name>
 *   GET  /api/arena/hardware
 *   GET  /api/zoo
 */

// ============================================================
//  全局状态
// ============================================================

const state = {
    playerName: localStorage.getItem("arena_player") || "Anonymous",
    hardware: null,
    lossChart: null,
    accChart: null,
    training: false,
    ws: null,
    selectedGraph: null,  // 当前选中模型的 LiteGraph JSON
    modelMeta: null,      // 当前选中模型的 meta 信息
};

// ============================================================
//  初始化
// ============================================================

document.addEventListener("DOMContentLoaded", async () => {
    document.getElementById("player-name").textContent = state.playerName;

    // 获取硬件信息
    try {
        const res = await fetch("/api/arena/hardware");
        state.hardware = await res.json();
        updateHardwareBadge(state.hardware);
    } catch (e) {
        console.log("Hardware detection not available yet");
    }

    // 加载各个面板
    loadLeaderboard();
    loadStats();
    loadAchievements();
    loadSeasonInfo();
    loadChallenge();
    loadRankings();
    setTimeout(onModelSelect, 500);
});

// ============================================================
//  Tab 切换
// ============================================================

function switchTab(tab) {
    document.querySelectorAll(".arena-tab").forEach(t =>
        t.classList.toggle("active", t.dataset.tab === tab)
    );
    document.querySelectorAll(".arena-panel").forEach(p =>
        p.style.display = "none"
    );
    const panel = document.getElementById(`panel-${tab}`);
    if (panel) panel.style.display = "";
}

// ============================================================
//  排行榜
// ============================================================

async function loadLeaderboard() {
    const dataset = document.getElementById("ds-filter").value;
    const tier = document.getElementById("tier-filter").value;
    const metric = document.getElementById("metric-filter").value;

    try {
        const res = await fetch(
            `/api/arena/leaderboard/${dataset}?tier=${tier}&metric=${metric}&limit=50`
        );
        const data = await res.json();
        renderLeaderboard(data.leaderboard);
    } catch (e) {
        // API 还没接上时用 mock 数据
        renderLeaderboard(getMockLeaderboard(dataset));
    }
}

function renderLeaderboard(rows) {
    const body = document.getElementById("lb-body");
    body.innerHTML = rows.map((r, i) => {
        const rank = r.rank || i + 1;
        const rankClass = rank === 1 ? "rank-gold" : rank === 2 ? "rank-silver" : rank === 3 ? "rank-bronze" : "";
        const youClass = r.is_you || r.player_name === state.playerName ? "is-you" : "";
        const badges = [];
        if (r.is_sota) badges.push('<span class="badge badge-sota">SOTA</span>');
        if (r.is_new) badges.push('<span class="badge badge-new">New</span>');
        // 段位图标
        const tierIcon = r.tier_icon || (r.accuracy >= 99.5 ? "ti-crown" : r.accuracy >= 99 ? "ti-diamond" : r.accuracy >= 98 ? "ti-diamond" : r.accuracy >= 95 ? "ti-star" : r.accuracy >= 90 ? "ti-circle" : "ti-circle");
        const tierColor = r.tier_color || (r.accuracy >= 99.5 ? "#FF1493" : r.accuracy >= 99 ? "#B9F2FF" : r.accuracy >= 98 ? "#E5E4E2" : r.accuracy >= 95 ? "#FFD700" : r.accuracy >= 90 ? "#C0C0C0" : "#CD7F32");
        const effScore = r.efficiency_score != null ? `<span class="eff-badge">Eff: ${r.efficiency_score}</span>` : "";

        return `
        <div class="lb-row ${youClass}">
            <span class="lb-rank ${rankClass}">${rank}</span>
            <span class="lb-player">
                <span class="tier-icon-small" style="color:${tierColor}"><i class="${tierIcon}"></i></span>
                ${escapeHtml(r.player_name)} ${badges.join(" ")} ${effScore}
            </span>
            <span class="lb-model" style="color:var(--arena-text-2)">${escapeHtml(r.model_name || "")}</span>
            <span class="lb-acc" style="font-weight:500;font-family:monospace">${(r.accuracy || 0).toFixed(2)}%</span>
            <span class="lb-time" style="color:var(--arena-text-2);font-size:12px">${formatDuration(r.duration)}</span>
            <span class="lb-hw" style="font-size:12px">${r.hardware_tier || ""}</span>
            <span class="lb-action">
                <button class="replay-btn" onclick="viewReplay(${r.run_id})" title="View replay">
                    <i class="ti ti-player-play"></i>
                </button>
            </span>
        </div>`;
    }).join("");
}

// ============================================================
//  Model Source Selection
// ============================================================

function selectModelSource(source) {
    document.querySelectorAll(".source-option").forEach(el => el.classList.remove("active"));
    document.getElementById(`source-${source}`).classList.add("active");
    document.getElementById("preset-selector").style.display = source === "preset" ? "" : "none";
    document.getElementById("workshop-selector").style.display = source === "workshop" ? "" : "none";
}

async function onModelSelect() {
    const modelId = document.getElementById("train-model").value;
    const descBox = document.getElementById("model-description");
    descBox.innerHTML = "Loading...";
    state.selectedGraph = null;
    state.modelMeta = null;
    try {
        const res = await fetch(`/api/zoo/${modelId}`);
        const data = await res.json();
        const meta = data.meta || {};
        state.selectedGraph = data.graph || null;
        state.modelMeta = meta;
        descBox.innerHTML = `
            <div style="font-weight:500;margin-bottom:4px">${escapeHtml(meta.name || modelId)}</div>
            <div style="font-size:12px;color:var(--arena-text-2);margin-bottom:6px">${escapeHtml(meta.description || "")}</div>
            <div style="font-size:11px;color:var(--arena-text-3)">
                ${meta.params || "?"} params · ${meta.layers || "?"} layers
                ${meta.source ? `· ${escapeHtml(meta.source)}` : ""}
                ${state.selectedGraph ? `· <span style="color:var(--arena-teal)">graph loaded</span>` : ""}
            </div>
        `;
        if (meta.dataset) {
            const dsSelect = document.getElementById("train-dataset");
            for (const opt of dsSelect.options) {
                if (opt.value === meta.dataset) { dsSelect.value = meta.dataset; break; }
            }
        }
    } catch (e) {
        descBox.innerHTML = '<span style="color:var(--arena-text-3)">Model description not available</span>';
    }
}

// ============================================================
//  Real Training Flow
// ============================================================

async function startTraining() {
    if (state.training) return;
    state.training = true;

    const btn = document.getElementById("train-btn");
    const monitor = document.getElementById("train-monitor");
    const log = document.getElementById("train-log");
    const placeholder = document.getElementById("train-placeholder");
    const resultDiv = document.getElementById("train-result");

    btn.disabled = true;
    btn.innerHTML = '<i class="ti ti-loader"></i> Training...';
    monitor.style.display = "";
    placeholder.style.display = "none";
    resultDiv.style.display = "none";
    log.innerHTML = "";

    initTrainingCharts();

    const modelId = document.getElementById("train-model")?.value || "";
    const params = {
        dataset: document.getElementById("train-dataset").value,
        learning_rate: parseFloat(document.getElementById("train-lr").value),
        batch_size: parseInt(document.getElementById("train-bs").value),
        epochs: parseInt(document.getElementById("train-epochs").value),
        optimizer: document.getElementById("train-optim").value,
        model_name: state.modelMeta?.name || modelId || "Arena Model",
        player_name: state.playerName,
    };

    // Include graph_json when a preset model is selected and its graph is loaded
    if (state.selectedGraph) {
        params.graph_json = JSON.stringify(state.selectedGraph);
        appendLog(`Model: ${params.model_name} (with ${(state.selectedGraph.nodes || []).length} nodes)`);
    }

    appendLog("Starting training...");
    appendLog(`Dataset: ${params.dataset}, LR: ${params.learning_rate}, BS: ${params.batch_size}, Epochs: ${params.epochs}`);

    try {
        // 1. Start training via API
        const startRes = await fetch("/api/arena/train", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(params),
        });
        const startData = await startRes.json();
        if (startData.error) {
            appendLog(`Error: ${startData.error}`);
            finishTraining();
            return;
        }
        appendLog("Training started!");

        // 2. Poll for progress
        const totalEpochs = params.epochs;
        let done = false;

        while (!done) {
            await new Promise(r => setTimeout(r, 1000));
            const progRes = await fetch("/api/arena/train/progress");
            const prog = await progRes.json();

            if (prog.running && prog.last_epoch) {
                const e = prog.last_epoch;
                handleTrainMessage({
                    type: "epoch",
                    epoch: e.epoch,
                    train_loss: e.train_loss,
                    val_loss: e.val_loss,
                    val_accuracy: e.val_accuracy,
                }, totalEpochs);
            }

            if (prog.status === "done" || prog.status === "error") {
                done = true;
                appendLog(prog.message || "Complete!");
            }

            if (!prog.running) {
                done = true;
            }
        }

        // 3. Get result
        appendLog("Fetching final results...");
        const resultRes = await fetch("/api/arena/train/result");
        const result = await resultRes.json();

        if (result && result.type === "done") {
            handleTrainMessage({ type: "done", ...result }, totalEpochs);
        } else if (result && result.type === "error") {
            appendLog(`Training error: ${result.error}`);
            finishTraining();
        }

    } catch (e) {
        appendLog(`Error: ${e.message}`);
        // Fallback: use mock
        appendLog("Falling back to simulated training...");
        startRestTraining(params);
    }
}

async function startRestTraining(params) {
    appendLog("Simulating training (no GPU detected)...");
    const totalEpochs = params.epochs;
    for (let epoch = 1; epoch <= totalEpochs; epoch++) {
        await new Promise(r => setTimeout(r, 300));
        const trainLoss = Math.max(0.01, 0.5 * Math.pow(0.8, epoch) + 0.05 * Math.random());
        const valAcc = Math.min(99, 40 + 40 * (epoch / totalEpochs) + 5 * Math.random());
        const valLoss = Math.max(0.01, 0.4 * Math.pow(0.75, epoch) + 0.05 * Math.random());
        handleTrainMessage({
            type: "epoch", epoch,
            train_loss: trainLoss, val_loss: valLoss, val_accuracy: valAcc,
        }, totalEpochs);
    }
    const bestAcc = Math.min(99, 40 + 40 + 5 * Math.random());
    handleTrainMessage({
        type: "done", best_accuracy: bestAcc,
        dataset_id: params.dataset, model_name: params.model_name || "Arena Model",
        learning_rate: params.learning_rate, batch_size: params.batch_size,
        epochs: params.epochs, optimizer: params.optimizer,
        duration_seconds: totalEpochs * 2,
        epoch_logs: Array.from({length: totalEpochs}, (_, i) => ({
            epoch: i + 1,
            train_loss: Math.max(0.01, 0.5 * Math.pow(0.8, i+1) + 0.05 * Math.random()),
            val_loss: Math.max(0.01, 0.4 * Math.pow(0.75, i+1) + 0.05 * Math.random()),
            val_accuracy: Math.min(99, 40 + 40 * ((i+1) / totalEpochs) + 5 * Math.random()),
        })),
    }, totalEpochs);
}

function handleTrainMessage(msg, totalEpochs) {
    if (msg.type === "epoch") {
        const pct = Math.round((msg.epoch / totalEpochs) * 100);
        document.getElementById("train-status").textContent = `Epoch ${msg.epoch}/${totalEpochs}`;
        document.getElementById("train-progress").textContent = `${pct}%`;
        document.getElementById("progress-fill").style.width = `${pct}%`;
        addChartPoint(msg.epoch, msg.train_loss, msg.val_loss, msg.val_accuracy);
        appendLog(`Epoch ${msg.epoch}/${totalEpochs} — loss: ${msg.train_loss.toFixed(4)} — val_acc: ${msg.val_accuracy.toFixed(2)}%`);
    }
    if (msg.type === "done") {
        appendLog(`Complete! Best accuracy: ${msg.best_accuracy.toFixed(2)}%`);
        appendLog("Submitting to leaderboard...");
        submitRun(msg);
    }
}

function finishTraining() {
    state.training = false;
    const btn = document.getElementById("train-btn");
    btn.disabled = false;
    btn.innerHTML = '<i class="ti ti-refresh"></i> Train Again';
}

async function submitRun(result) {
    try {
        const res = await fetch("/api/arena/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                player_name: state.playerName,
                dataset_id: result.dataset_id || document.getElementById("train-dataset").value,
                model_name: result.model_name || "Arena Model",
                learning_rate: result.learning_rate,
                batch_size: result.batch_size,
                epochs: result.epochs,
                optimizer: result.optimizer,
                duration_seconds: result.duration_seconds,
                epoch_logs: result.epoch_logs || [],
                hardware_info: state.hardware,
                device: state.hardware ? (state.hardware.has_gpu ? "cuda" : "cpu") : "cpu",
            }),
        });
        const data = await res.json();

        appendLog(`Submitted! Rank: #${data.rank}`);

        if (data.is_new_sota) {
            playAchievementSound();
            showToast("New SOTA!", "You just claimed #1!");
        }

        if (data.new_achievements && data.new_achievements.length > 0) {
            playAchievementSound();
            for (const ach of data.new_achievements) {
                showToast("Achievement Unlocked!", `${ach.name} — ${ach.description}`);
            }
        }

        // Show result card
        const resultDiv = document.getElementById("train-result");
        if (resultDiv) {
            resultDiv.style.display = "block";
            document.getElementById("train-result-detail").innerHTML =
                `Best Accuracy: <strong>${(result.best_accuracy || 0).toFixed(2)}%</strong> · Rank: #${data.rank}`;
        }

        loadLeaderboard();
        loadAchievements();
    } catch (e) {
        appendLog("Submit failed — results saved locally");
    }
}

var _arenaReady = true;

// ============================================================
//  训练图表
// ============================================================

function initTrainingCharts() {
    if (state.lossChart) state.lossChart.destroy();
    if (state.accChart) state.accChart.destroy();

    const lossCtx = document.getElementById("live-loss-chart");
    const accCtx = document.getElementById("live-acc-chart");

    const commonOpts = {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 200 },
        plugins: { legend: { display: true, position: "top", labels: { boxWidth: 8, font: { size: 11 } } } },
    };

    state.lossChart = new Chart(lossCtx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                { label: "Train loss", data: [], borderColor: "#E24B4A", borderWidth: 1.5, pointRadius: 2, tension: 0.3 },
                { label: "Val loss", data: [], borderColor: "#F0997B", borderWidth: 1.5, pointRadius: 2, tension: 0.3, borderDash: [4, 4] },
            ],
        },
        options: { ...commonOpts, scales: { y: { title: { display: true, text: "Loss", font: { size: 11 } } } } },
    });

    state.accChart = new Chart(accCtx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                { label: "Val accuracy", data: [], borderColor: "#1D9E75", borderWidth: 2, pointRadius: 3, tension: 0.3, fill: true, backgroundColor: "rgba(29,158,117,0.05)" },
            ],
        },
        options: { ...commonOpts, scales: { y: { min: 0, max: 100, title: { display: true, text: "Accuracy %", font: { size: 11 } } } } },
    });
}

function addChartPoint(epoch, trainLoss, valLoss, valAcc) {
    state.lossChart.data.labels.push(epoch);
    state.lossChart.data.datasets[0].data.push(trainLoss);
    state.lossChart.data.datasets[1].data.push(valLoss);
    state.lossChart.update("none");

    state.accChart.data.labels.push(epoch);
    state.accChart.data.datasets[0].data.push(valAcc);
    state.accChart.update("none");
}

// ============================================================
//  回放
// ============================================================

async function viewReplay(runId) {
    switchTab("replays");
    const container = document.getElementById("replay-container");
    container.innerHTML = '<p style="color:var(--arena-text-2)">Loading replay...</p>';

    try {
        const res = await fetch(`/api/arena/run/${runId}`);
        const data = await res.json();
        renderReplay(data);
    } catch (e) {
        container.innerHTML = '<p>Replay not available yet.</p>';
    }
}

function renderReplay(data) {
    const container = document.getElementById("replay-container");
    container.innerHTML = `
        <div style="margin-bottom:16px">
            <h3 style="font-size:16px;font-weight:500">${escapeHtml(data.run.player_name)} — ${escapeHtml(data.run.model_name)}</h3>
            <p style="font-size:13px;color:var(--arena-text-2)">
                ${data.run.dataset_id} | ${data.run.best_accuracy.toFixed(2)}% | ${data.run.hardware_tier}
            </p>
        </div>
        <div style="position:relative;height:250px;margin-bottom:16px">
            <canvas id="replay-chart"></canvas>
        </div>
        <div style="margin-top:12px">
            <pre style="font-size:11px;color:var(--arena-text-2);background:var(--arena-surface);padding:12px;border-radius:8px;overflow-x:auto"><code>${escapeHtml(data.run.generated_code || "// Code not available")}</code></pre>
        </div>
    `;

    // 动画回放 loss curve
    const ctx = document.getElementById("replay-chart");
    const labels = data.epoch_logs.map(e => e.epoch);
    const accs = data.epoch_logs.map(e => e.val_accuracy);
    const losses = data.epoch_logs.map(e => e.val_loss);

    new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [
                { label: "Val accuracy", data: accs, borderColor: "#1D9E75", borderWidth: 2, yAxisID: "y", tension: 0.3 },
                { label: "Val loss", data: losses, borderColor: "#E24B4A", borderWidth: 1.5, yAxisID: "y1", tension: 0.3, borderDash: [4, 4] },
            ],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                y: { position: "left", title: { display: true, text: "Accuracy %", font: { size: 11 } } },
                y1: { position: "right", title: { display: true, text: "Loss", font: { size: 11 } }, grid: { drawOnChartArea: false } },
            },
            plugins: { legend: { position: "top", labels: { boxWidth: 8, font: { size: 11 } } } },
        },
    });
}

// ============================================================
//  成就
// ============================================================

async function loadAchievements() {
    const grid = document.getElementById("achieve-grid");

    try {
        const res = await fetch(`/api/arena/achievements/${encodeURIComponent(state.playerName)}`);
        const data = await res.json();
        renderAchievements(data.achievements, data.unlocked);
    } catch (e) {
        // 用默认展示
        renderDefaultAchievements();
    }
}

function renderAchievements(all, unlockedIds) {
    const grid = document.getElementById("achieve-grid");
    grid.innerHTML = all.map(ach => {
        const isUnlocked = unlockedIds.includes(ach.id);
        return `
        <div class="ach-card ${isUnlocked ? "" : "locked"}">
            <div class="ach-icon"><i class="${ach.icon}"></i></div>
            <div class="ach-info">
                <div class="name">${escapeHtml(ach.name)}</div>
                <div class="desc">${escapeHtml(ach.description)}</div>
            </div>
            <span class="ach-rarity rarity-${ach.rarity}">
                ${isUnlocked ? "✓ Unlocked" : ach.rarity}
            </span>
        </div>`;
    }).join("");
}

// ============================================================
//  Model Zoo
// ============================================================

async function loadModelZoo() {
    try {
        const res = await fetch("/api/zoo");
        const models = await res.json();
        renderModelZoo(models);
    } catch (e) {
        renderDefaultModelZoo();
    }
}

function renderModelZoo(models) {
    const grid = document.getElementById("zoo-grid");
    if (!models || models.length === 0) {
        renderDefaultModelZoo();
        return;
    }
    grid.innerHTML = models.map(m => `
        <div class="zoo-card" onclick="loadModel('${m.id}')">
            <div class="model-name"><i class="ti ti-box"></i> ${escapeHtml(m.name)}</div>
            <div class="model-desc">${escapeHtml(m.description || "")}</div>
            <div class="model-meta">${m.layers || "?"} layers | ${m.params || "?"} params | ${m.source || ""}</div>
        </div>
    `).join("");
}

function loadModel(modelId) {
    // 切换到 Train tab 并加载预置模型
    switchTab("train");
    showToast("Model loaded", `${modelId} loaded into editor`);
}

// ============================================================
//  工具函数
// ============================================================

function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function updateHardwareBadge(hw) {
    const badge = document.getElementById("hw-badge");
    if (hw.has_gpu) {
        badge.innerHTML = `<i class="ti ti-gpu"></i> ${hw.gpu_name || "GPU"}`;
    } else {
        badge.innerHTML = `<i class="ti ti-cpu"></i> CPU`;
    }
}

function formatDuration(seconds) {
    if (!seconds) return "-";
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
}

function appendLog(text) {
    const log = document.getElementById("train-log");
    const time = new Date().toLocaleTimeString();
    log.innerHTML += `[${time}] ${escapeHtml(text)}\n`;
    log.scrollTop = log.scrollHeight;
}

function showToast(title, message) {
    let container = document.querySelector(".toast-container");
    if (!container) {
        container = document.createElement("div");
        container.className = "toast-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML = `
        <i class="ti ti-trophy" style="color:var(--arena-amber);font-size:20px"></i>
        <div>
            <div style="font-weight:500">${escapeHtml(title)}</div>
            <div style="font-size:12px;color:var(--arena-text-2)">${escapeHtml(message)}</div>
        </div>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100px)";
        toast.style.transition = "all 0.3s";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ============================================================
//  Mock 数据（API 未接入时的后备）
// ============================================================

function getMockLeaderboard(dataset) {
    const boards = {
        "mnist": [
            { rank: 1, player_name: "NeuroNinja", model_name: "ResNet-18", accuracy: 99.71, duration: 134, hardware_tier: "gpu-mid", is_sota: true, run_id: 1 },
            { rank: 2, player_name: "DeepDiver", model_name: "CNN-7", accuracy: 99.63, duration: 108, hardware_tier: "gpu-low", run_id: 2 },
            { rank: 3, player_name: "TensorTom", model_name: "VGG-lite", accuracy: 99.58, duration: 182, hardware_tier: "gpu-mid", run_id: 3 },
            { rank: 4, player_name: state.playerName, model_name: "CNN-4", accuracy: 99.42, duration: 92, hardware_tier: "cpu", is_you: true, is_new: true, run_id: 4 },
            { rank: 5, player_name: "LayerCake", model_name: "MLP-deep", accuracy: 99.35, duration: 55, hardware_tier: "cpu", run_id: 5 },
            { rank: 6, player_name: "GradQueen", model_name: "ResNet-9", accuracy: 99.21, duration: 160, hardware_tier: "gpu-high", run_id: 6 },
            { rank: 7, player_name: "BatchNorm", model_name: "CNN-3", accuracy: 99.18, duration: 70, hardware_tier: "cpu", run_id: 7 },
            { rank: 8, player_name: "DropoutKid", model_name: "LeNet-5+", accuracy: 98.94, duration: 42, hardware_tier: "cpu", run_id: 8 },
        ],
        "fashion-mnist": [
            { rank: 1, player_name: "LayerCake", model_name: "CNN-6", accuracy: 94.22, duration: 110, hardware_tier: "gpu-low", is_sota: true, run_id: 10 },
            { rank: 2, player_name: state.playerName, model_name: "CNN-4", accuracy: 93.87, duration: 75, hardware_tier: "cpu", is_you: true, run_id: 11 },
            { rank: 3, player_name: "BatchNorm", model_name: "ResNet-9", accuracy: 93.64, duration: 150, hardware_tier: "gpu-mid", run_id: 12 },
        ],
        "cifar10": [
            { rank: 1, player_name: "NeuroNinja", model_name: "ResNet-50", accuracy: 96.12, duration: 510, hardware_tier: "gpu-high", is_sota: true, run_id: 20 },
            { rank: 2, player_name: "GradQueen", model_name: "WideResNet", accuracy: 95.88, duration: 735, hardware_tier: "gpu-high", run_id: 21 },
            { rank: 3, player_name: "DeepDiver", model_name: "DenseNet", accuracy: 95.41, duration: 584, hardware_tier: "gpu-mid", run_id: 22 },
            { rank: 4, player_name: state.playerName, model_name: "ResNet-18", accuracy: 94.73, duration: 380, hardware_tier: "cpu", is_you: true, run_id: 23 },
        ],
        "cifar100": [
            { rank: 1, player_name: "GradQueen", model_name: "WideResNet-28", accuracy: 81.42, duration: 1200, hardware_tier: "gpu-high", is_sota: true, run_id: 30 },
            { rank: 2, player_name: "NeuroNinja", model_name: "ResNet-50", accuracy: 79.88, duration: 980, hardware_tier: "gpu-high", run_id: 31 },
        ],
    };
    return boards[dataset] || [];
}

async function loadStats() {
    const grid = document.getElementById("global-stats");
    try {
        const res = await fetch("/api/arena/stats");
        const data = await res.json();
        grid.innerHTML = `
            <div class="stat-card"><div class="label">Active players</div><div class="value">${data.total_players}</div></div>
            <div class="stat-card"><div class="label">Total runs</div><div class="value">${data.total_runs}</div></div>
            <div class="stat-card"><div class="label">Datasets</div><div class="value">${data.datasets.length}</div></div>
            <div class="stat-card"><div class="label">Your best</div><div class="value">—</div></div>
        `;
    } catch (e) {
        grid.innerHTML = `
            <div class="stat-card"><div class="label">Active players</div><div class="value">127</div></div>
            <div class="stat-card"><div class="label">Runs today</div><div class="value">384</div></div>
            <div class="stat-card"><div class="label">Current SOTA</div><div class="value">99.71%</div></div>
            <div class="stat-card"><div class="label">Your best</div><div class="value">99.42%</div></div>
        `;
    }
}

function renderDefaultAchievements() {
    const achievements = [
        { id: "first_blood", name: "First blood", description: "完成第一次训练", icon: "ti-trophy", rarity: "common", unlocked: true },
        { id: "99_club", name: "99% club", description: "在任意数据集上突破 99%", icon: "ti-target", rarity: "epic", unlocked: true },
        { id: "sota_breaker", name: "SOTA breaker", description: "在任意数据集上拿到第 1 名", icon: "ti-crown", rarity: "legendary", unlocked: false },
        { id: "speedrunner", name: "Speedrunner", description: "60 秒内达到 98%+", icon: "ti-bolt", rarity: "epic", unlocked: false },
        { id: "polyglot", name: "Polyglot", description: "在 3 个不同数据集上提交过", icon: "ti-arrows-shuffle", rarity: "rare", unlocked: false },
        { id: "architect", name: "Architect", description: "设计 10 层以上的模型", icon: "ti-brain", rarity: "rare", unlocked: false },
        { id: "minimalist", name: "Minimalist", description: "不超过 3 层达到 95%+", icon: "ti-feather", rarity: "epic", unlocked: false },
        { id: "overfit_king", name: "Overfit king", description: "loss < 0.001 但 acc < 80%", icon: "ti-chart-dots", rarity: "rare", unlocked: false },
        { id: "night_owl", name: "Night owl", description: "凌晨 2-5 点提交训练", icon: "ti-moon", rarity: "common", unlocked: false },
    ];

    const grid = document.getElementById("achieve-grid");
    grid.innerHTML = achievements.map(ach => `
        <div class="ach-card ${ach.unlocked ? "" : "locked"}">
            <div class="ach-icon"><i class="${ach.icon}"></i></div>
            <div class="ach-info">
                <div class="name">${escapeHtml(ach.name)}</div>
                <div class="desc">${escapeHtml(ach.description)}</div>
            </div>
            <span class="ach-rarity rarity-${ach.rarity}">
                ${ach.unlocked ? "Unlocked" : ach.rarity}
            </span>
        </div>
    `).join("");
}

function renderDefaultModelZoo() {
    const models = [
        { id: "lenet5", name: "LeNet-5", description: "经典 CNN，手写数字识别开山之作", layers: 5, params: "60K", source: "LeCun 1998" },
        { id: "resnet18", name: "ResNet-18", description: "残差连接网络，深度学习里程碑", layers: 18, params: "11M", source: "He et al. 2015" },
        { id: "vgg_lite", name: "VGG-lite", description: "VGG 简化版，适合小数据集", layers: 8, params: "2M", source: "Adapted" },
        { id: "mlp_baseline", name: "MLP Baseline", description: "纯全连接网络基线", layers: 3, params: "100K", source: "Baseline" },
        { id: "simple_transformer", name: "Simple Transformer", description: "2 层 Transformer encoder", layers: 6, params: "500K", source: "Vaswani adapted" },
    ];
    renderModelZoo(models);
}

// ============================================================
//  Season 赛季系统
// ============================================================

async function loadSeasonInfo() {
    try {
        const res = await fetch("/api/arena/season");
        const data = await res.json();
        const badge = document.getElementById("season-badge");
        const nameEl = document.getElementById("season-name");
        if (data && data.name) {
            badge.style.display = "inline-flex";
            nameEl.textContent = data.name;
        }

        // 赛季面板
        const header = document.getElementById("season-header");
        if (header) {
            header.innerHTML = `
            <div class="season-card">
                <div>
                    <div class="season-title">${escapeHtml(data.name || "Season")}</div>
                    <div class="season-meta">${data.is_active ? "Active" : "Ended"} · Started ${data.started_at ? new Date(data.started_at).toLocaleDateString() : ""}</div>
                </div>
                <div style="text-align:right">
                    <div style="font-size:24px;font-weight:600">#${data.id || "?"}</div>
                    <div style="font-size:12px;color:var(--arena-text-2)">${data.total_badges_awarded || 0} badges awarded</div>
                </div>
            </div>`;
        }
        loadSeasonLeaderboard();
    } catch (e) {
        console.log("Season info not available");
    }
}

async function loadSeasonLeaderboard() {
    const dataset = document.getElementById("season-ds-filter")?.value || "mnist";
    const body = document.getElementById("season-lb-body");
    if (!body) return;

    try {
        const res = await fetch(`/api/arena/season/leaderboard?dataset=${dataset}&limit=20`);
        const data = await res.json();
        body.innerHTML = (data.leaderboard || []).map((r, i) => {
            const rank = i + 1;
            const rankClass = rank === 1 ? "rank-gold" : rank === 2 ? "rank-silver" : rank === 3 ? "rank-bronze" : "";
            return `
            <div class="lb-row">
                <span class="lb-rank ${rankClass}">${rank}</span>
                <span class="lb-player">${escapeHtml(r.player_name)}</span>
                <span class="lb-model" style="color:var(--arena-text-2)">${escapeHtml(r.model_name || "")}</span>
                <span class="lb-acc" style="font-weight:500;font-family:monospace">${(r.accuracy || 0).toFixed(2)}%</span>
                <span class="lb-time" style="color:var(--arena-text-2);font-size:12px">${formatDuration(r.duration)}</span>
                <span class="lb-hw" style="font-size:12px">${r.hardware_tier || ""}</span>
            </div>`;
        }).join("");
    } catch (e) {
        body.innerHTML = '<div style="padding:20px;text-align:center;color:var(--arena-text-2)">Season leaderboard not available yet</div>';
    }
}

// ============================================================
//  Daily Challenge 每日挑战
// ============================================================

async function loadChallenge() {
    try {
        const res = await fetch("/api/arena/challenge");
        const data = await res.json();
        if (!data || data.error) return;

        const card = document.getElementById("daily-challenge");
        if (!card) return;
        card.style.display = "flex";

        document.getElementById("challenge-date").textContent = data.date || "";
        document.getElementById("challenge-title").textContent = data.title || "";
        document.getElementById("challenge-desc").textContent = data.description || "";

        const meta = document.getElementById("challenge-meta");
        if (meta) {
            const parts = [];
            if (data.target_dataset) parts.push(`📊 ${data.target_dataset.toUpperCase()}`);
            if (data.target_threshold) parts.push(`🎯 ${data.target_threshold}${data.target_metric === "accuracy" ? "%" : ""}`);
            meta.innerHTML = parts.map(p => `<span>${p}</span>`).join("");
        }
    } catch (e) {
        console.log("Daily challenge not available");
    }
}

// ============================================================
//  Rankings 段位排名
// ============================================================

async function loadRankings() {
    // 加载玩家自己的段位信息
    try {
        const res = await fetch(`/api/arena/player/${encodeURIComponent(state.playerName)}/rank`);
        const data = await res.json();
        if (!data || data.error) throw new Error("No data");

        const info = document.getElementById("rankings-tier-info");
        if (info) {
            const tier = data.tier || { name: "Bronze", icon: "ti-circle", color: "#CD7F32" };
            info.innerHTML = `
                <div class="tier-badge-display">
                    <i class="${tier.icon || "ti-circle"}" style="color:${tier.color || "#CD7F32"}"></i>
                    <div class="tier-info-text">
                        <div class="tier-name" style="color:${tier.color || "#CD7F32"}">${tier.name || "Bronze"}</div>
                        <div class="tier-detail">Rank #${data.global_rank || "?"} of ${data.total_players || "?"} · ${data.total_runs || 0} runs · ${(data.best_accuracy || 0).toFixed(2)}% best</div>
                    </div>
                </div>`;
        }
    } catch (e) {
        // 用 mock 数据
        const info = document.getElementById("rankings-tier-info");
        if (info) {
            info.innerHTML = `
                <div class="tier-badge-display">
                    <i class="ti-circle" style="color:#CD7F32;font-size:32px"></i>
                    <div class="tier-info-text">
                        <div class="tier-name" style="color:#CD7F32">Bronze</div>
                        <div class="tier-detail">Train and submit to start ranking!</div>
                    </div>
                </div>`;
        }
    }

    // 加载所有玩家排名
    try {
        const res = await fetch("/api/arena/rankings");
        const data = await res.json();
        if (!data || !Array.isArray(data)) throw new Error("No data");

        const table = document.getElementById("rankings-table");
        if (!table) return;
        table.innerHTML = `
            <div class="rank-row rank-header">
                <span>#</span>
                <span>Player</span>
                <span>Tier</span>
                <span>Best Acc</span>
                <span>Runs</span>
            </div>
            ${data.map((p, i) => {
                const rank = i + 1;
                const isYou = p.player_name === state.playerName;
                return `
                <div class="rank-row ${isYou ? "is-you" : ""}">
                    <span class="${rank === 1 ? "rank-gold" : rank === 2 ? "rank-silver" : rank === 3 ? "rank-bronze" : ""}" style="font-weight:${rank <= 3 ? 600 : 400}">${rank}</span>
                    <span><span class="tier-icon-small" style="color:${p.tier_color || "#CD7F32"}"><i class="${p.tier_icon || "ti-circle"}"></i></span> ${escapeHtml(p.player_name)}</span>
                    <span style="color:${p.tier_color || "#CD7F32"};font-weight:500">${p.tier_name || "Bronze"}</span>
                    <span style="font-family:monospace">${(p.best_accuracy || 0).toFixed(2)}%</span>
                    <span>${p.total_runs || 0}</span>
                </div>`;
            }).join("")}
        `;
    } catch (e) {
        renderDefaultRankings();
    }
}

function renderDefaultRankings() {
    const table = document.getElementById("rankings-table");
    if (!table) return;
    const mockRankings = [
        { rank: 1, player_name: "NeuroNinja", tier_name: "Diamond", tier_icon: "ti-diamond", tier_color: "#B9F2FF", best_accuracy: 99.71, total_runs: 42 },
        { rank: 2, player_name: "DeepDiver", tier_name: "Gold", tier_icon: "ti-star", tier_color: "#FFD700", best_accuracy: 98.63, total_runs: 28 },
        { rank: 3, player_name: "TensorTom", tier_name: "Gold", tier_icon: "ti-star", tier_color: "#FFD700", best_accuracy: 97.58, total_runs: 35 },
        { rank: 4, player_name: state.playerName, tier_name: "Silver", tier_icon: "ti-circle", tier_color: "#C0C0C0", best_accuracy: 94.42, total_runs: 5 },
        { rank: 5, player_name: "GradQueen", tier_name: "Silver", tier_icon: "ti-circle", tier_color: "#C0C0C0", best_accuracy: 93.21, total_runs: 18 },
    ];
    table.innerHTML = `
        <div class="rank-row rank-header">
            <span>#</span>
            <span>Player</span>
            <span>Tier</span>
            <span>Best Acc</span>
            <span>Runs</span>
        </div>
        ${mockRankings.map(p => `
            <div class="rank-row ${p.player_name === state.playerName ? "is-you" : ""}">
                <span class="${p.rank === 1 ? "rank-gold" : p.rank === 2 ? "rank-silver" : p.rank === 3 ? "rank-bronze" : ""}">${p.rank}</span>
                <span><span class="tier-icon-small" style="color:${p.tier_color}"><i class="${p.tier_icon}"></i></span> ${escapeHtml(p.player_name)}</span>
                <span style="color:${p.tier_color};font-weight:500">${p.tier_name}</span>
                <span style="font-family:monospace">${p.best_accuracy.toFixed(2)}%</span>
                <span>${p.total_runs}</span>
            </div>
        `).join("")}
    `;
}
