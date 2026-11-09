# 电流缓动与羽化蒙版（充电动效定稿）

来源：2026-11 车机「003 充电中」实做，定稿 2026-11-09（Rive 桌面版 1.9.x + 本地 MCP）。前序几何/追尾见 [效果-路径电流与脚本复用.md](aurora-path-fx.md)。

> 验证状态：`script_diagnostics` 返回 `[]`；8 层羽化 + 单条电流在编辑器播放不卡；参数与单文件预览页逐项对齐。

## TL;DR

1. **电流要"起步快、接近车尾慢"，不要改 `fxSpeed`**：存进度 `prog 0→1`，用缓动曲线映射成头部距离；`fxSpeed` 只决定总时长。
2. **Rive 没有羽化 `clipPath`，只有硬边**：同一条电流多边形按 N 层外扩、每层低透明度叠画下层图，8 层 / 外扩 290px 是"平滑且不卡"的定稿。
3. **蒙版必须换到画板坐标**：`clipPath` 之后先 `transform(Mat2D.withTranslation(-1639,-682))` 再 `drawImage`，否则下层图整体偏移。
4. **层数不是性能主因**：蒙版面积 × 同屏电流条数才是。先把 `REVEAL_EXTRA` 压到 290、保证同时只有一条电流，再谈加层。

## 一、电流缓动：进度模型

匀速写法 `self.fxOffset = self.fxOffset + self.fxSpeed * dt` 只能得到"整根匀速弹出"，调 `fxSpeed` 只会整体快慢，做不出末段减速。

改成**存进度**、每帧把进度映射成头部弧长：

```lua
-- cubic-bezier 求值：牛顿迭代解 x -> t
local function fxBezier(p: number, x1: number, y1: number, x2: number, y2: number): number
    local t: number = p
    for _ = 1, 6 do
        local mt: number = 1 - t
        local x: number = 3 * mt * mt * t * x1 + 3 * mt * t * t * x2 + t * t * t
        local dx: number = 3 * mt * mt * x1 + 6 * mt * t * (x2 - x1) + 3 * t * t * (1 - x2)
        if math.abs(dx) < 0.000001 then break end
        t = t - (x - p) / dx
        if t < 0 then t = 0 elseif t > 1 then t = 1 end
    end
    local mt2: number = 1 - t
    return 3 * mt2 * mt2 * t * y1 + 3 * mt2 * t * t * y2 + t * t * t
end

-- 起步快、接近车尾慢：Quart 缓出 + 25% 线性保底
local function pulseHead(self: Car, prog: number, maxDraw: number): number
    local target: number = math.max(1, maxDraw + self.fxPulse)
    local eased: number = 0.25 * prog + 0.75 * fxBezier(prog, 0.25, 0.10, 0.25, 1.00)
    return eased * target
end
```

推进只维护 `prog`：

```lua
local rear: number = self.dist - self.fxRear
local travel: number = math.max(0.15, (rear + self.fxPulse) / math.max(1, self.fxSpeed))
for i = #self.fxPulses, 1, -1 do
    local prog: number = self.fxPulses[i] + dt / travel
    self.fxPulses[i] = prog
    if prog >= 1 then table.remove(self.fxPulses, i) end
end
```

要点：

| 项 | 取值 | 说明 |
|---|---|---|
| 曲线 | `cubic-bezier(0.25, 0.10, 0.25, 1.00)` | Quart 一族缓出：前段起速、末段长尾 |
| 混合 | `0.25 * p + 0.75 * eased` | 纯缓出末段斜率趋 0，看起来"停住"；25% 线性保底 |
| 实测速度 | 10% 处 ≈1.1×、中段峰值 ≈1.5–1.6×、末段 ≈0.4× 平均速度 | 混合后的等效斜率 |
| `fxSpeed` | 1520 px/s | 不再等于瞬时速度，只用来算 `travel`（整根跑完的时长） |

车循环重置时**必须清空进度数组**（`self.fxPulses = {}`），否则上一圈的进度会带进新圈。

## 二、羽化蒙版：用多层硬边模拟渐变

Rive 的 `clipPath` 只有硬边，没有 feather/mask 渐变。做法是"由外到内、逐层加密度"：

- 上层图（`003_bg_04_6`）压在下层图（`003_bg_04_5`）之上；
- 用电流多边形当 clip，把**下层图**以低透明度叠回去，区域内就"透"出下层；
- 同一形状做 N 份，外扩量从 `REVEAL_EXTRA` 线性递减到 0，每份重画一次。

```lua
local rings: { { number } } = {}
local ringCount: number = 8
for i = 0, ringCount - 1 do
    local k: number = 1 - i / (ringCount - 1)
    rings[#rings + 1] = { REVEAL_EXTRA * k, 0.6 / ringCount }
end

local mask = self.revealPath
for _, r in ipairs(rings) do
    local extra: number = r[1]
    local alpha: number = r[2]
    mask:reset()
    for _, prog in ipairs(self.fxPulses) do
        local head: number = pulseHead(self, prog, maxDraw)
        local tail: number = head - self.fxPulse
        if head >= 0 and tail <= maxDraw then
            addFxPulse(self, mask, head, tail, maxDraw, extra)
        end
    end
    renderer:save()
    renderer:clipPath(mask)
    renderer:transform(Mat2D.withTranslation(REVEAL_OFF_X, REVEAL_OFF_Y))
    renderer:drawImage(self.reveal, self.sampler, 'srcOver', alpha)
    renderer:restore()
end
```

