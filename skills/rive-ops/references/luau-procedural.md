# 程序化动画（Luau 脚本）

用 Node / Path Effect 脚本替代关键帧的完整经验。全部结论来自 2026-11 实车机充电呼吸灯项目的实测，环境：Rive 桌面版 Early Access 1.9.x + CLI 1.8.0。

## 一、协议速查

| 协议 | 用途 | 生命周期 | 挂载位置 |
|---|---|---|---|
| `Node` | 自绘几何 / 渲染素材 | `init(self, context)` → `advance(self, seconds)->bool` → `update` → `draw(self, renderer)` | 画板右键菜单选脚本 |
| `Layout` | 布局算法 | 同上 + `measure()`、`resize(self, size, scale)` | 必须是 Layout 组件的子级 |
| `PathEffect` | 改写真实路径几何 | `update(self, inPath: PathData) -> PathData` + 可选 `advance` | 挂在 **Stroke** 的 Effects 上 |
| `ListenerAction` / `TransitionCondition` / `Converter` / `Util` / `Test` | 状态机 / 数据 / 测试 | 各异 | 各自面板 |

工厂模式：脚本必须 `return function(): Node<T> return {...} end`；**在 `init()` 里创建的对象用 `late()` 占位**（`path = late()`），默认值直接写数字。

## 二、绘制三条铁律（实测，违反即"全黑但 0 error"）

1. **Path / Paint 只在 `init` 里创建**，`draw` 里只读不改。官方："Create paths and paints in `init`, then use them in `draw`"。工厂里 `Path.new()` 虽然能跑，但对象会被所有实例共享。
2. **`drawPath` 之后，本帧不得再碰这条 Path**——`reset()`、`moveTo`、`lineTo` 都算。官方："if you mutate it after drawing, you must wait until the next frame"。正确结构：

```lua
function draw(self, renderer)
    self.path:reset()          -- reset 只在绘制前
    for _, p in ipairs(self.particles) do
        self.path:moveTo(...)   -- 累积所有几何
        self.path:cubicTo(...)
        self.path:close()
    end
    renderer:drawPath(self.path, self.paint)   -- 最后一次性画
end
```

3. **多个绘制档必须各自一套 Path**。实测：两档共用同一批 Path，后一档的 `reset()` 会擦掉前一档**已提交**的几何——症状是画面全空，而编译 0 error。

性能副产品：40 颗粒子逐颗画是 120 次 `drawPath`/帧；按"累积成一条路径再画"降为 2~4 次。

## 三、颜色 alpha 是 0–255（最大单坑）

```lua
Color.rgba(190, 255, 220, 230)   -- ✅ alpha 满量程 255
Color.rgba(190, 255, 220, 0.90)  -- ❌ 被当作 0.9/255 ≈ 0.35%，完全透明
```

- `Color.rgb(r, g, b)` 三参数版默认不透明——**三参能显示、四参看不见**，就是这个原因，极易误判成"渐变/脚本不生效"。
- `Paint` 没有 `fillRule` 属性，写入被静默忽略。**脚本路径按顺时针填充**（y 向下），逆时针轮廓 fill 直接不可见。
- `Paint` 有 `feather`（羽化），`setLineDash` 没有——dash 要用 Path Effect 自己实现。

## 四、画布/渐变/羽化的坑

| 项 | 结论 |
|---|---|
| 径向渐变 `startX/Y → endX/Y` | MCP 写入行为不稳（写 50 被当成"50 倍尺寸外"）。要平滑衰减，用 **N 层同心薄圆叠加 + plus/additive**：层间半径差 <2px、每层 alpha ≤3/255，肉眼即连续 |
| `setPaints` 改已有渐变 | 会把 `paint` 写成 `null`（形状彻底不渲染）；新建用 `addPaints`，改停靠点用 `addGradientStops`，都不稳 |
| 预渲染 PNG 辉光 | 最稳，但 `upload_asset` 走 CDN，**系统代理会掐 TLS**（`HandshakeException`），需关代理 |

## 五、生命周期与时钟（实测，forge.mograph 交叉验证）

| | 播放（Play / runtime） | Design 模式 |
|---|---|---|
| `advance` | 每帧 ~60/s | 事件触发时补跑，`seconds` **恒为 0** |
| `draw` | 每帧 | 每次重绘（平移/缩放画布也会触发） |

- **`capture_artboard` 不执行脚本**——静态截图里脚本内容永远不出现。验证脚本只能：①编辑器里播 + 看 Console；②CLI `--screenshot`。
- `draw` 可能在第一次 `advance` 之前就被调用，不要依赖 advance 先跑。
- `advance` 返回 `false` = 退订逐帧时钟（ draw 仍会调）。
- Design 模式下 `seconds` 恒 0：**任何 `d = f(seconds)` 的数学都要防 0**，用累计时间 `self.t += seconds` 驱动。

## 六、协议识别与排查

