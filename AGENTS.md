# AGENTS.md — 给 AI / 未来的你：关键坑速记

> 📌 **文档基线**：2026-11-10 v1.10.0（待回填）—— 更正「改 listener 只能删了重建」，补 `930` 键与「跨文件粘贴只丢脚本」：README 13 主题、坑位表 84 行（不含表头）、结论先行 61 条、references 34 篇与 docs 一一对应；改 docs 后先 `tools/sync-skill.ps1 -Check` 再 `-Install`（见「约定」）
> **更新文档/代码后，请更新此行**（日期 + 新 commit hash），并在 CHANGELOG 追加版本

本仓库整理 **Rive 使用技巧**（MCP 联调 / CLI 与 RML / 搬运 / 体检 / 运行时）。**只收录实际验证过的做法**，未验证的明确标注"暂不收录"。回答相关问题前先读这份。

## 技术栈

- Rive 桌面版 1.9.x（Microsoft Store 包，进程名 `Rive`）+ 内置本地 MCP
- Rive CLI（技术预览）：`~/.rive/bin`，凭据存 Windows 凭据管理器
- 目标宿主：车机 HMI（Qt / Android / WebView 三条路线）
- 工具脚本：PowerShell 5.1（Windows）

## 结论先行（少走弯路）

1. **要 AI 改正在编辑的文件** → 走本地 MCP `http://127.0.0.1:9791/mcp`，**Rive 必须开着**，Early Access。
2. **跨文件搬画板** → **绝不用剪贴板**（随机丢图片/mesh/嵌套）。走 `export_file(rev)` → 删光目标画板 → `upload_rev(open_file)` → `delete_objects` 清理。
3. **导出 `.rev` 报 `HandshakeException`** → 系统代理掐断 TLS，**关代理**。这条最反直觉，先查它。
4. **`export_file` 的 `destination` 传目录**，不是文件路径。
5. **`upload_rev` 的 `open_file` 要求目标零画板**，否则原样不动并报错。
6. **`capture_artboard` 必须先 `focusArtboard`**，否则返回空白图（连背景色都不生效）。
7. **`animation_editor` 只认活动画板**，`data.artboardId` 被静默忽略。
8. **判断交互画板能不能上机**：`inputs == 0 && dataBinds == 0 && animStates >= 2` → 代码驱动不了。
9. **带脚本的 `.riv` 上 Web 必须 `--publish`**，未签名脚本被 CDN 拒绝。
10. **`.gitattributes` 必须有 `*.riv binary`**，否则 Windows 换行转换会损坏文件
11. **`.riv` 只装「默认画板 + 组件画板」**，其余画板连同动画/状态机被排除。画板的 `includeInExport` 属性**不是**导出开关（写入无效），判据是 `isComponent`。交付前必须核验，或每屏拆一个文件
12. **字体 Type 必须是 Embedded**：编辑器里"等一会正常"是云端取字体；`.riv` 里没有字体数据时运行时中文**永久豆腐**
13. **AI 导 SVG 给 Rive 前必须把文字转轮廓**：否则 Rive 按 font-family 落到内置 Inter 字体（无 CJK），中文全灭
14. **`upload_asset` 只认 data URI**；传路径返回假 id `0-0`。**一切属性写入必须回读验证**（批量写入会静默失败）
15. **Illustrator COM 第一行设 `DONTDISPLAYALERTS`**，否则弹窗挂死 COM；`Artboards` 集合禁止 foreach 枚举。
16. **桌面编辑器没有素材磁盘缓存**：每次打开从云端拉全量资产；打开慢先做资产审计，不要先改 DNS 或装系统字体。
17. **`delete_objects` 也能删资产 ID**（实测）；`upload_asset` 重名返回假 `0-0`，换唯一名后再用属性键 `203` 改名；幽灵 `0-0` 重启后消失。
18. **字体一直转圈 / Not Found** 先验证字体文件；旧资产记录卡住时重传/子集化。子集化后必须校验字符覆盖、回读 `279`、截图对比，并保留全量字体 `.rev`。
19. **按压动效总时长 500ms = 按下 200ms + 抬起 300ms**；不要把 500ms 当成抬起段再加 200ms（42 帧会明显偏长）。
20. **多个开关按钮必须一按钮一层状态机**；所有按钮塞在同一个 Layer 时，只能有一个按钮保持激活。
21. **点击切换用 Listener Action Script 读 boolean 取反**；脚本类型必须是 `listenerAction`，`context:viewModel()` 前必须把 ViewModel 绑定到画板。
22. **要"把 A 并进 B 且不清空 B"** → `upload_rev` 做不到（要求目标零画板）。走 `.rev` → `rive create` 两个 CLI 工程 → `skills/rive-ops/scripts/rive-merge/rml_merge.py` → `fill_assets.py` → `gate.py --fix --verify` → `rive push`。
23. **`rive --verify` / `--once` 无任何输出直接崩（exit `3221226505` = `0xC0000409`）** → 先查**资产文件名**：中文/全角名必崩，同一份字节改成 `asset_NNN.<ext>` 就 `0 errors`（实测对照）。`gate.py --fix-names` 一键改。
24. **`FontAsset exportTypeValue="referenced"`** 是同一崩溃的第二诱因；缺这个属性表示 embedded，不要误报。
25. **`rive pull` 在 1.8.0 必崩**，拆工程用 `rive create <dir> --from-rev=<x.rev>`；`rive push --name` 只接受 ASCII；**CLI 没有删除远程文件**的命令，联调草稿只能留在云端。
26. **同一 id 在目标顶层、在来源画板内**（本案例 10 个 `CubicEaseInterpolator`）→ 合并会出重复 id、动画静默绑错对象；必须对已占用 id 重分配并重写子树引用。
27. **`addSvgInstance` 静默丢弃内嵌 `<image>`**：矢量路径全在、位图 0 个 Image 节点、**不报错不告警**。位图必须 `upload_asset`(data URI) + `addImageInstance` 单独进；判据是数一遍 `types` 含 `Image` 的节点。
28. **图片实例的 `x/y` 是原点位置**（`380/381` 默认 `50/50` 在中心），不是左上角 → 填 `left+w/2, top+h/2`；`addImageInstance` **不接宽高**、按位图原生像素进场 → 回写 `sx`(16)/`sy`(17)；新加对象默认**垫底** → `sendToFront`。
29. **`clipPath` 不会被导入**：Rive 建出来的 Shape 是空的，圆角/异形遮罩必须在位图 alpha 里烘焙。`scripts/svg-prep.py clip` 直接把 clipPath 解成 `x,y,w,h,r`。
30. **AI 的中文图层名会变成方块**：导出时写成逐字节字符引用（SVG 声明 `iso-8859-1`），落成 `0x80–0x9F` 控制字符 → 界面显示方块。只有**图层名是中文**的素材会中招，`rename_objects` 改回。
31. **素材导入的验收是像素比对**：`.ai` 导 PNG24 当参考图，两侧 resize 到画板尺寸算平均差。实测正确 0.10–0.14/255、错位 2.5–3.2/255，阈值取 `0.5`。
32. **`capture_artboard` 报 `has no drawable area`**：一是画板未激活（先 `focusArtboard`），二是该画板 `computedwidth/height`(810/811) 卡成 0 —— 写 w/h、`resizeArtboard`、改缩放都刷不回，**只能删画板重建**（重建时每步截图，即未再复现）。
33. **`viewmodel_editor` 的写路径：命令齐全；崩溃非必现，但真崩过（2026-11-04 三次）**——官方命令确实存在：`createViewModels` / `addProperties` / `createViewModelInstances` / `bindViewModelToArtboard` / `databind`；配套 `path_editor.createParametricShapes`（建按钮形状）与 `create_listeners`（`click`/`down`/`up` + `viewModelChange`/`scripted`）。**不能宣称"MCP 建不了按钮"**。2026-11-05 一轮完整链路（建空壳 VM → addProperties → createViewModelInstances → bindViewModelToArtboard → databind 到 ScriptInput → 建 3 个按钮 → create_listeners click → reorder sendToFront）全部成功、未崩。做法：先存快照；按契约逐步调用并回读；崩一次就转 UI，别重试同一命令。
33b. **导入慢要量，别猜**：一页 531 对象全链路实测 9.6 s（导出 4.9 / 写 Rive 4.0 / 后处理 0.65 / 验收 0.32）；`upload_asset`+`addSvgInstance` 占 36%，且都在解析同一份 SVG。**真正的瓶颈是"每次现写驱动脚本"** —— 同一批步骤现成脚本跑 9.6 s，实跑 65 s。优化驱动脚本（一条命令），不是优化任何单步。
34. **位图的可见框 ≠ `<image>` 上的 `x/y/width/height`**：Figma 的 pattern 填充会叠 `clip-path` + `transform="rotate()"`。004 的车按 clip 矩形算出来是**空白**、按 `<image>` 矩形放**偏到画外**，真实可见框是 `(1623,153.5) 114.5×47.5`（`<image>` 写的是 `1751.82,53.45` + `rotate(89.815)`）。→ **别手算**：只放这一张图 + 全 `<defs>`，铺满画布透明渲染，取 alpha `getbbox()`。
35. **裁完必须断言"不是空的"**：`getbbox()` 返回的是**该图自身像素坐标**，换算画布坐标时多乘一次缩放就会裁到画布外——`PIL` 不报错、补透明，得到**尺寸正确、内容全空**的 PNG。它一路都"成功"（资产 id 正常、节点建出、`810/811` 对得上），到编辑器里才看见空图层。判据 `alpha.max() == 0`。
36. **导入卡在 `An SVG import is in progress` 的判据**：**读取类调用秒回**（`session_info`/`get_artboard_hierarchy`）、**渲染类全挂**（`addSvgInstance`/`capture_artboard`）= 编辑器主线程被占。两个真因：SVG 里有指向**已删除 `<mask>`** 的悬空引用；单份 SVG 太大（154 KB 实测拖死，拆成 4 份 26–62 KB 秒过）。`undo` 解不开，**只能重启桌面端**。
37. **`capture_artboard` 对*所有*画板都报 `has no drawable area`** = **整机级离屏渲染故障**，不是某块画板的毛病（判据：连以前能截的对照画板也挂、所有画板 `810/811` 都是 0）。**别按旧结论"删画板重建"**——会白删好画板；它会自愈，本轮约 40 分钟后恢复。
38. **像素验收的阈值是相对基线，不是常数 `0.5`**：先量「源 SVG vs 参考图」得到下限。004 基线 **1.40**、Rive 结果 **1.43** = PASS；拿绝对 `0.5` 判会把正确结果判成失败，然后去改一个本来没毛病的地方。
39. **层序：新对象追加到 `children` 末尾，而 `children` 是 top→bottom**（所以"后加的"= 最底，"先加的"反而在上面）。→ **按"目标从上到下"顺序依次添加，层序自动正确**，不用逐个 `sendToFront`。事后调整用 `reorder_objects`，参数是 **`operations[]`** 而非 `objects`。代价：位图没法插回原组内部，只能整体在组之上。
40. **SVG 的解析与转换在 Rive 服务端做**：报 `SVG conversion for asset X is unavailable` 就是这次转换失败，**同一资产重试无意义**，必须换新资产重传。等待是跨网络的，所以"慢"和"死"从外面看一模一样 → 用 `children` 里是否出现该组来判定结果。
41. **服务端转换器不解析 `<use>`**：Figma 导出的图标与字形大量靠它。轻则那块内容消失，重则整份资产转换失败。必须本地展开成内联 `<g transform="translate(…)">` + 深拷贝（拷完去掉 `id`）。
42. **`<use>` 展开后可能是空组**：它引用的字形轮廓躺在 `<font>` 里，而上游按"Rive 不消费 `<font>`"已经裁掉了。展开后 0 条 `path` 就是"字形残骸"，直接跳过——别反复重试（3 次 × 4 秒白等）。
43. **`addImageInstance` 的返回可能没有 `nodeId`**，但节点确实建好了 → 回读 `children` 按 `name` 取 id，别对着 `None` 去写属性。
44. **每组 SVG 不要携带整份 `<defs>`**：按 `url(#…)` / `href="#…"` 的引用闭包裁剪，只留本组走得到的。005 从 130–199 KB/组降到 1.3–1.8 KB，渲染结果一像素不差（MAE 0.012）。
45. **无 `clip` / `transform` 的位图直接取原生像素**（`scale` 100%），既省一次隔离渲染、又不丢分辨率；只有带 `clip` + `rotate()` 的才需要"隔离渲染 + alpha bbox"。
46. **开关按钮只关不开** → click 监听器挂的是 `viewModelChange` 常量（false），每次点击只会重复写同一个值。改用 `scripted` Listener Action 取反（`p.value = not p.value`）；旧 listener 可用 `delete_objects` 直接删；`animation_editor queryStateMachine` 回读 `actions[].scriptAssetId`，`script_diagnostics` 必须 `[]`。"全部显示"这类单向复位继续用 `viewModelChange`，常量值在 `BindablePropertyBoolean` 键 **634**。
47. **MCP 没有建文本对象的命令** → 中文标签用 fontTools 轮廓 + 定尺寸 SVG + `addSvgInstance`。资产尺寸 = viewBox（88×44 按钮配 42×20 / 70×17）；SVG 变换落在子 `Group`（实测 42×20 标签 `sx≈8.59%`、`x≈22`），外层 `Node` 的 `810/811` 读回 0、轮廓顶点也取不到 → 落点只能用 `capture_artboard` 验收；不要在已缩放组里再套 `translate`（宽度会炸到 276px）。
48. **路径光带整条不可见** → 填充多边形是逆时针（y 向下），0 error。顺时针绕序：`-n` 侧尾→头 → 头半圆 → `+n` 侧头→尾 → 尾半圆。
49. **两个画板要用不同脚本/参数** → 共用同一个 `scriptAsset` 时改常量会互相影响。新建脚本用 `manage_scripts.create`（可带 content，借 `scripts/rive_mcp.py` 从本地文件读，避免把 28KB 塞进对话）；**MCP 没有 attach 接口，必须用户在目标画板右键添加脚本节点**。
50. **右键新建脚本节点** → 默认落在画板中心 `(1280,720)`、最上层。要 `set_property_values` 到路径父级坐标（如 `1639,682`），再 `reorder_objects` 调到地图之上、UI 之下；`duplicate_objects` 不能复制 ScriptAsset（报 not a Component），同脚本可复制节点且不要改 848。
51. **ScriptInputs 不能中文化** → 面板标签就是 ASCII 字段名（Luau 标识符不支持中文）；不要重命名 ScriptInput 对象，重编译会重建（实测 id `291-*`→`297-*`）。中文写源码注释；顺序用 `reorder_objects` 对输入子对象 `sendToFront`；数值键 **243**、布尔 **245**。
52. **电流长度随车位置自适应** → `lenScale = clamp((dist/TOTAL)/0.5, 0, 1)`，`pulseLen = fxPulse*lenScale`；宽度渐变分母必须用实际 `head-tail`。50% 后保持 100%，`fxPulse` 仍是基础参数。（2026-11-09 定稿改为常值长度 + 缓动，见 57；本条保留为「长度随进度变化」的可选方案）
53. **桌面端卡 `Compiling` 先分层，不要先查文件**：浏览器同文件正常、桌面端打开**别的文件也卡** → 客户端层。桌面端**不写运行日志**（`LocalCache` 只有 prefs + Sentry，正常时 breadcrumb 0 字节）；改量进程：CPU 持续增长 + IO≈0 = 本地在算，不是网络。
54. **想"重载编辑器数据"删 `editorProperties` / 改 `fileSafeMode` 都无效**：`editorProperties` 打开文件即从文档重建（4 864 → 463 → 4 868 字节）；`fileSafeMode=true` 被客户端写回 `false`。本轮最终靠「卸载 + 删包数据 + 装最新版」恢复，但版本与安装方式两变量同时改变，**不能归因单项**。
55. **改已有 listener 的 action**：~~没有 update 命令，只能删了重建~~ → **已被第 60 条取代**：可直接 `set_property_values` 改 `scriptAssetId`（键 `930`），删监听重建只作兜底。
56. **`find_objects` 按节点名搜，中文是画面文字不是节点名**：本文件节点名是英文前缀，搜「沙 / 尘 / 全部」返回空；用 `BTN_` / `TXT_` 核对每画板各 3 条防重复副本。「全部开关」主开关语义 `next = not (sandOn and dustOn)`：两个都开才全关，否则全开。
57. **电流"起步快、到车尾慢"不要改 `fxSpeed`**：那是总时长。存进度 `prog 0→1`，用 `0.25*p + 0.75*bezier(0.25,0.10,0.25,1.00)` 映射头部弧长；纯缓出末段斜率趋 0，会看起来"停住"，必须留 25% 线性保底。
58. **Rive 没有羽化 clip**：`clipPath` 只有硬边。羽化 = 同一电流多边形做 N 层、`extra` 从 290 递减到 0、每层 alpha 7.5% 叠画下层图；成本 ≈ 蒙版面积 × 层数 × 电流条数，先压面积与条数再加层（660 + 双电流时 5 层就卡，290 + 单条时 8 层不卡）。
59. **跨文件粘贴只丢脚本，不丢 ViewModel**：画板 / 图层 / 状态机 / 动画 / ViewModel 定义与实例、过渡条件里的 `viewModelId` 都会跟过去，唯独脚本资产不带——监听动作 `scriptAssetId` 变 `0-0`，点击无反应且不报错。修法：`manage_scripts` 重建 → `930` 重指 → 回读 + 预览点击；**不要重建 VM**（会多份同名，以 `conditions` 引用的 `viewModelId` 为准）。
60. **ListenerAction 的 `scriptAssetId` 是键 `930`，可直接改**：与节点脚本的 `848` 不通用——`848` 改完不重绑（init 跑、draw 不来），`930` 改完立即生效（实测 12 个 click 监听一次性批量重指，`script_diagnostics == []`）；写字符串键 `scriptAssetId` 报 `invalid_property_key`。
61. **"点击没反应"先排除编辑器卡顿**：本轮 12 个按钮"点不动"实为编辑器卡顿，预览恢复后同一批按钮全部正常；判定脚本问题前先重开预览。

