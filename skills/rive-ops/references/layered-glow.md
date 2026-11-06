# 多图层叠辉光

在脚本里做"平滑径向辉光"的可行方法与不可行方法。结论：**MCP 写渐变不可靠，脚本里也无法依赖渐变，用 N 层同心薄圆叠加**。

## 一、为什么不能用渐变

| 尝试 | 结果 |
|---|---|
| `setPaints` 写带 alpha 停靠点的径向渐变 | `paint` 变 `null`，形状彻底不渲染 |
| `addGradientStops` 补多停靠点 | 同样 `paint: null` / 几乎不可见 |
| 末端 stop alpha = 00 | **整个渐变判为"无颜色"，直接不渲染**（改 02 才有输出） |
| `startX=50`（想用百分比） | 被当成 50 **倍**尺寸 → 渐变中心飞出画布，只剩边角余光 |
| 预渲染 PNG + `upload_asset` | 最稳，但走 CDN，**系统代理掐 TLS**（`HandshakeException`），需关代理 |

对照组：`Color.rgb` 三参不透明渐变能渲染——又是 alpha 量纲陷阱的变体（见《脚本颜色与透明度量纲》）。

## 二、多层薄叠加公式

核心：**加法混合下，N 层同心薄圆的累积不透明度 = 1 − (1 − a)^N**，层与层半径差足够小时视觉上就是连续渐变。

| 每层 a（0–255） | 层数 N | 中心累积 | 用途 |
|---|---|---|---|
| 12 | 32 | ≈ 0.78 | 主辉光 |
| 3 | 24 | ≈ 0.25 | 淡脉冲 |
| 2 | 24 | ≈ 0.17 | 很淡 |
| 1 | 24 | ≈ 0.09 | 下限 |

**平滑条件**：相邻层半径差 `< 2px`（在 2560 画板上），每层 alpha `≤ 3/255`。层数不够（如 7 层、每层 22%）会出现肉眼可见的同心环带。

## 三、代码模板（无关键帧，恒定亮度只变半径）

```lua
local IR = 29
local function addCircle(path, cx, cy, rad)   -- 顺时针四点 cubic
    path:moveTo(Vector.xy(cx + rad, cy))
    path:cubicTo(Vector.xy(cx + rad, cy + rad*0.5519), Vector.xy(cx + rad*0.5519, cy + rad), Vector.xy(cx, cy + rad))
    path:cubicTo(Vector.xy(cx - rad*0.5519, cy + rad), Vector.xy(cx - rad, cy + rad*0.5519), Vector.xy(cx - rad, cy))
    path:cubicTo(Vector.xy(cx - rad, cy - rad*0.5519), Vector.xy(cx - rad*0.5519, cy - rad), Vector.xy(cx, cy - rad))
    path:cubicTo(Vector.xy(cx + rad*0.5519, cy - rad), Vector.xy(cx + rad, cy - rad*0.5519), Vector.xy(cx + rad, cy))
    path:close()
end

-- 24 层，恒定 alpha，半径进公式（"只变大小不变透明度"）
function drawGlow(self, renderer, base)
    for i = 1, 24 do
        local f = 1.34 - 0.84 * (i / 24)      -- 1.34 → 0.50 连续过渡
        self.glowPath:reset()                 -- reset 只在绘制前（Path 铁律）
        addCircle(self.glowPath, 0, 0, base * f)
        renderer:drawPath(self.glowPath, self.glowPaint)   -- alpha 固定
    end
end
```

- 每帧 24 次 `drawPath` 完全没有性能问题（比 32 个关键帧圆盘对象便宜得多）。
- **"脉冲"就是 `base` 进公式**：`base = IR*1.15 * (1 + 0.26*pulse)`，`pulse = sin³(2πt/0.75)`——亮度恒定，只有半径呼吸（用户明确要求过：脉冲只变大小不变透明度）。
- 若要亮度也变：准备 2~4 支固定 alpha 的 Paint 按档位切换（**draw 里改 `paint.color` 同样违反 Path 铁律的姊妹规则，Paint 也要 init 预建多支**）。

## 四、关键帧版对照（在 MCP 里做同样的事）

| 步骤 | 操作 |
|---|---|
| 建 N 个椭圆 | `createParametricShapes`（一次批量），`parentId` 挂辉光组 |
| 上色 | `setPaints`（solid 纯色可靠；渐变不可靠） |
| 混合 | `{23: 12}`（plus），逐个设置 |
| 归位 | **`group_editor` 传了 parentId+x/y 仍可能落在世界 (0,0)**，局部坐标变 `(-2227,-1170)`，必须回读写回 `0,0` |
| 动画 | 对**组**打 scale + opacity 键（子元素不动） |

## 五、验证清单

1. 纯色探针（不透明方块）确认节点会渲染（见《脚本颜色与透明度量纲》）；
2. 峰值帧与静止帧抓 diff：**图标像素必须逐字节不变**（辉光在图标之后绘制且不透明度受控）；
3. 沿半径采样 alpha 剖面：单调递减、无回跳、相邻步差 ≤ 3/255 即无可见台阶。
