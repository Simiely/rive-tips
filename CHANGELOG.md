# CHANGELOG

## v1.9.0 — 2026-11-09

新增「电流缓动与羽化蒙版」：把 003 定稿的两处手感改动写成可复用规则——节奏用「进度 + 缓动」而不是调 `fxSpeed`；羽化用多层硬边 `clipPath` 模拟，并给出层数与性能的取舍边界。

### 新增

- `docs/效果-电流缓动与羽化蒙版.md`：进度模型（存 `prog`、`travel = (rear + fxPulse) / fxSpeed`）、`cubic-bezier(0.25,0.10,0.25,1.00)` + 25% 线性保底、8 层外扩蒙版（`extra` 290→0、每层 7.5%、srcOver 最内圈约 46%）、画板坐标平移 `(-1639,-682)`、心跳 2.4s 同相位发射、定稿参数表与 6 条坑位。
- `docs/效果索引.md` 增「电流缓动与羽化蒙版」入口。

### 更新

- `docs/效果-路径电流与脚本复用.md`：§二 补 2026-11-09 定稿说明（长度改常值、推进改缓动），并链到新文档。
- `docs/速查表.md`：坑位表 78 → **82 行**（缓动节奏 / 硬边 clip / 蒙版偏移 / 层数性能）。
- `AGENTS.md`：文档基线升 v1.9.0，结论先行 56 → **58 条**（缓动、羽化各一条），FAQ 路由补一条；第 52 条标注已被 57 取代。
- `skills/rive-ops/SKILL.md`：references 33 → **34 篇**，坑位 78 → **82 行**，任务路由与参考清单各补一条。
- `tools/sync-skill.ps1`：映射新增 `docs/效果-电流缓动与羽化蒙版.md -> references/effect-feather-easing.md`。

### 实测数据

- 羽化：`REVEAL_EXTRA=290` + 单条电流时 8 层在 1536×864 画板流畅；此前 `REVEAL_EXTRA=660` + 两条电流时 5 层即明显卡顿 → 成本 ≈ 蒙版面积 × 层数 × 电流条数。
- 缓动混合后等效速度：10% 进度 ≈1.1×、中段峰值 ≈1.5–1.6×、末段 ≈0.4× 平均速度。
- 心跳 2.4s（Timeline 144 帧 @60fps），发射相位 0.08；`script_diagnostics` 返回 `[]`。
- 参数：车速 18 px/s、区间 44%→80%、电流 550px / 头 8 / 尾 2 / `fxRear` 40.08。

## v1.8.0 — 2026-11-06

新增「桌面端编译卡死排查」，并把「全部开关」主开关与 listener 改造边界写进按钮文档。本轮把"查日志"这条无效路径明确关掉：Rive 桌面端不写运行日志，只能量进程。

### 新增

- `docs/桌面端编译卡死排查.md`：三层对照（同文件 / 别的文件 / 空白文件）、`LocalCache` 实际内容、Sentry `breadcrumbs` 0 字节、CPU 增量 + IO 速率判据（CPU 涨 + IO≈0 = 本地在算）、网络/证书排除、5 项无效操作实测、最终恢复与**归因边界**（版本与安装方式两变量同时改变）。
- `docs/按钮开关与按压动效.md` 新增 **§十「全部开关」主开关**：三按钮布局、`next = not (sandOn and dustOn)` 语义、`delete_objects` 删 listener → `create_listeners` 重建 `scripted` action、画板 `583`/`584` 绑定回读、`BTN_`/`TXT_` 防重复副本。

### 更新

- `docs/速查表.md`：坑位表 72 → **78 行**（桌面端 Compiling 分层 / 无运行日志 / editorProperties 与 fileSafeMode 无效 / 改 listener 无 update / 搜中文名搜不到节点 / 全部开关语义）。
- `AGENTS.md`：文档基线升到 v1.8.0，结论先行 52 → **56 条**，FAQ 路由补桌面端编译卡死行，references 14 → **33 篇**。
- `skills/rive-ops/SKILL.md`：铁律 52 → **56 条**，任务路由与参考清单各补一条，`完整 72 行` 改为 78。
- `README.md`：主题 12 → **13**，技能参考 12 → **33 篇**，快速开始补一条。
- `tools/sync-skill.ps1`：映射新增 `docs/桌面端编译卡死排查.md -> references/desktop-compile.md`；并把 18 个历史未映射文档一并补进映射（references 15 → **33**），`-Check` 全绿。

### 实测数据

- 卡住时：CPU 5 秒内涨 2.64s（≈53% 单核，另有线程 46% / 15%），IO **0 KB/s**，GPU 3D 引擎 **2.1%**；进程 600–750 MB。
- 浏览器同文件 **0.6s**；桌面端打开其他文件同样卡。
- 网络：TCP 443 98–211ms、HTTPS 首页 0.67–0.72s；代理日志显示 `*.rive.app` 全 DIRECT。
- 清 `editorProperties`：`shared_preferences.json` 4 864 → 463 → 4 868 字节（打开即重建）。
- 恢复：卸载 + 删包数据 + 安装最新测试版；版本与安装方式同时改变，**未做单项归因**。

