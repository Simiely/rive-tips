# AI 素材导入链路：Illustrator → SVG → Rive

**TL;DR**：`.ai` 不能直接进 Rive。可靠链路是 **Illustrator 脚本导出 SVG（文字转轮廓 + 表现属性）→ 裁 `<font>` / 展开 `style` / 补尺寸 → data URI 上传 → `addSvgInstance` 铺矢量层 → 位图必须单独上传 + `addImageInstance`（`addSvgInstance` 会静默丢掉内嵌 `<image>`）→ 位图三坑（原点 / 垫底 / 缩放）→ 裁切遮罩烘焙进位图 → 拿 `.ai` 的渲染做像素验收**。跳过任何一步都会以"看起来成功、实际不可用"收场。

> 更新时间：2026-10-29 ｜ 已验证：Illustrator 30.1.0 + Rive 桌面版 1.9.x（Windows）
> 样本：3 个 2048×1152 启动页（矢量 450–515 对象/页，位图 2 张），最终像素差 0.10–0.14/255

## 一、全链路总览

```
.ai (PDF 兼容)
  │  ① Illustrator COM / ExtendScript 导出 SVG
  │     DONTDISPLAYALERTS 必设 + 文字倒序 createOutline()
  ▼
.svg（可能内嵌 <font> + <text> + <image>）
  │  ② 后处理：裁 <font>、展开 style=、补 width/height
  │  ③ 解出内嵌 <image>：transform 链 → 绝对 x/y/w/h
  ▼
干净 SVG  +  独立 PNG 清单（含目标矩形）
  │  ④ upload_asset（data URI）
  ▼
SVGAsset  /  ImageAsset
  │  ⑤ assets_tool addSvgInstance  →  矢量层（位图会丢！）
  │  ⑥ addImageInstance           →  位图另放，再修三坑
  │  ⑦ 遮罩烘焙（clipPath 不导入）
  ▼
画板  │  ⑧ 像素比对（.ai 的 PNG24 渲染当裁判）
  ▼
完成
```

> 配套脚本：`scripts/svg-prep.py`（`clean` / `images` / `clip` / `mask` / `verify` 五个子命令），把 ②③⑦⑧ 步的重复劳动固化成命令，坐标和阈值都是本文实测值。
> `scripts/ai-svg-export.ps1 -OutlineText` 覆盖 ① 步（转轮廓 + 表现属性 + 全部 COM 防呆）。

## 二、① 用脚本驱动 Illustrator 导出

Illustrator 正在运行时，用 COM 附着到**当前实例**，不要另起进程：

```powershell
$ai = [Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')
```

导出脚本（含全部防呆）：

```javascript
// ① 第一行必须是它 —— 否则任何确认框都会把 COM 调用挂死
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;

var doc = null;
for (var i = 0; i < app.documents.length; i++) {
  if (app.documents[i].name == "261026x01深色.ai") { doc = app.documents[i]; break; }
}
if (!doc) { doc = app.open(new File("D:/src/深色.ai")); }

// ② 文字倒序转轮廓：createOutline() 会把文本帧换成组，倒序索引才不会错位
for (var k = doc.textFrames.length - 1; k >= 0; k--) {
  try { doc.textFrames[k].createOutline(); } catch (e) {}
}

var opt = new ExportOptionsSVG();
opt.embedRasterImages = true;          // 位图内联，避免外部依赖
opt.preserveEditability = false;       // 瘦身，输出更干净
// ③ 让属性写成表现属性，而不是 style="..."（Rive 不解析 style）
opt.cssProperties = SVGCSSPropertyLocation.PRESENTATIONATTRIBUTES;
// 注意：不要设 opt.fontType = SVGFontType.OUTLINEFONT
// —— 30.1.0 上会静默失败（不生成文件），见第四节

var f = new File("D:/out/dark.svg");
doc.exportFile(f, ExportType.SVG, opt);
doc.close(SaveOptions.DONOTSAVECHANGES);
```

通过 COM 执行：`$ai.DoJavaScript($js)`。

> **不要在原地改源文件**：`DONOTSAVECHANGES` 关掉即可。转轮廓是单向的，源 `.ai` 一旦保存就回不去了。

### 这一层的坑（全部实测）

