---
name: rive-ops
description: This skill should be used when working with Rive — desktop MCP integration, editing artboards, importing Illustrator (.ai) assets, transferring artboards between files, merging a whole file into another without clearing it, exporting .riv deliverables, auditing artboards, diagnosing slow file loads / asset bloat / font loading, diagnosing a desktop editor stuck on "Compiling", or diagnosing Rive text/font/z-order/rendering issues. Packages field-verified PowerShell helpers, a runtime acceptance page, and pitfall references collected from production work (Chinese).
agent_created: true
---

# Rive 运维手册（实盘验证版）

所有规则均来自真实交付演练（2026-10），每一条都踩过并有验证证据。动手前先读「铁律」，再按「任务路由」选择流程；细节按需加载 `references/`。

## 0. 环境自检

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 9791   # Rive 桌面版 MCP，App 必须开着
.\scripts\rive-mcp.ps1 -Tool session_info               # 单次调用封装
```

- 端点：`http://127.0.0.1:9791/mcp`，Streamable HTTP，仅桌面版、Early Access。
- 工具集会变，脚本里不要硬编码能力假设。

## 1. 任务路由

| 任务 | 走法 | 深入参考 |
|---|---|---|
| 读场景 / 改属性 / 截图 | `get_selection` / `set_property_values` / `capture_artboard` | `references/mcp.md` |
| 从零用代码生成动效 / 进 Git | `rive create` 建工程 → 写 `scene.rml` → 三查（verify / inspect / screenshot）→ `--once` / `--publish` | `references/cli.md` |
| 画板体检 / 搬运后核验 | `scripts/rive-audit.ps1`（八项指纹 → TSV） | `references/audit.md` |
| 跨文件搬画板 | `export_file(rev)` → `scripts/rive-import.ps1` → 删多余 → 指纹核验 | `references/transfer.md` |
| 整文件合并且**不清空**目标 | `rive create --from-rev` 拆两个工程 → `scripts/rive-merge/rml_merge.py` → `fill_assets.py` → `gate.py --fix --verify` → `rive push` | `references/merge.md` |
| Illustrator 素材导入 | 两个入口：`.ai` 走 `scripts/ai-svg-export.ps1 -OutlineText`；**手头已是分层 SVG 就直接从 `svg-prep.py` 起**。→ `clean/images/clip` → data URI 上传（`name=` 用 ASCII）→ **按命名组拆分** `addSvgInstance`（单份 <60 KB）→ 位图单独 `addImageInstance` + 五坑 → 像素比对 | `references/asset-import.md` |
| 导出 `.riv` 交付 | Publish 导出 → 组件规则 → 字体 Embedded → 运行时验收 | `references/delivery.md` |
| 运行时验收 | `assets/runtime-check-index.html` + 本地静态服务器 + Edge 无头截图 | `references/delivery.md` |
| 选运行时 / 上车机 | `webgl2` 优先，同屏多实例加 `useOffscreenRenderer`；Qt / Android / WebView 三条路线 | `references/runtime.md` |
| 交互做了但代码驱动不了 | 查 `inputs` / `dataBinds`（铁律 14）→ 补 ViewModel 触发并 `bindViewModelToArtboard` | `references/binding.md` |
| 打开慢 / 素材字体转圈 / 资产瘦身 | `listAssets` → 图片 `206` / 字体 `279` 审计 → `delete_objects` 删未使用 → fontTools 子集化 | `references/performance.md` |
| 桌面端一直 `Compiling` / 浏览器正常 | 先三层对照（同文件 / 别的文件 / 空白文件）→ 量进程 CPU 增量 + IO：CPU 涨 + IO≈0 = 本地在算 → 别找日志，客户端不写 | `references/desktop-compile.md` |
| 按钮按压 / 开关 / 激活态 | 浮层 + 橙点 → 30 帧动画 → ViewModel bool → Listener Action Script toggle → 一按钮一层状态机 | `references/toggle-button.md` |
| 沿路径电流 / 光带追尾 / 长度自适应 | 离线展平路径 → 沿法向铺窄条 → 顺时针绕序 + 圆头圆尾 → 加宽羽化叠加做辉光；`tail = car.dist - gap`，长度按进度 `clamp` | `references/aurora-path-fx.md` |
| 电流快慢节奏 / 光晕羽化蒙版 | 存进度 `prog` → bezier 缓动映射头部；蒙版 = 同一形状 8 层外扩（290→0）+ 每层 7.5% 叠加，`clipPath` 后先平移回画板坐标 | `references/effect-feather-easing.md` |

