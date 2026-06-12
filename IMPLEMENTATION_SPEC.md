# Let's SOTA!!!!! — 完整施工方案

> 将此文件交给 Claude Code / Codex 等 AI，按步骤执行即可。
> 项目根目录：`C:\Users\user\Desktop\myproject\CortexNodus`

---

## 0. 项目现状

### 架构
```
CortexNodus/
├── app.py              # Flask 主路由
├── arena/              # 竞技系统后端
│   ├── models.py       # SQLAlchemy 数据模型
│   ├── leaderboard.py  # 排行榜 blueprint (/api/arena/*)
│   ├── achievements.py # 20个成就定义
│   ├── season.py       # 赛季系统
│   ├── challenges.py   # 每日挑战
│   ├── ranking.py      # ELO段位系统
│   ├── train.py        # ArenaTrainer 训练桥接
│   ├── datasets.py     # 数据集注册
│   └── replay.py       # 训练回放
├── templates/
│   ├── arena.html      # Let's SOTA!!!!! 主页 (/) 
│   └── workshop.html   # Studio 模型搭建 (/workshop)
├── static/
│   ├── arena.css       # 竞技系统样式
│   ├── arena.js        # 前端逻辑
│   ├── designer.js     # LiteGraph 编辑器逻辑
│   └── style.css       # 原始编辑器样式
├── model_zoo/
│   ├── registry.json   # 5个预置模型索引
│   ├── lenet5/         # graph.json + meta.json
│   ├── mlp_baseline/
│   ├── resnet18/
│   ├── vgg_lite/
│   └── simple_transformer/
└── data/
    └── arena.db        # SQLite
```

### 现有页面路由
- `/` → `templates/arena.html`（Let's SOTA!!!!! 竞技主页）
- `/workshop` → `templates/workshop.html`（Studio 模型搭建）
- `/arena` → redirect to `/`

---

## 1. 配色回滚 → 紫色/黑色/灰色