### 未验证（不收录进正文，仅在此备注）

- 双显卡 / 虚拟显示适配器线索（Intel UHD 770 + RTX 4070 SUPER + OrayIdd / RayLink / Zako）：未做强制高性能 GPU、禁用虚拟显示器的 A/B，不能算已证实原因。
- 测试版与正式版差异：未单独验证。

## v1.7.0 — 2026-11-05

新增「路径电流（追尾流光）」：一条辉光电流从路径右下的充电图标出发，追着车尾跑，长度随车位置自适应；并把「同文件两个画板各用一套脚本/参数」的 MCP 边界一次写清。

### 新增

- `docs/效果-路径电流与脚本复用.md`：三层画法（底轨 / 加宽羽化泛光 / 本体）、顺时针绕序、逐 2px 采样与 `(-sin,cos)` 法线、尾 5 → 头 17.5 渐变、头尾半圆帽、`maxDraw = dist - 57.25` 追尾、`lenScale = clamp(prog/0.5)` 自适应长度、双画板双脚本、ScriptInputs 面板规则、实测数据。
- `docs/效果索引.md` 增「沿路径电流（追车尾）」入口。
- `docs/速查表.md` 补 5 行（光带不可见 / 双画板互相影响 / 新脚本节点落点 / 跨画板复用与 848 不重绑 / ScriptInputs 中文化与键值），坑位表 67 → **72 行**。
- `skills/rive-ops/SKILL.md` 铁律 48 → **52 条**，任务路由与参考清单各增一条。
- `tools/sync-skill.ps1` 映射新增 `docs/效果-路径电流与脚本复用.md -> references/aurora-path-fx.md`。
- `AGENTS.md` 文档基线升到 v1.7.0：结论先行 47 → **52 条**，references **14 篇**。

### 实测数据

- 本地基准 2560×1440、`rive . --bench=600`：空场景 render 0.965ms，底轨+本体 1.181ms，加羽化泛光 1.258ms = **净增 0.293ms/帧**（p95 +0.435ms）。
- 路径 24 顶点、总长 2701.79px；车图 95×229 @50%，车尾后退 57.25px；脉冲 675 / 间隔 750（003 定稿间隔 200）、头宽 17.5 / 尾宽 5、速度 500px/s。

## v1.6.2 — 2026-11-05

修正路径顶点角度单位：MCP `query_property_values` 返回的 `inrotation/outrotation`（键 84/86）是**度**，不是弧度。

### 修正

- `docs/路径几何与坐标系映射.md`、`docs/车沿路径走（drawImage驱动）.md`：控制柄角度改为「度」；Lua 使用前先 `math.rad`。判据：24 顶点按度展平得 **2701.79px**，与 `TOTAL=2700.9` 吻合；按弧度得 **3140px**，明显偏离。
- 调研「极光充电流」时在本地 2560×1440 基准验证了 Node Script 三层绘制（底轨 + 本体 + feather 泛光）：完整效果相对空场景 **+0.293ms/帧**；同时发现 `PathMeasure:positionAndTangent(0)` 返回的切线未归一化（模长 237.48），必须手动归一化。

## v1.6.1 — 2026-11-05

修复「003 充电中」控制按钮只能关、不能开，并补齐中文标签。

### 修复

- 左右两个开关按钮原来挂 `viewModelChange` 常量 false，第二次点击仍写 false → 换成 `scripted` Listener Action（`prop.value = not prop.value`）；旧监听器用 `delete_objects` 删除后重建。`queryStateMachine` 复核：`sandToggle` / `dustToggle` → `scripted`，`scriptAssetId` 正确；`script_diagnostics` 均为 `[]`。
- 「全部显示」保留 `viewModelChange` 常量 true（`BindablePropertyBoolean` 键 634 回读 `true`）。
- 三个按钮下移到 y=240，补「沙粒 / 灰尘 / 全部显示」标签。
- 按钮改为 **64×64 圆形**（矩形宽=高=直径，四角半径 32，监听目标 ID 不变）；文字移到圆形下方（节点 y=304，墨迹与圆底间隙约 17px）。用截图 + PIL 量白字/圆形 bbox 校正 x，最终三个标签中心与圆心误差 ≤1.7px。

### 新增

- `docs/按钮开关与按压动效.md` 新增 §九：只关不开的根因与修法、MCP 无文本对象时用 SVG 轮廓做中文标签（42×20 / 70×17；外层 `Node` 不暴露包围盒，落点用 `capture_artboard` 验收）。
- `docs/速查表.md` 补 2 行，坑位表 65 → **67 行**；`skills/rive-ops/SKILL.md` 铁律 46 → **48 条**；`AGENTS.md` 结论 45 → **47 条**。

## v1.6.0 — 2026-11-05

新增「车尾沙尘」效果：车沿路径移动，尾流持续喷出**沙粒**（4 色小点）与**灰尘**（无贴图柔边大圆）。官方没有粒子系统与 compute，这层完全由 Node Script + `drawPath` 组合出来，并给出可复现的性能基准。