| 参数 | 值 | 作用 |
|---|---|---|
| `ringCount` | 8 | 过渡层数；越多边缘越平滑 |
| `extra` | `290 × (1 - i/7)` | 290 → 0，外圈先铺、内圈后叠 |
| 每层 alpha | `0.6 / 8 = 7.5%` | srcOver 叠 8 次，最内圈约 46% |
| `REVEAL_OFF_X/Y` | `-1639 / -682` | 脚本局部坐标 → 画板坐标 |

性能取舍（本机实测，1536×864 画板）：

- `REVEAL_EXTRA=660` + 同时两条电流时，5 层就明显卡；
- 压到 290 + 单条电流后，4 层流畅，加到 8 层仍不卡；
- 结论：成本 ≈ 蒙版面积 × 层数 × 电流条数，先压面积与条数，再加层。

## 三、坐标对齐

`PATH` 与电流多边形都画在脚本节点的局部坐标里（节点位于 `(1639,682)`），而 `reveal` 位图是整张画板尺寸（1536×864）。所以 clip 之后必须把画板坐标平移 `(-1639,-682)`，否则下层图会整体偏出光晕范围。

同类问题的通用判据：**如果蒙版里的图整体偏移，先查这个平移量**，而不是去改图片自身的 `x/y`。

## 四、与心跳同步发射

- `beatCycle = 2.4`（Timeline 144 帧 @60fps 循环），心跳缩放 / 颜色 / 辉光关键帧同周期；
- 在相位 `0.08` 处 `table.insert(self.fxPulses, 0)`，灯亮与电流出发同一帧；
- 跨周期判断用前后两次取模，避免 `beatT` 归零时漏发：

```lua
local ph: number = self.beatT % beatCycle
local prev: number = (self.beatT - dt) % beatCycle
local function hit(p: number): boolean
    if prev <= ph then return prev <= p and p < ph end
    return p >= prev or p < ph
end
if hit(0.08) then table.insert(self.fxPulses, 0) end
```

## 五、定稿参数（003 充电中）

| 类别 | 参数 | 值 |
|---|---|---|
| 行驶 | `CAR_SPEED` / `START_PCT` / `END_PCT` | 18 px/s / 0.44 / 0.80 |
| 车辆 | `CAR_SCALE` / `SHADOW_SCALE` / `ROT_OFF` | 0.35 / 0.7 / 90 |
| 路径 | `CAR_SMOOTH` | 4（前后各 4 点均值 + 几何切线） |
| 电流 | `fxSpeed` / `fxPulse` / `fxHeadW` / `fxTailW` / `fxRear` | 1520 / 550 / 8 / 2 / 40.08 |
| 蒙版 | `REVEAL_EXTRA` / 层数 / 每层 alpha | 290 / 8 / 7.5% |
| 心跳 | `beatCycle` / 发射相位 | 2.4 s / 0.08 |

## 六、配套预览页

同一套参数另做了单文件 HTML（Canvas 2D）用于快速试参：

- 13 项参数实时联动（车速、起终点、车身比例、电流速度/长度/粗细、发射间隔、心跳幅度、外扩、遮罩强度、路径亮度、平滑）；
- 羽化用 `globalCompositeOperation='destination-in'` + `ctx.filter='blur(14px)'`，在半分辨率离屏画布（1280×720）上做；
- 背景压缩成 1536×864 JPEG(q86) 后 base64 内嵌，`file://` 双击即可打开（单文件约 415 KB）。

预览页只用于调参，不参与交付；交付仍以 `.riv` 为准。

## 七、坑位

| 现象 | 原因 | 处理 |
|---|---|---|
| 电流末段"停住" | 纯缓出曲线末尾斜率趋 0 | 混 25% 线性：`0.25*p + 0.75*eased` |
| 起步并没有更快 | 只改了 `fxSpeed` | 改的是总时长；快慢节奏必须走缓动曲线 |
| 蒙版边缘仍是硬切 | 只有一层 clip | 加层：`extra` 递减 + 每层 alpha 递减 |
| 下层图整体偏移 | 脚本局部坐标 vs 画板坐标 | `transform(-1639,-682)` 后再 `drawImage` |
| 层数一加就卡 | 蒙版面积大 / 同时多条电流 | 先压 `REVEAL_EXTRA` 与电流条数，再加层 |
| 循环后电流凭空出现在中途 | 进度数组没清 | 重置 `dist` 时同时 `fxPulses = {}` |

## 八、验收

1. `script_diagnostics` 为空数组；
2. 编辑器播放：全程只有一条电流、长度恒定、起步快末段慢、光晕边缘无硬切；
3. 与预览页对照：同一组参数下节奏一致（预览页 `dist` / `travel` / `pulseHead` 与脚本同构）。

## 来源

- 本机实测：2026-11-09，Rive 桌面版 1.9.x，本地 MCP（文件「测试文档」画板「003 充电中」）。
- 缓动曲线参考：[MDN — cubic-bezier()](https://developer.mozilla.org/zh-CN/docs/Web/CSS/easing-function/cubic-bezier)。
