# CHANGELOG

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
