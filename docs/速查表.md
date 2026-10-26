# 速查表

一页纸装下常用的端点、命令、参数和坑。详细说明见各主题文档。

## 一、MCP

| 项 | 值 |
|---|---|
| 端点 | `http://127.0.0.1:9791/mcp` |
| 传输 | Streamable HTTP |
| 前提 | Rive 桌面版**运行中**（关掉即失效）、Early Access 构建 |
| 握手返回 | `serverInfo: {"name":"rive","version":"0.6"}` |
| 工具数 | 40（截至 2026-10） |

最小配置：

```json
{ "mcpServers": { "rive": { "url": "http://127.0.0.1:9791/mcp" } } }
```

## 二、最常用的 8 个工具

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `session_info` | 现在开着哪些文件、哪个是活动的 | — |
| `get_selection` | 当前选中了什么 | — |
| `list_artboards` / `open_file_editor` | 列画板；`command` 走 `listArtboards` / `focusArtboard` / `renameArtboard` / `resizeArtboard` | `data.artboardId` |
| `get_artboard_hierarchy` | 画板里的对象树 | `artboardId`、`depth`（别超 6） |
| `animation_editor` | 状态机 / 关键帧 / 转换 / 条件 | `command` + `data` |
| `viewmodel_editor` | ViewModel / 属性 / 绑定 / converter | `command` + `data` |
| `capture_artboard` | 画板渲染成 PNG | `artboardId`、`longEdge`（64–1536） |
| `export_file` | 导出 `.riv` / `.rev` | `format`、`destination`**传目录** |

## 三、行为红线（实测）

| 行为 | 说明 |
|---|---|
| 跨文件复制 | **不存在**。只能走 `.rev` 导出导入 |
| `animation_editor` 指定画板 | **`data.artboardId` 被静默忽略**，只认活动画板，先 `focusArtboard` |
| `capture_artboard` 未激活画板 | 返回**空白图**，连背景色都不生效 |
| `export_file` 的 destination | 必须是**目录**；传文件路径报 `destination directory is not usable` |
| `upload_rev` 的 `open_file` | 目标必须**零画板**，否则原样不动并报错 |
| `simulateStateMachine` | 会**还原**写入值；不渲染像素；编辑态下拒跑 |

## 四、CLI

| 命令 | 作用 |
|---|---|
| `rive create <dir>` | 建项目（`rive.yaml` / `scene.rml` / `AGENTS.md` / `.gitignore`） |
| `rive <dir>` | 开实时预览窗口，改文件自动重建 |
| `rive <dir> --verify` | 只编译，不写文件 |
| `rive inspect <dir> --summary` | 编了什么 + problems |
| `rive <dir> --screenshot=x.png` | 无头渲染一帧 |
| `rive <dir> --once` | 写 unsigned `.riv` |
| `rive <dir> --publish` | 写 signed `.riv`（需登录，可能加水印） |
| `rive <dir> --rev` | 写 `.rev`，可在编辑器继续编辑 |
| `rive create <dir> --from-rev=f.rev` | 把编辑器文件转成 RML 项目 |
| `rive push` / `rive pull` | 与账号里的文件同步（pull **覆盖本地**） |
| `rive schema <Type> --animatable` | 查哪些属性能 K 帧 |
| `rive docs --search <词>` | 搜 CLI 自带文档 |
| `rive doctor` | 自检五项 |

安装（Windows）：`irm https://releases.rive.app/cli/install.ps1 | iex`

## 五、RML 值格式

| 类型 | 写法 |
|---|---|
| 颜色 | ARGB hex，**不带 `#`**：`FFFF5A3C` |
| 布尔 | `"true"` / `"false"`（字符串形式） |
| 旋转 | **弧度**，整圈 `6.2831855` |
| 动画时间 | **帧**（默认 60fps）；转换时长是**毫秒** |
| id | `0:12` 形式，全文档唯一 |

## 六、运行时

| 包 / 平台 | 渲染器 | 备注 |
|---|---|---|
| `@rive-app/webgl2` | Rive Renderer | **默认选它**，保真度最高 |
| `@rive-app/canvas` | Canvas2D | 实例多 / 混合模式重时更快 |
| `@rive-app/canvas-lite` | Canvas2D | 裁掉文字、布局、音频、脚本 |
| `@rive-app/canvas-single` | Canvas2D | wasm 内联，单请求 |
| `@rive-app/webgl` | — | **已废弃**（v2.37.0 后停更） |
| Apple / Android / Flutter / Unity / Unreal / C++ / RN | 多为 Rive Renderer | Flutter 用 `Factory.rive` 或 `Factory.flutter` |

## 七、坑位速查

| 现象 | 原因 | 解法 |
|---|---|---|
| 导出报 `HandshakeException` | 系统代理掐断了 TLS | **关代理**再导 |
| `upload_rev` 报 requires no artboards | 目标文件还有画板 | 删光再导 |
| 截图是空白 | 画板未激活 | 先 `focusArtboard` |
| 粘贴到另一个文件丢内容 | 跨文件粘贴要重建对象，图片/mesh/嵌套最易掉 | 走 `.rev`（[详见](跨文件搬运画板.md)） |
| 交互画板"上机动不了" | 无 inputs 也无 dataBinds | 补 ViewModel 触发 |
| 文字绑定了但不显示 | 绑到了 Text 而不是 Text Run | 改绑 Run |
| 换行符把 `.riv` 弄坏 | Git 当文本处理了 | `.gitattributes` 加 `*.riv binary` |
| 带脚本的文件上 Web 被拒 | 未签名 | `--publish` 构建 |
| 同屏多个实例掉帧 / 上下文丢失 | WebGL 上下文上限 | `useOffscreenRenderer: true` |
| **导出的 `.riv` 只有一两个画板** | `.riv` 只装「默认画板 + 组件画板」 | 要交付的画板标记为组件，或每屏拆一个文件（[详见](导出规则与交付验收.md)） |
| **运行时中文全是 ▯（编辑器正常）** | 字体 Type 不是 Embedded，包里没有字体数据 | 字体资产设 `Type=Embedded` + `Include=All glyphs` |
| **`upload_asset` 返回假 id `0-0`** | `file` 参数传了文件路径 | 改用 **data URI**，上传后 `listAssets` 复查 |
| **SVG 导入后中文全灭** | 文字按 font-family 落到内置 Inter 字体（无 CJK） | AI 里先 **Type → Create Outlines** 再导 SVG |
| **截图/导出对某些画板永远黑屏或 403** | Early Access 离屏渲染 bug，与内容无关 | 编辑器里看内容为准；换对照画板确认服务没挂 |
| **写入"成功"但没生效** | 批量 `set_property_values` 静默失败 | **写入后必须回读验证**，逐个写更稳 |
| **COM 调 Illustrator 挂死** | 未屏蔽弹窗 | ExtendScript 第一行设 `DONTDISPLAYALERTS`（[详见](AI素材导入链路.md)） |

## 八、画板指纹（核验口径）

```
状态机数 / 层数 / 状态数 / 动画状态数 / 转换数 / inputs 数 / listeners 数 / 线性动画数
```

搬运或改名前后各采集一次，逐项比对。工具见 [`scripts/rive-audit.ps1`](../scripts/rive-audit.ps1)。
