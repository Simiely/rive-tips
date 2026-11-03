# AI 素材导入链路：Illustrator → SVG → Rive

**TL;DR**：`.ai` 不能直接进 Rive。可靠链路是 **Illustrator 脚本导出 SVG（文字转轮廓 + 表现属性）→ 裁 `<font>` / 展开 `style` / 补尺寸 → data URI 上传 → `addSvgInstance` 铺矢量层 → 位图必须单独上传 + `addImageInstance`（`addSvgInstance` 会静默丢掉内嵌 `<image>`）→ 位图五坑（原点 / 层序 / 缩放 / **可见框 ≠ `<image>` 矩形** / **裁完是空的**）→ 裁切遮罩烘焙进位图 → 拿参考渲染做像素验收（**阈值相对源基线，不是常数**）**。跳过任何一步都会以"看起来成功、实际不可用"收场。

> 更新时间：2026-11-03 ｜ 已验证：Illustrator 30.1.0 + Rive 桌面版 1.9.x（Windows）
> 样本：3 个 2048×1152 启动页（矢量 450–515 对象/页，位图 2 张），最终像素差 0.10–0.14/255；1 个 2560×1440 车机页（5 个命名组 / 4 张位图 / 7829 对象），Rive 结果 1.43 vs 源 SVG 基线 1.40
> **入口不止一个**：手头已经是分层 SVG（Figma 直接导出、或上一轮从 PDF 转出来的中间产物）时，第二节整段可以跳过，见[第十三节](#十三从现成分层-svg-直接进跳过-illustrator)。

## 一、全链路总览

```
.ai (PDF 兼容)          ┌─ 也可以是现成的分层 SVG，① 整段跳过（见第十三节）
  │  ① Illustrator COM / ExtendScript 导出 SVG
  │     DONTDISPLAYALERTS 必设 + 文字倒序 createOutline()
  ▼
.svg（可能内嵌 <font> + <text> + <image>）
  │  ② 后处理：裁 <font>、展开 style=、补 width/height
  │  ③ 解出内嵌 <image>：可见框 ≠ <image> 矩形，用渲染器取 alpha bbox
  ▼
干净 SVG  +  独立 PNG 清单（含目标矩形，裁完断言非空）
  │  ④ upload_asset（data URI，name= 只用 ASCII）
  ▼
SVGAsset  /  ImageAsset
  │  ⑤ assets_tool addSvgInstance  →  矢量层（位图会丢！按组拆分，单份 <60 KB）
  │  ⑥ addImageInstance           →  位图另放，修五坑（原点/层序/缩放/可见框/空图）
  │  ⑦ 遮罩烘焙（clipPath 不导入）
  ▼
画板  │  ⑧ 像素比对（先量源基线，判据 ≤ 基线 + 0.3）
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

### 坑 4：可见框不等于 `<image>` 上的 `x/y/width/height`

上面三个坑都默认"图片按 `<image>` 的矩形铺在画布上"。**Figma 导出的稿子经常不是**：`<image>` 可能只是一块 pattern 的填充内容，真正露出来的区域由 `clip-path` 决定，还常常叠一层 `transform="rotate(…)"` 把纹理转正。

004 那页的车辆图就是这样：

```xml
<image x="1751.82" y="53.45" width="246.88" height="139.51"
       transform="rotate(89.815 1751.82 53.5371)"
       clip-path="url(#004_patclip_3)" .../>
```

按 `clipPath` 的矩形（`1751.82,53.54` 246.88×139.34）去裁 → **空白**；按 `<image>` 自己的矩形去放 → 偏到画外。真实可见框是 **`(1623, 153.5) 114.5×47.5`**，跟两者都不沾边。同一页的专辑封面更极端：`<image>` 是 189.68×237.16 的整张照片，可见部分只有 **`64×64`**。

`svg-prep.py images` 也是按 `<image>` 解矩形的，遇到这类素材同样会算错。**别手算，让渲染器算**：

1. 拼一个只含这一张 `<image>` 的 SVG，`<defs>` 全带上（`clipPath`、pattern 都在里面）
2. 铺满整张画布透明渲染（`width/height` = 画布，`viewBox` 用画布坐标）
3. `PIL` 的 `getbbox()` 就是可见框，直接裁

```python
bbox = Image.open(iso_png).convert("RGBA").getbbox()   # 真实可见框，几何交给渲染器
```

### 坑 5：裁完必须断言"不是空的"

同一个坑的另一半，也是最贵的一次教训。超采样渲染（比如 2× 出 5120×2880）后，`getbbox()` 给的是**该图自己的像素坐标**；换算成画布坐标时除了缩放倍数、裁剪时又乘了一次，就会裁到画布外——`PIL` 不报错，越界部分补透明，得到**尺寸正确、内容全空**的 PNG。

这种 PNG 一路都"成功"：`upload_asset` 返回正常 id、`addImageInstance` 建出节点、`set_property_values` 写入尺寸、回读 `810/811` 全对——直到在编辑器里看见图层是空的。本轮就是这样交付了一次，用户一句"车还没导进去"才暴露。

```python
crop = iso.crop(box_2x)
alpha = np.array(crop)[..., 3]
assert (alpha > 8).sum() > 0, "裁出来是空的：坐标乘了两次缩放"
```

判据：`alpha.max() == 0` 就是全空。`addImageInstance` 之后别只看尺寸，顺手看一眼位图本身。

### 坑 6：烘焙图是目标的 N 倍时会大出一圈

为了不让位图放大后发软，烘焙常按 2×/4× 出图。Rive 按位图**真实像素**以 100% 进场，于是"尺寸对、比例错"：

```
目标 114.5 px，烘焙图 458 px  →  缩放 = 100 × 114.5 / 458 = 25%
```

`810/811` 回读会立刻暴露（114.5 的目标读出来是 458）。反推一次就能定位是倍数没除掉。

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

**但 `0.5` 不是常数，是相对基线的。** 上面这句只在那批样本成立——它们的源 `.ai` 与 SVG 渲染几乎一致，误差全来自抗锯齿。换成 Figma 导出的稿子，**源 SVG 自己对参考图就有 1.4 的差**（filter 烘焙、pattern 化、Type3 字形都会拉高），这时拿绝对值 `0.5` 判，会把**正确的结果**判成失败，然后去改一个本来没毛病的地方。

正确口径：先量一次「**源 SVG vs 参考图**」得到基线，判据取 `Rive 结果 ≤ 基线 + 0.3`。

| 样本 | 源 SVG vs 参考 | Rive 结果 | 判 |
|---|---|---|---|
| 2048×1152 启动页 | ≈0.1（几乎重合） | 0.10–0.14 | PASS（绝对 0.5 也 PASS） |
| 2560×1440 车机页 004 | **1.40** | **1.43** | PASS（绝对 0.5 会误判 FAIL） |

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
□ SVG：拆 defs 时同步删掉 mask= / filter= 引用属性（悬空引用会让导入器永久卡死）
□ SVG：单份控制在 60 KB 内，按命名组拆分导入
□ 上传：data URI 的 name= 只用 ASCII；上传后 listAssets 复查（防假 0-0）
□ 矢量：addSvgInstance → 数一遍 Image 节点（本轮应为 0）
□ 位图：可见框用"隔离渲染 + alpha bbox"取，不按 <image> / clipPath 手算
□ 位图：裁完断言 alpha>8 像素数 > 0（防"尺寸对、内容空"）
□ 位图：addImageInstance 传**中心**坐标（left+w/2, top+h/2）
□ 位图：按"目标从上到下"顺序添加，层序自动正确（新对象追加到 children 末尾）
□ 位图：回写 sx/sy（= 100 × 目标宽 / 位图真实像素宽），回读 computedwidth/height = 目标值
□ 遮罩：clipPath 几何烘进位图 alpha（超采样 4×）
□ 名字：扫 _xNN_ / 控制字符，rename_objects 修
□ 验收：先量源 SVG 基线，判据 = 不超过基线 + 0.3（不是绝对 0.5）
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

## 十二、耗时分布：优化哪一步才有意义

一页 2048×1152 纯矢量（531 个对象）从 `.ai` 到验收通过，**全链路 9.6 秒**。逐步骤实测（`Stopwatch` / `time.perf_counter`，同一台机器，Illustrator 已热）：

| 阶段 | 步骤 | 耗时 | 占比 |
|---|---|---|---|
| ① AI 导出 | COM 附加 + 打开 + `exportFile`（含转轮廓） | **4,893 ms** | 51% |
| ② SVG 后处理 | `clean` | 220 ms | |
| | `images` | 222 ms | |
| | `clip` | 206 ms | |
| ③ 写进 Rive | `connect` 握手 | 28 ms | |
| | `upload_asset`（14 KB SVG，data URI） | **1,289 ms** | 13% |
| | `createArtboard` | 37 ms | |
| | `focusArtboard` | 2–17 ms | |
| | `addSvgInstance`（531 对象） | **2,213 ms** | 23% |
| | `arrangeArtboard` | 25 ms | |
| | `capture_artboard` 2048 | 106 ms | |
| ④ 验收 | `verify` 像素比对 | 321 ms | 3% |
| ⑤ 清理 | 删临时画板 + 资产 | 134 ms | 1% |

三条结论，按重要性排：

**1. 单步都不慢，编胶水脚本才是瓶颈。** 本轮实跑从导出完成到截图出来用了 **65 秒**，同样的步骤用现成脚本只要 **9.6 秒**。差额全在"读上一步输出 → 现写下一个脚本 → 再跑"这个循环里（那次还撞上同名画板导致断言失败）。**要优化的是驱动脚本，不是任何单独一步**——6 倍的差距在这里，不在 `addSvgInstance` 那 2 秒。

**2. `upload_asset` + `addSvgInstance` 合计 3.5 秒 = 全链路 36%，且都在解析同一份 SVG。** 这是唯一能"一次改动降两处"的杠杆：在 Illustrator 里合并同色路径、清掉无意义分组，两个数字一起降。代价是丢可编辑性，适合"导入即用"的页面。（只有方向，没做对照实验。）

**3. 别为省时间砍掉 `verify`。** 它只要 321 ms，却是全链路唯一的保险——错位版本 3.16/255 就是靠它拦下的。3% 的占比换一个客观判据，是最划算的一笔。

优化顺序（按收益）：

```
1. 一条命令跑完整链路（65 s → 10–12 s，收益最大）
2. 上游瘦身 SVG（同时降 upload + addSvgInstance）
3. 复用已上传的 SVG 资产（省 1.3 s/页，批量线性叠加）
4. clean+images+clip 合成一次调用（省 ~300 ms 的 Python 启动开销）
5. Illustrator 别导完就关（冷启首次导出是热态的十几倍）
```

批量导多页时还有一条：**导出共用一次 Illustrator 会话**，第二页起跳过 COM 附加与文档打开，比每页独立起一次快得多。

## 十三、从现成分层 SVG 直接进（跳过 Illustrator）

本链路的入口通常是 `.ai`，靠第二节的 Illustrator 脚本转出 SVG。但手头**已经是分层 SVG** 时（Figma 直接导出、设计那边给的分层稿、或上一轮从 PDF 转出来的中间产物），第二节整段可以跳过，直接从第三节（后处理）往后走。004 那页就是这么做的，一次过。

代价是要自己决定三件 Illustrator 脚本本来会替你想掉的事：

**1. 哪些东西该拍平**

Rive 不吃 `filter` / `mask` / `clipPath` / 内嵌 `<image>`。分层 SVG 里这些会散落在不同位置，处理方式不同：

| 出现位置 | 处理 |
|---|---|
| 整幅背景（底色 + 照片 + 渐变） | 整组渲染成一张画布尺寸的 PNG，当**最底层**铺进去 |
| 组内的阴影 / 模糊（`filter`） | 上游已烘焙成位图就按普通位图走第七节；没有就得自己烘 |
| `<g mask="url(#…)">` | 删掉 `mask` **属性**保留内容；**别只删 `<defs>` 里的 `<mask>`**（见第十四节） |

**2. 文字已经是轮廓了吗**

Figma 导出的 SVG 通常已经是 `<path>`，没有问题；如果里面还有 `<text>` 或 `<font>`，先转轮廓或裁掉，规则同第四节。

**3. 拆成几份导**

一份大 SVG 会把导入器拖死。按命名组拆，每份 30–60 KB，一份一个 `addSvgInstance`。好处不只是稳：**拆开后每组在 Rive 里天然就是独立的顶层组**，做动效时好选。

### 层序：新对象追加到末尾，不是"垫底"

文档别处常写"新对象默认垫底"，容易被读成"它会跑到最底"。更准确的说法是：**新对象追加到画板 `children` 的末尾，而 `children` 的顺序就是绘制顺序 top → bottom**。所以追加到末尾 = 画在最下面，**先加的反而在上面**。

由此有个很省事的推论：**按"目标从上到下"的顺序依次添加，层序自动正确**，不需要逐个 `sendToFront`。004 的落位顺序（左边先加）：

```
car → fx → album → 底部导航栏 → 地图区域 → 左侧信息面板 → 顶部状态栏 → bg_plate
```

背景板最后加，天然沉到最底。要事后调整，`reorder_objects` 的参数是 **`operations` 数组**：

```json
{ "operations": [ { "objectId": "32-12", "order": "sendToBack" } ] }
```

传 `{"objects": [...]}` 会报 `operations must be an array`。

> 这个模型也有代价：**位图没法插回它原本所在的组内部**。004 的投影（`fx`）本来在地图组里、压在车辆下面，现在只能放在所有组之上。视觉上无感（一层柔和暗影），但严格说层序和源文件不同。要精确还原，得把该组从图片位置切成上下两段分别导入。

## 十四、导入卡死：判据与自救

**先搞清一件事：SVG 的解析与转换在 Rive 服务端做，不在本机。** 报错原文是

```
SVG conversion for asset 46-16311 is unavailable, so there is nothing to import.
Rive converts SVGs server-side; check the editor for details.
```

这条决定了后面所有现象的性质：**等待是跨网络的**，所以"慢"和"死"从外面看一模一样；**同一个 asset 转换失败后重试没有意义**，必须换新资产重传。

**症状**：`addSvgInstance` 迟迟不返回（客户端先超时），之后每次导入都回 `An SVG import is in progress for this file. Wait for it to finish, then retry.`，`undo` 报 `Undone` 但解不开。

**判据（关键，能省掉反复重试）**：卡住时**读取类调用照常秒回**（`session_info` / `get_artboard_hierarchy` / `query_property_values`），**渲染类调用全部挂住**（`addSvgInstance` / `capture_artboard`）。出现这个组合就是主线程在等这次转换——不是网络、不是 token、不是权限问题，重试和改参数都没用。

**三个真因**（本轮各中一次）：

1. **SVG 里有指向已删除 defs 的悬空引用**。为绕开"Rive 不导入 `filter`/`mask`"把 `<mask>` 从 `<defs>` 删了，却留下 `<g mask="url(#mask0)">`——转换就此阻塞。**删 defs 时必须同步清掉所有引用属性。**
2. **单次导入太大**。一份 154 KB / 78 条路径（其中一条 58 KB）的 SVG 把转换拖死；按命名组拆成 4 份（26–62 KB）后每份都是秒级。
3. **`<use>` 引用**。服务端转换器不解析它，详见下一节。

**自救**：`undo` 解不开，只能重启 Rive 桌面端。文件是云文档，已导入的对象不会丢，重启后接着导即可。注意重启后 `capture_artboard` 可能先报一段时间的 `has no drawable area`（第三种原因见[速查表](速查表.md)「对所有画板都报」那一行），等它自愈——**时间不固定**：一次约 40 分钟，另一次超过 45 分钟仍未恢复。

**预防**：

```bash
grep -o 'mask="url(#[^)]*)'  x.svg        # 列引用
grep -o '<mask id="[^"]*"'   x.svg        # 对照 defs 里还剩什么，两边必须一一对上
grep -o '<use'               x.svg        # 有输出就先展开（下一节）
```

## 十五、`<use>` 与服务端转换器

Figma 导出的分层 SVG 经常用 `<use>` 复用图标和字形。**Rive 的服务端转换器不解析 `<use>`**：轻则那块内容消失，重则整个资产转换失败（`SVG conversion ... is unavailable`），而报错里只说"去看看编辑器"，不告诉你原因。

**本地先展开**：把每个 `<use href="#id" x= y=>` 替换成内联的 `<g transform="translate(x,y)">` + 被引用元素的深拷贝（拷完把 `id` 去掉，否则重复 id 会让后续引用串台），递归展开更深层的 `<use>`，然后把因此变成孤儿的 `<defs>` 裁掉。

这一步顺带解决体积问题：005 的 `<defs>` 里有 64 个 `<g>`，四个命名组各自携带整份 defs 是 130–199 KB/组；**按引用闭包裁剪**（只保留本组实际 `url(#…)` / `href="#…"` 能走到的）后降到 1.3–1.8 KB，渲染结果一像素不差（MAE 0.012）。

### 但展开后可能是空组，这很正常

005 的三组 `<use>` 全部指向 `font_43_*`——**字体字形**。而这些字形的轮廓定义躺在 `<font>` 块里，上游按"Rive 不消费 `<font>`"把它裁掉了（见第三节）：

```
<use xlink:href="#font_43_12">     ← 引用还在
<font id="font_43">…<glyph …/>     ← 轮廓已被裁掉
```

于是展开出来的是空 `<g>`，转成 Rive 后什么也没有。**这不是导入丢东西**，是这份 SVG 里本来就没有这些矢量了；它们只存在于烘焙出来的位图里。

判断方法：展开后统计每组还剩多少 `path`/`rect`。为 0 就说明这组全是"字形残骸"，直接跳过，别在它身上反复重试（一轮 3 次 × 4 秒，白等）。005 的顶部状态栏和底部导航栏就是这种情况，最终只导入了 `地图区域` 和 `左侧信息面板` 两层。

## 十六、几个不报错的失败（都踩过）

| 动作 | 失败长什么样 | 正确做法 |
|---|---|---|
| `upload_asset` 传中文文件名 | 报 `Invalid argument(s): Illegal percent encoding in URI` | data URI 的 `name=` 只用 ASCII（`004_g0.svg`）；Rive 里想要的图层名走 `addSvgInstance` 的 `name` 参数，那个可以是中文 |
| 刚 `addImageInstance` 就写 `sx/sy` | 返回 `success: true`，值没变（回读还是 100） | 写完回读，不对就再写一次。**不只是"批量写"会失败，新节点刚建好时也会被吞** |
| `addImageInstance` 的返回里**没有 `nodeId`** | 返回体缺字段，但节点已经建好了 | 回读 `children` 按 `name` 取 id 再写属性；别对着 `None` 调 `set_property_values` |
| 烘焙图是目标的 N 倍 | 位置对、尺寸大 N 倍 | 缩放 = `100 × 目标宽 / 位图真实像素宽`；004 是 4 倍 → 25% |
| 换掉某张位图 | —— | 写 `206` 指向新资产即可，`x/y` 不动；但**缩放要重新确认**，新图素尺寸未必一样 |


## 来源

- Adobe 官方示例脚本 SaveAsSVGs.jsx（`exportFile` + `ExportOptionsSVG` 用法）
- [Rive Fonts](https://rive.app/docs/runtimes/web/fonts)（兜底字体是运行时 API，编辑器无自动兜底）
- [Rive Assets](https://rive.app/docs/editor/fundamentals/assets-overview)（Embedded / Referenced / Hosted）
- [Rive MCP Integration](https://rive.app/docs/editor/ai/mcp)（`upload_asset` / `addSvgInstance` / `addImageInstance`）
- rive-flutter issue [#338](https://github.com/rive-app/rive-flutter/issues/338)（Inter 兜底行为）
- 第二至五节为本机实测（2026-10-26）
- 第六至十一节为本机实测（2026-10-29）：3 个 2048×1152 启动页、矢量 450–515 对象/页 + 2 张位图；`addSvgInstance` 丢图、原点偏移半个图标、圆角遮罩 124×124 r=20.571、像素差 0.10–0.14/255 均为该批实测值
- 第十二节耗时数据为本机实测（2026-10-29，同一台机器）：逐步骤用 `Stopwatch` / `time.perf_counter` 计时，取单次值；机器负载会让绝对值浮动，但各步骤之间的比例关系稳定
- 第十三至十六节为本机实测（2026-11-03）：1 个 2560×1440 车机页（`004.ai` → 分层 SVG，5 个命名组、4 张位图、7829 对象），入口跳过 Illustrator。样本值：车辆可见框 `(1623,153.5) 114.5×47.5`（`<image>` 写的是 `1751.82,53.45 246.88×139.51` + `rotate(89.815)` + clip）、专辑 `64×64`、投影 `145×84`；源 SVG vs 参考图基线 **1.40**、Rive 结果 **1.43**；导入卡死两次（悬空 `mask` 引用 / 154 KB 单份 SVG），重启桌面端后恢复；`capture_artboard` 全线 `has no drawable area` 持续约 40 分钟后自愈
- 同链路批量复用（002 / 003 / 005 三页，2026-11-03）：5 张位图/页。**无 `clip`/`transform` 的位图直接取原生像素**（scale 100%，省一次渲染且不丢分辨率），带 `clip`+`rotate` 的才走隔离渲染。离线合成 vs 源渲染 MAE：002 **0.313**、003 **0.344**、005 **0.012**。第十五节的 `<use>` 结论来自 005 的 81 处引用（其字形轮廓在上游 `clean` 阶段已随 `<font>` 裁掉，展开后是空组）
