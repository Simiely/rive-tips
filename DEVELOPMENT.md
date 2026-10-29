# DEVELOPMENT.md — 架构说明与问题记录

## 项目概览

本仓库是 Rive 的使用经验库，不是代码项目。产出物是**文档 + 少量验证脚本**。

- **目标读者**：设计师（怎么用）、开发（怎么接）、AI（怎么自动改）
- **内容边界**：只写验证过的；官方文档能查到的写链接 + 结论，不整段搬运
- **不做的事**：不做 Rive 教程翻译，不做运行时源码分析

## 架构说明

```
rive-tips/
├── README.md            门面：主题索引（唯一枚举文件名的位置）+ 快速开始
├── AGENTS.md            给 AI：结论先行 + FAQ 路由 + 约定
├── DEVELOPMENT.md       本文件：架构 + 问题记录
├── CHANGELOG.md         版本历史
├── docs/                主题文档：一主题一篇（当前 12 篇，清单见 README 主题表）
├── scripts/             配合 MCP / CLI / 素材导入的验证脚本（PowerShell + Python，6 个）
├── tools/               runtime-check 验收页 + sync-skill 同步脚本
└── skills/rive-ops/     WorkBuddy 技能包：SKILL.md + scripts/ + references/（docs 快照）
```

**分层逻辑**：README 是索引，docs 是正文，scripts / tools 是"能跑的证据"，skills 是可安装的出口（`references/` 由 `tools/sync-skill.ps1` 从 docs 生成；`scripts/` 顶层文件按字节同步进 `skills/rive-ops/scripts/`；两者都不手改）。

**为什么这棵树只写层级**：v1.0.0 的树在这里逐篇列 docs 文件名，之后每加一篇就腐化一次，到 v1.4.0 已经少了 5 篇和 3 个目录。文件枚举集中在 README 一处，这里只描述职责。

**为什么按主题切、不按功能切**：读者的问题是"我要搬画板"而不是"我要用 `upload_rev`"。按场景切，一篇解决问题。

## 关键问题与方案

### 问题：导出 `.rev` 报 HandshakeException

**TL;DR**：系统代理（Clash/mihomo 一类）掐断了 App 内导出请求的 TLS 握手，关掉代理即可。

- 问题：`export_file` 反复失败，报 `RiveException: Issue with web service client GET, original message: HandshakeException: Connection terminated during handshake`，但 App 打开云端文件、编辑、截图全都正常
- 根因：桌面版（Flutter）导出走独立 HTTP 客户端，链路经过系统代理时握手被断。浏览器走同一代理正常，所以极易误判为"Rive 服务挂了"
- 解决：临时关闭系统代理 → 重新导出 → 成功后再打开代理。导出结果带 `embeddedAssets: true`，不依赖网络
- 预防：**导出类操作失败先隔离网络**（关代理 / 换网络），别在 App 里反复重试

### 问题：剪贴板跨文件粘贴随机丢内容

**TL;DR**：跨文件粘贴是在目标文件里重新序列化重建对象，图片 / mesh / 嵌套画板最容易掉；改用 `.rev` 文件级搬运。

- 问题：选中多个画板复制到另一个文件，有时内容不全，且**每次丢的还不一样**
- 根因：粘贴不是搬字节。官方更新日志有成串修复记录（图片、嵌套画板、mesh），说明这是结构性难点；多选 + 重资产画板会放大
- 解决：`export_file(rev)` → 删光目标画板 → `upload_rev(open_file)` → `delete_objects` 清理多余
- 预防：跨文件搬运一律走文件级；搬完用指纹逐画板核验，不靠肉眼

### 问题：`upload_rev` 导入被拒

**TL;DR**：`target=open_file` 要求目标文件**一块画板都没有**。

- 问题：报 `target open_file requires a file with no artboards; this file already contains an artboard and was left unchanged`
- 根因：导入语义是"把整包内容装进一个空文件"，不是"合并进现有文件"
- 解决：先 `delete_objects` 删光目标文件所有画板（含默认画板），再导入
- 预防：导入前先 `list_artboards` 确认数量为 0

### 问题：`capture_artboard` 返回空白图

**TL;DR**：画板未激活时截图为空，且 `backgroundColor` 不生效。

- 问题：对非活动画板截图，得到纯白图片，误以为资产没导进来
- 根因：渲染只对激活画板生效
- 解决：先 `open_file_editor {command: "focusArtboard"}`，再 `capture_artboard`
- 预防：批量截图时逐个 focus；把"空白图"当成"没激活"的第一嫌疑，而不是资产丢失

### 问题：`animation_editor` 传 artboardId 无效

**TL;DR**：该工具只作用于活动画板，`data.artboardId` 被静默忽略。

- 问题：三个不同画板传同一个参数，返回的是同一个状态机
- 根因：工具的定位是"操作当前编辑对象"，不做跨画板寻址
- 解决：`focusArtboard` 后再调用；批量采集时循环 focus
- 预防：写脚本时把 focus 当成调用前置条件，而不是可选优化

### 问题：`export_file` 报 destination directory 不可用

**TL;DR**：`destination` 要传**目录**，不是文件路径。

- 问题：传 `...\out\a.rev` 报 `destination directory is not usable ... (destination directory does not exist)`
- 根因：参数语义是"写到哪个目录"，文件名由 App 按文档名生成
- 解决：只传目录，例如 `...\out`；导出结果里读 `path` 拿真实文件名
- 预防：读参数说明时注意 "The file is written into destination" 这层含义

### 问题：PowerShell 5.1 执行脚本报"字符串缺少终止符"