## FAQ 路由

- "怎么让 AI 直接改我的 Rive 文件" → [docs/MCP接入与联调.md](docs/MCP接入与联调.md)
- "怎么用代码从零生成动效 / 进版本管理" → [docs/CLI与RML工作流.md](docs/CLI与RML工作流.md)
- "复制粘贴丢了东西 / 怎么把画板搬到另一个文件" → [docs/跨文件搬运画板.md](docs/跨文件搬运画板.md)
- "把 A 文件全部内容并进 B 且不能清空 B" → [docs/无清空合并文件.md](docs/无清空合并文件.md)
- "文件要交付给开发了 / 怎么体检" → [docs/画板体检与交付整理.md](docs/画板体检与交付整理.md)
- "用哪个运行时 / 怎么上车机" → [docs/运行时选型与车机落地.md](docs/运行时选型与车机落地.md)
- "交互做了但代码触发不了" → [docs/数据绑定与状态机驱动.md](docs/数据绑定与状态机驱动.md)
- "打开文件很慢 / 素材和字体一直转圈" → [docs/性能诊断与资产瘦身.md](docs/性能诊断与资产瘦身.md)
- "桌面端一直 Compiling / 浏览器正常 / 清缓存无效 / 想读编译日志" → [docs/桌面端编译卡死排查.md](docs/桌面端编译卡死排查.md)
- "要做按钮按压 / 开关 / 激活态动效" → [docs/按钮开关与按压动效.md](docs/按钮开关与按压动效.md)
- "路径上一条电流追着车尾跑 / 光带宽度渐变和辉光 / 两个画板想用不同参数" → [docs/效果-路径电流与脚本复用.md](docs/效果-路径电流与脚本复用.md)
- "电流起步要快、到车尾要慢 / 光晕边缘要羽化 / 加层就卡" → [docs/效果-电流缓动与羽化蒙版.md](docs/效果-电流缓动与羽化蒙版.md)
- "设计稿（.ai / SVG）怎么导进来 / 位图丢了 / 位图是空的 / 图标圆角没了 / 图层名变方块 / 导入卡住不动 / 截图报 no drawable area" → [docs/AI素材导入链路.md](docs/AI素材导入链路.md)
- 端点、命令、坑位一览 → [docs/速查表.md](docs/速查表.md)

