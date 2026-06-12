# Let's SOTA!!!!!

> AI模型竞技训练平台 — 拖拽搭建神经网络，刷SOTA，实时排行榜，成就系统，一键部署

![Python](https://img.shields.io/badge/python-3.8+-blue) ![Flask](https://img.shields.io/badge/flask-3.0+-black) ![PyTorch](https://img.shields.io/badge/pytorch-2.3+-red) ![License](https://img.shields.io/badge/license-GPL--3.0-green)

---

## 🎯 核心循环

```
设计模型 → 选数据集 → 训练 → 提交分数 → 排行榜 → 优化 → 再来！
```

Kaggle的竞技性 + Scratch的拖拽体验 + 游戏化的成就/称号系统

---

## 🚀 快速开始

### 环境要求
- Python 3.8+
- PyTorch (CPU或GPU均可)
- pip

### 安装 & 启动

```bash
git clone https://github.com/Takamatsu-Hikaru/Lets_SOTA.git
cd Lets_SOTA

pip install -r requirements.txt
python app.py
```

打开浏览器访问：
- **http://localhost:5000** — Arena 竞技主页
- **http://localhost:5000/workshop** — Studio 模型搭建工坊

### Docker 启动

```bash
docker compose up --build
```

---

## 🎮 功能模块

### 🏆 Arena（竞技面板）
- 排行榜 — 6个数据集 × 4个硬件分组 × 3个排名指标
- 训练面板 — 选预置模型或Studio自定义图 → 填超参 → 一键训练 → 自动提交
- 回放系统 — 查看任意历史的训练曲线和代码

### ⭐ 成就系统
20个成就，分6类：里程碑/精度/速度/多样性/竞争/架构/隐藏
- Legendary: SOTA Breaker, Dethroned
- Epic: 99% Club, Speedrunner, Minimalist
- 解锁时带 **金属合体音效** + 弹窗动画

### 🥇 段位排名
```
Bronze (0%) → Silver (90%) → Gold (95%) → Platinum (98%) → Diamond (99%) → SOTA Champion (99.5%+)
```
全局ELO排名 + 硬件效率分数

### 📅 赛季系统
30天一个赛季，季末快照 + 徽章颁发 + 新赛季自动开始

### 🔥 每日挑战
8种随机约束挑战（"3层以内"、"batch size=8"、"不用卷积"等），每日自动刷新

### 🤖 Studio 新手教程
画布上的**动态阴影拼图**教学：
1. LeNet-5 — 经典MNIST分类器
2. CNN — BatchNorm卷积网络
3. ResNet — 残差跳跃连接
- 阴影引导 → 拖拽节点 → 自动吸附 → 🔊合体音效
- 30秒无操作弹出 `[Auto]` 一键补全

---

## 🧱 预置模型 (Model Zoo)

| 模型 | 数据集 | 参数量 | 亮点 |
|------|--------|--------|------|
| LeNet-5 | MNIST | 60K | 经典CNN入门 |
| MLP Baseline | MNIST | 100K | 纯全连接基线 |
| ResNet-18 Lite | MNIST | ~500K | 残差连接 (Add节点) |
| VGG-lite | CIFAR-10 | 2M | VGG简化版 |
| Simple Transformer | WikiText-2 | ~500K | GPTBlock×2 |

---

## 🛠️ Tech Stack

| 层 | 技术 |
|----|------|
| 前端 | LiteGraph.js + Chart.js + Tabler Icons |
| 后端 | Flask + Flask-SocketIO + Flask-SQLAlchemy |
| AI | PyTorch + torchvision |
| 数据库 | SQLite |
| 部署 | Docker + docker-compose |

---

## 📁 项目结构

```
Lets_SOTA/
├── app.py                 # Flask 主路由
├── arena/                 # 竞技系统后端
│   ├── models.py          # SQLAlchemy 数据模型 (7 tables)
│   ├── leaderboard.py     # 排行榜 API Blueprint
│   ├── achievements.py    # 20个成就 + 自动检查
│   ├── season.py          # 赛季系统
│   ├── challenges.py      # 每日挑战
│   ├── ranking.py         # ELO段位 + 效率分数
│   ├── train.py           # ArenaTrainer 训练桥接
│   ├── datasets.py        # 数据集注册 (6 datasets)
│   └── replay.py          # 训练回放
├── ml/                    # 机器学习引擎 (基于CortexNodus)
│   ├── designer.py        # LiteGraph节点注册 + 模型构建
│   ├── code_generator.py  # PyTorch代码生成
│   ├── data_loader.py     # 数据加载器
│   └── visualization.py   # 训练可视化
├── templates/
│   ├── arena.html         # Let's SOTA!!!!! 主页
│   └── workshop.html      # Studio 模型搭建 + Tutorial
├── static/
│   ├── arena.css          # 紫色主题样式
│   ├── arena.js           # 竞技前端逻辑
│   ├── designer.js        # LiteGraph 编辑器
│   ├── tutorial.css       # 教程系统样式
│   ├── tutorial.js        # 阴影拼图教程引擎
│   └── sounds/
│       └── transformup.mp3 # 金属合体音效
├── model_zoo/             # 预置模型库
│   ├── registry.json
│   ├── lenet5/            # graph.json + meta.json
│   ├── mlp_baseline/
│   ├── resnet18/
│   ├── vgg_lite/
│   └── simple_transformer/
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 🔬 示例

### 训练一个 LeNet-5 在 MNIST 上：

1. 打开 Arena → Train Tab
2. 选 Preset Model: LeNet-5
3. 数据集自动切到 MNIST
4. 点 **Start Training**
5. 训练曲线实时更新 → 完成自动提交排行榜 → 解锁成就

### Studio 手动设计模型：

1. 打开 `/workshop`
2. 点 **Tutorial** 选 LeNet-5 入门
3. 跟着阴影拼图搭建
4. 搭好后回到 Arena → Train → From Studio → 开始训练

---

## 📄 致谢

- 基于 [CortexNodus](https://github.com/streetartist/CortexNodus) by Wen Jiaxian (UESTC)
- [LiteGraph.js](https://github.com/jagenjo/litegraph.js)
- [PyTorch](https://pytorch.org/)
- 音效: Bluezone Corporation (free license)

---

## 📝 License

GPL-3.0 — 详见 [LICENSE](LICENSE)