## 2. 铁律（违反任意一条都会浪费半小时以上）

> **备份策略**：默认**不导出** `.rev` 备份（`export_file` 走网络、易超时/失败）。任何写入或删除前，提醒用户自行在 Rive 里存快照；是否备份由用户决定，不阻塞改动。

1. `capture_artboard` 前必须 `focusArtboard`，否则返回**空白图**（连 `backgroundColor` 都不生效）；整幅纯黑是另一类问题，见铁律 12。
2. `animation_editor` 只作用于**活动画板**，`data.artboardId` 被静默忽略。
3. `export_file` 的 `destination` 传**目录**，不是文件路径。
4. 导出报 `HandshakeException` = 系统代理掐 TLS，**关代理**再导。
5. `upload_asset` 只认 **data URI**；传路径返回假 id `0-0`。上传后必须 `listAssets` 复查。
6. **一切属性写入必须回读验证**——批量 `set_property_values` 会静默失败（返回空 values）。
7. `.riv` 只装「默认画板 + 组件画板」；画板的 `includeInExport` 是**假开关**，判据是 `isComponent`。交付前逐画板核验或每屏拆一个文件。
8. 字体资产 `Type` 必须 **Embedded**；否则运行时中文永久豆腐（编辑器"等一会正常"是云端取字体的假象）。
9. AI 导 SVG 给 Rive 前，**文字必须转轮廓**（Type → Create Outlines）；否则 Rive 按 font-family 落到内置 Inter（无 CJK），中文全灭。
10. **后添加的对象垫底**（z 序）。先铺背景后放内容会翻车；放错了就删掉重加。
11. Illustrator COM 第一行设 `DONTDISPLAYALERTS`，否则弹窗挂死 COM；`Artboards` 集合**禁止 foreach** 枚举；文档名**精确匹配**（深色/浅色同前缀）。
12. `capture_artboard` 对部分画板稳定黑屏/403，且**可能返回陈旧渲染**——编辑器显示才是内容判据，验收交付用运行时页。
13. `.gitattributes` 必须有 `*.riv binary`。
14. 交互画板判据：`inputs == 0 && dataBinds == 0 && animStates >= 2` → 代码驱动不了。
15. PowerShell 5.1 读无 BOM 的 UTF-8 脚本会按 ANSI 解析——脚本输出用 ASCII，中文结果写文件再看。
16. 桌面编辑器**没有素材磁盘缓存**；每次打开从云端拉全量资产。打开慢先做资产审计，不要先改 DNS 或装系统字体。
17. `delete_objects` 也能删**资产 ID**（实测）；`upload_asset` 重名返回假 `0-0`，换唯一名后再用属性键 `203` 改名；幽灵 `0-0` 重启后消失。
18. 字体一直转圈 / Not Found 先验证字体文件；旧资产记录卡住时重传/子集化。子集化后必须校验字符覆盖、回读 `279`、截图对比，并提醒用户存快照。
19. 按压动效总时长 500ms = 按下 200ms + 抬起 300ms；不要做成 42 帧（200 + 500）。
20. 多个开关按钮必须一按钮一层状态机；同一个 Layer 塞多个按钮只能有一个保持激活。
21. 点击切换用 Listener Action Script 读 boolean 取反；脚本类型必须是 listenerAction，`context:viewModel()` 前必须绑定 ViewModel。
22. CLI 1.8.0 的 `rive --verify` / `--once` **无输出直接崩溃**（exit `3221226505` = `0xC0000409`）先查资产文件名：**非 ASCII 名（中文/全角括号）必崩**，同一份字节改成 `asset_NNN.<ext>` 就 `0 errors`。`gate.py --fix-names` 一键改。
23. `FontAsset exportTypeValue="referenced"` 是同一崩溃的第二诱因；缺这个属性表示 embedded，不算坑。`gate.py --fix-fonts` 一键改。
24. `rive pull` 在 1.8.0 必崩；拆工程用 `rive create <dir> --from-rev=<x.rev>`。`rive push --name` 只收 ASCII；CLI **没有删除远程文件**的命令，联调草稿会留在云端。
25. 同一 id 在目标里是顶层、在来源里嵌在画板内（或反之），合并后会出现重复 id，动画静默绑错对象——对已占用的 id 重新分配并重写子树引用，不能只按顶层判冲突。
26. **`addSvgInstance` 静默丢弃内嵌 `<image>`**：矢量全在、位图 0 个 Image 节点、不报错。位图必须 `upload_asset`(data URI) + `addImageInstance` 单独进；判据是数一遍 `types` 含 `Image` 的节点。
27. 图片实例的 `x/y` 是**原点**位置（`380/381` 默认 `50/50` 在中心）→ 填 `left+w/2, top+h/2`；`addImageInstance` **不接宽高**、按位图原生像素进场 → 回写 `sx`(16)/`sy`(17) 并回读 `810/811`；**新加对象落在 `children` 末尾 = 最底**，层序靠添加顺序排（铁律 36）。
28. **`clipPath` 不会被导入**：建出来的 Shape 是空的，圆角/异形遮罩要在位图 alpha 里烘焙（`svg-prep.py clip` 直接给几何）。
29. **AI 的中文图层名会变成方块**：导出时写成逐字节字符引用（声明 `iso-8859-1`），落成 `0x80–0x9F` 控制字符。只有图层名是中文的素材会中招，`rename_objects` 改回。
30. **素材导入的验收是像素比对**：参考侧导出 PNG，两侧 resize 到画板尺寸算平均差。**阈值是相对基线，不是常数**——先量「源 SVG vs 参考图」，判据取 `≤ 基线 + 0.3`。2048×1152 启动页基线≈0.1、结果 0.10–0.14；2560×1440 车机页基线 **1.40**、结果 **1.43** 同样 PASS。拿绝对 `0.5` 判会误杀后者。
31. `capture_artboard` 报 `has no drawable area`：①画板未激活（先 `focusArtboard`）②该画板 `computedwidth/height`(810/811) 卡成 0 ③**整机级离屏渲染故障**——判据是连以前能截的对照画板也挂、**所有**画板 810/811 都为 0。③别按①②的结论删画板重建（会白删），它**会自愈**，本轮约 40 分钟后恢复。
32. **导入慢先量再优**：一页 531 对象全链路 9.6 s（导出 4,893 / `upload_asset` 1,289 / `addSvgInstance` 2,213 / `verify` 321 ms）。`upload`+`addSvgInstance` 占 36% 且都在解析同一份 SVG，瘦身上游能一次降两处。但**别把单步当瓶颈**：同一批步骤用现成脚本 9.6 s、现写脚本实跑 65 s，差额全在"读输出→写脚本→再跑"的循环里。详见 `references/asset-import.md` 第十二节。
33. **位图的可见框 ≠ `<image>` 上的 `x/y/width/height`**：Figma 的 pattern 填充会叠 `clip-path` + `transform="rotate()"`。004 的车按 clip 矩形算出来是**空白**、按 `<image>` 矩形放**偏到画外**，真实是 `(1623,153.5) 114.5×47.5`。→ **别手算**：只放这一张图 + 全 `<defs>`、铺满画布透明渲染、取 alpha `getbbox()`。
34. **裁完必须断言"不是空的"**：`getbbox()` 是**该图自身像素坐标**，换算画布坐标时多乘一次缩放就裁到画布外——`PIL` 补透明，得到尺寸对、内容全空的 PNG，而资产 id / 节点 / `810`/`811` 全都正常。判据 `alpha.max() == 0`。
35. **导入卡在 `An SVG import is in progress` 永不释放**：判据是**读取类调用秒回**（`session_info`/`get_artboard_hierarchy`）、**渲染类全挂**（`addSvgInstance`/`capture_artboard`）= 编辑器主线程被占。两个真因：SVG 里有指向**已删除 `<mask>`** 的悬空引用；单份 SVG 太大（154 KB 拖死，拆成 4 份 26–62 KB 秒过）。`undo` 解不开，**只能重启桌面端**。
36. **层序**：`children` 的顺序是 top→bottom，新对象**追加到末尾 = 最底**，所以"先加的反而在上面"。→ **按"目标从上到下"依次添加，层序自动正确**，不用逐个 `sendToFront`。事后调整：`reorder_objects` 的参数是 **`operations[]`**，传 `objects` 报 `operations must be an array`。代价：位图插不回原组内部。
37. **`upload_asset` 的 data URI 里 `name=` 只收 ASCII**：中文报 `Illegal percent encoding in URI`。Rive 里想要的图层名走 `addSvgInstance` 的 `name` 参数（那里可以是中文）。
38. **刚建好的节点立刻写属性会被吞**（不只是"批量写"）：`addImageInstance` 后马上写 `sx/sy` 返回 `success: true` 但值不变 → 写后回读，不对再写。另：烘焙图是目标的 N 倍时，缩放 = `100 × 目标宽 / 位图真实像素宽`（4 倍图 → 25%）。
39. **SVG 的解析与转换在 Rive 服务端做**：报 `SVG conversion for asset X is unavailable` 就是这次转换失败，**同一资产重试无意义**，必须换新资产重传。等待是跨网络的，"慢"与"死"外层同形 → 用 `children` 里有没有出现该组来判定结果。
40. **服务端转换器不解析 `<use>`**（Figma 的图标/字形大量靠它）：轻则那块内容消失，重则整份资产转换失败。本地展开成内联 `<g transform="translate(…)">` + 深拷贝（拷完去掉 `id`）。
41. **`<use>` 展开后可能是空组**：引用的字形轮廓躺在 `<font>` 里、已被上游按"Rive 不消费 `<font>`"裁掉。展开后 0 条 `path` 就跳过，别重试（3 次 × 4 秒白等）。
42. **每组 SVG 别携带整份 `<defs>`**：按 `url(#…)` / `href="#…"` 引用闭包裁剪，只留本组走得到的。005 从 130–199 KB/组降到 1.3–1.8 KB，渲染不变。
43. **`addImageInstance` 可能不回 `nodeId`**（节点已建好）→ 回读 `children` 按 `name` 取 id。另：无 `clip`/`transform` 的位图直接取**原生像素**（scale 100%），比隔离渲染更准更省。
44. **粒子要跟随移动物体**：位姿只在对象脚本里算得出（本案例 `car_probe` 的 `PATH`+`sampleAt`），发射/更新/绘制都写进该脚本，别在另一个脚本里猜坐标。
45. **时间推进必须在开关判断之前**：`self.t += dt` 若放在 `if not ENABLED then return end` 之后，关掉一条粒子线会让另一条的噪声场冻结。
46. **`drawPath` 批绘共享透明度**：逐粒渐隐只能分年龄桶（有损）或用 `drawImageMeshInstanced` 的 per-instance opacity（精确）；官方无 compute、无 noise API，湍流需自写。
47. **开关按钮只关不开**：click 监听器挂 `viewModelChange` 常量 false，重复点击只写同一个值。改 `scripted` Listener Action 取反（`p.value = not p.value`）；旧 listener 用 `delete_objects` 删；`queryStateMachine` 复核 `actions[].scriptAssetId`；单向复位保留常量写入（`BindablePropertyBoolean` 键 634）。
48. **MCP 无建文本对象的命令**：中文标签走 fontTools 轮廓 → 定尺寸 SVG → `upload_asset` + `addSvgInstance`；外层 `Node` 只是壳，SVG 变换在子 `Group`（`810/811`=0、取不到顶点），落点用 `capture_artboard` 验收；别在缩放组里再套 translate（276px 事故）。
49. **路径光带整条不可见但 0 error** → 填充多边形绕序反了（画布 y 向下，可见需顺时针）：`-n` 侧尾→头 → 头半圆 → `+n` 侧头→尾 → 尾半圆；先截图再怀疑透明度。
50. **两个画板要不同脚本/参数** → 共用同一 `scriptAsset` 时改常量互相污染。新脚本走 `manage_scripts.create`（可带 content，借 `scripts/rive_mcp.py` 读本地文件，别把 28 KB 塞进对话）；**MCP 没有 attach 接口**，脚本节点必须用户在目标画板右键添加，`duplicate_objects` 复制不了 ScriptAsset（报 not a Component），也别改属性 `848`。
51. **右键新建脚本节点落点错** → 默认画板中心 `(1280,720)` 且最上层：`set_property_values` 到父级坐标（如 `1639,682`）→ `reorder_objects` 压到地图之上、UI 之下。
52. **ScriptInputs 不能中文化** → 面板标签就是 ASCII 字段名（Luau 标识符不支持中文），改名会在重编译时重建对象（实测 `291-*`→`297-*`）并丢顺序；中文只写源码注释，顺序用 `reorder_objects` 对输入子对象 `sendToFront`，数值键 **243**、布尔 **245**。
53. **桌面端卡 `Compiling` 先分层**：浏览器同一文件正常、桌面打开别的文件也卡 → 客户端层，不要审计文件。桌面端**不写运行日志**（`LocalCache` 只有 prefs + Sentry，正常时 breadcrumb 0 字节）；量进程：CPU 持续增长 + IO≈0 = 本地在算，不是网络。
54. **删 `editorProperties` / 改 `fileSafeMode` 不算"重载编辑器数据"**：`editorProperties` 打开文件即从文档重建；`fileSafeMode=true` 被客户端写回 `false`。本轮最终靠「卸载 + 删包数据 + 装最新版」恢复，但版本与安装方式两变量同时改变，不能归因单项。
55. **改已有 listener 的 action**：~~没有 update 命令，只能删了重建~~ → 已被第 58 条取代：直接 `set_property_values` 改 `scriptAssetId`（键 `930`），删监听重建只作兜底。
56. **`find_objects` 按节点名搜**，中文是画面文字不是节点名；用 `BTN_` / `TXT_` 核对每画板各 3 条防重复副本。「全部开关」主开关 `next = not (sandOn and dustOn)`：两个都开才全关，否则全开。
57. **跨文件粘贴只丢脚本，不丢 ViewModel**：画板 / 状态机 / 动画 / ViewModel 与条件里的 `viewModelId` 都会跟过去，唯独脚本资产不带——监听动作 `scriptAssetId` 变 `0-0`，点击无反应且不报错。`manage_scripts` 重建 → 重指 → 回读 + 预览点击；**不要重建 VM**（会多份同名，以 `conditions` 引用的 id 为准）。
58. **ListenerAction 的 `scriptAssetId` 是键 `930`，可直接改**：与节点脚本的 `848` 不通用（`848` 改完不重绑，`930` 改完立即生效）；字符串键报 `invalid_property_key`。
59. **"点击没反应"先排除编辑器卡顿**：本轮 12 个按钮实为卡顿，预览恢复后全部正常；先重开预览再查绑定。

