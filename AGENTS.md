# AGENTS.md — 给 AI / 未来的你：关键坑速记

> 📌 **文档基线**：2026-11-18 v1.14.1（`85bfc82`）—— 规范 2.1.4 拆分：结论第 13–71 条入 `rules/结论与坑.md`｜前序 2026-11-16 v1.14.0（`77a2bb1`）—— 补「动态效果定义表（SVG）」「icon 图形填充」+ 插值曲线编辑节｜同日 repo-kit 2.5.3 / 规范 2.1.2（`f1e95e2`，link-only）　← 前序：2026-11-13 v1.13.0（`ab31035`）
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

> **第 13 条起（共 60 条）见 @rules/结论与坑.md** —— 编号保持原样，与「坑位 N」引用一致，别在这里重排。

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
- "双击 Rive 完全没反应 / 进程 1 秒内退出 / 分不清是卡死还是没启动" → [docs/桌面端打不开排查.md](docs/桌面端打不开排查.md)
- "把动效整理成规范文档 / 什么时间做什么 / 给开发复刻节奏" → [docs/动态效果定义表（SVG）.md](docs/动态效果定义表（SVG）.md)
- "图标从下往上填满 / 涨水效果 / 半缺环绕行 / 缺口被填满了" → [docs/效果-icon图形填充.md](docs/效果-icon图形填充.md)
- "要做按钮按压 / 开关 / 激活态动效" → [docs/按钮开关与按压动效.md](docs/按钮开关与按压动效.md)
- "把脚本画的车/素材换掉 / 只换了图片节点结果车不动了" → [docs/车沿路径走（drawImage驱动）.md](docs/车沿路径走（drawImage驱动）.md) §八 换车
- "换了图标/辉光之后动画不跳了 / 跳是跳了但位置偏了、放大往右下跑" → [docs/换素材后动画不生效.md](docs/换素材后动画不生效.md)
- "做底盘脉冲扩散 / 多圈光环循环外扩 / 渐变环边缘发虚偏亮" → [docs/效果-径向渐变扩散环.md](docs/效果-径向渐变扩散环.md)
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
- **枚举分两类**：**主题类**新增/删除只改 `README.md` 主题表 + 本文件 FAQ 路由；**效果类**（`效果-*.md`）登记在 `docs/效果索引.md`，同时在选型树里看是否需要新增分支。`DEVELOPMENT.md` 的树只写层级与职责，不补文件名、更不写篇数（v1.0.0→v1.4.0 期间就在那棵树上腐化了 5 篇文档，2026-11-13 又发现树里的「12 篇」早已是 34 篇）
- **技能同步**：`skills/rive-ops/references/` 是 `docs/` 的快照，`skills/rive-ops/scripts/` 顶层文件是 `scripts/` 的字节副本。改任何 docs 或顶层 scripts 后必须运行 `tools/sync-skill.ps1`（加 `-Install` 同时刷新安装目录）；同步会按映射表把 `](中文名.md)` 重写成 `](英文名.md)`，所以快照里没有 docs 也能点开链接。`tools/sync-skill.ps1 -Check` 只校验不写入：`DRIFT` / `MISSING SCRIPT` / `SKILL-ONLY` / `STALE COUNT`（`SKILL.md` 里引用的坑位数与真实表行数不符）/ `BOM IN SKILL.md`（PS 5.1 写文件带的 BOM 会顶掉 frontmatter 的 `---`）/ 死链，任一命中就返回非零退出码（`scripts/rive-merge/` 是技能独有目录，不参与同步）。**改 `SKILL.md` 别用 `Set-Content -Encoding UTF8`**，用能控制 BOM 的方式写
- **入库流程**：新增/修改文档的完整 7 步（含最容易漏的「进 `$map` 映射表」与「跑 `-Install`」）、`-Check` 的七类校验、四个必须维护的数字，全部在 [CONTRIBUTING.md](CONTRIBUTING.md)。本节与脚本头部注释只讲原则，不复述步骤

## 常用命令

```powershell

# ⛔ 第一铁律：Rive MCP 调用绝不猜形状

**任何 MCP 工具调用的 `data` 结构，必须先离线读契约再发**（`probe/tools.json` 里每个工具的 `inputSchema.properties.data` 就是完整契约，不需要 Rive 运行）。猜错形状的代价是分级的：

- 轻则**静默丢弃**：字段被忽略、返回 success 但什么都没发生（坑位 33：createViewModels 内联 properties，见 @rules/结论与坑.md）；
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