### 新增

- `docs/效果-沙尘尾流.md`：为什么必须写在车辆脚本里（位姿只有 `car_probe` 的 `PATH`+`sampleAt` 算得出）、实现骨架、定稿参数（沙 400/s·1.2s·720 粒，尘 320/s·1.0s·480 粒，开角 1.4 / 2.0 rad）、`drawPath` 批绘共享透明度的两种解法、实测性能与 5 个坑。
- `docs/效果索引.md` 增「车尾沙尘」入口。
- `docs/速查表.md` 补 3 行（粒子不跟随移动对象 / 时间推进位置导致另一条线冻结 / 逐粒渐隐做不出来），坑位表 62 → **65 行**。
- `skills/rive-ops/SKILL.md` 铁律 43 → **46 条**（对应上述三条）。
- `tools/sync-skill.ps1` 映射新增 `docs/效果-沙尘尾流.md -> references/sand-dust-trail.md`。

### 实测数据

- `rive . --bench=600`（i7-14700 + RTX 4070 SUPER，800×600 原生 headless）：
  - 空画面 render **0.242 ms**
  - 720 沙粒 · 20 条分桶 `drawPath`：advance 0.024 / render **0.725 ms**
  - 720 沙粒 · 逐粒 720 次 `drawPath`：render **0.786 ms**（仅比批绘多 0.06 ms）
  - 1200 个大圆（r=30，模拟灰尘填充）：render **0.552 ms**
  - 完整（1920 粒 + 每粒 value noise）：advance **0.411 ms** / render **0.740 ms**，合计 ≈**1.15 ms/帧**（60fps 预算 7%）
- 结论：批绘与逐粒调用在原生渲染器上几乎等价；瓶颈是逐粒噪声与大面积 alpha 填充。

### 坑

- `Paint.with({ color = 0xFFFFF3D4 })` 数字色值不报错但整批不可见，必须 `Color.rgba(...)`
- `self.t += dt` 放在 `if not ENABLED then return end` 之后 → 关掉沙粒后灰尘的噪声场冻结
- 该画板 `capture_artboard` 连续三次返回同一张旧图（SHA256 一致），不能作为视觉验收证据，以编辑器播放为准

## v1.5.2 — 2026-11-03

把 002 / 003 / 005 三页按同一链路批量导入（四页排成 2→3→4→5）时，撞上了 v1.5.1 完全没写的一层：**Rive 的 SVG 解析与转换在服务端做**。这层一揭开，两件此前只能记成"偶发"的事就对上了——"导入卡住"其实是跨网络等转换，"转换失败"是**终局错误**而不是抖动。顺带补完 `<use>`、defs 体积、`addImageInstance` 不回 id 三处。

### 新增

- `docs/AI素材导入链路.md` 新增**第十五节「`<use>` 与服务端转换器」**：Figma 导出的图标与字形大量靠 `<use>`，服务端转换器不解析它 → 本地展开成内联 `<g transform="translate(…)">`；而展开后**可能得到空组**（它引用的字形轮廓躺在 `<font>` 里、已被上游裁掉），要能识别并跳过，而不是反复重试。
- **§十四 重写**：先讲清"转换在服务端"这一事实，再讲卡死；真因从两条补到三条（多出 `<use>`）；并明确 **同一资产转换失败后重试无意义，必须换新资产**。
- §十三 补一条省事又更准的做法：**无 `clip`/`transform` 的位图直接取原生像素**（scale 100%），不必走隔离渲染。

### 更新

- `docs/速查表.md`：坑位表 56 → **62 行**（服务端转换失败 / 转换慢与卡死同形 / `<use>` 不解析 / 展开后空组 / defs 体积异常 / 不回 `nodeId`）
- `AGENTS.md`：结论先行 39 → **45 条**
- `skills/rive-ops/SKILL.md`：铁律 38 → **43 条**；排障路由补 3 行；两处行数引用统一为 **62**
- §十四 的自救说明补上自愈时间不固定：一次约 40 分钟，另一次超过 45 分钟仍未恢复（按判据**没有删画板**）

### 实测数据

- 三页（2560×1440，各 5 张位图）离线合成 vs 源渲染：002 **0.313**、003 **0.344**、005 **0.012**
- `<use>`：005 共 **81 处**（顶部状态栏 9 / 左侧信息面板 59 / 底部导航栏 13），全部指向 `font_43_*`；展开后各组分别剩 **0 / 17 / 0** 条 `path` —— 顶部状态栏与底部导航栏本来就没有矢量，内容只在整幅烘焙底图里，最终只导入 `地图区域` + `左侧信息面板` 两层
- defs 引用闭包裁剪：005 的 4 个组从 **129.5 / 130.3 / 199.1 / 129.9 KB** 降到 **1.3 / 1.8 / 71.7 / 1.7 KB**，MAE 不变（0.012）
- 服务端转换失败原文：`SVG conversion for asset 46-16311 is unavailable, so there is nothing to import. Rive converts SVGs server-side; check the editor for details.`
- `addImageInstance` 不回 `nodeId` 本轮出现 2 次（004 的背景板、002 的首张位图），两次节点都建好了

