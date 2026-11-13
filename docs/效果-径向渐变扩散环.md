# 效果：径向渐变扩散环

车/图标脚下周期性向外扩散的**多圈光环**。适合"脉冲扩散""充能波纹""呼吸底盘光"这类需要一圈套一圈往外扩的效果。

## TL;DR

1. **一枚静态圆 + 一条径向渐变**，之后只靠 `Mat2D.withScale` 缩放，**不重建几何**。旧做法（每帧 `path:reset()` + 重新画圆 + 多档 alpha 切换）能扔就扔。
2. **渐变半径必须 ×√2**：CSS `radial-gradient(circle, …)` 的 `100%` 落在**最远角**，而圆的边界在 `1/√2 ≈ 0.707` 处。不乘 √2，渐变会提前到边，环会偏亮偏实。
3. **Rive canvas 脚本没有 `globalAlpha`**。单环透明度只能 `renderer:save()` → `renderer:modulateOpacity(op)` → `drawPath` → `renderer:restore()`，它是**乘法**因子，必须配对 restore。
4. **多环 = 一个累加时钟**：`phase = fxT % INTERVAL`，第 k 圈的年龄 `age = phase + k × INTERVAL`，`age < LIFE` 才画。同屏环数 `ceil(LIFE / INTERVAL)`。
5. **色标要做成中空**：把 50% 处的 alpha 压到 1% 出头，才会读成"一圈光环"；线性锥形会读成"一块实心片"。

---

## 一、效果分解（参考语义）

| 项 | 参考实现 | 说明 |
|---|---|---|
| 生成 | `setInterval(1.0s)` 追加一个 div | 每隔一段时间新增一圈 |
| 尺寸 | `radial-gradient` 圆，直径 350 | 从 0 缩放到 1.5 倍 |
| 生命 | 2.5s 扩散 + 0.5s 渐隐 = 3.0s | 前段不透明，末段淡出 |
| 缓动 | `ease-out` | 起快末慢 |
| 混合 | 叠加发光 | Rive 对应 `blendMode = 'additive'` |

映射到脚本就是「一枚圆 × 一条渐变 × 一个时钟」，没有任何逐帧重建。

---

## 二、几何：一枚静态圆

`init` 里建一次，之后永不重建。用 4 段三次贝塞尔画圆，控制点系数 `0.5522847498`：

```lua
local ringR: number = RING_SIZE * 0.5 * RING_K
local kk: number = ringR * 0.5522847498
self.ringPath = Path.new()
self.ringPath:moveTo(Vector.xy(ringR, 0))
self.ringPath:cubicTo(Vector.xy(ringR, kk), Vector.xy(kk, ringR), Vector.xy(0, ringR))
self.ringPath:cubicTo(Vector.xy(-kk, ringR), Vector.xy(-ringR, kk), Vector.xy(-ringR, 0))
self.ringPath:cubicTo(Vector.xy(-ringR, -kk), Vector.xy(-kk, -ringR), Vector.xy(0, -ringR))
self.ringPath:cubicTo(Vector.xy(kk, -ringR), Vector.xy(ringR, -kk), Vector.xy(ringR, 0))
self.ringPath:close()
```

半径带 `RING_K` 是为了**只改一个数就能整体缩放**：基准半径 = `175 × RING_K`。

---

## 三、渐变：为什么半径要 ×√2

```lua
gradient = Gradient.radial(Vector.xy(0, 0), ringR * RING_GRAD_K, {   -- RING_GRAD_K = sqrt(2)
    { position = 0,    color = RING_C0 },
    { position = 0.50, color = RING_C50 },
    { position = 0.70, color = RING_C70 },
    { position = 1,    color = RING_C100 },
}),
```

CSS 的 `radial-gradient(circle, …)` 默认 sizing 是 **farthest-corner**：`100%` 对应到方形盒子的最远角，距离是半径的 √2 倍。而圆的实际边界在半径处，也就是归一化距离 `1/√2 ≈ 0.707`。

**推论（很实用）**：

- `0.70` 这个色标几乎正好落在圆的边界上 → 它决定"环的最外圈亮度"；
- `1.00` 这个色标**永远在圆外**，写的值不会被看到（留它是为了语义完整，改它没有视觉影响）。

不做 √2 校正，`0.70` 会落在 `0.70 × r` 处，环会提前变亮、边缘发虚，且最难调。

---

## 四、多环的时间模型

```lua
local phase: number = (self.fxT or 0) % RING_INTERVAL
for k = RING_COUNT - 1, 0, -1 do          -- 老环先画（压底层），新环压上层
    local age: number = phase + k * RING_INTERVAL
    if age < RING_LIFE then
        local p: number = age / RING_LIFE
        local sc: number = RING_MAX_SCALE * easeOut(p)
        local op: number = 1
        if p > RING_APPEAR / RING_LIFE then
            op = 1 - easeOut((p - RING_APPEAR / RING_LIFE) / (1 - RING_APPEAR / RING_LIFE))
        end
        ...
    end
end
```

