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
| `rive <dir> --publish` | 写 signed `.riv`（需登录；未 `push` 绑定账户文件、或工作区低于 Cadet 会**加水印**） |
| `rive <dir> --rev` | 写 `.rev`，可在编辑器继续编辑 |
| `rive create <dir> --from-rev=f.rev` | 把编辑器文件转成 RML 项目（**目标目录须为空或新建**） |
| `rive create <dir> --from-remote-file[=id]` | 直接从账号里的文件建工程（登录；链接写入 `rive.yaml`，供 push / pull） |
| `rive push` / `rive pull` | 与账号里的文件同步（pull **覆盖本地**，默认 `[y/N]` 选 N） |
| `rive ls` | 列账号里的项目 / 文件（`--json` 拿 file id，`push --project` 要用） |
| `rive schema <Type> --animatable` | 查哪些属性能 K 帧 |
| `rive docs --search <词>` | 搜 CLI 自带文档 |
| `rive doctor` | 自检五项 |

安装（Windows）：`irm https://releases.rive.app/cli/install.ps1 | iex`

### 合并两个文件（不清空目标）

`upload_rev` 要求目标零画板，所以"并进已有内容的文件"走不通 MCP。用 CLI 四步（脚本在 `skills/rive-ops/scripts/rive-merge/`，Python 3.8+，无第三方依赖）：

```powershell
rive create work\tgt --from-rev=目标.rev      # 两边各拆一个工程（目标目录须为空或新建）
rive create work\src --from-rev=来源.rev
python rml_merge.py --target work\tgt --source work\src --out work\out `
    --target-rev 目标.rev --source-rev 来源.rev --prune-orphans