## v1.5.1 — 2026-11-03

v1.5.0 的位图链路在 004.ai（2560×1440 车机页）上**第二次翻车**：三张位图全是空的，而所有参数读回来都对。复盘下来，所谓"位图三坑"其实是**五坑**，验收阈值也不能用绝对值，另外入口和卡死两头都缺。本次补齐这四段。

### 新增

- `docs/AI素材导入链路.md` 新增三节：
  - **第十三节「从现成分层 SVG 直接进（跳过 Illustrator）」**：手头已是分层 SVG（Figma 直接导出、或上一轮从 PDF 转出的中间产物）时，第二节整段不需要。要自己决定三件事：哪些该拍平、文字是否已是轮廓、拆几份导。附**层序模型**（见下面「修正」第 3 条）。
  - **第十四节「导入卡死：判据与自救」**：判据是**读取类调用秒回 + 渲染类全挂**（编辑器主线程被占）。两个真因：SVG 里有指向**已删除 `<mask>`** 的悬空引用；单份 SVG 太大。`undo` 解不开，只能重启桌面端。附预防用的两条 `grep`。
  - **第十五节「几个不报错的失败」**：中文 `name=` 报 `Illegal percent encoding`、新节点立即写属性被吞、烘焙 N 倍图导致尺寸翻倍、换资产后缩放要重算。
- §七 位图坑从三个补到 **六个**：坑 4「可见框 ≠ `<image>` 的 `x/y/width/height`」、坑 5「裁完必须断言非空」、坑 6「烘焙图是目标的 N 倍」。
- §一 链路总览补上"也可以是现成分层 SVG"分支。

### 修正

1. **§九 像素验收的阈值口径**。原文"阈值取 `mean < 0.5` 有足够余量"只在那批 2048×1152 启动页成立——它们的源 `.ai` 与 SVG 渲染几乎重合，0.5 的余量给的是抗锯齿。004 的**源 SVG 对参考图基线本身就是 1.40**（filter 烘焙、pattern 化、Type3 字形都会拉高），Rive 结果 **1.43** 明明是满分，按绝对值 0.5 却判 FAIL。改为「先量源基线，判据 = 不超过基线 + 0.3」，并补两行对照表。
2. **铁律 31 / 速查表 `has no drawable area`**。原文只有两种原因，且都是"删画板重建"。实测有第三种：**整机级离屏渲染故障**——判据是连以前能截的对照画板也挂、**所有**画板 `810/811` 都是 0。照旧结论会白删好画板。它会**自愈**（本轮约 40 分钟）。
3. **铁律 27 的层序措辞**。"新加对象默认垫底"容易被读成"它会跑到最底"。更准确：**新对象追加到 `children` 末尾，而 `children` 是 top→bottom**，所以"先加的反而在上面"。由此给出更省事的做法——**按"目标从上到下"顺序依次添加，层序自动正确**，不用逐个 `sendToFront`。事后调整的参数是 `operations[]`，传 `objects` 报 `operations must be an array`。
4. **铁律 30 阈值**同步改为相对基线。

### 更新

- `docs/速查表.md`：坑位表 46 → **56 行**（补 10 条：中文 `name=` / 尺寸翻倍 / 新节点写入被吞 / 可见框算错 / 裁出空图 / 导入卡死 / 卡死判据 / 全画板 no drawable area / 阈值误判 / `operations` 参数）
- `AGENTS.md`：结论先行 33 → **39 条**（第 34–39 条即上述六条）；FAQ 路由补「位图是空的 / 导入卡住不动 / 截图报 no drawable area」
- `skills/rive-ops/SKILL.md`：铁律 32 → **38 条**；任务路由的素材导入行改写为「两入口 + 按命名组拆分」；排障路由补 4 行；两处行数引用（46 / 36）统一为 56

### 实测数据

- 004 页面：2560×1440，5 个命名组、4 张位图、7829 对象（77 Shape / 1308 PointsPath / 74 Fill / 2 ClippingShape）
- 位图真实可见框：车辆 `(1623,153.5) 114.5×47.5`（`<image>` 写的是 `1751.82,53.45` + `rotate(89.815 1751.82 53.5371)` + clip）；专辑 `64×64`（`<image>` 是 189.68×237.16）；投影 `145×84`
- 像素验收：源 SVG vs PDF 基线 **1.40**；Rive vs PDF **1.43**；Rive vs 期望合成图 **0.518**
- 导入卡死两次：悬空 `mask` 引用（约 25 分钟无响应）、单份 154 KB SVG；拆成 26–62 KB 的 4 份后每份秒级
- `set_property_values` 写缩放踩两坑：批量被吞、**新节点刚建好也被吞**，都靠回读 `810/811` 才发现（读回来是 100% 而不是目标值）

## v1.5.0 — 2026-10-29