## 3. 脚本速用

```powershell
# 单次 MCP 调用（图片可落盘）
.\scripts\rive-mcp.ps1 -Tool session_info
.\scripts\rive-mcp.ps1 -Tool capture_artboard -ArgsJson '{"artboardId":"0-1","longEdge":1024}' -OutImage out.png

# 批量调用改 Python（PowerShell -File 会吞 JSON 双引号 → Invalid JSON primitive）
#   CLI：python .\scripts\rive_mcp.py <tool> '{"json"}' [--out shot.png]
#   导入：from rive_mcp import connect, call_text
#         sid = connect(); call_text("query_property_values", {"propertyKeys": {"15-1": [7]}}, sid)
python .\scripts\rive_mcp.py query_property_values '{"propertyKeys":{"15-1":[7,8]}}'

# 全画板指纹体检（输出 TSV）
.\scripts\rive-audit.ps1 -OutFile audit.tsv

# .rev 整包导入（先在编辑器里切到目标文件，脚本轮询等待）
.\scripts\rive-import.ps1 -TargetFileId 2682212 -RevPath D:\export\src.rev

# Illustrator 导出 SVG（精确文件名匹配 + 全部 COM 防呆；-OutlineText 转轮廓）
.\scripts\ai-svg-export.ps1 -FileName '261026x01深色.ai' -SourceAi 'D:\src\261026x01深色.ai' -OutSvg 'D:\out\dark.svg' -OutlineText

# 整文件合并且不清空目标（Python 3.8+，无第三方依赖；rmlcore.py 为共享库）
python .\scripts\rive-merge\rml_merge.py --target work\tgt --source work\src --out work\out `
    --target-rev 目标.rev --source-rev 来源.rev --prune-orphans
