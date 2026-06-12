# Studio 新手教程 — 动态阴影拼图方案

---

## 核心体验：拼拼图

**不是文本弹窗教学，不是自动演示。**

是画布上的**动态阴影**，告诉用户"把这块拼到这里"。

```
Canvas 状态（教程进行中）：

  ┌──────┐     ┌──────────┐     ┌──────────┐
  │MNIST │────▶│ ░░░░░░░░ │────▶│ ░░░░░░░░ │
  └──────┘     │ Conv2D   │     │  ReLU    │   ← 半透明阴影
  (已放置)     │ ░░░░░░░░ │     │ ░░░░░░░░ │      发蓝光·脉动
               └──────────┘     └──────────┘
                   ↑                 ↑
               "把 Conv2D        "然后是 ReLU"
               放到这里"          (阴影自动出现)
```

### 每一步流程

1. 画布上已经有一些**半透明发光阴影节点**，像拼图空位
2. 旁边的简短文字气泡说明（不是大面板，是小气泡）
3. 用户从左侧拖出对应的节点 → 放到阴影附近
4. **自动吸附**到阴影位置 + **TransformUp 金属合体音效**
5. 阴影变实心节点，自动连上线
6. 下一个阴影出现
7. 有些重复步骤（如连续两个 Conv+Pool）会出现 `[Auto]` 按钮一键补全
8. 一整组模块完成后 → **成就 chime 🎵**
9. 继续下一组，或点击 `[退出教程]` 回到自由搭建

---

## 三个模块

| 模块 | 说明 | 阴影组数 |
|------|------|---------|
| **LeNet-5** | MNIST → Conv→Pool→Conv→Pool→Flatten→Dense×3→Loss | 约7步，含1个 Auto |
| **CNN** | 更自由的 Conv→BN→ReLU→Pool 组合 | 约5步，引导但不严格 |
| **ResNet** | 残差连接：Conv→ReLU→Conv→Add（两条线） | 约6步，含连线指导 |

用户可以**选择做或不做**，也可以随时退出。

---

## 阴影的技术实现

### 阴影 = 特殊的 LiteGraph 节点

每次教程步骤开始前，在画布特定位置创建**半透明节点**：

```javascript
const shadow = LiteGraph.createNode("Conv2D");
shadow.pos = [300, 200];
shadow.bgcolor = "rgba(59, 130, 246, 0.12)";
shadow.boxcolor = "rgba(59, 130, 246, 0.35)";
shadow.flags.pinned = true;          // 不可拖动
shadow.title = "?";                   // 节点标题模糊化
shadow.isTutorialShadow = true;       // 自定义标记
canvas.graph.add(shadow);
```

### 脉动动画

通过 `canvas.onDrawForeground` 叠加绘制：

```javascript
canvas.onDrawForeground = function(ctx) {
  if (tutorial.active) {
    tutorial.getShadows().forEach(shadow => {
      const pulse = 0.3 + 0.2 * Math.sin(Date.now() / 400);
      ctx.beginPath();
      ctx.roundRect(shadow.pos[0]-4, shadow.pos[1]-4, 
                     shadow.size[0]+8, shadow.size[1]+8, 6);
      ctx.strokeStyle = `rgba(59, 130, 246, ${pulse})`;
      ctx.lineWidth = 2;
      ctx.stroke();
    });
  }
};
```

### 检测用户放置

```javascript
graph.onNodeAdded = function(node) {
  if (!tutorial.active || node.isTutorialShadow) return;
  
  const expected = tutorial.getCurrentStep().expects;
  
  if (node.type === expected.type) {
    // 检查位置是否靠近阴影
    const shadow = tutorial.getCurrentShadow();
    const dist = distance(node.pos, shadow.pos);
    if (dist < 150) {
      // 吸附 + 替换阴影
      node.pos = shadow.pos;
      canvas.graph.remove(shadow);
      autoWire(node);              // 自动连线
      playSound('transformup');    // 合体音效
      tutorial.advance();          // 下一步
    }
  }
};
```

### 自动连线

当前一个阴影确认后，自动把新节点和前一个节点连接起来：
- 自动检测输入/输出端口匹配
- 连线时也有一个"连线生长"动画

---

## Auto 补全

对于重复性步骤（比如三个 Dense 层），阴影旁边会出现一个脉冲的 `[Auto]` 按钮：

```javascript
// canvas.onDrawForeground 中绘制
if (step.hasAutoFill) {
  // 在阴影下方绘制 [Auto] 按钮
  // 用户点击后批量生成其余节点 + 连线
  // 每一步间隔 300ms，依次触发 TransformUp 音效
}
```

---

## 文字气泡（不是大面板）

连接时出现的说明文字是**画布上的小气泡**，不是右侧大面板：

```
     ┌──────────┐
     │ ░░░░░░░░ │
     │ ░░░░░░░░ │
     └──────────┘
        ╱  ╲
       ╱    ╲
  ┌──────────────┐
  │  卷积层提取   │       ← 小气泡，附着在阴影附近
  │  图像特征     │         半透明背景，2-3行字
  └──────────────┘
```

### 气泡规则
- 不超过 15 个字，只写**为什么做这步**，不写**怎么操作**
- 最多显示 6 秒自动淡出
- 如果用户超过 30 秒没操作，重新显示一次

---

## 音效系统汇总

| 时机 | 音效 | 来源 |
|------|------|------|
| 节点吸附/合体 | **TransformUp** 金属咔嗒 | Pixabay → 转为 base64 内嵌 |
| 一组完成 (chime) | **成就 chime** (C5→E5→G5) | Web Audio API 生成 |
| Auto 补全 | 快速连续 TransformUp × N | 间隔 150ms 播放 |

---

## ✔ 已确认的决策

| 决策点 | 选择 |
|--------|------|
| 气泡文字风格 | **技术解说**（"Conv2D 通过卷积核提取局部特征"） |
| Auto 补全触发 | **30 秒无操作自动弹出提示**，用户可选接受或忽略 |

## ✘ 已废弃

- 配色方案 → 见 `IMPLEMENTATION_SPEC.md` 第1节（紫色+黑色+灰色，SOTA 金色）

---

**你觉得这个方向对吗？有什么要调整的？** 确定了我再开始做实现。
