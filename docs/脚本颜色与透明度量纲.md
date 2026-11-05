# 脚本颜色与透明度量纲

Rive 脚本里"明明画了却看不见"的头号原因。本文全部结论来自实测（2026-11，Early Access 1.9.x）。

## 一、核心规则

```lua
Color.rgb(r, g, b)               -- 三参：默认完全不透明
Color.rgba(r, g, b, a)           -- 四参：a ∈ 0..255，不是 0..1！
Color.rgba(190, 255, 220, 230)   -- ✅ 90% 不透明
Color.rgba(190, 255, 220, 0.90)  -- ❌ 0.90/255 ≈ 0.35%，肉眼全透明
```

- **`a` 是 0–255 整数语义**（官方 Script Inputs 类型表示例：`Color.rgba(255,0,0,255)`）。
- **`Color.rgb` 三参版默认不透明**——这就是"三参能显示、四参看不见"这个诡异现象的根源，会把人引向"渐变坏了/脚本没跑/节点没挂"等完全错误的方向。

## 二、典型误判链（实际发生过的排查路径）

| 步骤 | 现象 | 错误结论 |
|---|---|---|
| 1 | 脚本 `draw` 在跑（有 print） | 排除"脚本没执行" ✓ |
| 2 | 节点 `type: node`、坐标正确 | 排除"节点没绑" ✓ |
| 3 | 换更大尺寸，还是淡 | 误判成"尺寸太小" → 白白放大 2.6 倍 |
| 4 | 换预渲染色块，能看见 | 才发现 alpha 量纲错了 |

**教训：改任何视觉参数前，先做一个"alpha=255 的纯色探针"**（一个 200×200 不透明方块），一步分清"没渲染"还是"渲染了但太淡"。

## 三、探针模板（保留复用）

```lua
type Probe = { path: Path, paint: Paint }
function init(self: Probe): boolean
    self.path = Path.new()
    self.paint = Paint.with({ color = Color.rgba(255, 60, 60, 255), style = 'fill' })
    -- 200x200 不透明红方块，顺时针（y 向下）
    self.path:moveTo(Vector.xy(-100, -100))
    self.path:lineTo(Vector.xy(100, -100))
    self.path:lineTo(Vector.xy(100, 100))
    self.path:lineTo(Vector.xy(-100, 100))
    self.path:close()
    return true
end
function draw(self: Probe, renderer: Renderer)
    renderer:drawPath(self.path, self.paint)
end
return function(): Node<Probe> return { path = late(), paint = late(), init = init, draw = draw } end
```

验证通过的量化口径：Console 里 `[PROBE] draw` 持续增长 + 画布上肉眼可见。两者缺一不可——**只有 print 增长没有像素 = 透明度量纲或 winding 问题**。

## 四、多层叠加的透明度配比

脚本里做"平滑辉光"靠 N 层同心薄圆叠加（见《多图层叠辉光》），总不透明度按**独立叠加**算：

```
center = 1 - (1 - a)^N
```

| 每层 alpha | 层数 N | 中心累积 | 观感 |
|---|---|---|---|
| 7/255 | 24 | ≈ 0.49 | 明显光晕 |
| 3/255 | 24 | ≈ 0.25 | 淡光晕 |
| 2/255 | 24 | ≈ 0.17 | 很淡 |
| 1/255 | 24 | ≈ 0.09 | 下限，再低被 8bit 量化吞掉 |

调透明度时**先算累积值**再改，避免"改了没反应"（低于 1/255 就是物理不可见）。

## 五、相关坑位速记

| 坑 | 现象 |
|---|---|
| `setPaints` 写带 alpha 渐变 | `paint` 变 `null`，形状不渲染 |
| 顺时针规则 | 脚本路径逆时针（y 向下）fill 不可见，与 alpha 无关但症状相同 |
| `additive` 混合 | 深底上叠加正确；但 alpha=0 时任何混合都不可见 |
| CLI 渲染正常、编辑器看不见 | 检查是否用了 `Color.rgb`（三参）与 `Color.rgba`（四参）**混用**导致亮度不一致 |
| `Paint.with({ color = 0xFFFFF3D4 })` | **不报错、整批不可见**：`color` 只认 `Color.rgb/rgba` 构造，十六进制整数被静默当无效值（本轮实测：截图全黑、`success: true`） |
