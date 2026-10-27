# CHANGELOG

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
