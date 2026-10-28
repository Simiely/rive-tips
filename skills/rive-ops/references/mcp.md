# Rive 桌面版 MCP：接入与联调

**TL;DR**：Rive 桌面版内置一个本地 MCP 服务（`http://127.0.0.1:9791/mcp`），App 开着才有。接上之后 AI 能**直接读写你正在编辑的那个文件**——读选区、改场景、截图自查、无头跑状态机。这是"和 AI 一起联调"最直接的一条路。

> 更新时间：2026-10-27 ｜ 状态：**Early Access**，工具集会变，别写进团队强流程

## 一、前提

| 条件 | 说明 |
|---|---|
| 平台 | **仅桌面版** Windows / macOS（网页版没有） |
| 版本 | Early Access 构建 |
| 运行状态 | Rive **必须开着**——服务由 App 进程托管，关掉 App 端口就没了 |
| 端口 | `127.0.0.1:9791`，只监听本机回环，不对外 |

判断是否在线，不用猜：

```powershell
Test-NetConnection -ComputerName 127.0.0.1 -Port 9791
# TcpTestSucceeded : True  → 服务在
```

## 二、配置

任何支持 **Streamable HTTP** 传输的 MCP 客户端都能接，配置就三行：

```json
{
  "mcpServers": {
    "rive": {
      "url": "http://127.0.0.1:9791/mcp"
    }
  }
}
```

- **Cursor**：设置 → Tools & MCPs → Add Custom MCP → 填上面的 JSON → 打开开关
- **Claude Code（终端）**：`claude mcp add --transport http rive http://127.0.0.1:9791/mcp`
- **WorkBuddy**：写入 `~/.workbuddy/mcp.json`，再在连接器管理页右上角「自定义连接器」里点 **Trust**（不点不生效）

握手成功的标志是 `serverInfo` 返回：

```json
{"name":"rive","version":"0.6"}
```

## 三、能力面（40 个工具）

| 分组 | 工具 | 能干什么 |
|---|---|---|
| 会话/文件 | `session_info`、`open_file_editor` | 列出打开的标签、哪个是活动文件；建/改名/改尺寸/移动画板；撤销 |
| 读取 | `query_objects`、`find_objects`、`get_artboard_hierarchy`、`get_selection`、`query_property_values`、`query_property_keys` | 查层级、按名字找对象、读选中、读属性值 |
| 写入 | `set_property_values`、`rename_objects`、`delete_objects`、`duplicate_objects`、`reorder_objects`、`reparent_objects`、`select_objects` | 直接改场景 |
| 造型 | `path_editor`、`layout_editor`、`group_editor`、`property_group_editor` | 参数化图形、flexbox 布局、分组、自定义属性组 |
| 动画 | `animation_editor` | 线性动画、关键帧、状态机、层、状态、转换、条件；`simulateStateMachine` 无头验证 |
| 交互 | `create_listeners` | hover / click / drag 监听器 |
| 数据 | `viewmodel_editor` | ViewModel、属性、实例、数据绑定、converter、枚举 |
| 资产 | `assets_tool`、`upload_asset`、`delete_objects` | 列资产、实例化图片/SVG；上传；`delete_objects` 也可删资产 ID |
| 组件 | `component_editor`、`mesh_rigging_tool` | 组件实例与列表；网格绑定骨骼与权重 |
| 脚本 | `manage_scripts`、`text_editor`、`get_scripts`、`grep`、`script_diagnostics`、`run_tests`、`recompile_all_scripts`、`read_console`、`get_scripting_reference` | Luau / WGSL 的读写、诊断、测试、控制台 |
| 文件 | `export_file`、`upload_rev` | 导出 `.riv` / `.rev`；导入 `.rev` |
| 验证 | `capture_artboard` | 把画板渲染成 PNG——**让 AI 看见像素，而不是靠对象树猜** |

`capture_artboard` 是这套工具里最关键的一个：它把"改完了对不对"从推断变成了观察。

## 四、实测行为（文档没写的那些）

这些是踩出来的，写工具说明里没有：

