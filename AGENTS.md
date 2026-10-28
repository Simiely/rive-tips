# AGENTS.md — 给 AI / 未来的你：关键坑速记

> 📌 **文档基线**：2026-10-28 v1.4.0 —— 无清空合并（CLI 四步管线）；`0xC0000409` 真因是非 ASCII 资产文件名；改 docs 后必须跑同步（见「约定」）
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

## FAQ 路由

- "怎么让 AI 直接改我的 Rive 文件" → [docs/MCP接入与联调.md](docs/MCP接入与联调.md)
- "怎么用代码从零生成动效 / 进版本管理" → [docs/CLI与RML工作流.md](docs/CLI与RML工作流.md)
- "复制粘贴丢了东西 / 怎么把画板搬到另一个文件" → [docs/跨文件搬运画板.md](docs/跨文件搬运画板.md)
- "把 A 文件全部内容并进 B 且不能清空 B" → [docs/无清空合并文件.md](docs/无清空合并文件.md)
- "文件要交付给开发了 / 怎么体检" → [docs/画板体检与交付整理.md](docs/画板体检与交付整理.md)
- "用哪个运行时 / 怎么上车机" → [docs/运行时选型与车机落地.md](docs/运行时选型与车机落地.md)
- "交互做了但代码触发不了" → [docs/数据绑定与状态机驱动.md](docs/数据绑定与状态机驱动.md)
- "打开文件很慢 / 素材和字体一直转圈" → [docs/性能诊断与资产瘦身.md](docs/性能诊断与资产瘦身.md)
- "要做按钮按压 / 开关 / 激活态动效" → [docs/按钮开关与按压动效.md](docs/按钮开关与按压动效.md)
- 端点、命令、坑位一览 → [docs/速查表.md](docs/速查表.md)

## 约定

- 文档标题与文件名一致，中文命名，不带空格
- 每个主题含 **TL;DR → 主体 → 来源**，来源必须是官方文档链接或"本机实测 + 日期"
- 不写 token、本机绝对路径、账号邮箱
- 未验证的内容不写进正文；确需提及就标"暂未收录"
- 涉及数字（工具数、画板数、状态数）注明采集日期，Early Access 阶段会变
- **技能同步**：`skills/rive-ops/references/` 是 `docs/` 的快照。改任何 docs 后必须运行 `tools/sync-skill.ps1`（加 `-Install` 同时刷新安装目录），否则技能与文档漂移

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

# 无清空合并（Python 3.8+；脚本在 skills/rive-ops/scripts/rive-merge/）
python skills/rive-ops/scripts/rive-merge/rml_merge.py --target work\tgt --source work\src --out work\out --target-rev 目标.rev --source-rev 来源.rev --prune-orphans
python skills/rive-ops/scripts/rive-merge/fill_assets.py --dir work\out --rev 目标.rev --rev 来源.rev --from work\src
python skills/rive-ops/scripts/rive-merge/gate.py --dir work\out --fix --verify

# docs 更新后同步技能快照（-Install 同时刷新 ~/.workbuddy/skills/rive-ops）
tools/sync-skill.ps1 -Install
```

## 备注

- MCP 与 CLI 的官方文档入口见各文档末尾「来源」
- Early Access 阶段工具集会变，脚本里不要硬编码能力假设