补完「AI 素材导入」的位图半条链路。原链路只覆盖矢量：`addSvgInstance` 会把 SVG 里内嵌的 `<image>` **静默丢掉**，三个启动页第一次导入时位图全灭，靠四轮返工才定位。本次把位图段的方法、坐标、阈值全部实测固化成文档 + 可执行脚本，目标是"照着跑一遍就对"。

### 新增

- `scripts/svg-prep.py` —— 导入前处理与验收五件套：`clean`（裁 `<font>` / 展开 `style=` / 补 `width/height`）、`images`（解出内嵌位图 + 它该占的矩形，直接给出**中心坐标与缩放百分比**）、`clip`（把 `clipPath` 解成 `x,y,w,h,r`）、`mask`（圆角遮罩烘进 alpha，4× 超采样）、`verify`（与 `.ai` 渲染做像素比对，带 PASS/FAIL 判据）
- `docs/AI素材导入链路.md` 新增六节：`addSvgInstance` 丢位图、位图三坑（原点/垫底/缩放）、`clipPath` 不导入与遮罩烘焙、像素验收口径、中文图层名乱码、可复用清单

### 修正

- `scripts/ai-svg-export.ps1`：新增 `-OutlineText`（**倒序** `createOutline()`）、`cssProperties=PRESENTATIONATTRIBUTES`、`preserveEditability=false`
- `scripts/ai-svg-export.ps1` **修掉一处语法错误**：`if (-not ($KeepOpen.IsPresent))` 原本被写在 ExtendScript 的 here-string 里，`-not` 不是 JavaScript —— 导出会成功，但紧接着这一行必然抛异常。改为拼装 PowerShell 字符串
- 同一脚本改为**只关闭自己 `app.open` 的文档**，且从不保存（转轮廓是单向的，不能碰别人的未保存改动）
- `scripts/svg-prep.py images` **缩放分母取错**：原来用 `<image>` 元素上 AI 写的 `width/height`（378×504），Rive 实际按**位图像素**（379×505）进场，比例因此算出 `33.3899%` 而非正确的 `33.3018%`。改为从 PNG IHDR / JPEG SOF 读真实像素，不一致时打印提醒
- `tools/sync-skill.ps1` 补上 `scripts/` 段：原来只同步 `docs/` 和运行时页面，技能里的脚本靠手抄，`ai-svg-export.ps1` 早已过期、`svg-prep.py` / `rive_mcp.py` 根本没进去。现按**字节**同步顶层脚本并纳入 `-Check`（`DRIFT` / `MISSING SCRIPT` / `SKILL-ONLY` 三类）；`scripts/rive-merge/` 是技能独有目录，跳过不动
- `tools/sync-skill.ps1` 新增 `STALE COUNT` 检查：`SKILL.md` 路由表末尾那句「完整 N 行对照表」是通往全表的入口，但它只是一句话、不是链接，死链检查抓不到——实际已从 36 漂到 46 而无人察觉。现在 `-Check` 会把它和 `docs/速查表.md` 的真实行数比对
- `tools/sync-skill.ps1` 新增 `BOM IN SKILL.md` / `BAD FRONTMATTER` 检查：PS 5.1 的 `Set-Content -Encoding UTF8` 会写 BOM，作用在 `SKILL.md` 上就把开头的 `---` 变成 `\uFEFF---`，YAML 解析器随即看不到 frontmatter——全程无报错。这个坑本轮真踩了一次（改 46 行数字时顺手写坏），所以补上防线

### 更新

- `docs/速查表.md`：坑位表 36 → **46 行**（补 10 条：位图消失 / 偏左上 / 看不见 / 尺寸不对 / 圆角丢失 / 名字变方块 / `no drawable area` / 删资产没命令 / 新建画板跑偏 / 怎么确认资产能删），资产属性键补 Image 节点六项
- **第二轮复用（QQ音乐重导）补三节实测**：`createArtboard` 自动挑空位（这次放到 x=9773，离目标列很远）→ 必须 `arrangeArtboard`；`listArtboards` 顺序按 **id 数值**排、不是创建顺序；`assets_tool` 没有 delete，资产走 `delete_objects`，删前逐画板读 `206` 证明 0 引用；**`addSvgInstance` 是一次性展开**，SVG 节点上没有资产键，资产落地即孤儿
- `AGENTS.md`：结论先行 26 → **33 条**；FAQ 加「设计稿怎么导进来」；常用命令加素材导入六条
- `README.md`：主题 8 的一句话重写、脚本表加 `svg-prep.py`、「最容易踩的坑」3 → **4 条**、快速开始加一条
- `skills/rive-ops/SKILL.md`：铁律 25 → **32 条**；任务路由的素材导入行重写；排障路由加 6 行；脚本速用补 `rive_mcp.py`
- `docs/AI素材导入链路.md` 新增**第十二节「耗时分布：优化哪一步才有意义」**：一页 531 对象全链路实测 9.6 s，逐步骤计时（导出 4,893 / `upload_asset` 1,289 / `addSvgInstance` 2,213 / `verify` 321 ms），并给出优化顺序。核心结论：**单步都不慢，瓶颈是"每次现写驱动脚本"——现成脚本 9.6 s、实跑 65 s**

