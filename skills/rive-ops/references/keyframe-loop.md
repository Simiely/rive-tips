# 关键帧循环防倒飞

MCP 烘循环关键帧时最容易踩、也最难排查的坑：**粒子沿路径"来回弹"**。本文给出根因、修复和通用验证脚本。

## 一、症状

粒子本该沿路径单向汇聚到图标，实际播放时却**往回飞**——像"来回弹"、"不流畅"。逐帧看不出问题，只有播放时可见。

## 二、根因（实测定位）

循环动画被拆成 N 趟（trip），每趟占 L 帧。生成关键帧时：

```python
# ❌ 错误写法
for trip in range(n):
    base = trip * L
    for q in QS:                     # q=1.0 的键落在 base+L
        f = base + round(t(q)/T * L) # 最后一趟的 q=1 落在 base+L == 下一趟的 base
        cells[(obj, prop, f)] = ...  # 按帧去重 → 下一趟起点覆盖上一趟终点！
```

**后果**：`modifyKeyFrames` 按帧去重，"到达图标"那一帧被下一趟的"出生点"覆盖。插值器只好从**倒数第二个采样**（还差一截没到）直接插值到新出生点——这 5 帧就是一条**从图标倒飞回外圈**的可见轨迹。

实测数据（修复前）：

```
f=46  x=2261.99
f=51  x=2270.41   ← 倒飞 +8.4，用了 5 帧（应为 1 帧瞬移）
```

## 三、修复

每趟占 `[base, base+L-1]`，下一趟从 `base+L` 开始：

```python
# ✅ 正确写法
span = L - 1                       # 最后一帧 = base+span
for q in QS_XY:
    f = base + round(t(q) / T * span)   # q=1.0 → base+L-1
...
# 下一趟 base' = base + L          # 与上一趟终点恰好隔 1 帧
```

修复后：

```
f=50  x=2251.35   ← 到达图标边缘（目标 2253.7）
f=51  x=2270.41   ← 1 帧内瞬移，且两端 opacity=0，肉眼不可见
```

## 四、通用验证脚本（打完帧必跑）

```python
# 对每个运动对象：
xs = sorted([(f, v) for f, v in keys if prop == "x"])
ops = {f: v for f, v in keys if prop == "opacity"}
teleports, bad = 0, 0
for (f0, v0), (f1, v1) in zip(xs, xs[1:]):
    if f1 - f0 <= 2 and abs(v1 - v0) > 10:      # 判定为瞬移
        teleports += 1
        if max(ops.get(f0, 0), ops.get(f1, 100)) > 1:
            bad += 1                              # 瞬移时还亮着 = bug
print(teleports, bad)   # 期望：bad == 0
```

实测：40 颗粒子 201 处瞬移、0 处带 opacity → 通过。

## 五、配套要点

| 项 | 要求 |
|---|---|
| 透明度包络 | `0.88 * min(smoothstep(0, 0.12, q), 1 - smoothstep(0.66, 1, q))`，保证路径两端必然为 0 |
| 瞬移帧采样 | 归位前后各打一帧 opacity=0（`f=L-1` 和 `f=L`） |
| 插值 | 5~6 个采样点 + `linear` 即可复刻 `q^1.7` 加速；`cubic` 反而可能过冲 |
| 时钟 | `advance` 里用 `self.t += seconds` 累计（Design 模式 seconds 恒 0，见脚本篇） |

## 六、为什么不能靠"重生时重置 px/py"

脚本版（程序化）里，重生粒子若保留上一世的 `px/py`，draw 会在重生帧画一条**横穿画面的长线**（从旧位置到新出生点）。两个修法：

1. `makeP()` 里把 `px/py` 初始化为新出生点；
2. draw 里加位移上限守卫：`sp > 阈值`（如出生半径的 1/3）就不画尾巴。

关键帧版没有这个问题（瞬移帧 opacity=0），程序化版必须显式处理。
