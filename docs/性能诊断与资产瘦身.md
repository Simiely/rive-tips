# 性能诊断与资产瘦身

**TL;DR**：Rive 桌面编辑器是**云端工作流**，没有素材磁盘缓存；打开文件慢，先量化资产，不要先怀疑 DNS 或系统字体。资产可审计（`listAssets` + 图片节点 `assetid` + 文本样式 `fontassetid`），`delete_objects` 能直接删资产 ID；字体一直转圈 / Not Found 多是**旧资产记录卡住**，用 fontTools 子集化 + 重传 + 重绑最稳。实测 72.2 MiB → **2.09 MiB**，资产 87 → 18，113 个文本样式重绑 0 失败，画板截图字节一致。

> 更新时间：2026-10-27 ｜ 已验证：Rive 桌面版 1.9.349.6338（Windows）+ 本地 MCP 40 工具；样本 8 画板 / 87 资产 / 113 文本样式

## 一、先判断慢在哪一层

打开文件慢可能是三件事：网络下载、解码/渲染、代理失败。先用三个数字分开：

1. **`.rev` 体积**：`export_file(format=rev, embed_assets=true)` 导出整包，文件大小就是当前资产总量的近似值。
2. **网卡计数**：导出前后 `Get-NetAdapterStatistics` 的 `ReceivedBytes` 差值；空闲 30 秒再测一次基线。
3. **进程状态**：`Get-Process Rive` 的 CPU / WorkingSet。

实测（直连、19 Mbps 档）：

| 指标 | 数值 |
|---|---|
| 原始 `.rev` | 72.2 MiB |
| 导出耗时 / 网卡接收 | 24.6 s / 66.2 MiB |
| 空闲 30 s 网卡 | 0.37 MiB |
| 折算速度 | 约 2.3 MiB/s（19 Mbps） |

结论：时间主要花在**下载 + 解码 31.5 MB 字体和 60 张图**，不是 DNS。

### 编辑器没有素材磁盘缓存

本机实测：

- Rive 的 MSIX 数据目录（`LocalCache` / `LocalState` / `TempState`）总共约 **0.05 MB**，只有偏好设置和 Sentry 上报。
- 安装包里没有 WebView2，也没有 sqlite/leveldb；进程里没有 WebView2 子进程。
- `AC\INetCache\container.dat` 为 0 字节。

即：**素材只在内存，退出即失，每次打开都重新从 `files.rive.app` / `cdn.rive.app` / `public.rive.app` 拉取**。这不是设置项，没有“缓存更多”的开关。

## 二、资产审计：先找出“没用的”

MCP 能直接读出引用关系，不需要靠肉眼猜。

### 图片

```powershell
# 1. 当前文件所有资产
scripts/rive-mcp.ps1 -Tool assets_tool -ArgsJson '{"command":"listAssets"}'

# 2. 每个画板里的 Image 节点
scripts/rive-mcp.ps1 -Tool find_objects -ArgsJson '{"artboardId":"0-322","type":"image"}'

# 3. 图片节点 -> 资产：属性键 206
scripts/rive-mcp.ps1 -Tool query_property_values -ArgsJson '{"propertyKeys":{"0-34208":[206]}}'
```

- `find_objects` 的 `type` 是宽松匹配，结果里要按 `Type == "Image"` 过滤。
- `listAssets` 返回的图片数减去被引用的唯一资产 ID，就是候选未使用图片。
- 实测样本：60 张图只有 **8 张被引用**（9 个 Image 节点），52 张未使用，其中 13 张 1920×1080 就占 14.96 MB。

### 字体

```powershell
# 1. 找到 TextStylePaint（text 过滤会同时返回 Text / Style / Run）
scripts/rive-mcp.ps1 -Tool find_objects -ArgsJson '{"artboardId":"0-1860","type":"text"}'

# 2. 文本样式 -> 字体：属性键 279
scripts/rive-mcp.ps1 -Tool query_property_values -ArgsJson '{"propertyKeys":{"0-38718":[279]}}'

# 3. 文本内容（TextValueRun）：属性键 268
scripts/rive-mcp.ps1 -Tool query_property_values -ArgsJson '{"propertyKeys":{"0-38721":[268]}}'
```

实测样本：14 个字体只有 **4 个被引用**；113 个文本样式只用了 4 个字重；全部文本合计只有 **198 个不同字符**（151 个汉字）。

### 资产属性键（实测）

| 用途 | 键 |
|---|---|
| Image 节点 -> 图片资产 | `206` |
| TextStylePaint -> 字体资产 | `279` |
| 资产名（可写） | `203` |
| 导出类型：embedded / referenced / hosted | `358` |
| 字体 Include：all / used / custom | `360` |
| CDN base URL | `362` |
| CDN UUID | `359` |
| Include in export | `801` |
| `size` | `211`（实测恒为 0，不能用） |