| 坑 | 后果 | 规避 |
|---|---|---|
| 不设 `DONTDISPLAYALERTS` | 任何弹窗把 COM 调用**挂死**，PowerShell 无限等待 | 第一行就设 |
| `foreach ($ab in $doc.Artboards)` | COM 集合枚举异常，**无限输出直到截断** | 用 `doc.Artboards.Count` + `Item(i)` |
| 文件名用子串匹配 | `深色.ai` 和 `浅色.ai` 同前缀，匹配到错误的文档 | **全名精确匹配** |
| `ExportOptionsSVG.fontType = OUTLINEFONT` | **静默失败**：调用返回成功但不生成文件 | 保持默认，转轮廓用 `createOutline()` |
| 正序 `createOutline()` | 集合在循环中被改写，索引错位、漏转 | **倒序**遍历 `textFrames` |
| 关闭已有文档 | 用户手上的未保存改动丢失 | 只关自己 `app.open` 的，且不保存 |
| 脚本里写中文 | PS 5.1 按 ANSI 读无 BOM 文件，中文变乱码、解析失败 | 脚本保持 ASCII，中文路径放 JSON 走 UTF-8 |

## 三、② SVG 后处理

Illustrator 默认导出的 SVG 有几个问题：

**1. 内嵌 `<font>` 块**（默认 TYPEFACE 模式会把字体嵌进去）。一份 1648×1440 的按钮素材能导出 **25 MB**，其中字体占了 24 MB+。Rive 不消费 `<font>`，直接裁掉：

```python
import re
c = open(src, encoding='iso-8859-1').read()
c = re.sub(r'<font[\s\S]*?</font>', '', c, count=1)
open(dst, 'w', encoding='utf-8').write(c)
# 实测：25.16 MB → 80 KB，path/g/clipPath 全部保留
```

注意编码：AI 导出的 SVG 头是 `iso-8859-1`，读写时别用错编码（中文会碎）。

**2. 残留 `style="..."`**。即使设了 `cssProperties`，渐变停靠点等位置仍可能写成 `style="stop-color:#00BC6E"`。Rive 不解析 style 属性，必须展开成表现属性：

```python
STYLE_RE = re.compile(r'\sstyle="([^"]*)"')
def expand_style(m):
    props = ['%s="%s"' % tuple(p.split(":", 1)) for p in m.group(1).split(";") if ":" in p]
    return " " + " ".join(props) if props else ""
txt = STYLE_RE.sub(expand_style, txt)
```

**3. 没有 `width/height`**。AI 常只写 `viewBox`，导入后拿不到真实尺寸。按 viewBox 补上。

**4. 文字以 `<text>` 元素存在**——这是导入失败的根源，见第四节。

## 四、③ 文字必须转轮廓（最重要的一条）

**SVG 的 `<text>` 依赖字体名解析**，这条是 SVG 领域的通识（iconoop、StackOverflow 交叉一致），在 Rive 里表现为：

```
Rive 导入 <text> → 按 font-family 找/建字体资产
  → AI 导出的字体名解析不到
  → 落到 Rive 内置兜底字体 Inter（自动创建资产）
  → Inter 没有中文字形
  → 中文全部不渲染
```