### 实测数据

- 三个 2048×1152 启动页（矢量 450–515 对象/页 + 2 张位图）：像素差 **0.10 / 0.13 / 0.14**（`/255`）；同一批的错位版本 **3.16 / 2.51** —— 对错的差距 20 倍以上，阈值 `0.5` 有足够余量
- 位图：`460×127 @(796.833,483.5)`；`379×505 → 126.214×168.286`（缩放 `33.3018% / 33.324%`）
- 圆角遮罩：`clipPath` 解出 `(788,478) 124×124 r=20.571`，换成图像素是 `(3.3,66.4) 372.4×372.1 r=61.8`
- 脚本自测：`clean` 产物与手工产物**逐字节一致**（14615 B / 18 path / 19 fill）；`mask` 与手工遮罩**逐像素一致**（0.0000/255）

## v1.4.1 — 2026-10-28

索引与技能快照一致性修复。v1.4.0 的新主题在 README 与速查表里都查不到，技能快照里有 13 条死链。**不改任何实测结论**，只补入口、对齐数字、修同步链路。

### 修正

- **README 补「无清空合并文件」主题**（v1.4.0 新增的文档从未进过门面）：主题表 11 → 12 行，「快速开始」加一条路由
- **速查表补合并管线与两个坑**：「四、CLI」新增合并四步命令块、`--from-rev` 目标目录须为空或新建、`--publish` 水印条件、「七、坑位速查」新增 `0xC0000409`（非 ASCII 文件名）与 `upload_rev` 无法并入已有文件两行（34 → 36 行）
- **技能快照 13 条死链**：`tools/sync-skill.ps1` 改为复制时按映射表重写相对链接（`](中文名.md)` → `](英文名.md)`），未映射的降级为纯文本；新增 `-Check` 校验漂移、未映射文档与死链
- **README 脚本表**补 `rive_mcp.py`，表头改为「PowerShell + Python」
- **`SKILL.md` 铁律 1**：`capture_artboard` 未激活返回**空白图**（不是黑屏——纯黑/403 是另一类，见铁律 12）；排障路由把两者拆成两行
- **`DEVELOPMENT.md` 目录树**：不再逐篇枚举（v1.0.0 那棵树缺 5 篇文档、3 个目录），改为层级 + 职责，枚举只留 README
- **`v1.4.0` 漏记补全**：AGENTS、SKILL、sync 脚本的改动补进 v1.4.0 的「更新」

### 新增

- `skills/rive-ops/references/` 补齐 4 篇：`cli.md`、`audit.md`、`runtime.md`、`binding.md` —— 12 篇 docs 全部有快照（原 8 篇）
- `SKILL.md` 任务路由补 3 条（CLI / RML、运行时选型、数据绑定）
- `DEVELOPMENT.md` 补问题记录：`0xC0000409` 三组对照与判定方法（`$LASTEXITCODE` = `-1073740791` 且输出全空）

### 校验

- `tools/sync-skill.ps1 -Check` → `OK: 12 references in sync, 0 dead links.`
- 全库相对链接检查 → 0 死链；README 主题 12 行、坑位表 36 行、参考 12 篇三处数字一致

## v1.4.0 — 2026-10-28

新增「无清空合并」：把整份 Rive 文件并入另一个**已有内容**的文件，且不改动目标原内容。附带一套可执行的 CLI 脚本，而不是只写方法。

### 新增

- `skills/rive-ops/scripts/rive-merge/`：`rmlcore.py`（共享库 + `--selftest`）、`rml_merge.py`（合并，三层冲突语义 + 资产四级匹配 + 孤儿剪枝 + 自动转 ASCII 文件名）、`fill_assets.py`（从 `.rev` / 目录回填素材）、`gate.py`（构建前静态闸门，可 `--fix --verify`）、`rev_assets.py`（`.rev` ↔ 工程资产审计）
- `docs/无清空合并文件.md`：四步管线、冲突语义、0xC0000409 三坑、push 回写、已知限制
- `skills/rive-ops/references/merge.md`：同步快照

### 修正

- **`rive --verify` / `--once` 静默崩溃（exit `3221226505` = `0xC0000409`）的真因是资产文件名含非 ASCII**（中文、全角括号），不是内容损坏：同一份字节改成 `asset_NNN.<ext>` 后 `0 errors, 0 warnings`。`FontAsset exportTypeValue="referenced"` 是第二诱因。
- 合并时同一 id 在目标顶层、在来源画板内会产出重复 id；改为对已占用 id 重分配并重写子树引用。

### 更新

- `AGENTS.md`：结论先行 21 → 26 条（新增 `0xC0000409` 非 ASCII 文件名、`referenced` 第二诱因、`rive pull` 必崩、同 id 重复分配、无清空合并入口）
- `skills/rive-ops/SKILL.md`：铁律 21 → 25 条，任务路由加合并管线，排障路由加 3 行
- `tools/sync-skill.ps1`：映射表增加 `无清空合并文件.md → merge.md`

