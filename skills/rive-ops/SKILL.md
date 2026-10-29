---
name: rive-ops
description: This skill should be used when working with Rive — desktop MCP integration, editing artboards, importing Illustrator (.ai) assets, transferring artboards between files, merging a whole file into another without clearing it, exporting .riv deliverables, auditing artboards, diagnosing slow file loads / asset bloat / font loading, or diagnosing Rive text/font/z-order/rendering issues. Packages field-verified PowerShell helpers, a runtime acceptance page, and pitfall references collected from production work (Chinese).
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
| Illustrator 素材导入 | `scripts/ai-svg-export.ps1 -OutlineText` → `svg-prep.py clean/images/clip` → data URI 上传 → `addSvgInstance` 铺矢量 → 位图单独 `addImageInstance` + 三坑 → `svg-prep.py verify` | `references/asset-import.md` |
| 导出 `.riv` 交付 | Publish 导出 → 组件规则 → 字体 Embedded → 运行时验收 | `references/delivery.md` |
| 运行时验收 | `assets/runtime-check-index.html` + 本地静态服务器 + Edge 无头截图 | `references/delivery.md` |
| 选运行时 / 上车机 | `webgl2` 优先，同屏多实例加 `useOffscreenRenderer`；Qt / Android / WebView 三条路线 | `references/runtime.md` |
| 交互做了但代码驱动不了 | 查 `inputs` / `dataBinds`（铁律 14）→ 补 ViewModel 触发并 `bindViewModelToArtboard` | `references/binding.md` |
| 打开慢 / 素材字体转圈 / 资产瘦身 | `listAssets` → 图片 `206` / 字体 `279` 审计 → `delete_objects` 删未使用 → fontTools 子集化 | `references/performance.md` |
| 按钮按压 / 开关 / 激活态 | 浮层 + 橙点 → 30 帧动画 → ViewModel bool → Listener Action Script toggle → 一按钮一层状态机 | `references/toggle-button.md` |