交叉验证：rive-flutter 官方 issue [#338](https://github.com/rive-app/rive-flutter/issues/338) 记录了同一行为（文件里用 Open Sans，运行时却加载 `Inter-Regular`）；Rive 生态的 OpenRive 文档明确要求 "outline text and expand symbols in the design tool, then import"。

实测数据：导入后 14 段文字全部绑到了一个新建的 `Inter` 占位资产上，中文全灭；重绑到文件里真实的 SC 字体后才恢复。

**两种解法**：

| 方案 | 做法 | 适用 |
|---|---|---|
| **导出前转轮廓**（推荐） | 脚本里倒序 `createOutline()`（等价 UI 的 `Type → Create Outlines`） | 一次性素材，文字不需要在 Rive 里改 |
| 导入后重绑 | 逐个把 `TextStylePaint.fontassetid` 指到文件里真实的中文字体资产 | 文字要在 Rive 里继续编辑 |

重绑用 `set_property_values`，键名 `fontassetid`（可写，已验证）：

```json
{ "propertyValues": { "15-22": { "279": "0-1255" } } }
```

代价提醒：转轮廓是**单向**的，转完不能改字。保留可编辑母版，把轮廓版当导出物。

## 五、④ 上传：必须 data URI

`upload_asset` 的 `file` 参数**首选 data URI**：

```json
{ "file": "data:image/svg+xml;name=261026x01dark.svg;base64,<base64>" }
```

> 新版本工具说明里也接受 localhost 的绝对路径，但部分构建/沙箱下会因权限失败。**优先 data URI**——它不依赖编辑器能否读到你的磁盘。

**传本地文件路径在旧构建上是坏的**：返回 `{"success":true,"asset":{"id":"0-0",...}}`——一个假 id，资产列表里也找不到。别被 `success: true` 骗了，**上传后必须 `listAssets` 复查**。

尺寸参考：80 KB SVG → base64 约 109 KB，单次调用没有压力。

## 六、⑤ 放矢量层：`addSvgInstance`

```json
{ "command": "addSvgInstance", "data": { "assetId": "15-14", "parentId": "15-1" } }
```

返回 `nodeId` / `parentId` / `childCount`。

### 它会静默丢掉内嵌的 `<image>`

实测（2026-10-29）：一个含 1 张内嵌 PNG 的 2048×1152 SVG，导入后**画板里 0 个 Image 节点**——矢量路径、填充、渐变全在，位图整块消失，**不报错、不告警**。

所以位图必须走独立链路（第七节）。判据很简单：导入后 `get_artboard_hierarchy` 里数 `types` 含 `Image` 的节点，跟 SVG 里的 `<image>` 数量对一下。

### 顺带两个观察

- SVG 的 `<g id="...">` 会成为节点名；中文 id 会变成乱码，见第十节
- `<clipPath>` **不会被导入**：它对应的 `Shape` 会建出来但是空的（不生效），遮罩必须自己烘焙，见第八节

## 七、⑥ 位图单独进：三个必踩的坑

```
① 从 SVG 里解出 <image> 的 base64 + 它的绝对矩形（transform 链算）
② upload_asset(data:image/png;base64,...) → ImageAsset
③ addImageInstance { assetId, parentId: 画板id, x, y }
④ reorder_objects sendToFront
⑤ 按目标矩形回写 sx/sy
```

### 坑 1：`x/y` 是**原点**位置，不是左上角

Image 节点的 `originx/originy`（键 `380`/`381`）默认 `50/50`。所以 `x/y` 定位的是**中心点**：

```
要放在 left=786.893, top=455.857, w=126.214, h=168.286
→ x = 786.893 + 126.214/2 = 850.0
→ y = 455.857 + 168.286/2 = 540.0
```

直接填 SVG 坐标的后果：整体偏左上**半个图标**。这个偏移肉眼只像"有点歪"，量化后是确定的 230×63.5。

> 也可以把 `380/381` 改成 0 让 `x/y` 变成左上角，但保留中心原点更利于后续做缩放/旋转动画。

### 坑 2：新加的对象默认垫底

`addImageInstance` 加进来的图片排在画板子级的**最后**，而 Rive 是"后添加垫底"。整屏 SVG 的第一层是不透明背景色 —— 图片进去就被压在下面，**截图看起来像图片完全没进去**。

必须补一次 `sendToFront`，并回读画板 `children[0]` 确认。

### 坑 3：`addImageInstance` 不接尺寸，按位图原尺寸进场

没有 `width/height` 参数。位图原生 379×505、目标要 126.214×168.286，就得自己算比例回写缩放：

```
sx = 126.214 / 379 * 100 = 33.3018
sy = 168.286 / 505 * 100 = 33.324
```

写 `sx`(16) / `sy`(17) 后回读 `computedwidth`(810) / `computedheight`(811) 确认落到目标值。

**"原尺寸"是像素尺寸，不是 SVG 上写的尺寸。** 这条差点又踩一次：同一个 `<image>` 元素，AI 写的是 `width="378" height="504"`（显示尺寸），而里面嵌的 PNG 实际是 **379×505**。Rive 按**位图像素**进场，所以分母必须用 379/505——用 378/504 会得到 `33.3899 / 33.3901`，看着只差 0.09%，但在 126 px 的图标上是 0.11 px 的隐形偏移，验收时可能刚好卡在阈值边缘。

`svg-prep.py images` 现在直接从 PNG 的 IHDR / JPEG 的 SOF 读真实像素，两者不一致时会打一行 `! SVG declares … but the bitmap is …` 提醒。

### 位图相关的属性键（实测）

| 用途 | 键 |
|---|---|
| 图片资产引用 | `206` |
| x / y | `13` / `14` |
| 缩放 % | `16` / `17` |
| 不透明度 | `18` |
| 原点 x / y（%） | `380` / `381` |
| computed 宽 / 高（只读） | `810` / `811` |

## 八、⑦ 剪裁与遮罩：`clipPath` 不会跟着来

AI 里用剪切蒙版裁出来的圆角图标，导出 SVG 是一条独立的 `<clipPath>`（AI 会写成 `<defs><path id="SVGID_1_"/></defs>` + `<clipPath><use href="#SVGID_1_"/></clipPath>`）。Rive 不认，位图就带着白底直角整块露出来。

**做法：从 clipPath 读真实几何，把遮罩烘进位图的 alpha。**

实测那条圆角方框路径：

```
M788,498.571 C788,487.21,797.21,478,808.571,478
h82.858 C902.79,478,912,487.21,912,498.571
v82.858 C912,592.79,902.79,602,891.429,602
h-82.858 C797.21,602,788,592.79,788,581.429 V498.571z
```

读出来就是：矩形 `(788, 478) 124×124`，圆角半径 `808.571 - 788 = 20.571`。

再换算到位图像素（`379/126.214 ≈ 3.003`，`505/168.286 ≈ 3.001`）：

```
clip 在图像素坐标 = (3.3, 66.4) 372.4×372.1  r=61.8
```

用 4 倍超采样画 alpha 遮罩再缩放，边缘才不毛：

```python
S = 4
m = Image.new("L", (W*S, H*S), 0)
ImageDraw.Draw(m).rounded_rectangle([x0*S, y0*S, (x0+cw)*S, (y0+ch)*S], radius=r*S, fill=255)
m = m.resize((W, H), Image.LANCZOS)
out.putalpha(Image.composite(im.getchannel("A"), Image.new("L", (W, H), 0), m))
```

替换资产用 `set_property_values` 写 `206` 指到新上传的 img，**不用重建节点、不用重设位置**。

> 判据：位图四角是不是 `(255,255,255,255)`。全白不透明说明它是"白底满版"，设计里一定靠遮罩裁的。

## 九、⑧ 验收：拿 `.ai` 的渲染当裁判

编辑器里"看着对"不算数，`capture_artboard` 也有自己的脾气。可靠做法是**两边都出图，逐像素比**。

**参考图**：直接从 `.ai` 导 PNG24，跟 SVG 用同一套 COM 防呆：

```javascript
var opt = new ExportOptionsPNG24();
opt.antiAliasing = true; opt.artBoardClipping = true;
opt.horizontalScale = 100; opt.verticalScale = 100;
doc.exportFile(new File("D:/out/ref.png"), ExportType.PNG24, opt);
```

**比对**：两侧都 resize 到画板原生尺寸，算平均差与差异像素占比：

```python
diff = ImageChops.difference(a, b).convert("L")
hist = diff.histogram()
mean   = sum(i*n for i, n in enumerate(hist)) / (w*h)
ratio6 = sum(hist[16:]) / (w*h)     # 差异 > 6% 的像素占比
```

实测三页的判据：

| 情况 | 平均差 | 差异 >6% 像素 | 判定 |
|---|---|---|---|
| 纯矢量 A（对） | 0.10 / 255 | 0.18% | PASS |
| 矢量 + 圆角位图（对） | 0.13 / 255 | 0.26% | PASS |
| 纯矢量 B（对） | 0.14 / 255 | 0.26% | PASS |
| **位图偏半个图标** | **3.16 / 255** | **2.16%** | FAIL |
| **偏位 + 白底未遮罩** | **2.51 / 255** | **1.49%** | FAIL |

**对与错的差距是 20 倍以上**：正确的在 0.15 以内（纯抗锯齿），错位的都在 2.5 以上。阈值取 `mean < 0.5` 有足够余量，不会误判。

> 注意别用"差异像素占比"单独判：满屏背景色占了画面 90%，一个图标偏位只影响 2% 的像素，占比看起来很小，但平均差已经翻了 20 倍。`mean` 更灵敏。

### 录制注意

`capture_artboard` 对**未激活的画板**会直接报 `Artboard "xxx" has no drawable area.`，先 `focusArtboard`。

## 十、对象名乱码：中文变方块

**症状**：Layers 面板里本该是中文的组名显示成方块，或者 `å_x90_…` 这样的怪字符串。

**根因**：AI 导出时，含中文的**图层名**会被写成逐字节字符引用（`&#xE5;` 这种，因为 SVG 头声明 `iso-8859-1`）。解析后变成 latin-1 乱码，中间夹着 `0x80–0x9F` 的**控制字符** —— 这些控制字符在编辑器界面里就渲染成方块。

```
å_x90__xAF_å_x8A__x_A8_é_xA1__xB5_             → 启动页
æ_x87__x92_ä_xBA__xBA_æ_xA8__xAA_ç_x89__x88_   → 懒人横版
```

**只有 AI 图层名是中文的素材才会中招**。同一批三个文件里，两个的 SVG id 全是 `Design` / `Vector_…` / `Group_…` 默认名，一条都没有；只有带中文组名的那份出了两条乱码。

**检测**（全画板扫一遍）：`get_artboard_hierarchy(depth=20)`，找名字里含 `_x[0-9A-F]{2}_` 或 `0x80–0x9F` 控制字符的对象。

**修法**：`rename_objects` 批量改回中文。

```json
{ "renames": [ { "id": "4-542", "name": "启动页" } ] }
```

**预防**：导出后把 SVG 里含中文的 `id` 清成 ASCII，或在导入后统一批量改名。

## 十一、可复用清单

```
□ AI：DONTDISPLAYALERTS 首行、文档名全名精确匹配、只关自己开的文档
□ AI：倒序 createOutline() 转轮廓；cssProperties=PRESENTATIONATTRIBUTES
□ SVG：裁 <font>、展开残余 style=、按 viewBox 补 width/height
□ SVG：解出内嵌 <image> 的矩形（transform 链），别相信"导入就都在"
□ 上传：data URI；上传后 listAssets 复查（防假 0-0）
□ 矢量：addSvgInstance → 数一遍 Image 节点（本轮应为 0）
□ 位图：addImageInstance 传**中心**坐标（left+w/2, top+h/2）
□ 位图：reorder_objects sendToFront，回读 children[0]
□ 位图：回写 sx/sy，回读 computedwidth/height = 目标值
□ 遮罩：clipPath 几何烘进位图 alpha（超采样 4×）
□ 名字：扫 _xNN_ / 控制字符，rename_objects 修
□ 验收：.ai → PNG24 当参考图，像素平均差 < 0.5/255 才算过
□ 落位：createArtboard 会自动挑空位，建完 `arrangeArtboard` 摆到目标坐标
□ 收尾：废弃画板 delete_objects 删掉 → 再扫 `206` 确认旧资产 0 引用 → 删资产
```

### 收尾的两件事（第二轮复用实测）

**画板落位**：`createArtboard` 的 `x/y` 官方说明是"几乎不要传，Rive 会自己找空位"——这次它把新画板放到了 `x=9773`，离另外三个启动页的竖列（`x=-5085`）很远。所以"排到某页下面"要拆成两步：

```python
createArtboard([{"name": "QQ音乐启动页", "width": 2048, "height": 1152}])
arrangeArtboard([{"artboardId": new_id, "x": -5085, "y": 8082}])   # 上一页 y 6593 + 高 1152 + 间隔
```

`listArtboards` 的返回顺序是**按 id 数值**排的（`4-14` → `4-957` → `14-247`），既不是创建顺序也不是纯画布位置，所以别拿列表顺序当"层级顺序"的判断依据——**以画布 y 坐标为准**。

**资产清理**：`assets_tool` 没有 delete 命令，资产当普通对象删：

```python
delete_objects({"objectIds": ["3-133069"]})     # 这是资产 id，不是图形 id
```

删之前必须证明 0 引用：`listAssets` 不带引用计数，得逐画板 `find_objects(type="image")` 拿 id，再批量 `query_property_values` 读键 `206`。这次全文件 38 画板 / 60 个 image 图形扫下来，旧白底位图 `3-133069` 引用数确实是 0。

**SVG 资产是例外**：`addSvgInstance` 会把 SVG **一次性展开成实体路径**，生成的分组节点上没有资产引用键（位图有 `206`，SVG 没有）。所以删掉来源 SVG 资产不会影响已经建好的图形——但也意味着这个资产从导入那一刻起就是孤儿，留着只会占地方。

## 来源

- Adobe 官方示例脚本 SaveAsSVGs.jsx（`exportFile` + `ExportOptionsSVG` 用法）
- [Rive Fonts](https://rive.app/docs/runtimes/web/fonts)（兜底字体是运行时 API，编辑器无自动兜底）
- [Rive Assets](https://rive.app/docs/editor/fundamentals/assets-overview)（Embedded / Referenced / Hosted）
- [Rive MCP Integration](https://rive.app/docs/editor/ai/mcp)（`upload_asset` / `addSvgInstance` / `addImageInstance`）
- rive-flutter issue [#338](https://github.com/rive-app/rive-flutter/issues/338)（Inter 兜底行为）
- 第二至五节为本机实测（2026-10-26）
- 第六至十一节为本机实测（2026-10-29）：3 个 2048×1152 启动页、矢量 450–515 对象/页 + 2 张位图；`addSvgInstance` 丢图、原点偏移半个图标、圆角遮罩 124×124 r=20.571、像素差 0.10–0.14/255 均为该批实测值
