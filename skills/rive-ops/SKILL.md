---
name: rive-ops
description: This skill should be used when working with Rive — desktop MCP integration, editing artboards, importing Illustrator (.ai) assets, transferring artboards between files, exporting .riv deliverables, auditing artboards, diagnosing slow file loads / asset bloat / font loading, or diagnosing Rive text/font/z-order/rendering issues. Packages field-verified PowerShell helpers, a runtime acceptance page, and pitfall references collected from production work (Chinese).
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
| 画板体检 / 搬运后核验 | `scripts/rive-audit.ps1`（八项指纹 → TSV） | `references/pitfalls.md` |
| 跨文件搬画板 | `export_file(rev)` → `scripts/rive-import.ps1` → 删多余 → 指纹核验 | `references/transfer.md` |
| Illustrator 素材导入 | `scripts/ai-svg-export.ps1` → 裁 `<font>` → data URI 上传 → `addSvgInstance` | `references/asset-import.md` |
| 导出 `.riv` 交付 | Publish 导出 → 组件规则 → 字体 Embedded → 运行时验收 | `references/delivery.md` |
| 运行时验收 | `assets/runtime-check-index.html` + 本地静态服务器 + Edge 无头截图 | `references/delivery.md` |
| 打开慢 / 素材字体转圈 / 资产瘦身 | `listAssets` → 图片 `206` / 字体 `279` 审计 → `delete_objects` 删未使用 → fontTools 子集化 | `references/performance.md` |

## 2. 铁律（违反任意一条都会浪费半小时以上）

1. `capture_artboard` 前必须 `focusArtboard`，否则返回黑屏。
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

## 3. 脚本速用

```powershell
# 单次 MCP 调用（图片可落盘）
.\scripts\rive-mcp.ps1 -Tool session_info
.\scripts\rive-mcp.ps1 -Tool capture_artboard -ArgsJson '{"artboardId":"0-1","longEdge":1024}' -OutImage out.png

# 全画板指纹体检（输出 TSV）
.\scripts\rive-audit.ps1 -OutFile audit.tsv

# .rev 整包导入（先在编辑器里切到目标文件，脚本轮询等待）
.\scripts\rive-import.ps1 -TargetFileId 2682212 -RevPath D:\export\src.rev

# Illustrator 导出 SVG（精确文件名匹配 + 全部 COM 防呆）
.\scripts\ai-svg-export.ps1 -FileName '261026x01深色.ai' -SourceAi 'D:\src\261026x01深色.ai' -OutSvg 'D:\out\dark.svg'
```

导出 SVG 后的固定后处理：正则裁掉 `<font>...</font>` 块（实测 25 MB → 80 KB）；若路径带的是内联 `style="fill:..."`，需展开为 `fill="..."` 表现属性（Rive 不解析 style 属性）。

## 4. 排障路由（症状 → 解法）

| 症状 | 解法 |
|---|---|
| 导出报 `HandshakeException` | 关系统代理 |
| `upload_rev` 报 requires no artboards | 删光目标画板再导 |
| 截图空白 / 黑屏 / 403 | 先 `focusArtboard`；仍黑则查编辑器（渲染 bug 家族，与内容无关） |
| 运行时中文全是 ▯ | 字体 `Type=Embedded`；SVG 导入的文字查 fontassetid 是否落到 Inter |
| 交互画板上机动不了 | 按 14 补 ViewModel 触发 |
| `.riv` 画板数比源文件少 | 组件规则（7），拆文件或标组件 |
| 层级顺序不对 | 后添加垫底——删掉重加（`reorder_objects` 的 order 枚举未文档化） |
| 写入"成功"但没生效 | 回读验证；逐个写 |
| 打开文件慢 / 素材转圈 | 无磁盘缓存；先资产审计，删未使用，必要时字体子集化（`references/performance.md`） |
| 字体一直转圈 / Not Found | 旧资产记录卡住；fontTools 验证后重传/子集化；不要改 DNS |
| 本机装同名字体无效 | 编辑器只用 Google Fonts / 上传字体；本地字体仅 CLI 项目可用 |
| 要删未使用资产 | `delete_objects` 传资产 ID；删前备份 `.rev`，删后回读 `206`/`279` |

完整 30 行对照表：`references/pitfalls.md`。

## 5. 参考文件（按需加载）

- `references/pitfalls.md` —— 坑位速查（端点/命令/值格式/30 行对照）
- `references/mcp.md` —— MCP 40 工具分组、实测行为、联调套路
- `references/transfer.md` —— 跨文件搬运全流程与核验
- `references/asset-import.md` —— Illustrator → SVG → Rive 全链路（含 COM 防呆）
- `references/delivery.md` —— 导出规则、字体内嵌、验收清单
- `references/performance.md` —— 打开慢/素材字体转圈：无磁盘缓存、资产审计、`delete_objects` 删资产、字体子集化
- `assets/runtime-check-index.html` —— 运行时验收页（配 `npm i @rive-app/webgl2` + 静态服务器）

## 6. 来源与同步

- 本技能是 [Simiely/rive-tips](https://github.com/Simiely/rive-tips) 的技能化快照；`references/` 对应仓库 `docs/`，`pitfalls.md` 即仓库的 `速查表.md`。
- 仓库文档更新后，在仓库根目录运行 `tools/sync-skill.ps1 -Install` 重新同步快照并刷新安装目录——**不要手改 references/**，改仓库的 docs。
