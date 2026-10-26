# DEVELOPMENT.md — 架构说明与问题记录

## 项目概览

本仓库是 Rive 的使用经验库，不是代码项目。产出物是**文档 + 少量验证脚本**。

- **目标读者**：设计师（怎么用）、开发（怎么接）、AI（怎么自动改）
- **内容边界**：只写验证过的；官方文档能查到的写链接 + 结论，不整段搬运
- **不做的事**：不做 Rive 教程翻译，不做运行时源码分析

## 架构说明

```
rive-tips/
├── README.md            门面：主题索引 + 快速开始
├── AGENTS.md            给 AI：结论先行 + FAQ 路由 + 约定
├── DEVELOPMENT.md       本文件：架构 + 问题记录
├── CHANGELOG.md         版本历史
├── docs/                主题文档（一主题一篇）
│   ├── MCP接入与联调.md
│   ├── CLI与RML工作流.md
│   ├── 跨文件搬运画板.md
│   ├── 画板体检与交付整理.md
│   ├── 运行时选型与车机落地.md
│   ├── 数据绑定与状态机驱动.md
│   └── 速查表.md
└── scripts/             配合 MCP 的验证脚本
    ├── rive-mcp.ps1
    ├── rive-audit.ps1
    └── rive-import.ps1
```

**分层逻辑**：README 是索引，docs 是正文，scripts 是"能跑的证据"。三层各自独立，改一层不影响另两层。

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

## 来源

- 问题 1、3、4、5、6 来自对 Rive 桌面版 MCP 的实操（2026-10-26）
- 问题 2 另有官方更新日志佐证：[changelog / copy-paste 修复](https://rive.app/changelog/improvements-to-tooltips-copy-paste-and-shortcuts)
