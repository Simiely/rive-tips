# 导出规则与交付验收

**TL;DR**：`.riv` **只装「默认画板 + 标记为组件的画板」**，其余画板连同动画、状态机被整体排除——这是官方明文规则，不是 bug。交付前必须逐画板确认，再用**官方运行时**验收（编辑器能看见 ≠ 能交付）。

> 更新时间：2026-10-26 ｜ 已验证：33 画板 / 92 动画 / 280 状态的文件实测

## 一、规则：哪些画板会进 `.riv`

> 官方最佳实践原文（中文文档）：「并非 Rive 文件中的每个画板都会包含在导出的 `.riv` 中。**默认画板以及标记为组件（Components）的画板会自动包含。其他画板——包括它们的动画、状态机以及其他画板专属内容——会被排除。**」

实测数据（33 画板的文件）：

| 画板 | isComponent | includeInExport | 进 .riv？ |
|---|---|---|---|
| refresh / refresh-2 / refresh-2 2 / button(96×96) / Artboard | **true** | true/false 混合 | ✅ 5 个全进 |
| 其余 28 个（switch、swipe、浮层……） | false | 改成 true 也没用 | ❌ 全部排除 |

**关键结论**：

1. 判据是 **`isComponent`**，不是画板属性里的 `includeInExport`
2. 把 `includeInExport` 写成 true（MCP 可写、回读成功）**不影响导出结果**——导出体积与内容一个字节不变
3. 文档里没有给非组件画板提供"强制导出"的入口

## 二、两条交付路线

| 路线 | 做法 | 适用 |
|---|---|---|
| **拆文件（推荐）** | 每个功能屏一个 `.riv`，文件里只留一个**默认画板** | 车机/多屏项目：按屏加载、体积小、改一个屏不牵连其他屏 |
| 标记组件 | 把要交付的画板逐个转成 Component | 需要跨文件复用的部件 |

拆文件还有个隐藏收益：`.riv` 只装「默认画板 + 组件」，天然就把规范板、废弃板挡在包外，不用逐个清理。

## 二·补、编辑器加载 ≠ 交付体积

- 桌面编辑器每次打开都从云端拉全量资产，**没有素材磁盘缓存**；`.riv` 导出只装「默认画板 + 组件画板」。
- 字体 `Include`（All glyphs / Glyphs used / Custom）只影响 `.riv` 导出，不改变编辑器加载；编辑器仍用源字体文件。
- 编辑器打开慢：先做资产审计、删未使用资产，再按需字体子集化（[性能诊断与资产瘦身](性能诊断与资产瘦身.md)）。
- `.rev`（`embed_assets: true`）可当体积取证：PNG 签名/IHDR、TTF 表目录能拆出真实 payload。

## 三、字体内嵌（车机离线的生死线）

字体资产的三种 Type（[官方 Assets 文档](https://rive.app/docs/editor/fundamentals/assets-overview)）：

| Type | 行为 | 车机可用？ |
|---|---|---|
| **Embedded** | 数据写进 `.riv` | ✅ 唯一可用 |
| Referenced | 运行时由应用自己加载 | 需要写 asset loader |
| Hosted | 走 Rive CDN | ❌ 离线即豆腐，且需 Voyager 套餐 |

**症状对照**（实测）：

- **编辑器里"等一会就正常"** → 字体从云端/缓存取到了
- **`.riv` 在运行时里中文永远是 ▯（等多久都没用）** → 包里没有字体数据，`Type` 不是 Embedded

这两条同时出现，就是字体没内嵌。修法：Assets 面板选中字体 → Inspector → Export options → **Type = Embedded**。

字体的 `Include` 选项还有一层：`All glyphs` / `Glyphs used` / `Custom`。用 `Glyphs used` 时只嵌"文件里用到的字形"——**别把用到某些字的画板排除在导出外**（见第一节），否则那些字形会被裁掉。

## 四、验收：编辑器说了不算

编辑器预览和运行时渲染是两条管线，`capture_artboard` 还有已知的渲染失败家族（部分画板稳定黑屏/403，与内容无关）。所以验收只能靠**官方运行时**：

### 最小验证环境

```
rive-runtime-check/
├── index.html            ← 见仓库 tools/runtime-check/
├── test.riv              ← 待验收文件
└── node_modules/@rive-app/webgl2
```

`npm i @rive-app/webgl2`，`python -m http.server 8123`，浏览器开 `http://127.0.0.1:8123/index.html?f=test.riv`。

页面做三件事：**列出 `.riv` 里实际存在的画板**（数量 + 名字）、渲染默认画板、打印加载错误。

### 实测这门验收抓到过什么

| 案例 | 编辑器表现 | 运行时验收结果 |
|---|---|---|
| 33 画板文件导出 | 一切正常 | **`.riv` 只有 3362 字节、5 个画板**——28 个画板静默丢失 |
| `.rev` 搬运副本 | 文字"等一会"才正常 | 中文**全部豆腐块**（等 30 秒也没用）——字体没内嵌 |
| 交付脚本 | 正常 | 只装了一个 96×96 的按钮 |

没有这套验收，这三件事都会在**上机那天**才暴露。

### 用无头浏览器自动截图

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --headless=new --disable-gpu --enable-unsafe-swiftshader `
  --virtual-time-budget=12000 --window-size=1400,760 `
  --screenshot="D:\out\check.png" `
  "http://127.0.0.1:8123/index.html?f=test.riv"
```

## 五、交付前检查清单

```
□ 要交付的画板全部是「组件」或已拆成独立文件（每文件一个默认画板）
□ 每个字体资产 Type = Embedded
□ 字体 Include = All glyphs（或确认 Glyphs used 覆盖了所有用字）
□ 规范说明板（xxx animation doc）不在交付文件里
□ .gitattributes 有 *.riv binary
□ 运行时验收通过：画板数对、中文正常、交互能触发
```

## 来源

- 官方最佳实践（画板导出规则原文）、[Exporting for Runtime](https://rive.app/docs/editor/exporting)
- [Assets](https://rive.app/docs/editor/fundamentals/assets-overview)、[Font Assets](https://rive.app/docs/editor/text/fonts)
- [`.riv` File Format](https://rive.app/docs/runtimes/advanced-topic/format)（RIVE 魔数 / 版本头）
- 第一节、第三节的实测数据来自 33 画板文件（2026-10-26）