> 图片/字体资产的 `cdnbaseurl` 常是占位符 `https://public.rive.app/cdn/uuid`、`cdnuuid` 为空；这是当前版本的正常状态，不代表资产损坏。

## 三、删除未使用资产

**`delete_objects` 不只删场景对象，也能删资产 ID**——官方文档没写，实测有效（2026-10-27）：

```powershell
scripts/rive-mcp.ps1 -Tool delete_objects -ArgsJson '{"objectIds":["0-144658","0-144656"]}'
```

流程：

1. 先导出 `.rev` 备份（带 `embed_assets: true`）。
2. 按第二节算出“未被任何 Image/TextStylePaint 引用”的资产 ID。
3. 一次 `delete_objects` 批量删除；返回 `success` + `deleted` 列表。
4. 回读核验：9 个 Image 节点 `206`、113 个文本样式 `279` 全部指向现存资产。
5. 截图对比：Artboard 1 / Artboard 2 修改前后 PNG **字节数完全一致**。

实测：一次删除 61 个资产（51 图 + 10 字体），`listAssets` 87 → 25，画面无变化。

### 两个上传坑

- **`upload_asset` 重名会返回假 `0-0`**，即使传的是 data URI。表现是 `{"success":true,"asset":{"id":"0-0"}}`，`queryAsset` 查不到，绑定时报 `unknown_id`。
  - 解法：先传唯一名（如 `Union_icon`），成功后用属性键 **203** 改回原名。
  - 假 `0-0` 会作为幽灵条目留在 `listAssets` 里，`delete_objects` 删不掉；**重启 Rive 后消失**。
- **`upload_asset` 的 `file` 参数只认 data URI**；本地路径返回同样的假 `0-0`。上传后必须 `listAssets` 复查。

### Not Found 不等于数据丢失

Assets 面板的 `Not Found` 多数是后端缩略图/资产记录状态，不是资产数据缺失：

- 把最终 `.rev` 拆开验证：8 张 PNG + 11 个 SVG + 4 个字体全部在里面。
- 重新上传同样字形的资产后，仍可能短暂显示 `Not Found`，但渲染、导出正常。
- 只要 `.rev` 里有数据、画板截图正常，就不要为了消叹号反复重传；先重启刷新，仍不消失再带 fileId 报 Rive 支持。

## 四、字体问题与子集化

### 症状

- 4 个字体只有 2 个加载完成，面板里另外两个一直转圈。
- 聚焦使用这些字体的画板也不结束；60 秒内网卡实际收了 29.6 MiB，说明传输发生过，是**资产记录卡住**。
- 字体文件本身没问题：从 `.rev` 提取 4 个 TTF，fontTools 全部解析成功，字形数都是 29,221。
- 额外发现：Medium / Black 的 `name` 表不规范（family 名带字重、subfamily 写成 `Regular`），可能是触发后端注册异常的因素，但不是唯一原因。
- 用相同字形重新上传成新字体资产后，**立即加载完成**——根因是旧的资产记录，不是字体文件、DNS 或带宽。

### 子集化流程（实测 8 MB → 58–60 KB）

```powershell
# 1. 收集当前所有文本用字（TextValueRun + 键 268），写成 UTF-8 无 BOM
# 2. 子集化：保留 name / layout / glyph order
python -m fontTools.subset font.ttf `
  --text-file=chars.txt `
  --output-file=font_subset.ttf `
  --layout-features=* --glyph-names --symbol-cmap --legacy-cmap `
  --notdef-glyph --notdef-outline --recommended-glyphs `
  --name-IDs=* --name-legacy --name-languages=*