python .\scripts\rive-merge\fill_assets.py --dir work\out --rev 目标.rev --rev 来源.rev --from work\src
python .\scripts\rive-merge\gate.py --dir work\out --fix --verify      # 必须 PASS 再 push
python .\scripts\rive-merge\rev_assets.py --rev 目标.rev --rml work\tgt\scene.rml   # .rev ↔ 工程资产审计
python .\scripts\rive-merge\rmlcore.py --selftest

# 素材导入五件套：清理 → 解位图 → 解剪裁 → 遮罩 → 像素比对
python .\scripts\svg-prep.py clean  D:\out\dark.svg D:\out\dark_rive.svg
python .\scripts\svg-prep.py images D:\out\dark_rive.svg --outdir D:\out\img --json D:\out\img.json
python .\scripts\svg-prep.py clip   D:\out\dark_rive.svg
python .\scripts\svg-prep.py mask   D:\out\img\a.png D:\out\img\a_m.png --img-rect 786.893,455.857,126.214,168.286 --clip 788,478,124,124,20.571
python .\scripts\svg-prep.py verify D:\out\shot.png D:\out\ref.png --size 2048x1152
```

导出 SVG 后的固定后处理不再靠手写正则：`svg-prep.py clean` 一次做掉裁 `<font>`（实测 25 MB → 80 KB）、展开内联 `style="fill:..."` 为表现属性（Rive 不解析 style）、按 viewBox 补 `width/height`。

## 4. 排障路由（症状 → 解法）

| 症状 | 解法 |
|---|---|
| 导出报 `HandshakeException` | 关系统代理 |
| `upload_rev` 报 requires no artboards | 删光目标画板再导 |
| 截图整幅空白 | 画板未激活（连背景色都不生效） | 先 `focusArtboard` 再抓 |
| 截图纯黑 / 403 `UNACCESSIBLE` | Early Access 离屏渲染 bug，与内容无关 | 以编辑器显示为准；换对照画板确认服务没挂（铁律 12） |
| 运行时中文全是 ▯ | 字体 `Type=Embedded`；SVG 导入的文字查 fontassetid 是否落到 Inter |
| 交互画板上机动不了 | 按 14 补 ViewModel 触发（`references/binding.md`） |
| `.riv` 画板数比源文件少 | 组件规则（7），拆文件或标组件 |
| 层级顺序不对 | 后添加垫底——删掉重加（`reorder_objects` 的 order 枚举未文档化） |
| 写入"成功"但没生效 | 回读验证；逐个写 |
| 打开文件慢 / 素材转圈 | 无磁盘缓存；先资产审计，删未使用，必要时字体子集化（`references/performance.md`） |
| 想删资产但在 `assets_tool` 里找不到命令 | 它没有 delete；资产当对象删：`delete_objects({"objectIds":["资产id"]})`，删前逐画板扫 `206` 引用数为 0 |
| 新建画板跑到了画布别的角落 | `createArtboard` 自动挑空位（`x/y` 别传），建完用 `arrangeArtboard` 摆到目标坐标；`listArtboards` 顺序按 id 数值排，不是创建顺序 |
| 字体一直转圈 / Not Found | 旧资产记录卡住；fontTools 验证后重传/子集化；不要改 DNS |
| 本机装同名字体无效 | 编辑器只用 Google Fonts / 上传字体；本地字体仅 CLI 项目可用 |
| 要删未使用资产 | `delete_objects` 传资产 ID；删前提醒用户存快照，删后回读 `206`/`279` |
| `rive --verify` 无输出直接崩（exit `3221226505`） | 资产文件名转 ASCII（`gate.py --fix-names`）；再查 `exportTypeValue="referenced"` 的字体 |
| 要在**已有内容**的文件上并入另一个文件 | 走 CLI 合并管线，不要 `upload_rev`（它要求目标为空），见 `references/merge.md` |
| `rive pull` 崩溃 / 拿不到 CLI 工程 | 1.8.0 已知必崩；改用 `rive create <dir> --from-rev` |
| **`addSvgInstance` 后位图全没了** | 内嵌 `<image>` 被静默丢弃；位图单独 `upload_asset` + `addImageInstance`（铁律 26） |
| **位图偏左上半个 / 截图里看不见 / 尺寸不对** | 原点在中心、新对象垫底、按原生像素进场（铁律 27） |
| **圆角图标导入后白底直角外露** | `clipPath` 不导入；用 `svg-prep.py clip` 取几何烘焙 alpha（铁律 28） |
| **Layers 里中文名变方块** | 中文图层名被逐字节转义成控制字符；`rename_objects`（铁律 29） |
| **位图导进去了，但编辑器里是空的** | 裁剪坐标二次缩放，PNG 全透明（尺寸却对） | 裁完断言 `alpha>8` 像素数 > 0（铁律 34） |
| **位图偏到画外 / 按 clipPath 算出来是空白** | 可见框 ≠ `<image>` 矩形（pattern + rotate 叠加） | 隔离渲染取 alpha bbox（铁律 33） |
| **导入卡在 in progress，之后所有导入都被拒** | 悬空 `mask` 引用、或单份 SVG 过大 | 清引用属性、按组拆分；只能重启桌面端（铁律 35） |
| **所有画板截图都报 `has no drawable area`** | 整机级离屏渲染故障，不是画板问题 | 别删画板，等它自愈（铁律 31） |
| **报 `SVG conversion for asset X is unavailable`** | 服务端转换失败，同一资产重试无效 | 换新资产重传；先查 `<use>`、悬空引用、体积（铁律 39） |
| **整组内容消失，原文件里有 `<use>`** | 服务端转换器不解析 `<use>` | 本地展开成内联 `<g>`（铁律 40） |
| **`<use>` 展开后该组 0 条 path** | 引用的字形轮廓已被上游裁掉 | 跳过该组，别重试（铁律 41） |

完整 84 行对照表：`references/pitfalls.md`。表里没有的症状，先去那里按关键词搜一遍，再决定读哪篇。

## 5. 参考文件（按需加载）

- `references/pitfalls.md` —— 坑位速查（端点/命令/值格式/84 行对照）
- `references/mcp.md` —— MCP 40 工具分组、实测行为、联调套路
- `references/cli.md` —— CLI 与 RML：项目结构、三查、值格式、签名与水位印
- `references/audit.md` —— 画板体检与交付整理：八项指纹、六类高频问题、整理顺序
- `references/transfer.md` —— 跨文件搬运全流程与核验
- `references/merge.md` —— 无清空合并：四步 CLI 管线、冲突语义、0xC0000409 三坑、push 回写
- `references/asset-import.md` —— Illustrator → SVG → Rive 全链路（含 COM 防呆）
- `references/delivery.md` —— 导出规则、字体内嵌、验收清单
- `references/runtime.md` —— 运行时选型与车机落地：四个 Web 包、三条路线、上机前五项确认
- `references/binding.md` —— 数据绑定与状态机驱动：两套模型、三个绑定坑、无头验证
- `references/performance.md` —— 打开慢/素材字体转圈：无磁盘缓存、资产审计、`delete_objects` 删资产、字体子集化
- `references/desktop-compile.md` —— 桌面端卡 `Compiling`：分层对照、无运行日志、CPU/IO 判据、无效操作与归因边界
- `references/capture-stale.md` —— capture 与陈旧渲染：focus 前置、403/黑屏、旧图判据
- `references/context-drawimage.md` —— Context 取素材与 drawImage
- `references/patheffect-flow.md` —— PathEffect 描边流动
- `references/text-editor-limits.md` —— text_editor 批量编辑边界
- `references/keyframes-mcp.md` —— 关键帧动画 MCP 实操
- `references/keyframe-loop.md` —— 关键帧循环防倒飞
- `references/layered-glow.md` —— 多图层叠辉光
- `references/particle-gather.md` —— 粒子汇聚
- `references/energy-ring.md` —— 能量光圈
- `references/pulse-glow.md` —— 脉冲辉光与呼吸灯
- `references/effects-index.md` —— 效果索引
- `references/artboard-breathe.md` —— 画板素材的代码驱动缩放呼吸
- `references/luau-procedural.md` —— 程序化动画 Luau 脚本
- `references/editor-2026-ui.md` —— 编辑器 2026 界面变更对照
- `references/script-node-install.md` —— 脚本节点安装边界
- `references/script-color-units.md` —— 脚本颜色与透明度量纲
- `references/path-geometry.md` —— 路径几何与坐标系映射
- `references/car-follow-path.md` —— 车沿路径走（drawImage 驱动）
- `references/toggle-button.md` —— 按钮开关/按压：500ms 总时长、浮层/橙点、脚本 toggle、一按钮一层
- `references/aurora-path-fx.md` —— 沿路径电流/光带：参数解码、追尾与长度自适应、圆头圆尾、辉光分层、双画板双脚本
- `references/effect-feather-easing.md` —— 电流缓动（进度模型 + bezier）与羽化蒙版（8 层外扩、坐标对齐、性能取舍）
- `references/sand-dust-trail.md` —— 车尾沙尘：沙粒 + 灰尘双层粒子、分桶批绘、发射跟随
- `assets/runtime-check-index.html` —— 运行时验收页（配 `npm i @rive-app/webgl2` + 静态服务器）

## 6. 来源与同步

- 本技能是 [Simiely/rive-tips](https://github.com/Simiely/rive-tips) 的技能化快照；34 篇 `references/` 一一对应仓库 `docs/`（`pitfalls.md` 即 `速查表.md`）。同步复制时会重写相对链接，所以本目录没有 `docs/` 也能正常跳转。
- 仓库文档更新后，在仓库根目录运行 `tools/sync-skill.ps1 -Install` 重新同步快照并刷新安装目录——**不要手改 references/**，改仓库的 docs。`tools/sync-skill.ps1 -Check` 只校验不写入（漂移 / 未映射文档 / 死链）。