**TL;DR**：无 BOM 的 UTF-8 脚本被按 ANSI 读取，中文变乱码导致解析失败。

- 问题：脚本里有中文输出，执行时报 `ParserError: 字符串缺少终止符`，位置指向中文行
- 根因：Windows PowerShell 5.1 默认按系统 ANSI 代码页读取无 BOM 文件
- 解决：脚本内**输出统一用 ASCII**，中文结果写 UTF-8 文件再用读取工具查看；或保存为带 BOM 的 UTF-8
- 预防：跨工具链的脚本一律 ASCII 输出，避免编码成为隐性依赖

### 问题：`rive --verify` / `--once` 无输出直接崩（`0xC0000409`）

**TL;DR**：不是内容损坏，是**资产文件名含非 ASCII**（中文、全角括号）。同一份字节改成 `asset_NNN.<ext>` 就 `0 errors, 0 warnings`。

- 现象：`rive --verify` / `--once` 立刻退出，stdout / stderr **全空**，退出码 `3221226505`（`0xC0000409`），看起来像内存不足或工程损坏
- 判定：`$LASTEXITCODE` 为 `-1073740791` / `3221226505` 且没有任何输出 → 按**文件名**查，不要按内容查。Rust 侧 panic=abort，不会给任何提示
- 根因（三组对照）：原始工程（中文文件名）崩 → 全部改成 ASCII 名后通过 → 只把字体文件名改回中文，再崩
- 第二诱因：`FontAsset exportTypeValue="referenced"`；缺这个属性表示 embedded，不算坑
- 解决：`gate.py --fix-names --fix-fonts`；或合并时保留脚本默认的 ASCII 改名
- 预防：合并管线里把 `gate.py --verify` 当**构建前闸门**，PASS 了才 `rive push`

### 问题：`addSvgInstance` 导入后位图整块消失

**TL;DR**：它把 SVG 里内嵌的 `<image>` 静默丢掉——矢量全在、位图 0 个节点、不报错。位图必须单独上传再放。

- 问题：含内嵌 PNG 的 2048×1152 SVG 导入后，画板的层级里数不到任何 `Image` 节点，但路径 / 填充 / 渐变一个不少
- 根因：`addSvgInstance` 只把矢量子树实例化成 Shape 树，内嵌位图不参与（工具说明里没提）
- 解决：`svg-prep.py images` 解出 base64 与目标矩形 → `upload_asset`(data URI) → `addImageInstance`
- 预防：导入后**数一遍** `types` 含 `Image` 的节点，与 SVG 里 `<image>` 的个数对齐；不相等就是丢了

### 问题：位图落位偏左上半个图标

**TL;DR**：Image 节点的 `x/y` 是**原点**位置，默认原点在中心（`380/381` = 50/50），不是左上角。

- 问题：按 SVG 里算出的 `x/y` 直接赋给 `addImageInstance`，图片整体偏左上，偏移量正好是自身宽高的一半（本案例 230×63.5）
- 根因：轴向位置与 transform origin 的关系；`x/y` 平移的是原点那个点
- 解决：`x = left + w/2`、`y = top + h/2`；或把 `380/381` 改成 0
- 另外两个连带坑：新加对象默认**垫底**（整屏背景色会盖住它）→ `sendToFront`；`addImageInstance` **不接宽高**，按位图原生像素进场 → 回写 `sx`/`sy` 百分比

### 问题：`clipPath` 不导入，圆角图标变白底直角

**TL;DR**：Rive 会为 `clipPath` 建一个空 Shape，遮罩不生效；圆角要烘进位图的 alpha。

- 问题：AI 里用剪切蒙版裁出的圆角图标，导入后四个角是白的，露出一块方形底
- 根因：位图本身是"白底满版"，圆角来自 Illustrator 的 mask；`clipPath` 不被 Rive 消费
- 解决：`svg-prep.py clip` 把 `clipPath` 解成 `x,y,w,h,r`，再 `svg-prep.py mask` 用 4× 超采样烘进 alpha；替换资产只写 `206`
- 判据：位图四角是否 `(255,255,255,255)` —— 全白不透明就说明它靠遮罩

### 问题：中文图层名变成方块

**TL;DR**：AI 导出把中文图层名写成逐字节字符引用（声明 `iso-8859-1`），落进 Rive 是控制字符，界面显示方块。

- 问题：Layers 面板里两个组名显示成方块 / `å_x90_…`
- 根因：UTF-8 字节被当成 latin-1 存储，`0x80–0x9F` 是控制字符
- 解决：还原成字节再按 UTF-8 解出原文（`启动页`、`懒人横版`），`rename_objects` 改回
- 预防：只有**图层名是中文**的素材会中招（同批另两个文件 id 全是 `Vector_…` / `Group_…`，一条都没有）；导出后把中文 `id` 清成 ASCII 即可

## 来源

- 问题 1、3、4、5、6 来自对 Rive 桌面版 MCP 的实操（2026-10-26）
- 问题 2 另有官方更新日志佐证：[changelog / copy-paste 修复](https://rive.app/changelog/improvements-to-tooltips-copy-paste-and-shortcuts)
- 问题 8 来自 CLI 合并实战（2026-10-28）：目标 8 画板 + 来源 33 画板 → 产出 35 画板 / 21343 元素，`0 errors, 0 warnings`；三组对照明细见 [无清空合并文件](docs/无清空合并文件.md)
- 问题 9–12 来自素材导入实战（2026-10-29）：三个 2048×1152 启动页，错位/遮罩/乱码三处均在像素比对与全量扫描下定位；明细见 [AI素材导入链路](docs/AI素材导入链路.md)
