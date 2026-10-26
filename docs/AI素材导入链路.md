# AI 素材导入链路：Illustrator → SVG → Rive

**TL;DR**：`.ai` 不能直接进 Rive。可靠链路是 **Illustrator 脚本导出 SVG → 文字转轮廓 → 裁掉内嵌字体 → data URI 上传 → `addSvgInstance` 放置 → 截图验收**。每一步都有已知的坑，跳过任何一步都会以"看起来成功、实际不可用"收场。

> 更新时间：2026-10-26 ｜ 已验证：Illustrator 30.1.0 + Rive 桌面版 1.9.x（Windows）

## 一、全链路总览

```
.ai (PDF 兼容)
  │  ① Illustrator COM / ExtendScript 导出 SVG
  │     （DONTDISPLAYALERTS 必设，否则 COM 挂死）
  ▼
.svg（25MB 级，内嵌字体 + 文本元素）
  │  ② 裁掉 <font> 块（Rive 不消费，25MB → 80KB）
  │  ③ 文字转轮廓（关键，见第四节）
  ▼
精简 SVG
  │  ④ upload_asset（必须 data URI，路径参数是坏的）
  ▼
SVGAsset
  │  ⑤ assets_tool addSvgInstance 放到目标画板
  ▼
画板上的可编辑矢量
  │  ⑥ capture_artboard / get_artboard_hierarchy 验收
  ▼
完成
```

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

var opt = new ExportOptionsSVG();
opt.embedRasterImages = true;          // 位图内联，避免外部依赖
// 注意：不要设 opt.fontType = SVGFontType.OUTLINEFONT
// —— 30.1.0 上会静默失败（不生成文件），见第四节

var f = new File("D:/out/dark.svg");
doc.exportFile(f, ExportType.SVG, opt);
doc.close(SaveOptions.DONOTSAVECHANGES);
```

通过 COM 执行：`$ai.DoJavaScript($js)`。

### 这一层的坑（全部实测）

| 坑 | 后果 | 规避 |
|---|---|---|
| 不设 `DONTDISPLAYALERTS` | 任何弹窗把 COM 调用**挂死**，PowerShell 无限等待 | 第一行就设 |
| `foreach ($ab in $doc.Artboards)` | COM 集合枚举异常，**无限输出直到截断** | 用 `doc.Artboards.Count` + `Item(i)` |
| 文件名用子串匹配 | `深色.ai` 和 `浅色.ai` 同前缀，匹配到错误的文档 | **全名精确匹配** |
| `ExportOptionsSVG.fontType = OUTLINEFONT` | **静默失败**：调用返回成功但不生成文件 | 保持默认（TYPEFACE），文字问题用别的方法解（见第四节） |
| COM 间歇挂死 | `DoJavaScript` 无响应 | 先探活（短超时取 `Version`）；不行就让人工导出 |

## 三、②③ SVG 后处理

Illustrator 默认导出的 SVG 有两个问题：

**1. 内嵌 `<font>` 块**（默认 TYPEFACE 模式会把字体嵌进去）。一份 1648×1440 的按钮素材能导出 **25 MB**，其中字体占了 24 MB+。Rive 不消费 `<font>`，直接裁掉：

```python
import re
c = open(src, encoding='iso-8859-1').read()
c = re.sub(r'<font[\s\S]*?</font>', '', c, count=1)
open(dst, 'w', encoding='utf-8').write(c)
# 实测：25.16 MB → 80 KB，path/g/clipPath 全部保留
```

注意编码：AI 导出的 SVG 头是 `iso-8859-1`，读写时别用错编码（中文会碎）。

**2. 文字以 `<text>` 元素存在**——这是导入失败的根源，见第四节。

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
| **导出前转轮廓**（推荐） | AI 里全选文字 → `Type → Create Outlines`（Shift+Ctrl+O）→ 再导 SVG | 一次性素材，文字不需要在 Rive 里改 |
| 导入后重绑 | 逐个把 `TextStylePaint.fontassetid` 指到文件里真实的中文字体资产 | 文字要在 Rive 里继续编辑 |

重绑用 `set_property_values`，键名 `fontassetid`（可写，已验证）：

```json
{ "propertyValues": { "15-22": { "279": "0-1255" } } }
```

代价提醒：转轮廓是**单向**的，转完不能改字。保留可编辑母版，把轮廓版当导出物。

## 五、④ 上传：必须 data URI

`upload_asset` 的 `file` 参数**只认 data URI**：

```json
{ "file": "data:image/svg+xml;name=261026x01dark.svg;base64,<base64>" }
```

**传本地文件路径是坏的**：返回 `{"success":true,"asset":{"id":"0-0",...}}`——一个假 id，资产列表里也找不到。`C:\WINDOWS` 和用户目录都一样。别被 `success: true` 骗了，**上传后必须 `listAssets` 复查**。

尺寸参考：80 KB SVG → base64 约 109 KB，单次调用没有压力。

## 六、⑤⑥ 放置与验收

```json
{ "command": "addSvgInstance", "data": { "assetId": "15-14", "parentId": "15-1" } }
```

返回 `nodeId` / `parentId` / `childCount`。然后验收两件事：

1. **结构**：`get_artboard_hierarchy(depth=20)` —— 数对象、看类型分布（Shape/Fill/SolidColor/Text 应该都在）、抽查填充色的 RGBA（`colorred/colorgreen/colorblue/coloralpha`，键 118/136/210/218）
2. **像素**：`focusArtboard` → `capture_artboard` —— 确认真的画出来了

实测一次完整导入：`1574` 个对象（97 Shape / 96 Fill / 14 Text / 107 PointsPath），填充色逐项正确。

## 七、验收时的已知干扰

`capture_artboard` 对**部分画板**会稳定渲染成黑屏或直接 403 `UNACCESSIBLE`——与内容无关（隐藏文字、重绑字体都不能解），疑似 Early Access 离屏渲染的 bug。遇到黑屏时：

1. 先看**编辑器里**是否可见——编辑器显示才是内容判据
2. 换一个不含文字/不含该素材的画板对照，确认 capture 服务本身没挂
3. 别对着黑屏反复改数据——那是在解一个不存在的问题

另一个反向教训：**批量 `set_property_values` 可能静默失败**（返回 `values:{}` 但没写入）。本次 14 段文字的透明度恢复就栽在这——返回 success + 空 values，实际全是 0。**所有写入必须回读验证**，逐个写比批量稳。

## 来源

- Adobe 官方示例脚本 SaveAsSVGs.jsx（`exportFile` + `ExportOptionsSVG` 用法）
- [Rive Fonts](https://rive.app/docs/runtimes/web/fonts)（兜底字体是运行时 API，编辑器无自动兜底）
- [Rive Assets](https://rive.app/docs/editor/fundamentals/assets-overview)（Embedded / Referenced / Hosted）
- rive-flutter issue [#338](https://github.com/rive-app/rive-flutter/issues/338)（Inter 兜底行为）
- 第二、四、五、六节全部为本机实测（2026-10-26）