### 实测数据

- 目标 8 画板 + 来源 33 画板（74 MB 资产）→ 合并产物 35 画板 / 67 资产 / 21343 元素，`0 errors, 0 warnings`，`gate PASS`；`rive push` 回写后云端指纹与本地一致
- 剪枝一次清掉 34 个孤立资产；素材回填 53 个命中、14 个 `.luau` 由工程目录提供、0 缺失

## v1.3.5 — 2026-10-27

速查表补齐两个 API 形态坑。

### 更新

- `docs/速查表.md`：`duplicate_objects` 只返回数量、需回读父级找新 id；`addProperties` 的参数结构是 `viewModels[]`

## v1.3.4 — 2026-10-27

补齐工具链经验：MCP 调用封装与 GitHub 推送。

### 更新

- `scripts/rive_mcp.py`：Python MCP 客户端，dict 传参 + 复用 session，替代 PowerShell 传 JSON
- `docs/MCP接入与联调.md`：新增「调用封装：别用 PowerShell 传 JSON」
- `docs/速查表.md`：新增 3 条（PowerShell 引号被吞、push 认证失败、push 直连超时）

## v1.3.3 — 2026-10-27

浅色主题 Artboard 2 接入同一套按钮动效。

### 更新

- `docs/按钮开关与按压动效.md`：新增「浅色主题变体（Artboard 2）」，含配色对照、扁平矢量打组法、按填充做颜色关键帧、独立 ViewModel 实例
- `docs/速查表.md`：新增 4 条（浅色主题按填充变色、打组原点、批量复制父级、跨画板 ViewModel 实例）
- `skills/rive-ops/references/toggle-button.md`：同步

### 实测数据

- 12 个按钮打组 + 浮层后，待机渲染差异 0 像素
- `simulateStateMachine`：无线网络/全车锁 → Activating，蓝牙/主驾加热 → Deactivating
- 激活态橙卡 `#ffd96b2b` + 白字，关闭态与其它未激活按钮一致
- 状态机 15-1607 共 12 层，监听器 12 个，脚本全部复用

## v1.3.2 — 2026-10-27

主驾加热 / 主驾通风接入开关效果。

### 更新

- `docs/按钮开关与按压动效.md`：新增「带档位条的按钮」小节，记录复用原橙点、IdleActive、3 格档位条保持现状
- `skills/rive-ops/references/toggle-button.md`：同步

### 实测数据

- 关闭态底色 42/255、激活态 67/255，与其它按钮一致
- simulate：关闭命中 Deactivating，中途再开命中 Activating
- 待机截图与改前一致（仅字体抗锯齿差异）

## v1.3.1 — 2026-10-27

9 个按钮批量接入后的 MCP 批量陷阱。

### 更新

- `docs/按钮开关与按压动效.md`：新增「批量执行时的 API 陷阱」8 条；实测记录补充 9 按钮批量结果
- `skills/rive-ops/references/toggle-button.md`：同步上述内容

### 实测数据

- 蓝牙、无线网络、热点、专注模式、一键静音、系统清理、离车不下电、加油口盖、全车锁全部接入，状态机共 10 层
- 9 个 toggle 脚本诊断均为 `[]`；单按钮 simulate 激活/取消激活均命中对应 Layer
- 待机截图与改前逐像素一致（bbox 为空）

## v1.3.0 — 2026-10-27

按钮开关与按压动效：单图标 toggle + 一按钮一层。

### 新增文档

- `docs/按钮开关与按压动效.md` —— 500ms 总时长（按下 200ms + 抬起 300ms）、Quart-2/ease、浮层/橙点、Listener Action Script toggle、ViewModel、一按钮一层状态机、初始激活态处理

### 更新

- `docs/速查表.md`：新增 3 条按压/多按钮坑位（30 → 33 行）
- `README.md`：主题 10 → 11，技能参考 6 → 7 篇
- `AGENTS.md`：结论先行 18 → 21 条，新增按钮动效路由
- `skills/rive-ops`：新增 `references/toggle-button.md`，SKILL.md 增加路由、3 条铁律与参考
- `tools/sync-skill.ps1`：新增按钮文档 → toggle-button.md 映射

### 实测数据

- 屏幕清洁：按下 200ms、抬起 300ms、总 500ms；simulate 激活 33 帧完成、取消 52 帧完成
- 待机截图与修改前逐像素一致；激活态底色/橙点与主驾加热一致
- `screen_clean_toggle` 脚本诊断 `[]`，click listener 绑定浮层

## v1.2.0 — 2026-10-27

性能诊断与资产瘦身：实测 72.2 MiB → 2.09 MiB。

### 新增文档

- `docs/性能诊断与资产瘦身.md` —— 桌面编辑器无素材磁盘缓存；`.rev` 体积取证；资产审计（图片 `206` / 字体 `279`）；`delete_objects` 删资产 ID；`upload_asset` 重名假 `0-0`；字体卡加载/Not Found 的根因与 fontTools 子集化（8 MB → 58–60 KB）；本地字体仅 CLI 可用

### 更新