**目标**：当前是深蓝色，改成最初的紫色(#534AB7) + 深黑(#0e0e12) + 灰色(#1a1a1f/#8d89a3)，SOTA 提示用金色(#f0b839)，每日挑战不用白色。

### 1.1 修改 `static/arena.css` — CSS 变量

替换文件顶部的 `:root` 块为：

```css
:root {
    /* 底色 */
    --arena-bg: #0e0e12;
    --arena-surface: #1a1a1f;
    --arena-surface-2: #24242b;
    --arena-border: rgba(83, 74, 183, 0.18);

    /* 文字 */
    --arena-text: #e2e0ed;
    --arena-text-2: #8d89a3;
    --arena-text-3: #5a5670;

    /* 主色：紫色 */
    --arena-primary: #534AB7;
    --arena-primary-bg: rgba(83, 74, 183, 0.14);
    --arena-primary-hover: #4339a6;
    --arena-secondary: #7b74d4;
    --arena-accent: #8f88e8;

    /* SOTA 金色 */
    --arena-sota-gold: #f0b839;
    --arena-amber: #c8941e;
    --arena-amber-bg: rgba(200, 148, 30, 0.14);

    /* 辅助色 */
    --arena-teal: #0d9488;
    --arena-teal-bg: rgba(13, 148, 136, 0.12);
    --arena-coral: #e0886e;
    --arena-coral-bg: rgba(224, 136, 110, 0.12);
    --arena-red: #e25656;
    --arena-green: #3aaa7e;

    /* 圆角 */
    --arena-radius: 8px;
    --arena-radius-lg: 12px;
}
```

### 1.2 全局替换

在 `static/arena.css` 中做以下全局替换（`replace_all: true`）：

| 搜索 | 替换为 | 影响 |
|------|--------|------|
| `var(--arena-purple)` | `var(--arena-primary)` | 主色引用 |
| `var(--arena-purple-bg)` | `var(--arena-primary-bg)` | 紫色背景 |
| `.badge-sota` 的 color | `var(--arena-sota-gold)` | SOTA 徽章金色 |
| `.badge-new` 的 color | `var(--arena-secondary)` | 新记录徽章 |
| `.rarity-rare` 背景 | `rgba(123, 116, 212, 0.15)` | 稀有成就 |
| `.rarity-epic` 背景 | `rgba(143, 136, 232, 0.15)` | 史诗成就 |
| `.rarity-legendary` 背景 | `var(--arena-amber-bg)` | 传说成就 |

### 1.3 每日挑战卡片

在 `static/arena.css` 中找到 `.challenge-card`，改为：

```css
.challenge-card {
    border: 1px solid rgba(83, 74, 183, 0.25);
    border-radius: var(--arena-radius-lg);
    padding: 16px 20px;
    margin-bottom: 20px;
    background: var(--arena-surface);
    /* 不要 linear-gradient，不要白色 */
    box-shadow: 0 0 20px rgba(83, 74, 183, 0.06);
    display: flex;
    flex-direction: column;
    gap: 8px;
}
```

### 1.4 赛季徽章

找到 `.season-badge`，替换为：
```css
.season-badge {
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    background: var(--arena-primary-bg);
    color: var(--arena-secondary);
    border: 1px solid rgba(83, 74, 183, 0.3);
}
```

### 1.5 训练按钮

```css
.train-btn {
    background: var(--arena-primary);
    /* 其余保持不变 */
}
```

---

## 2. Studio 新手教程系统

### 核心理念

**不是文本弹窗，是画布上的动态阴影拼图。**

用户打开 Tutorial → 画布上有**半透明发光阴影节点**，像拼图空位：从左侧拖出正确节点 → 放到阴影上 → 自动吸附 + TransformUp 金属音效 → 阴影变实心 → 下一个阴影出现。

### 2.1 创建 `static/tutorial.css`

```css
/* 阴影节点样式（通过 JS 动态设置，此处为备用） */
.tutorial-shadow-node {
    border-style: dashed !important;
    border-color: rgba(83, 74, 183, 0.5) !important;
    background: rgba(83, 74, 183, 0.08) !important;
}

/* 文字气泡 */
.tutorial-bubble {
    position: absolute;
    background: rgba(26, 26, 31, 0.95);
    border: 1px solid rgba(83, 74, 183, 0.3);
    border-radius: 8px;
    padding: 8px 12px;
    color: #e2e0ed;
    font-size: 12px;
    max-width: 200px;
    pointer-events: none;
    z-index: 100;
    backdrop-filter: blur(8px);
    animation: bubbleFadeIn 0.3s ease;
}
@keyframes bubbleFadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}

/* 画笔按钮 */
.tutorial-auto-btn {
    position: absolute;
    background: rgba(83, 74, 183, 0.2);
    border: 1px solid var(--arena-primary);
    border-radius: 6px;
    color: var(--arena-secondary);
    font-size: 11px;
    padding: 4px 10px;
    cursor: pointer;
    z-index: 101;
    animation: pulseGlow 2s infinite;
}
@keyframes pulseGlow {
    0%, 100% { box-shadow: 0 0 8px rgba(83, 74, 183, 0.3); }
    50% { box-shadow: 0 0 16px rgba(83, 74, 183, 0.6); }
}

/* 教程入口按钮（workshop header 右侧） */
.tutorial-entry-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    background: var(--arena-primary-bg);
    border: 1px solid var(--arena-primary);
    border-radius: var(--arena-radius);
    color: var(--arena-secondary);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
}
.tutorial-entry-btn:hover {
    background: rgba(83, 74, 183, 0.25);
}
```

### 2.2 创建 `static/tutorial.js` — 核心引擎

以下是完整的 JS 模块结构。将此文件放在 `static/tutorial.js`。

```javascript
/**
 * Studio Tutorial Engine
 * 
 * "动态阴影拼图" — 画布上出现半透明阴影节点，用户放置匹配节点
 * 放置时自动吸附 + 连线 + TransformUp 音效
 * 一组完成后播放成就 chime
 * 30秒无操作 → 弹出 [Auto] 自动补全按钮
 */

// ============================================================
//  音效
// ============================================================

// TransformUp 下载后转 base64 内嵌（先占位）
let _transformUpBuffer = null;
async function loadTransformUpSound() {
    // 下载 Pixabay TransformUp MP3
    // https://pixabay.com/sound-effects/film-special-effects-transformup-78790/
    // 方法1：直接 fetch MP3 → decodeAudioData
    // 方法2：转 base64 字符串内嵌于此（推荐，避免依赖外部链接）
    // 此处先内嵌占位代码，实际集成时替换为真实 base64
    try {
        const ctx = new AudioContext();
        // 如果从文件系统加载: fetch('/static/sounds/transformup.mp3') → arrayBuffer → decodeAudioData
        const resp = await fetch('/static/sounds/transformup.mp3');
        const buf = await resp.arrayBuffer();
        _transformUpBuffer = await ctx.decodeAudioData(buf);
    } catch(e) {
        console.warn('TransformUp sound not loaded', e);
    }
}

function playTransformUp() {
    if (!_transformUpBuffer) return;
    try {
        const ctx = new AudioContext();
        const src = ctx.createBufferSource();
        src.buffer = _transformUpBuffer;
        const gain = ctx.createGain();
        gain.gain.value = 0.3;
        src.connect(gain).connect(ctx.destination);
        src.start(0);
    } catch(e) {}
}

// 成就 chime (Web Audio API 生成)
function playAchievementChime() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        [523.25, 659.25, 783.99].forEach((freq, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(0.15, ctx.currentTime + i * 0.12);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.12 + 0.5);
            osc.connect(gain).connect(ctx.destination);
            osc.start(ctx.currentTime + i * 0.12);
            osc.stop(ctx.currentTime + i * 0.12 + 0.5);
        });
    } catch(e) {}
}


// ============================================================
//  教程数据定义
// ============================================================

const TUTORIAL_MODULES = {
    lenet5: {
        title: 'Build LeNet-5',
        description: 'Classic handwritten digit classifier',
        steps: [
            {
                id: 1,
                expects: { action: 'add_node', type: 'MNIST' },
                pos: [100, 200],
                bubble: 'Start with MNIST dataset.\n28x28 grayscale images, 10 classes.',
                highlightEl: null,  // no DOM element, highlight canvas area
            },
            {
                id: 2,
                expects: { action: 'add_node', type: 'Conv2D' },
                pos: [340, 200],
                bubble: 'Conv2D layer: first convolution.\n6 filters of 5x5 extract basic features.',
                properties: { out_channels: 6, kernel_size: 5 },
                autoWire: { fromStep: 1, fromPort: 0, toPort: 0 },
            },
            {
                id: 3,
                expects: { action: 'add_node', type: 'MaxPool' },
                pos: [580, 200],
                bubble: 'MaxPool 2x2: downsample feature maps.\nHalves spatial dimensions, keeps strongest signals.',
                autoWire: { fromStep: 2, fromPort: 0, toPort: 0 },
            },
            {
                id: 4,
                expects: { action: 'add_node', type: 'Conv2D' },
                pos: [300, 340],
                bubble: 'Second convolution: 16 filters.\nDeeper layer learns more complex patterns.',
                properties: { out_channels: 16, kernel_size: 5 },
                autoWire: { fromStep: 3, fromPort: 0, toPort: 0 },
                hasAuto: true,  // 30s 无操作提示自动补全
            },
            {
                id: 5,
                expects: { action: 'add_node', type: 'MaxPool' },
                pos: [540, 340],
                bubble: 'Second pooling layer.',
                autoWire: { fromStep: 4, fromPort: 0, toPort: 0 },
            },
            {
                id: 6,
                expects: { action: 'add_node', type: 'Flatten' },
                pos: [100, 420],
                bubble: 'Flatten: reshape 2D features into 1D vector.\nConnects convolutions to dense layers.',
                autoWire: { fromStep: 5, fromPort: 0, toPort: 0 },
            },
            {
                id: 7,
                expects: { action: 'add_node', type: 'Dense' },
                pos: [340, 420],
                bubble: 'Dense(120): first fully-connected layer.\nCombines all extracted features.',
                properties: { out_features: 120 },
                autoWire: { fromStep: 6, fromPort: 0, toPort: 0 },
            },
            {
                id: 8,
                expects: { action: 'add_node', type: 'Dense' },
                pos: [580, 420],
                bubble: 'Dense(84): second dense layer.',
                properties: { out_features: 84 },
                autoWire: { fromStep: 7, fromPort: 0, toPort: 0 },
                hasAuto: true,
            },
            {
                id: 9,
                expects: { action: 'add_node', type: 'Dense' },
                pos: [340, 500],
                bubble: 'Dense(10): output layer.\n10 classes = 0-9 digits.',
                properties: { out_features: 10 },
                autoWire: { fromStep: 8, fromPort: 0, toPort: 0 },
            },
            {
                id: 10,
                expects: { action: 'add_node', type: 'Loss' },
                pos: [580, 500],
                bubble: 'Loss node: training target.\nCrossEntropy for classification.',
                properties: { kind: 'CrossEntropy', optimizer: 'Adam' },
                autoWire: { fromStep: 9, fromPort: 0, toPort: 0 },
                isFinal: true,
            },
        ],
    },

    cnn: {
        title: 'Build a CNN',
        description: 'Modern conv net with BatchNorm',
        steps: [
            {
                id: 1,
                expects: { action: 'add_node', type: 'CIFAR-10' },
                pos: [100, 200],
                bubble: 'CIFAR-10: 32x32 color images, 10 classes.\nMore challenging than MNIST.',
            },
            {
                id: 2,
                expects: { action: 'add_node', type: 'Conv2D' },
                pos: [340, 200],
                bubble: 'Conv2D with 32 filters, 3x3 kernel.',
                properties: { out_channels: 32, kernel_size: 3, padding: 1 },
                autoWire: { fromStep: 1, fromPort: 0, toPort: 0 },
            },
            {
                id: 3,
                expects: { action: 'add_node', type: 'BatchNorm2d' },
                pos: [580, 200],
                bubble: 'BatchNorm2d: normalize activations.\nStabilizes training, allows higher learning rates.',
                autoWire: { fromStep: 2, fromPort: 0, toPort: 0 },
            },
            {
                id: 4,
                expects: { action: 'add_node', type: 'ReLU' },
                pos: [580, 280],
                bubble: 'ReLU activation: f(x) = max(0, x).\nIntroduces non-linearity.',
                autoWire: { fromStep: 3, fromPort: 0, toPort: 0 },
            },
            {
                id: 5,
                expects: { action: 'add_node', type: 'MaxPool' },
                pos: [340, 360],
                bubble: 'MaxPool: downsample.\nReduces computation, provides translation invariance.',
                autoWire: { fromStep: 4, fromPort: 0, toPort: 0 },
            },
            {
                id: 6,
                expects: { action: 'add_node', type: 'Flatten' },
                pos: [340, 420],
                bubble: 'Flatten for classifier head.',
                autoWire: { fromStep: 5, fromPort: 0, toPort: 0 },
                hasAuto: true,
            },
            {
                id: 7,
                expects: { action: 'add_node', type: 'Dense' },
                pos: [340, 480],
                bubble: 'Dense output layer.',
                properties: { out_features: 10 },
                autoWire: { fromStep: 6, fromPort: 0, toPort: 0 },
            },
            {
                id: 8,
                expects: { action: 'add_node', type: 'Loss' },
                pos: [340, 540],
                bubble: 'Training goal.',
                properties: { kind: 'CrossEntropy', optimizer: 'Adam' },
                autoWire: { fromStep: 7, fromPort: 0, toPort: 0 },
                isFinal: true,
            },
        ],
    },

    resnet: {
        title: 'Build ResNet-18 Lite',
        description: 'Residual connection with skip',
        steps: [
            {
                id: 1,
                expects: { action: 'add_node', type: 'MNIST' },
                pos: [100, 200],
                bubble: 'MNIST dataset.',
            },
            {
                id: 2,
                expects: { action: 'add_node', type: 'Conv2D' },
                pos: [340, 150],
                bubble: 'First conv: 16 filters.',
                properties: { out_channels: 16, kernel_size: 3, padding: 1 },
                autoWire: { fromStep: 1, fromPort: 0, toPort: 0 },
            },
            {
                id: 3,
                expects: { action: 'add_node', type: 'BatchNorm2d' },
                pos: [580, 150],
                bubble: 'BatchNorm stabilizes residual path.',
                autoWire: { fromStep: 2, fromPort: 0, toPort: 0 },
            },
            {
                id: 4,
                expects: { action: 'add_node', type: 'ReLU' },
                pos: [820, 150],
                bubble: 'ReLU activation.',
                autoWire: { fromStep: 3, fromPort: 0, toPort: 0 },
            },
            {
                id: 5,
                expects: { action: 'add_node', type: 'Conv2D' },
                pos: [580, 280],
                bubble: 'Second conv in residual block.',
                properties: { out_channels: 16, kernel_size: 3, padding: 1 },
                autoWire: { fromStep: 4, fromPort: 0, toPort: 0 },
            },
            {
                id: 6,
                expects: { action: 'add_node', type: 'BatchNorm2d' },
                pos: [820, 280],
                bubble: 'BatchNorm after second conv.',
                autoWire: { fromStep: 5, fromPort: 0, toPort: 0 },
            },
            {
                id: 7,
                expects: { action: 'add_node', type: 'Add' },
                pos: [1060, 200],
                bubble: 'Add (Residual): skip-connection!\nConnects output of Step 4 + output of Step 6.\nThis is the key: identity shortcut lets gradient flow.',
                autoWire: [
                    { fromStep: 4, fromPort: 0, toPort: 0 },  // skip path
                    { fromStep: 6, fromPort: 0, toPort: 1 },  // main path
                ],
                highlightArrows: true,  // 画两条箭头动画指引
            },
            {
                id: 8,
                expects: { action: 'add_node', type: 'ReLU' },
                pos: [1300, 200],
                bubble: 'ReLU after residual add.',
                autoWire: { fromStep: 7, fromPort: 0, toPort: 0 },
            },
            {
                id: 9,
                expects: { action: 'add_node', type: 'MaxPool' },
                pos: [1300, 320],
                bubble: 'Downsample before classifier.',
                autoWire: { fromStep: 8, fromPort: 0, toPort: 0 },
                hasAuto: true,
            },
            {
                id: 10,
                expects: { action: 'add_node', type: 'Flatten' },
                pos: [1060, 380],
                bubble: 'Flatten for dense layers.',
                autoWire: { fromStep: 9, fromPort: 0, toPort: 0 },
            },
            {
                id: 11,
                expects: { action: 'add_node', type: 'Dense' },
                pos: [1060, 440],
                bubble: 'Dense output: 10 classes.',
                properties: { out_features: 10 },
                autoWire: { fromStep: 10, fromPort: 0, toPort: 0 },
            },
            {
                id: 12,
                expects: { action: 'add_node', type: 'Loss' },
                pos: [1060, 500],
                bubble: 'Training goal.',
                properties: { kind: 'CrossEntropy', optimizer: 'Adam' },
                autoWire: { fromStep: 11, fromPort: 0, toPort: 0 },
                isFinal: true,
            },
        ],
    },
};


// ============================================================
//  Tutorial Engine — 核心类
// ============================================================

class StudioTutorial {
    constructor(graph, canvas) {
        this.graph = graph;
        this.canvas = canvas;
        this.active = false;
        this.module = null;
        this.moduleIndex = 0;       // 当前模块 0=lenet5, 1=cnn, 2=resnet
        this.stepIndex = 0;
        this.shadowNodes = [];      // 当前步骤的阴影节点
        this.placedNodes = [];      // 已放置的实心节点
        this.bubbleEl = null;       // 气泡 DOM 元素
        this.autoBtnEl = null;      // Auto 按钮 DOM 元素
        this.idleTimer = null;      // 30秒无操作计时器
        this._origOnNodeAdded = null;
        this._origOnConnectionChange = null;
        this._origOnDrawForeground = null;
    }

    // ——— 启动教程 ———
    start(moduleKey = 'lenet5') {
        this.active = true;
        this.module = TUTORIAL_MODULES[moduleKey];
        this.stepIndex = 0;
        this.shadowNodes = [];
        this.placedNodes = [];

        // 安装 hooks
        this._installHooks();

        // 显示第一步阴影
        this._showStep(0);

        // 播放入场音效
        loadTransformUpSound();
    }

    // ——— 停止教程 ———
    stop() {
        this.active = false;
        // 清除所有阴影节点（保留已放置的实心节点）
        this.shadowNodes.forEach(n => this.graph.remove(n));
        this.shadowNodes = [];
        this._hideBubble();
        this._hideAutoBtn();
        this._uninstallHooks();
    }

    // ——— 显示某一步 ———
    _showStep(index) {
        this.stepIndex = index;
        const step = this.module.steps[index];
        if (!step) {
            this._finishModule();
            return;
        }

        // 清除旧阴影
        this.shadowNodes.forEach(n => this.graph.remove(n));
        this.shadowNodes = [];

        // 创建阴影节点
        this._createShadow(step);

        // 显示气泡
        this._showBubble(step);

        // 处理 autoWire 高亮箭头
        if (step.highlightArrows) {
            this._drawGuideArrows(step);
        }

        // 重置 30s 空闲计时器
        this._resetIdleTimer(step);
    }

    // ——— 创建阴影节点 ———
    _createShadow(step) {
        const node = LiteGraph.createNode(step.expects.type);
        node.pos = step.pos;
        node.bgcolor = 'rgba(83, 74, 183, 0.08)';
        node.boxcolor = 'rgba(83, 74, 183, 0.4)';
        node.flags.pinned = true;         // 不可拖动
        node.mode = 3;                    // NEVER 执行模式，避免干扰
        if (step.properties) {
            Object.assign(node.properties, step.properties);
        }
        node.isTutorialShadow = true;
        node._stepId = step.id;
        this.graph.add(node);
        this.shadowNodes.push(node);
    }

    // ——— 显示文字气泡 ———
    _showBubble(step) {
        this._hideBubble();
        if (!step.bubble) return;

        const el = document.createElement('div');
        el.className = 'tutorial-bubble';
        el.innerText = step.bubble;
        // 定位在阴影节点附近
        const shadow = this.shadowNodes[0];
        if (shadow) {
            const canvasRect = this.canvas.canvas.getBoundingClientRect();
            // 转换 canvas 坐标到屏幕坐标
            // shadow.pos 是 canvas 内坐标，需要偏移 canvas 的 DOM 位置
            el.style.left = (canvasRect.left + 20) + 'px';
            el.style.bottom = (window.innerHeight - canvasRect.top + 10) + 'px';
        }
        document.body.appendChild(el);
        this.bubbleEl = el;
    }

    _hideBubble() {
        if (this.bubbleEl) { this.bubbleEl.remove(); this.bubbleEl = null; }
    }

    // ——— 显示 Auto 按钮 ———
    _showAutoBtn(step) {
        this._hideAutoBtn();
        const el = document.createElement('button');
        el.className = 'tutorial-auto-btn';
        el.innerText = 'Auto-fill remaining steps';
        el.onclick = () => this._autoComplete();
        // 放在阴影节点旁边
        const shadow = this.shadowNodes[0];
        if (shadow) {
            const canvasRect = this.canvas.canvas.getBoundingClientRect();
            el.style.left = (canvasRect.left + 20) + 'px';
            el.style.bottom = (window.innerHeight - canvasRect.top + 40) + 'px';
        }
        document.body.appendChild(el);
        this.autoBtnEl = el;
    }

    _hideAutoBtn() {
        if (this.autoBtnEl) { this.autoBtnEl.remove(); this.autoBtnEl = null; }
    }

    // ——— 30 秒空闲计时器 ———
    _resetIdleTimer(step) {
        clearTimeout(this.idleTimer);
        if (step.hasAuto) {
            this.idleTimer = setTimeout(() => {
                this._showAutoBtn(step);
            }, 30000);
        }
    }

    // ——— 自动补全 ———
    _autoComplete() {
        this._hideAutoBtn();
        // 从当前 step 开始，逐秒自动放置剩余节点
        const remaining = this.module.steps.slice(this.stepIndex);
        remaining.forEach((step, i) => {
            setTimeout(() => {
                const node = LiteGraph.createNode(step.expects.type);
                node.pos = step.pos;
                if (step.properties) Object.assign(node.properties, step.properties);
                this.graph.add(node);
                this.placedNodes.push(node);
                playTransformUp();
                // 如果下一步是最终步，完成后播放 chime
                if (i === remaining.length - 1 && step.isFinal) {
                    setTimeout(playAchievementChime, 400);
                }
            }, i * 300);
        });
        // 直接跳到完成
        setTimeout(() => this._finishModule(), remaining.length * 300 + 200);
    }

    // ——— 完成当前模块 ———
    _finishModule() {
        this.stop();
        playAchievementChime();
        // 弹出提示
        alert(`[Tutorial] ${this.module.title} module complete! Choose another or start free building.`);
        // 画布恢复自由状态，已搭建的模型保留
    }

    // ——— 安装 LiteGraph hooks ———
    _installHooks() {
        // 保存原始 handler
        this._origOnNodeAdded = this.graph.onNodeAdded;
        this._origOnConnectionChange = this.graph.onConnectionChange;

        const self = this;
        this.graph.onNodeAdded = function(node) {
            // 先调用原始 handler
            if (self._origOnNodeAdded) self._origOnNodeAdded.call(this, node);
            if (!self.active || node.isTutorialShadow) return;

            const step = self.module.steps[self.stepIndex];
            if (!step) return;

            // 检查用户是否放置了匹配的节点
            if (node.type === step.expects.type) {
                // 检查位置是否接近阴影
                const shadow = self.shadowNodes[0];
                if (shadow) {
                    const dx = node.pos[0] - shadow.pos[0];
                    const dy = node.pos[1] - shadow.pos[1];
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 200) {
                        // 吸附！
                        node.pos = [shadow.pos[0], shadow.pos[1]];
                        self.placedNodes.push(node);

                        // 删除阴影
                        self.graph.remove(shadow);
                        self.shadowNodes = [];

                        // 自动连线
                        if (step.autoWire) {
                            setTimeout(() => self._doAutoWire(node, step), 100);
                        }

                        // 音效
                        playTransformUp();

                        // 下一步
                        self._idleTimeout = null;
                        clearTimeout(self.idleTimer);
                        self._hideAutoBtn();
                        setTimeout(() => self._showStep(self.stepIndex + 1), 300);
                    }
                }
            }
        };
    }

    // ——— 卸载 hooks ———
    _uninstallHooks() {
        if (this._origOnNodeAdded !== null) {
            this.graph.onNodeAdded = this._origOnNodeAdded;
        }
        if (this._origOnConnectionChange !== null) {
            this.graph.onConnectionChange = this._origOnConnectionChange;
        }
        clearTimeout(this.idleTimer);
    }

    // ——— 自动连线 ———
    _doAutoWire(newNode, step) {
        // step.autoWire 可以是单个对象或数组
        const wires = Array.isArray(step.autoWire) ? step.autoWire : [step.autoWire];

        wires.forEach(w => {
            const fromNode = this.placedNodes[w.fromStep - 1]; // placedNodes 按 step id 索引
            if (fromNode) {
                // 连线：fromNode 的 output[w.fromPort] → newNode 的 input[w.toPort]
                const fromOutput = w.fromPort || 0;
                const toInput = w.toPort || 0;
                fromNode.connect(fromOutput, newNode, toInput);
            }
        });
    }

    // ——— 残差箭头指引 ———
    _drawGuideArrows(step) {
        // 在画布上绘制动画箭头，指引用户连接两条线到 Add 节点
        // 使用 canvas.onDrawForeground
        const self = this;
        this._origOnDrawForeground = this.canvas.onDrawForeground;
        this.canvas.onDrawForeground = function(ctx, rect) {
            if (self._origOnDrawForeground) self._origOnDrawForeground.call(this, ctx, rect);
            if (!self.active) return;
            // 绘制从 Step 4 和 Step 6 到 Add 节点的虚线动画箭头
            // 用 ctx.setLineDash 做虚线 + ctx.strokeStyle 半透明紫色
            ctx.save();
            ctx.setLineDash([6, 4]);
            ctx.strokeStyle = 'rgba(83, 74, 183, 0.5)';
            ctx.lineWidth = 2;
            // ... 绘制逻辑 ...
            ctx.restore();
        };
    }
}

// ——— 全局单例 ———
let tutorial = null;

function initTutorial(graph, canvas) {
    tutorial = new StudioTutorial(graph, canvas);
    return tutorial;
}
```

### 2.3 集成到 `workshop.html`

在 `templates/workshop.html` 中：

**① Head 添加 CSS：**
```html
<link rel="stylesheet" href="/static/tutorial.css">
```

**② Header 添加按钮（"Back to Arena" 旁边）：**
```html
<button class="tutorial-entry-btn" id="btn-tutorial">
    <i class="ti ti-book"></i> Tutorial
</button>
```

**③ 页面底部添加 tutorial.js（在 designer.js 之后）：**
```html
<script src="/static/tutorial.js"></script>
<script>
    // 在 designer.js 的 graph/canvas 初始化完成后
    // graph 和 canvas 是 designer.js 中的全局变量
    initTutorial(graph, canvas);
    
    // 教程入口按钮
    document.getElementById('btn-tutorial').onclick = function() {
        if (tutorial.active) {
            tutorial.stop();
            this.innerHTML = '<i class="ti ti-book"></i> Tutorial';
        } else {
            // 弹出选择菜单或直接开始
            const choice = confirm(
                'Choose tutorial:\n' +
                'OK = LeNet-5\n' +
                'Cancel = Choose later'
            );
            if (choice) {
                tutorial.start('lenet5');
                this.innerHTML = '<i class="ti ti-x"></i> Exit Tutorial';
            } else {
                // 显示3个模块选择
                showTutorialPicker();
            }
        }
    };
    
    function showTutorialPicker() {
        // 弹出一个小菜单选择模块
        const modules = ['lenet5', 'cnn', 'resnet'];
        const names = ['LeNet-5 (Easy)', 'CNN (Medium)', 'ResNet (Advanced)'];
        const choice = prompt('Choose module:\n1. ' + names[0] + '\n2. ' + names[1] + '\n3. ' + names[2], '1');
        const idx = parseInt(choice) - 1;
        if (idx >= 0 && idx < 3) {
            tutorial.start(modules[idx]);
            document.getElementById('btn-tutorial').innerHTML = '<i class="ti ti-x"></i> Exit Tutorial';
        }
    }
</script>
```

---

## 3. TransformUp 音效集成

### 3.1 下载音效

从以下链接手动下载 MP3：
```
https://pixabay.com/sound-effects/film-special-effects-transformup-78790/
```

### 3.2 集成方式（三种可选）

**方法 A — 文件系统（推荐）：**
1. 将 MP3 文件保存为 `C:\Users\user\Desktop\myproject\CortexNodus\static\sounds\transformup.mp3`
2. `static/tutorial.js` 中的 `loadTransformUpSound()` 通过 fetch 加载

**方法 B — Base64 内嵌：**
1. 用在线工具将 MP3 转为 base64 字符串
2. 替换 `static/tutorial.js` 中 `loadTransformUpSound()` 内的占位代码

**方法 C — 直接 <audio> 标签：**
```html
<audio id="transformup-sound" preload="auto">
    <source src="/static/sounds/transformup.mp3" type="audio/mpeg">
</audio>
```
然后在 JS 中用 `document.getElementById('transformup-sound').play()`

---

## 4. 施工顺序（给 AI 的步骤清单）

### Step 1: 配色回滚
- [ ] 编辑 `static/arena.css` — 替换 `:root` 块（参考 1.1）
- [ ] 全局替换颜色引用（参考 1.2）
- [ ] 修改 `.challenge-card`（参考 1.3）
- [ ] 修改 `.season-badge`（参考 1.4）
- [ ] 验证：启动服务器，打开浏览器确认深紫色背景

### Step 2: 创建 tutorial 文件
- [ ] 创建 `static/tutorial.css`（参考 2.1）
- [ ] 创建 `static/tutorial.js`（参考 2.2，需完整复制）

### Step 3: 集成到 workshop.html
- [ ] 在 `<head>` 中添加 tutorial.css 引用
- [ ] 在 header 中添加 Tutorial 按钮
- [ ] 在页面底部（designer.js 之后）添加初始化脚本（参考 2.3）

### Step 4: 音效
- [ ] 创建 `static/sounds/` 目录
- [ ] 手动下载 TransformUp MP3 放入该目录
- [ ] 确认 tutorial.js 中的 `loadTransformUpSound()` 加载路径正确

### Step 5: 测试
- [ ] 启动服务器 `python app.py`
- [ ] 访问 `http://localhost:5000/workshop`
- [ ] 点击 Tutorial → 选择 LeNet-5
- [ ] 验证阴影出现、放置吸附、连线、音效
- [ ] 验证 30 秒 Auto 按钮出现
- [ ] 验证完成后的 chime
- [ ] 验证退出教程后模型保留

---

## 5. 已知需要 AI 自行处理的细节

以下是不在施工方案中、需要 AI 根据实际情况调整的：

1. **阴影节点的 LiteGraph 模式**：`node.mode = 3` 是 LiteGraph.NEVER（不参与执行）。如果版本不支持，尝试 `node.mode = 0` 但确保模型执行时跳过阴影节点。

2. **Auto 按钮的位置**：代码中 `el.style.left/top/bottom` 是估算值，需要根据实际 DOM 结构调整。

3. **残差连接的箭头动画**：`_drawGuideArrows()` 中的 `ctx.drawLine()` 需要填写实际的节点坐标和偏移量。

4. **graph.onNodeAdded hook 冲突**：`designer.js` 中已有 `graph.onNodeAdded = triggerSaveState`，tutorial.js 需要先保存 `graph.onNodeAdded` 才能在 `_installHooks` 中正确包装。如果 designer.js 的赋值在 tutorial.js 之后，需调整加载顺序。

5. **tutorial.js 中 `graph` 和 `canvas` 全局变量**：这两个是 `designer.js` 中的全局变量。tutorial.js 必须在 `designer.js` 之后加载。

---

*文档结束。开始施工。*
