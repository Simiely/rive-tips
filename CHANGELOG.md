# CHANGELOG

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