| 现象 | 原因 | 办法 |
|---|---|---|
| `get_scripts` 里 `type: utility` | 脚本加载失败（协议没识别成 node） | 不会出现在画板右键菜单。常见根因：作用域错误（`local` 变量出了 `if` 块还引用）、字段没在工厂里齐、`late()` 缺失 |
| `script_diagnostics` 返回 `[]` | **不可信**。编译失败的脚本它也返回空 | 用 CLI `rive <dir> --verify`，能给出**带行号**的类型错误 |
| 脚本有错 | 不出现在任何"添加到场景"菜单里 | 先修错再找菜单 |
| `local X: { number } = {...}` 模块级带类型数组 | **Luau 编译器段错误**（CLI exit 139、零输出） | 改成局部 if/else 内联字面量 |

排查顺序：CLI `--verify`（拿行号）→ `get_scripts` 看类型 → Console `print`。

## 七、脚本的安装（MCP 边界）

| 操作 | MCP | 说明 |
|---|---|---|
| 建/删/改名脚本文件 | ✅ `manage_scripts` | 只管文件，不管内容（内容用 `text_editor`） |
| **新建脚本节点** | ❌ 无接口 | 只能画板右键菜单选脚本（菜单只在脚本 `type: node` 时出现） |
| **改已有节点的 `scriptAssetId`（键 848）** | ⚠️ 能写但**不重绑** | 运行时实例在节点创建/复制那一刻就按原脚本绑定，事后改字段 init 能跑、draw 不来 |
| 复制别的脚本节点再改指向 | ❌ 同上 | 实测两次失败 |
| **删除 ScriptAsset** | ⚠️ **连带删除引用它的节点** | 替换脚本内容务必走 `text_editor` 改源码，不要删了重建 |
| 给 Stroke 挂 Path Effect | ❌ Stroke 属性键里无 script/effects 槽 | 只能编辑器：选中 Shape → 右面板 Stroke 区 → Options → Effects → `+` → Script Effects |
| 层级面板 | 不显示 Fill/Stroke 子行 | Shape 展开只 reveal **Path**；样式在右面板的 Fill/Stroke 区 |

## 八、Path Effect：给素材真实轮廓做 dash

官方协议：`update(self, inPath: PathData) -> PathData`，运行时把**素材真实路径**交给脚本——这是脚本拿到素材几何的唯一途径（Node 脚本拿不到）。

复刻 canvas 描边流动的要点：

```lua
-- 参考 HTML：setLineDash([52,188]) + lineDashOffset = -strokeOff
-- 关键：240 是 dash 周期，不是路径总长；每条子路径独立应用同一全局相位
local PERIOD, DASH, SPEED = 240, 52, 100
local off = self.off % PERIOD
-- 亮段：d - off ∈ [k*240, k*240+52]（负号 → 沿路径正方向前进）
```

- 输出用 `Path`：`m = inPath:measure()` 拿 `m.length`；`m:positionAndTangent(d)` 返回 `(position, tangent)`。
- **转角平滑**：不要 `lineTo` 折线，用切线做 Hermite 控制点：`cubicTo(p0 + t0*h, p1 - t1*h, p1)`，`h = ds/3`，采样密度 ~1px 一段。
- **`advance` 里必须 `context:markNeedsUpdate()`**，否则内部状态变了运行时不重算，效果看起来"冻结"。
- dash 前进方向由 `±off` 决定；方向反了改一个符号。
- 无内置 `setLineDash`：**新版编辑器有原生 Dash 效果**（Effects 面板，可与 Trim 叠加），Offset 用关键帧驱动就是非程序化方案；要程序化只能走本协议。

## 九、"用素材的效果"怎么代码化

脚本**不能修改场景里已有节点的 transform**（没有 API）。素材代码化的唯一模式：

1. 素材转成 **Component Artboard**（编辑器右键 Convert to Component）；
2. 脚本加 `icon: Input<Artboard>` 输入（工厂里 `icon = late()`）；
3. `advance` 里 `self.icon:advance(seconds)`；`draw` 里：

```lua
renderer:save()
renderer:transform(Mat2D.withTranslation(0, dy) * Mat2D.withRotation(rot) * Mat2D.withScale(sc, sc))
self.icon:draw(renderer)
renderer:restore()
```

呼吸/浮动/倾斜就全变成公式。Web 端脚本需 `--publish` 签名；**车机 C++ 原生支持**。

## 十、定稿参数（车机充电呼吸灯 · 程序化版）

| 效果 | 参数 | 备注 |
|---|---|---|
| 粒子 | `count=110`、场 `θ∈[-0.50,1.62]`、`rInner=IR+16`、`R≈116`、`pow(rand,0.82/0.78)` | 点半径 `p.r*(0.7+0.55near)*0.55`，颜色 `rgba(170,255,195,200)` |
| 粒子速度 | `pace*(26+(120+280*grad)*q^1.7)`，`pace=(0.55+0.45r)*(0.55+0.45clamp(0.4+dy/240))` | 弧线 `+n*sin(πq)*bow`，`bow∈±6` |
| 脉冲辉光 | **恒定亮度只变半径**：`base=IR*1.15*(1+0.26*pulse)`，`pulse=sin³(2πt/0.75)` | 24 层薄叠加，每层 alpha 2（中心累积 ≈0.17） |
| 光圈 | 周期 1.4s、寿命 0.656s，半径 `IR*0.95→IR*3.1`，alpha 4 档 110→18 | 加法混合 |
| 描边 | `dash=52/240`、`SPEED=100`、`rgba(190,255,220,230)`、宽 1.3、周期 2.4s | Path Effect，Hermite 平滑 |