## 约定

- 文档标题与文件名一致，中文命名，不带空格
- 每个主题含 **TL;DR → 主体 → 来源**，来源必须是官方文档链接或"本机实测 + 日期"
- 不写 token、本机绝对路径、账号邮箱
- 未验证的内容不写进正文；确需提及就标"暂未收录"
- 涉及数字（工具数、画板数、状态数）注明采集日期，Early Access 阶段会变
- **枚举只在 README**：新增/删除主题时只改 README 主题表与 AGENTS 的 FAQ 路由；`DEVELOPMENT.md` 的树只写层级与职责，不补文件名（v1.0.0→v1.4.0 期间就在那棵树上腐化了 5 篇文档）
- **技能同步**：`skills/rive-ops/references/` 是 `docs/` 的快照，`skills/rive-ops/scripts/` 顶层文件是 `scripts/` 的字节副本。改任何 docs 或顶层 scripts 后必须运行 `tools/sync-skill.ps1`（加 `-Install` 同时刷新安装目录）；同步会按映射表把 `](中文名.md)` 重写成 `](英文名.md)`，所以快照里没有 docs 也能点开链接。`tools/sync-skill.ps1 -Check` 只校验不写入：`DRIFT` / `MISSING SCRIPT` / `SKILL-ONLY` / `STALE COUNT`（`SKILL.md` 里引用的坑位数与真实表行数不符）/ `BOM IN SKILL.md`（PS 5.1 写文件带的 BOM 会顶掉 frontmatter 的 `---`）/ 死链，任一命中就返回非零退出码（`scripts/rive-merge/` 是技能独有目录，不参与同步）。**改 `SKILL.md` 别用 `Set-Content -Encoding UTF8`**，用能控制 BOM 的方式写