只需一个变量 `self.fxT = self.fxT + dt`，不需要维护"环对象池"。
`k` 从大到小遍历，保证先生成的那圈压在下层，和参考实现里 `appendChild` 的顺序一致。

缓动是 CSS `ease-out` 的等价物，二分反解 `x(u) = t` 再取 `y(u)`（14 次迭代、容差 `4e-4` 足够，肉眼无差）：

```lua
local function cubicBezier(p1x, p1y, p2x, p2y, t)
    if t <= 0 then return 0 end
    if t >= 1 then return 1 end
    local lo, hi, u = 0, 1, t
    for _ = 1, 14 do
        local m = 1 - u
        local x = 3*m*m*u*p1x + 3*m*u*u*p2x + u*u*u
        if math.abs(x - t) < 0.0004 then break end
        if x < t then lo = u else hi = u end
        u = (lo + hi) * 0.5
    end
    local m = 1 - u
    return 3*m*m*u*p1y + 3*m*u*u*p2y + u*u*u
end
local function easeOut(p) return cubicBezier(0, 0, 0.58, 1, p) end
```

---

## 五、单环透明度：modulateOpacity

脚本层**没有** `globalAlpha`，也不该为了透明度去建一堆 alpha 分桶的 `Paint`。正解：

```lua
renderer:save()
renderer:transform(Mat2D.withTranslation(cx, cy))
renderer:transform(Mat2D.withScale(sc, sc))
renderer:modulateOpacity(op)          -- 乘法因子 0..1
renderer:drawPath(self.ringPath, self.ringPaint)
renderer:restore()
```

- `modulateOpacity` 是**乘法**，会叠乘到 paint 自身的 alpha 上——所以色标里的 alpha 照常生效，`op` 只是再乘一次；
- 它被 `save()/restore()` 捕获，**必须配对**，否则会把后面所有绘制一起压暗；
- 平移和缩放都放在同一对 save/restore 里，环之间互不干扰。

> 对比：早期为了做"单个多边形不同透明度"，把同一形状按 alpha 分成 32 档、每档一个 `Paint`。那是**几何分桶**，
> 环数一多就是几十次 `drawPath`。有渐变可用时不要走那条路。

---

## 六、绘制顺序与混合

```
drawFx → drawIconGlow → drawRings → drawDust → drawSand → 车
```

环必须压在沙尘与车身**之下**，否则车身轮廓会被橙光洗白。混合用 `additive`：
多环重叠处自然累加变亮，正好是想"更亮"时的最优解（比调 `RING_ALPHA` 更自然，因为只亮在交叠区）。

---

## 七、定稿参数

以下为「004 充电完成」车下扩散环的实测定稿（2026-11-12）。

| 参数 | 值 | 含义 |
|---|---|---|
| `RING_SIZE` | 350 | 参考实现的直径，一般不动 |
| `RING_K` | **0.1934** | 缩放系数，基准半径 = `175 × K` = **33.845** |
| `RING_MAX_SCALE` | 1.5 | 峰值倍率 → 峰值半径 **50.7675**（外径 ≈101.5） |
| `RING_INTERVAL` | **2.0** s | 生成间隔 |
| `RING_APPEAR` | **5.0** s | 扩散时长 |
| `RING_DISAPPEAR` | **1.0** s | 渐隐时长 |
| `RING_LIFE` | 6.0 s | `APPEAR + DISAPPEAR` |
| `RING_COUNT` | 3 | `ceil(LIFE / INTERVAL)` |
| `RING_GRAD_K` | `sqrt(2)` | 最远角校正 |
| 混合 | `additive` | — |

色标（`RING_ALPHA = 1.0` 时的实际 0–255）：

| 位置 | 颜色 | alpha | 意图 |
|---|---|---|---|
| 0% | `140,106,82` | 0 | 圆心全透 |
| 50% | `255,108,0` | **3（1.2%）** | 圆心附近几乎不可见 → 中空光环 |
| 70% | `255,108,0` | **66（26%）** | 亮环本体（刚好在圆边界上） |
| 100% | `255,193,148` | 192（75%） | 圆外，看不到 |

> 这三个 alpha 是把"线性锥形实心片"调成"通透光环"的关键：**只降 50% 那一档**，
> 70% 那档保持 26%，视觉上就从"一盘橙光"变成"一圈涟漪"。

---

## 八、调参：尺寸 / 速度 / 亮度

### 尺寸

只改 `RING_K`，其他不动。基准半径与峰值半径同比例变化。

