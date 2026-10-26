# AGENTS.md — 给 AI / 未来的你：关键坑速记

> 📌 **文档基线**：2026-10-26（commit `2c0adb8`）完成四件套首次建立
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

## FAQ 路由

- "怎么让 AI 直接改我的 Rive 文件" → [docs/MCP接入与联调.md](docs/MCP接入与联调.md)
- "怎么用代码从零生成动效 / 进版本管理" → [docs/CLI与RML工作流.md](docs/CLI与RML工作流.md)
- "复制粘贴丢了东西 / 怎么把画板搬到另一个文件" → [docs/跨文件搬运画板.md](docs/跨文件搬运画板.md)
- "文件要交付给开发了 / 怎么体检" → [docs/画板体检与交付整理.md](docs/画板体检与交付整理.md)
- "用哪个运行时 / 怎么上车机" → [docs/运行时选型与车机落地.md](docs/运行时选型与车机落地.md)
- "交互做了但代码触发不了" → [docs/数据绑定与状态机驱动.md](docs/数据绑定与状态机驱动.md)
- 端点、命令、坑位一览 → [docs/速查表.md](docs/速查表.md)

## 约定

- 文档标题与文件名一致，中文命名，不带空格
- 每个主题含 **TL;DR → 主体 → 来源**，来源必须是官方文档链接或"本机实测 + 日期"
- 不写 token、本机绝对路径、账号邮箱
- 未验证的内容不写进正文；确需提及就标"暂未收录"
- 涉及数字（工具数、画板数、状态数）注明采集日期，Early Access 阶段会变

## 常用命令

```powershell
# MCP 是否在线
Test-NetConnection -ComputerName 127.0.0.1 -Port 9791

# 单次调用
scripts/rive-mcp.ps1 -Tool session_info
scripts/rive-mcp.ps1 -Tool capture_artboard -ArgsJson '{"artboardId":"0-1","longEdge":1024}' -OutImage out.png

# 体检
scripts/rive-audit.ps1 -OutFile audit.tsv

# 导入 .rev（需先在编辑器里切到目标文件）
scripts/rive-import.ps1 -TargetFileId 1234567 -RevPath D:\export\src.rev
```

## 备注

- MCP 与 CLI 的官方文档入口见各文档末尾「来源」
- Early Access 阶段工具集会变，脚本里不要硬编码能力假设
