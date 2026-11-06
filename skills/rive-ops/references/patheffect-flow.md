# PathEffect 描边流动

用 Path Effect 脚本在**素材真实轮廓**上复刻 canvas 的 `setLineDash` 流动描边。这是脚本拿到素材路径几何的**唯一途径**（Node 脚本拿不到）。

## 一、参考语义（HTML 原文）

```js
const iconClip = new Path2D(P1); iconClip.addPath(new Path2D(P2));  // 圆环+闪电，两条子路径
const STROKE_LEN = 240, STROKE_DASH = 52;                            // 240 是 dash 周期！
strokeOff = (strokeOff + dt * strokeSpeed) % STROKE_LEN;             // 100px/s
ctx.setLineDash([52, 240 - 52]);
ctx.lineDashOffset = -strokeOff;                                     // 负号 → 沿路径正方向
ctx.stroke(iconClip);                                                // 描真实合并轮廓
```

三个关键语义：

1. **`240` 是 dash 周期**（52 实段 + 188 空段），**不是路径总长**——按路径长度缩放 dash 是错的；
2. **每条子路径从自己的起点应用同一全局相位**——两条路径长度不同，但相位同步；
3. **`-strokeOff` 的负号**决定方向：`+off` 会让图案沿路径倒退。

## 二、完整实现

```lua
local PERIOD, DASH, SPEED = 240, 52, 100

type StrokeFx = { context: Context?, off: number }

local function init(self: StrokeFx, context: Context): boolean
    self.context = context
    self.off = 0
    return true
end

-- Hermite 平滑：切线做控制点，转角 C1 连续（折线在闪电急弯处会有棱角）
local function emitSeg(out: Path, m: PathMeasure, L: number, s: number, e: number)
    local lo, hi = math.max(0, s), math.min(L, e)
    if hi - lo < 0.5 then return end
    local steps = math.max(8, math.ceil(hi - lo))   -- ~1px 采样一段
    local ds = (hi - lo) / steps
    local p0, t0 = m:positionAndTangent(lo)
    out:moveTo(p0)
    for i = 1, steps do
        local d1 = math.min(L, lo + ds * i)
        local p1, t1 = m:positionAndTangent(d1)
        local h = ds / 3
        out:cubicTo(Vector.xy(p0.x + t0.x*h, p0.y + t0.y*h),
                    Vector.xy(p1.x - t1.x*h, p1.y - t1.y*h), p1)
        p0, t0 = p1, t1
    end
end

local function update(self: StrokeFx, inPath: PathData): PathData
    local out = Path.new()
    local m = inPath:measure()
    local L = m.length
    if L <= 0.0001 then return out end
    local off = self.off % PERIOD
    -- 亮段：d - off ∈ [k*240, k*240+52]，扫描所有 k 覆盖 [0, L]
    local kmin = math.floor((-off - DASH) / PERIOD) - 1
    local kmax = math.ceil((L - off) / PERIOD) + 1
    local k = kmin
    while k <= kmax do
        emitSeg(out, m, L, k * PERIOD + off, k * PERIOD + off + DASH)
        k = k + 1
    end
    return out
end

local function advance(self: StrokeFx, seconds: number): boolean
    self.off = self.off + seconds * SPEED
    if self.context then self.context:markNeedsUpdate() end   -- 必须！
    return true
end

return function(): PathEffect<StrokeFx>
    return { context = late(), off = 0, init = init, update = update, advance = advance }
end
```

## 三、四个必踩的坑

| 坑 | 症状 | 修正 |
|---|---|---|
| **方向反了** | 弧段沿路径倒着跑 | 亮段用 `d - off`（负 offset 语义），不是 `d + off` |
| **折线棱角** | 闪电急弯处生硬 | `lineTo` 换 Hermite `cubicTo`（切线控制点） |
| **效果冻结** | 挂上后静止不动 | `advance` 里漏了 `context:markNeedsUpdate()` |
| **按长度缩放 dash** | 亮段长度随路径变化 | `240` 是周期，dash 固定 52px，与路径长度无关 |

## 四、安装（MCP 边界）

| 操作 | 可行性 |
|---|---|
| 建脚本文件 | ✅ `manage_scripts`（会返回 `type: pathEffect`） |
| **挂到 Stroke 上** | ❌ Stroke 属性键只有 `thickness/cap/join/position/blend`，无 effects/script 槽 |
| 复制已有带效果的 Stroke | ❌ 文件里若从没有过 `ScriptedPathEffect` 对象则无源可复制 |

编辑器 UI（2026 版，Effects 已从描边选项迁到独立面板）：

> 层级选 **Shape**（不是 Group！Group 的 Style 显示 Group，无 Fill/Stroke 区）→ 右面板 **Stroke** 区 → Options(⋯) → **Effects** → `+` → **Script Effects** → 选脚本。

## 五、与原生 Dash 的取舍

| | 原生 Dash 效果 | Path Effect 脚本 |
|---|---|---|
| 描真实轮廓 | ✅ | ✅ |
| 驱动方式 | Offset 关键帧（非程序化） | 代码（程序化） |
| 参数化 | 属性面板 | 代码常量 |
| 稳定性 | 原生，最稳 | 依赖脚本运行时 |

官方文档确认新版编辑器里 **Trim Path / Dash / Feather 都在 Effects 面板**且可叠加。非程序化需求优先原生 Dash；要"速度/长度由代码算"才用 Path Effect。