# 3. 校验覆盖
python -c "from fontTools.ttLib import TTFont; f=TTFont('font_subset.ttf'); cmap=f.getBestCmap(); print([c for c in open('chars.txt',encoding='utf-8').read() if ord(c) not in cmap])"
```

实测：4 个字体各约 8.1–8.3 MB，子集后 **58–60 KB**，每个 350 glyphs；198 个字符覆盖 **0 缺失**。

上传与替换：

1. `upload_asset` 传唯一名（如 `HarmonyOS_Sans_SC_Medium_sub`），拿到新字体 ID。
2. `set_property_values` 把所有 TextStylePaint 的 `279` 批量改到新 ID。
3. **回读验证**：113 个样式逐个比对，0 不匹配才继续。
4. 删除 4 个旧字体资产；`listAssets` 恢复到 18 个资产（4 字体 + 8 图 + 4 SVG + 2 脚本）。
5. 截图 Artboard 1 / Artboard 2，修改前后 PNG 字节数完全一致。
6. 重新导出 `.rev`：**2,187,553 B（2.09 MiB）**，导出 10.1 秒。

### 风险

- 子集字体只含当前用字；**以后新增这些字之外的字符会缺字**。
- 保留全量字体 `.rev` 母版，随时可以恢复，或按更大字符集（如常用 3500 汉字）重新子集，每个字体约 0.5–1 MB。
- 子集化前确认字体许可允许修改/子集。

## 五、本地字体与本地编辑

**桌面编辑器不能用系统/本地字体**：

- 编辑器字体只来自 Google Fonts 或**文件里上传的字体资产**；本机装了同名字体也不会自动使用。
- Fallback Fonts 是运行时能力，需要应用自己提供；浏览器出于安全限制也不能直接访问系统字体。
- 想把字体当本地文件用，只有 **CLI 本地项目**：`rive pull` 会把字体下载成本地文件，`rive <dir>` 本地预览；但 CLI 不是可视化编辑器，也没有 MCP。
- `.riv` / `.rev` 的“导入”是导入**文件浏览器（上传到云端）**，不是从磁盘直接打开；Windows 上没有 `.rev` 文件关联。

## 六、网络与代理

- Rive 域名：`api.` / `files.` / `cdn.` / `public.` / `editor.` / `releases.` / `proxy.` / `telemetry.rive.app`。
- 代理掐 TLS 的表现是 `HandshakeException`；导出和素材加载都会受影响。
- mihomo / Clash Party 可在覆写文件的 `+rules:` 最前面加：

```yaml
+rules:
  - DOMAIN-SUFFIX,rive.app,DIRECT
```

重启 Clash Party 后，用日志确认：

```
[TCP] --> api.rive.app:443 match DomainSuffix(rive.app) using DIRECT
```

- **DNS 不是瓶颈**：缓存后解析 6–69 ms，首次冷解析 0.2–0.7 秒；真正慢的是 8 MB 字体本身。
- 不建议写 hosts 固定 CloudFront/AWS IP，边缘 IP 会变，可能选到更差的节点。

## 七、实测结果

| 阶段 | `.rev` 体积 | 资产数 | 导出耗时 |
|---|---|---|---|
| 原始 | 75,708,136 B（72.2 MiB） | 87 | 24.6 s |
| 删除未使用资产 | 34,771,844 B（33.2 MiB） | 25 | 10.5 s |
| 字体子集化 | **2,187,553 B（2.09 MiB）** | **18** | 10.1 s |

体积减少 **97.1%**；113 个文本样式重绑 0 失败；Artboard 1 / Artboard 2 截图字节一致；Assets 面板无转圈、无 Not Found。

## 八、复用手册

```powershell
# 资产清单
scripts/rive-mcp.ps1 -Tool assets_tool -ArgsJson '{"command":"listAssets"}'

# 画板里的图片节点
scripts/rive-mcp.ps1 -Tool find_objects -ArgsJson '{"artboardId":"0-322","type":"image"}'

# 图片引用
scripts/rive-mcp.ps1 -Tool query_property_values -ArgsJson '{"propertyKeys":{"0-34208":[206]}}'

# 文本样式 -> 字体
scripts/rive-mcp.ps1 -Tool query_property_values -ArgsJson '{"propertyKeys":{"0-38718":[279]}}'

# 删资产（先备份 .rev）
scripts/rive-mcp.ps1 -Tool delete_objects -ArgsJson '{"objectIds":["0-144658"]}'

# 上传字体/SVG/图片（data URI）
scripts/rive-mcp.ps1 -Tool upload_asset -ArgsJson '{"file":"data:font/ttf;name=font_sub.ttf;base64,...","name":"font_sub"}'

# 导出整包体检
scripts/rive-mcp.ps1 -Tool export_file -ArgsJson '{"format":"rev","destination":"D:\\out","embed_assets":true}'
```

## 九、回滚

- 删资产前导出的 `.rev` 是完整快照；需要恢复时把它导入文件浏览器（上传）即可。
- 字体子集化前的全量字体保留在 `.rev` 里；恢复全量字体 = 重新上传字体 + 重绑 `279`。
- 所有删除/重绑操作都要先备份、后回读验证；不要凭 `success: true` 判断成功。

## 来源

- 官方文档：[Assets](https://rive.app/docs/editor/fundamentals/assets-overview)（Embedded / Referenced / Hosted）
- 官方文档：[Font Assets](https://rive.app/docs/editor/text/fonts)（Google Fonts、Include 选项）
- 官方文档：[Feature Support](https://rive.app/docs/feature-support)（Fallback Fonts 按运行时支持）
- 官方文档：[Web Fonts](https://rive.app/docs/runtimes/web/fonts)（浏览器不能访问系统字体）
- 官方文档：[Rive CLI Overview](https://rive.app/docs/cli/overview)（本地项目与本地字体）
- 官方文档：[Mihomo 规则](https://wiki.metacubex.one/config/rules/)（DOMAIN-SUFFIX）
- 本文第一至第八节全部为本机实测（Rive 桌面版 1.9.349.6338，2026-10-27）