python fill_assets.py --dir work\out --rev 目标.rev --rev 来源.rev --from work\src
python gate.py --dir work\out --fix --verify   # 必须 PASS 再 push
rive push work\out --project=<file id> --name=<ASCII 名>
```

冲突三档（`replace` / `skip` / `keep`）、资产四级匹配、已知限制见 [无清空合并文件](merge.md)。

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
| 粘贴到另一个文件丢内容 | 跨文件粘贴要重建对象，图片/mesh/嵌套最易掉 | 走 `.rev`（[详见](transfer.md)） |
| 交互画板"上机动不了" | 无 inputs 也无 dataBinds | 补 ViewModel 触发 |
| 文字绑定了但不显示 | 绑到了 Text 而不是 Text Run | 改绑 Run |
| 换行符把 `.riv` 弄坏 | Git 当文本处理了 | `.gitattributes` 加 `*.riv binary` |
| 带脚本的文件上 Web 被拒 | 未签名 | `--publish` 构建 |
| 同屏多个实例掉帧 / 上下文丢失 | WebGL 上下文上限 | `useOffscreenRenderer: true` |
| **导出的 `.riv` 只有一两个画板** | `.riv` 只装「默认画板 + 组件画板」 | 要交付的画板标记为组件，或每屏拆一个文件（[详见](delivery.md)） |
| **运行时中文全是 ▯（编辑器正常）** | 字体 Type 不是 Embedded，包里没有字体数据 | 字体资产设 `Type=Embedded` + `Include=All glyphs` |
| **`upload_asset` 返回假 id `0-0`** | `file` 参数传了文件路径 | 改用 **data URI**，上传后 `listAssets` 复查 |
| **SVG 导入后中文全灭** | 文字按 font-family 落到内置 Inter 字体（无 CJK） | AI 里先 **Type → Create Outlines** 再导 SVG |
| **截图/导出对某些画板永远黑屏或 403** | Early Access 离屏渲染 bug，与内容无关 | 编辑器里看内容为准；换对照画板确认服务没挂 |
| **写入"成功"但没生效** | 批量 `set_property_values` 静默失败 | **写入后必须回读验证**，逐个写更稳 |
| **打开文件慢 / 素材转圈** | 桌面编辑器无素材磁盘缓存，每次从云端拉全量资产 | 先做资产审计，删未使用资产，必要时字体子集化（[详见](performance.md)） |
| **`delete_objects` 能删资产 ID** | 官方只写删对象，实测资产 ID 也可删 | 删前导出 `.rev` 备份，删后回读 `206`/`279` 核验（[详见](performance.md)） |
| **`upload_asset` 重名返回假 `0-0`** | 已存在同名资产（data URI 也一样） | 换唯一名上传，再用属性键 `203` 改回原名；幽灵条目重启后消失 |
| **字体一直转圈 / Not Found** | 旧字体资产记录卡住，不是字体文件损坏 | fontTools 验证；重传同字形/子集化后重绑 `279`；不要改 DNS |
| **字体加载慢** | 4 个 CJK 字体 31.5 MB，冷下载 | 按实际用字子集化：8 MB → 约 60 KB（[详见](performance.md)） |
| **本机装同名字体无效** | 编辑器只用 Google Fonts / 上传字体 | 本地字体只支持 CLI 项目；编辑器不读系统字体 |
| **按压效果偏长** | 把 500ms 当成抬起段，做成 42 帧 | 总时长 30 帧：按下 12 帧 + 抬起 18 帧（200ms + 300ms） |
| **多个按钮只能一个激活** | 所有按钮塞在同一个状态机 Layer | 一按钮一层；每层 Idle / Activating / Deactivating |
| **点击切换没反应** | opacity 0 浮层不命中 / 监听器挂错 | 监听器挂 Shape；必要时加透明命中层；脚本类型必须 listenerAction |
| **面板 Not Found 不一定缺数据** | 后端缩略图/资产记录状态 | 用 `.rev` 拆解验证数据；渲染/导出正常就保留 |
| **浅色主题按钮激活后不变色** | 扁平矢量没有文字对象，颜色分散在卡片和每个图标/轮廓填充上 | 按填充逐个做颜色关键帧：卡片 `#141a1a1a↔#ffd96b2b`、图标/文字 `#a61a1a1a↔#ffffffff`（[详见](toggle-button.md)） |
| **打组后缩放跑偏** | `group_editor` 的组原点落在 `objectIds` 第一个对象上 | 把**卡片放第一个**，组原点正好是按钮中心 |
| **批量复制位置全乱** | `duplicate_objects` 一次传多个 ID，副本全部成为最后一个对象的兄弟；且只返回数量不给 id | 逐个复制，或复制后逐个 `reparent_objects`；新 id 回读父级 `children` 找 |
| **`addProperties` 报 `viewModels must be an array`** | 参数不是 `viewModelId` 平铺，而是 `data.addProperties.viewModels[]` | 每次可批量传多个 ViewModel，属性一次加完 |
| **浅色画板开关和深色联动** | ViewModel 实例被两个画板共用 | 每个画板建独立实例并 `bindViewModelToArtboard`；脚本是文档级的，可以复用 |
| **PowerShell 调 MCP 报 `Invalid JSON primitive`** | `-File` 传参把 JSON 双引号吞了，不是服务没起 | 批量改用 `scripts/rive_mcp.py`，dict 传参并复用 session（[详见](mcp.md)） |
| **`git push` 报 `No anonymous write access`** | `GH_TOKEN` 失效或凭据管理器里没有 GitHub 凭据 | 走 `127.0.0.1:7890` 代理；临时把 token 写进 remote URL 推送，**推完立刻恢复 URL 并撤销 token** |
| **`git push` 直连超时** | github.com:443 无法直连 | 只给这条命令加 `HTTPS_PROXY=http://127.0.0.1:7890`，不要永久写进 git config |
| **COM 调 Illustrator 挂死** | 未屏蔽弹窗 | ExtendScript 第一行设 `DONTDISPLAYALERTS`（[详见](asset-import.md)） |
| **`rive --verify` / `--once` 无输出直接崩（exit `3221226505` = `0xC0000409`）** | 资产文件名含非 ASCII（中文、全角括号）必崩；`FontAsset exportTypeValue="referenced"` 是第二诱因 | `gate.py --fix-names --fix-fonts`；判定：`$LASTEXITCODE` = `-1073740791` 且 stdout/stderr 全空（[详见](merge.md)） |
| **想把 A 文件并进有内容的 B，`upload_rev` 被拒** | `upload_rev(open_file)` 要求目标零画板 | 走 CLI 合并四步管线（见「四、CLI」），不要清空目标（[详见](merge.md)） |

## 八、画板指纹（核验口径）

```
状态机数 / 层数 / 状态数 / 动画状态数 / 转换数 / inputs 数 / listeners 数 / 线性动画数
```

搬运或改名前后各采集一次，逐项比对。工具见 [`scripts/rive-audit.ps1`](../scripts/rive-audit.ps1)。

## 九、资产属性键（实测）

| 用途 | 键 |
|---|---|
| Image 节点 -> 图片资产 | `206` |
| TextStylePaint -> 字体资产 | `279` |
| 资产名（可写） | `203` |
| 导出类型 embedded / referenced / hosted | `358` |
| 字体 Include all / used / custom | `360` |
| CDN base URL / UUID | `362` / `359` |
| Include in export | `801` |
| `size` | `211`（实测恒为 0，不能用） |

资产审计与字体子集化的完整流程见 [性能诊断与资产瘦身](performance.md)。