## 常用命令

```powershell

# ⛔ 第一铁律：Rive MCP 调用绝不猜形状

**任何 MCP 工具调用的 `data` 结构，必须先离线读契约再发**（`probe/tools.json` 里每个工具的 `inputSchema.properties.data` 就是完整契约，不需要 Rive 运行）。猜错形状的代价是分级的：

- 轻则**静默丢弃**：字段被忽略、返回 success 但什么都没发生（坑位 33：createViewModels 内联 properties）；
- 重则**编辑器闪退**：用户丢历史、全链路返工（2026-11-04 实测两次：addProperties 猜形状直接崩）。

流程：**读 schema → 按契约发 → 回读验证**。三步缺一不可。

# MCP 是否在线
Test-NetConnection -ComputerName 127.0.0.1 -Port 9791

# 单次调用
scripts/rive-mcp.ps1 -Tool session_info
scripts/rive-mcp.ps1 -Tool capture_artboard -ArgsJson '{"artboardId":"0-1","longEdge":1024}' -OutImage out.png

# 体检
scripts/rive-audit.ps1 -OutFile audit.tsv

# 导入 .rev（需先在编辑器里切到目标文件）
scripts/rive-import.ps1 -TargetFileId 1234567 -RevPath D:\export\src.rev

# 无清空合并（Python 3.8+；脚本在 skills/rive-ops/scripts/rive-merge/）
python skills/rive-ops/scripts/rive-merge/rml_merge.py --target work\tgt --source work\src --out work\out --target-rev 目标.rev --source-rev 来源.rev --prune-orphans
python skills/rive-ops/scripts/rive-merge/fill_assets.py --dir work\out --rev 目标.rev --rev 来源.rev --from work\src
python skills/rive-ops/scripts/rive-merge/gate.py --dir work\out --fix --verify

# 素材导入：导出（转轮廓）→ 清理 → 解位图/剪裁几何 → 遮罩 → 像素比对
scripts/ai-svg-export.ps1 -FileName 'x.ai' -SourceAi 'D:\src\x.ai' -OutSvg 'D:\out\x.svg' -OutlineText
python scripts/svg-prep.py clean  D:\out\x.svg D:\out\x_rive.svg
python scripts/svg-prep.py images D:\out\x_rive.svg --outdir D:\out\img --json D:\out\img.json
python scripts/svg-prep.py clip   D:\out\x_rive.svg
python scripts/svg-prep.py mask   D:\out\img\a.png D:\out\img\a_m.png --img-rect 786.893,455.857,126.214,168.286 --clip 788,478,124,124,20.571
python scripts/svg-prep.py verify shot.png ref.png --size 2048x1152

# docs 更新后先校验（漂移 / 未映射文档 / 死链，非零退出即失败），再同步
tools/sync-skill.ps1 -Check
tools/sync-skill.ps1 -Install   # 同时刷新 ~/.workbuddy/skills/rive-ops
```

## 备注

- MCP 与 CLI 的官方文档入口见各文档末尾「来源」
- Early Access 阶段工具集会变，脚本里不要硬编码能力假设