### 速度：**时间膨胀**，不是只改一个数

要让整体变慢、但**不改变同屏密度**，把三个时间常数**同比例**缩放：

```lua
-- 速度 50%
RING_INTERVAL  = 2.0   -- 原 1.0
RING_APPEAR    = 5.0   -- 原 2.5
RING_DISAPPEAR = 1.0   -- 原 0.5
-- RING_LIFE 自动 3.0 → 6.0；RING_COUNT = ceil(6/2) = 3，密度不变
```

因为 `RING_COUNT = ceil(LIFE / INTERVAL)`，只要三者同比，环数恒定，
视觉上就是"同一套环跑得慢了一半"，而不是"环变少"。

**反例**：只把 `RING_APPEAR` 拉长、`RING_INTERVAL` 不动 → 环数变多、环变大，
这是"更密的波纹"，是另一个需求，别混用。

### 亮度

两个旋钮，优先用第一个：

| 旋钮 | 效果 |
|---|---|
| `blendMode = 'additive'` | 只让**交叠区**变亮，层次自然（推荐） |
| `RING_ALPHA` | 整体乘法提亮，会把单环也一起拉亮，容易糊 |

---

## 九、与《效果-能量光圈》怎么选

两篇都是"圆环扩散"，但实现代际不同：

| | 本篇（径向渐变版） | 《效果-能量光圈》 |
|---|---|---|
| 几何 | init 建一次，之后只 transform | 每帧 `reset()` + 重新画圆 |
| 透明度 | `modulateOpacity` 连续 | 4 档 alpha 硬切换（`u<0.25/0.5/0.75`） |
| 填充 | 径向渐变（中心到边缘连续过渡） | 纯色（靠 alpha 档位模拟） |
| 环形状 | 实心圆面 + 渐变（外缘自然消失） | 圆**环**（`thickness` 从 2.4 收到 1.2） |
| 适合 | 柔和光雾扩散、底盘脉冲 | 明确的细环、需要控制线宽 |

**判据**：要"雾状/光晕感"用本篇；要"一根细亮线在扩散"用能量光圈。

---

## 十、性能

- 每环 **1 次 `drawPath`**，3 环 = 3 次/帧；旧的分桶方案同尺寸下是几十次。
- 渐变在 `init` 里建好，逐帧零分配。
- 开销主要在**填充面积**（透明像素也要光栅化），不在环数。面积压不住时先缩 `RING_K`，别减环。

---

## 十一、注意事项

| 现象 | 原因 | 处理 |
|---|---|---|
| 环偏亮、边缘发虚 | 渐变半径没乘 √2 | `RING_GRAD_K = math.sqrt(2)` |
| 环读成一块实心片 | 50% 档 alpha 太高（线性锥形） | 把 50% 档压到 1% 左右，只留 70% 档 |
| 后面的绘制全变暗 | `modulateOpacity` 没配对 `restore` | 每次 `save()` 必须有 `restore()` |
| 重叠处过曝成白 | 多环 + additive 累加 | 降 70% 档 alpha，或减少同屏环数 |
| 环盖住车身 | 绘制顺序在车之后 | 把 `drawRings` 提到车身 `drawImage` 之前 |
| 改速度后环变多了 | 只改了 `APPEAR` | 三个时间常数同比改（见 §八） |

---

## 十二、验收

1. `recompile_all_scripts` 后 `script_diagnostics` 为 `[]`；
2. `read_console` 里 init 打印的基准半径 / 峰值半径符合 `175 × RING_K`；
3. 编辑器播放：环从中心向外匀加速扩散、前段不透明、末段淡出，同屏环数与 `ceil(LIFE/INTERVAL)` 一致；
4. 离线复刻可信度（可选）：用同一套参数渲染静帧，与浏览器版本比对 —— 本机实测环半径 60 / 175 / 255 px 三级对齐，
   R 通道平均绝对差 **6.1/255（≈2.4%）**，差异集中在边缘抗锯齿。

---

## 来源

- 本机实测：2026-11-12，Rive 桌面版 1.9.x + 本地 MCP，文件「充电桌面」画板「004 充电完成」（`3-37978`），脚本 `car_probe_004`。
- 参考原型：多 `radial-gradient` 圆叠放的 HTML 脉冲扩散（`interval 1.0s / size 350 / appear 2.5s / disappear 0.5s / ease-out`）。
- CSS 渐变 sizing：[MDN — radial-gradient()](https://developer.mozilla.org/zh-CN/docs/Web/CSS/gradient/radial-gradient)。
- 缓动等价：[MDN — ease-out](https://developer.mozilla.org/zh-CN/docs/Web/CSS/easing-function)（`cubic-bezier(0, 0, 0.58, 1)`）。