1. **只能操作当前活动文件**。没有"打开另一个文件"的工具，也没有跨文件复制。想搬内容只能走 `.rev`（见 [跨文件搬运画板](transfer.md)）。
2. **`animation_editor` 只作用于活动画板**，传 `data.artboardId` 会被**静默忽略**——三个不同画板传同一个 id，返回的是同一个状态机。要查别的画板必须先 `focusArtboard`。
3. **`capture_artboard` 对未激活的画板返回空白图**，连 `backgroundColor` 都不生效。先 `focusArtboard` 再抓。
4. **`export_file` 的 `destination` 传目录，不是文件路径**。传 `...\out\a.rev` 会报 `destination directory is not usable`；传 `...\out` 才对，文件名由 App 决定。
5. **`upload_rev` 的 `target=open_file` 要求目标文件一块画板都没有**，否则报 `requires a file with no artboards` 并原样不动。先把画板删光。
6. **`simulateStateMachine` 会还原它写入的值**，跑完文档不变——可以放心用来验证；但它**不渲染像素**，只能看 trace（进入的 state、走过的 transition、触发的事件）。
7. **`export_file` 需要网络**。导出 `.rev` 时如果本机代理不通，会报 `HandshakeException: Connection terminated during handshake`——关掉系统代理再导。这个坑排查了很久，表现完全不像网络问题。
8. **`upload_asset` 只认 data URI**。传本地文件路径会返回 `{"success":true,"asset":{"id":"0-0",...}}`——假 id，资产列表里也找不到，而 `success: true` 很有迷惑性。正确形态：`data:image/svg+xml;name=x.svg;base64,<...>`。**上传后必须 `listAssets` 复查**。
9. **`capture_artboard` 存在"渲染失败家族"**：部分画板稳定输出纯黑或 403 `UNACCESSIBLE`，与内容无关（隐藏文字、重绑字体、改尺寸都不能解），疑似 Early Access 离屏渲染 bug。遇到黑屏先看**编辑器里**是否可见，别对着黑屏改数据。
10. **批量 `set_property_values` 可能静默失败**：返回 `{"success":true,"values":{}}` 但实际没写入。所有写入必须**回读验证**；逐个写比批量稳。
11. **`delete_objects` 也能删资产 ID**：把 `assets_tool/listAssets` 返回的资产 id 传进去即可，官方文档只写“删对象”。删前导 `.rev` 备份，删后回读 `206`/`279` 核验；假 `0-0` 幽灵条目删不掉，重启 App 后消失。
12. **`upload_asset` 重名会返回假 `0-0`**（data URI 也一样）：先传唯一名，再用属性键 `203` 改回原名；上传后 `listAssets` 复查。
13. **字体资产也是“对象”**：`TextStylePaint.fontassetid=279`、资产名 `203`、导出类型 `358`、Include `360`、CDN `362`/`359`；`size=211` 恒为 0。字体子集化与重绑见 [性能诊断与资产瘦身](performance.md)。
14. **面板 `Not Found`/转圈不等于数据缺失**：先用 `export_file(rev, embed_assets=true)` 拆包验证；旧资产记录卡住时重传同字形/子集化，不要改 DNS 或反复重传。

## 五、联调套路

一套顺手的循环：

```
① get_selection / get_artboard_hierarchy   → 知道现在是什么
② set_property_values / animation_editor    → 改
③ capture_artboard                          → 看结果（先 focusArtboard）
④ simulateStateMachine                      → 确认交互逻辑真的跳了
```

第 ③ 步和第 ④ 步是分开的，别混：截图证明**看起来对**，模拟证明**跑起来对**。一个绑定接错属性、或者图形画了但透明，前两步都过得去。

### 调用封装：别用 PowerShell 传 JSON

`scripts/rive-mcp.ps1` 做单次调用没问题，但 PowerShell `-File` 传参时会**吞掉 JSON 里的双引号**，服务端报 `Invalid JSON primitive: xxx`，看起来像连接失败。批量操作改用 `scripts/rive_mcp.py`：

```python
from rive_mcp import connect, call_text
sid = connect()
call_text("query_property_values", {"propertyKeys": {"15-1": [7, 8]}}, sid)
```

- 一次 `connect()` 复用同一个 session，几十次调用不用反复握手
- 参数是 Python dict，不存在引号转义问题
- 返回值直接 `json.loads`，便于按 id 建索引、批量生成关键帧

## 六、局限

- 不能跨文件操作，不能开关文件
- 不能按名字取状态机输入以外的东西——很多 API 要 objectId
- **`stateMachineInputs` 类交互和 ViewModel 是两套模型**，读的时候要先分清（见 [数据绑定与状态机驱动](binding.md)）
- Early Access，工具名和参数都可能变；脚本里别硬编码能力假设

## 来源

- 官方文档：[Rive MCP Integration](https://rive.app/docs/editor/ai/mcp)
- 官方文档：[Working with AI Agents](https://rive.app/docs/cli/agents)
- 本文第四节全部为本机实测（Rive 桌面版 1.9.x，2026-10-27）
