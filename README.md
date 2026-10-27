# Rive 使用技巧速查

Rive 实操技巧速查手册，按主题索引。内容经官方文档核实 + 实际验证，每个主题含 **场景 → 做法 → 坑**。

遵循 knowledge-base [单项目规范](https://github.com/Simiely/knowledge-base/tree/main/模板库/单项目规范)。

## 这是什么

记录在 Rive（桌面版 1.9.x / CLI 技术预览）实战中验证过的做法。当前覆盖：

| # | 主题 | 一句话 |
|---|---|---|
| 1 | [MCP 接入与联调](docs/MCP接入与联调.md) | 桌面版内置本地 MCP（`127.0.0.1:9791`），AI 能直接读写正在编辑的文件、截图自查、无头跑状态机 |
| 2 | [CLI 与 RML 工作流](docs/CLI与RML工作流.md) | `rive create` 把动效变成文本工程，实时预览 + 三查（verify / inspect / screenshot），可进 Git |
| 3 | [跨文件搬运画板](docs/跨文件搬运画板.md) | 剪贴板跨文件粘贴**会随机丢内容**；正解是 `.rev` 导出导入 + 指纹核验 |
| 4 | [画板体检与交付整理](docs/画板体检与交付整理.md) | 说明书 ≠ 交付件：驱动入口缺失、命名撞车、尺寸差 1px、双份实现怎么查 |
| 5 | [运行时选型与车机落地](docs/运行时选型与车机落地.md) | 四个 Web 包的取舍、Qt / Android / WebView 三条车机路线、上机前五项确认 |
| 6 | [数据绑定与状态机驱动](docs/数据绑定与状态机驱动.md) | State Machine Input 与 ViewModel 两套模型、三个高频绑定坑、怎么验证交互真的会跳 |
| 7 | [AI 素材导入链路](docs/AI素材导入链路.md) | Illustrator 脚本导出 SVG → 文字转轮廓 → data URI 上传 → 放置验收，全链路防呆 |
| 8 | [导出规则与交付验收](docs/导出规则与交付验收.md) | `.riv` 只装「默认画板+组件」、字体必须 Embedded、运行时验收才是判据 |
| 9 | [性能诊断与资产瘦身](docs/性能诊断与资产瘦身.md) | 打开慢/素材字体转圈：无磁盘缓存、资产审计、`delete_objects` 删资产、字体子集化 72 MB → 2 MB |
| 10 | [按钮开关与按压动效](docs/按钮开关与按压动效.md) | 单图标 toggle：500ms = 200ms 按下 + 300ms 抬起、B4B4B4 35% 浮层、橙点、Listener Action Script、一按钮一层 |
| 11 | [速查表](docs/速查表.md) | 一页纸：端点、命令、值格式、坑位对照 |

> 说明：颜色管理、音频事件、GPU Canvas / 3D、Flash 导入、Semantics 无障碍等主题，因未在本环境逐一验证，暂不收录，验证后再补。

## 文档

- [📖 速查表（一页纸总览）](docs/速查表.md)
- [🤖 AGENTS.md（给 AI / 未来的你：关键坑速记）](AGENTS.md)
- [🔧 DEVELOPMENT.md（架构说明与问题记录）](DEVELOPMENT.md)
- [📜 CHANGELOG.md（版本历史）](CHANGELOG.md)

## 脚本

`scripts/` 下是配合 MCP 用的 PowerShell 工具，参数化、不含本机路径：

| 脚本 | 用途 |
|---|---|
| [`rive-mcp.ps1`](scripts/rive-mcp.ps1) | MCP 单次调用封装：`-Tool <工具名> -ArgsJson '<json>'`，图片可落盘 |
| [`rive-audit.ps1`](scripts/rive-audit.ps1) | 遍历所有画板采集指纹，输出 TSV（体检 / 搬运后核验） |
| [`rive-import.ps1`](scripts/rive-import.ps1) | `.rev` 整包导入：等待目标文件激活 → 清空画板 → 导入 → 报告 |
| [`ai-svg-export.ps1`](scripts/ai-svg-export.ps1) | 驱动运行中的 Illustrator 导出 SVG（COM + 全部防呆），供 Rive 导入 |

工具：[`tools/runtime-check/`](tools/runtime-check/) —— 本地运行时验收页，列出 `.riv` 实际包含的画板并渲染，是"能不能交付"的判据。

Agent Skill：[`skills/rive-ops/`](skills/rive-ops/) —— 把本库精华打包成 WorkBuddy 技能（SKILL.md + 4 个脚本 + 7 篇参考 + 验收页），安装到 `~/.workbuddy/skills/rive-ops/` 即可在对话中自动触发。**改 docs 后运行 `tools/sync-skill.ps1 -Install` 保持技能与文档同步**（`references/` 是 `docs/` 的快照）。

## 三个最容易踩的坑

1. **导出 `.rev` 时被系统代理掐死** —— 报 `HandshakeException`，看起来完全不像网络问题。关代理再来。
2. **`capture_artboard` 抓空白** —— 画板没激活。先 `focusArtboard`。
3. **跨文件粘贴丢内容** —— 不是手误。走 `.rev`，见 [主题 3](docs/跨文件搬运画板.md)。

## 官方参考

- [Rive 运行时文档](https://rive.app/docs/runtimes)
- [Rive CLI](https://rive.app/docs/cli/overview) ｜ [RML](https://rive.app/docs/runtimes/advanced-topic/rml)
- [MCP Integration](https://rive.app/docs/editor/ai/mcp) ｜ [Working with AI Agents](https://rive.app/docs/cli/agents)
- [Canvas vs WebGL2](https://rive.app/docs/runtimes/web/canvas-vs-webgl)
- [Data Binding](https://rive.app/docs/editor/data-binding)

## 快速开始

- **想让 AI 直接改你正在编辑的文件** → [MCP 接入与联调](docs/MCP接入与联调.md)
- **想从零用代码生成动效 / 进 Git** → [CLI 与 RML 工作流](docs/CLI与RML工作流.md)
- **画板要搬到另一个文件** → [跨文件搬运画板](docs/跨文件搬运画板.md)
- **动效要交给开发上机了** → [画板体检与交付整理](docs/画板体检与交付整理.md)
- **打开文件很慢 / 素材字体一直转圈** → [性能诊断与资产瘦身](docs/性能诊断与资产瘦身.md)
- **不确定选哪个运行时** → [运行时选型与车机落地](docs/运行时选型与车机落地.md)
- **交互做了但代码驱动不了** → [数据绑定与状态机驱动](docs/数据绑定与状态机驱动.md)