- `docs/速查表.md`：坑位表 23 → 30 行，新增「资产属性键」一节
- `docs/MCP接入与联调.md`：实测行为 10 → 14 条（delete_objects 删资产 / 重名 0-0 / 字体资产属性键 / Not Found 不代表缺数据）
- `docs/导出规则与交付验收.md`：新增「编辑器加载 ≠ 交付体积」
- `AGENTS.md`：结论先行 15 → 18 条，新增性能诊断路由
- `README.md`：主题 9 → 10，技能参考 5 → 6 篇
- `skills/rive-ops`：新增 `references/performance.md`，SKILL.md 增加任务路由、3 条铁律与排障行
- `tools/sync-skill.ps1`：新增性能文档 → performance.md 映射

### 实测数据

- 资产 87 → 18（图片 60 → 8，字体 14 → 4）
- `.rev` 75,708,136 B → 34,771,844 B（删冗余）→ 2,187,553 B（字体子集化），减少 97.1%
- 113 个文本样式重绑，0 失败；Artboard 1/2 截图字节一致

## v1.1.1 — 2026-10-26

Agent Skill 化 + 同步机制，防止技能与文档漂移。

### 新增

- `skills/rive-ops/` —— Agent Skill 包：SKILL.md（任务路由 + 15 条铁律 + 排障路由）+ 4 个实盘脚本 + 5 篇参考快照 + 运行时验收页；已安装于 `~/.workbuddy/skills/rive-ops/`
- `tools/sync-skill.ps1` —— docs → 技能快照同步脚本（`-Install` 同时刷新安装目录）

### 维护规则

- `skills/rive-ops/references/` 是 `docs/` 的快照：**改 docs 后必须跑 `tools/sync-skill.ps1`**，否则技能漂移（AGENTS 约定与 README 已写入此规则）

## v1.1.0 — 2026-10-26

实盘交付演练沉淀：`.ai` 素材导入链路 + `.riv` 导出规则 + 运行时验收。

### 新增文档

- `docs/AI素材导入链路.md` —— Illustrator COM 导出 SVG → 裁字体 → data URI 上传 → 放置验收；含 COM 防呆（DONTDISPLAYALERTS / Artboards 禁 foreach / OUTLINEFONT 静默失败）、"文字必须转轮廓"（Inter 兜底无 CJK，交叉验证 rive-flutter#338）
- `docs/导出规则与交付验收.md` —— **`.riv` 只装「默认画板 + 组件画板」**（`includeInExport` 是假开关，判据是 `isComponent`，实测 33 画板 → 3362 B）；字体 Type 必须 Embedded（否则运行时中文永久豆腐）；运行时验收环境与无头截图命令

### 新增脚本 / 工具

- `scripts/ai-svg-export.ps1` —— 驱动运行中的 Illustrator 导出 SVG（精确文件名匹配、DONTDISPLAYALERTS、不保存关闭）
- `tools/runtime-check/` —— 官方 webgl2 运行时验收页：列出 `.riv` 实际画板、渲染、报错；配 Edge 无头截图命令

### 更新

- `docs/MCP接入与联调.md`：实测行为补充 3 条（upload_asset data URI / capture 渲染失败家族 / 批量写入静默失败）
- `docs/速查表.md`：坑位对照表 16 → 23 行
- `AGENTS.md`：结论先行 10 → 15 条

## v1.0.0 — 2026-10-26

首次建立。按 knowledge-base 单项目规范落地四件套 + 主题文档 + 验证脚本。

### 新增文档

- `docs/MCP接入与联调.md` —— 桌面版本地 MCP（`127.0.0.1:9791`）：配置、40 个工具分组、7 条实测行为、联调循环
- `docs/CLI与RML工作流.md` —— `rive create` 项目结构、三查（verify / inspect / screenshot）、RML 语法与值格式、与编辑器互通、签名与水位印
- `docs/跨文件搬运画板.md` —— 剪贴板随机丢失的根因与官方证据、`.rev` 文件级搬运流程、三个实测坑、指纹核验
- `docs/画板体检与交付整理.md` —— 八项指纹口径、六类高频问题、整理顺序、改造后证明
- `docs/运行时选型与车机落地.md` —— 四个 Web 包的取舍、其他平台、车机三条路线、上机前五项确认
- `docs/数据绑定与状态机驱动.md` —— 两套驱动模型对照、ViewModel 绑定三个坑、无入口画板判据、无头验证
- `docs/速查表.md` —— 端点、工具、命令、值格式、坑位、指纹一页纸

### 新增脚本

- `scripts/rive-mcp.ps1` —— MCP 单次调用封装（握手 + 调用 + 图片落盘）
- `scripts/rive-audit.ps1` —— 全画板指纹采集，输出 TSV
- `scripts/rive-import.ps1` —— `.rev` 导入（等待目标激活 → 清空 → 导入 → 报告）

### 新增工程文件

- `.gitattributes` —— `*.riv` / `*.rev` 标为 binary（防换行符损坏）
- `.gitignore` —— 忽略导出产物与系统文件