## 2. 铁律（违反任意一条都会浪费半小时以上）

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
18. 字体一直转圈 / Not Found 先验证字体文件；旧资产记录卡住时重传/子集化。子集化后必须校验字符覆盖、回读 `279`、截图对比，并保留全量字体 `.rev`。
19. 按压动效总时长 500ms = 按下 200ms + 抬起 300ms；不要做成 42 帧（200 + 500）。
20. 多个开关按钮必须一按钮一层状态机；同一个 Layer 塞多个按钮只能有一个保持激活。
21. 点击切换用 Listener Action Script 读 boolean 取反；脚本类型必须是 listenerAction，`context:viewModel()` 前必须绑定 ViewModel。
22. CLI 1.8.0 的 `rive --verify` / `--once` **无输出直接崩溃**（exit `3221226505` = `0xC0000409`）先查资产文件名：**非 ASCII 名（中文/全角括号）必崩**，同一份字节改成 `asset_NNN.<ext>` 就 `0 errors`。`gate.py --fix-names` 一键改。
23. `FontAsset exportTypeValue="referenced"` 是同一崩溃的第二诱因；缺这个属性表示 embedded，不算坑。`gate.py --fix-fonts` 一键改。
24. `rive pull` 在 1.8.0 必崩；拆工程用 `rive create <dir> --from-rev=<x.rev>`。`rive push --name` 只收 ASCII；CLI **没有删除远程文件**的命令，联调草稿会留在云端。
25. 同一 id 在目标里是顶层、在来源里嵌在画板内（或反之），合并后会出现重复 id，动画静默绑错对象——对已占用的 id 重新分配并重写子树引用，不能只按顶层判冲突。
26. **`addSvgInstance` 静默丢弃内嵌 `<image>`**：矢量全在、位图 0 个 Image 节点、不报错。位图必须 `upload_asset`(data URI) + `addImageInstance` 单独进；判据是数一遍 `types` 含 `Image` 的节点。
27. 图片实例的 `x/y` 是**原点**位置（`380/381` 默认 `50/50` 在中心）→ 填 `left+w/2, top+h/2`；`addImageInstance` **不接宽高**、按位图原生像素进场 → 回写 `sx`(16)/`sy`(17) 并回读 `810/811`；新加对象默认**垫底** → `sendToFront`。
28. **`clipPath` 不会被导入**：建出来的 Shape 是空的，圆角/异形遮罩要在位图 alpha 里烘焙（`svg-prep.py clip` 直接给几何）。
29. **AI 的中文图层名会变成方块**：导出时写成逐字节字符引用（声明 `iso-8859-1`），落成 `0x80–0x9F` 控制字符。只有图层名是中文的素材会中招，`rename_objects` 改回。
30. **素材导入的验收是像素比对**：`.ai` 导 PNG24 当参考图，两侧 resize 到画板尺寸算平均差。正确 0.10–0.14/255、错位 2.5–3.2/255，阈值 `0.5`。
31. `capture_artboard` 报 `has no drawable area`：一是画板未激活，二是该画板 `computedwidth/height`(810/811) 卡成 0 —— 写 w/h、`resizeArtboard`、改缩放都刷不回，**只能删画板重建**。
32. **导入慢先量再优**：一页 531 对象全链路 9.6 s（导出 4,893 / `upload_asset` 1,289 / `addSvgInstance` 2,213 / `verify` 321 ms）。`upload`+`addSvgInstance` 占 36% 且都在解析同一份 SVG，瘦身上游能一次降两处。但**别把单步当瓶颈**：同一批步骤用现成脚本 9.6 s、现写脚本实跑 65 s，差额全在"读输出→写脚本→再跑"的循环里。详见 `references/asset-import.md` 第十二节。

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
| 要删未使用资产 | `delete_objects` 传资产 ID；删前备份 `.rev`，删后回读 `206`/`279` |
| `rive --verify` 无输出直接崩（exit `3221226505`） | 资产文件名转 ASCII（`gate.py --fix-names`）；再查 `exportTypeValue="referenced"` 的字体 |
| 要在**已有内容**的文件上并入另一个文件 | 走 CLI 合并管线，不要 `upload_rev`（它要求目标为空），见 `references/merge.md` |
| `rive pull` 崩溃 / 拿不到 CLI 工程 | 1.8.0 已知必崩；改用 `rive create <dir> --from-rev` |
| **`addSvgInstance` 后位图全没了** | 内嵌 `<image>` 被静默丢弃；位图单独 `upload_asset` + `addImageInstance`（铁律 26） |
| **位图偏左上半个 / 截图里看不见 / 尺寸不对** | 原点在中心、新对象垫底、按原生像素进场（铁律 27） |
| **圆角图标导入后白底直角外露** | `clipPath` 不导入；用 `svg-prep.py clip` 取几何烘焙 alpha（铁律 28） |
| **Layers 里中文名变方块** | 中文图层名被逐字节转义成控制字符；`rename_objects`（铁律 29） |

完整 46 行对照表：`references/pitfalls.md`。表里没有的症状，先去那里按关键词搜一遍，再决定读哪篇。

## 5. 参考文件（按需加载）

- `references/pitfalls.md` —— 坑位速查（端点/命令/值格式/36 行对照）
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
- `references/toggle-button.md` —— 按钮开关/按压：500ms 总时长、浮层/橙点、脚本 toggle、一按钮一层
- `assets/runtime-check-index.html` —— 运行时验收页（配 `npm i @rive-app/webgl2` + 静态服务器）

## 6. 来源与同步

- 本技能是 [Simiely/rive-tips](https://github.com/Simiely/rive-tips) 的技能化快照；12 篇 `references/` 一一对应仓库 `docs/`（`pitfalls.md` 即 `速查表.md`）。同步复制时会重写相对链接，所以本目录没有 `docs/` 也能正常跳转。
- 仓库文档更新后，在仓库根目录运行 `tools/sync-skill.ps1 -Install` 重新同步快照并刷新安装目录——**不要手改 references/**，改仓库的 docs。`tools/sync-skill.ps1 -Check` 只校验不写入（漂移 / 未映射文档 / 死链）。
