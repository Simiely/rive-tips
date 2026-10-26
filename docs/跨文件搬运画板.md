# 跨文件搬运画板：别用剪贴板

**TL;DR**：把画板从一个 Rive 文件复制到另一个，**Ctrl+C / Ctrl+V 会随机丢内容**。正解是走文件级的 `.rev` 导出 → 导入 → 清理，全程无损，且能逐项核验。

> 更新时间：2026-10-26 ｜ 已验证：桌面版 1.9.x

## 一、问题

选中若干画板 → 复制 → 切到另一个文件 → 粘贴。**结果是随机的**：有时全过来了，有时少了几个图形、少了一层状态机、少了图片。

不是操作的问题。Rive 官方更新日志里有成串的同类修复：

- "Copy-pasting solos with images from one file to another **should now paste all images**"
- "Fixed issue with copy-pasting artboards with **nested artboards**"
- "Fixed issue in which copy-pasting one image with a **mesh**… resulting in the second mesh applied to a copy of the first image"

**根因**：跨文件粘贴不是搬字节，而是**在目标文件里重新序列化、重新重建对象**。图片、mesh、嵌套结构、状态机引用，都要在这一步重新解析——任何一处解析失败就是静默丢失。

放大风险的因素：

| 因素 | 影响 |
|---|---|
| 一次选很多画板 | 剪贴板负载变大，失败面变大 |
| 画板含图片 / mesh / 组件 | 重建成本最高，最容易掉 |
| 系统里有剪贴板钩子（输入法、协作软件、网盘） | 大负载可能被截断 |

## 二、先别猜，先量

粘贴出问题时，人的第一反应是"是不是名字被改了/尺寸变了"。这类判断要**验证过再写结论**。

举个真实的例子：画板列表里显示 `整 个系统动效描述`（中间多一个空格），看起来像粘贴把名字改坏了。但查层级接口，画板名是 `整个系统动效描述`，完全正常——**列表里那个空格是终端渲染的换行问题，不是数据**。

判据要落在数据上：

```
get_selection          → 选中了什么
get_artboard_hierarchy → 里面到底有什么
list_artboards         → 名字、尺寸、id
```

## 三、正解：文件级搬运

```
源文件 --export_file(rev)--> .rev --upload_rev(open_file)--> 目标文件 --delete_objects--> 只留要的
```

### 步骤

1. **导出源文件整包**

   ```
   export_file  format=rev  destination=<目录>
   ```

   `destination` **必须是目录**，不是文件路径。传文件路径会报 `destination directory is not usable`。
   导出带 `embeddedAssets: true`，图片字体全都内嵌，不依赖源文件。

2. **清空目标文件**

   `upload_rev` 的 `target=open_file` 要求目标**一块画板都没有**：

   > target open_file requires a file with no artboards; this file already contains an artboard and was left unchanged.

   所以先把目标文件里现有画板删光。删最后一块画板是允许的，删完再导。

3. **导入**

   ```
   upload_rev  file=<.rev 绝对路径>  target=open_file
   ```

   返回 `objectCount` 可以立刻对一下量级。

4. **删掉不要的**

   导入是整包进来的。按 id 保留列表，把其余的用 `delete_objects` 批量删。

### 最大的坑：导出被代理掐死

导出 `.rev` 时如果开着系统代理，会得到：

```
RiveException: Issue with web service client GET
HandshakeException: Connection terminated during handshake
```

**看起来完全不像网络问题**（App 明明能正常开云端文件），但确实是。解决：**临时关掉系统代理**再导。导出完成后可以再打开。

同类坑还有：`.rev` 备份在部分套餐下会被拒绝（`a .rev backup is an upgrade feature and may be refused`），此时 `.riv` 是可行替代——但 `.riv` **不能**用 `upload_rev` 导回去。

## 四、核验：别相信"看起来在"

导入之后必须**逐画板比对指纹**，否则"少了三层状态机"这种问题肉眼看不出来。

指纹字段（全部能从 MCP 读到）：

```
状态机数 / 层数 / 状态数 / 动画状态数 / 转换数 / inputs 数 / listeners 数 / 动画数
```

导出前从源文件采集一遍，导入后从目标文件采集一遍，逐项比。`skills` 里附的 `scripts/rive-audit.ps1` 就是干这个的，输出形如：

```
button                    1/10/54/24/34/11/17/21   MATCH
switch                    1/2/10/4/6/2/2/4         MATCH
```

再加一道视觉验证：对关键画板 `capture_artboard`（**先 focusArtboard**），确认图片、文字、配色都在。结构对 + 像素对，才算搬成功。

## 五、如果非要走剪贴板

降低损失的做法是**一次只搬一个画板，搬完立刻核验，缺了当场重来**。因为丢失是随机的，逐个小批量能显著提高单次成功率，而且每次失败都能定位到具体画板。

但这是兜底，不是方案。画板含图片/mesh 时，重复失败的概率不低。

## 六、不要做的事

- ❌ 不要靠"再粘一次"覆盖：Rive 会生成重名画板（`xxx 2`），后面清理更麻烦
- ❌ 不要在目标文件里重建动画：状态机、关键帧、绑定关系重建等于重做
- ❌ 不要假设粘贴后 id 不变：跨文件粘贴会重新分配 id，脚本里别硬编码源 id

## 来源

- 官方更新日志：[Folders for Inputs and Listeners](https://rive.app/changelog/folders-for-inputs-and-listeners)（图片粘贴修复）
- 官方更新日志：[Improvements to tooltips, copy-paste, and shortcuts](https://rive.app/changelog/improvements-to-tooltips-copy-paste-and-shortcuts)（嵌套画板粘贴修复）
- 官方文档：[Rive MCP Integration](https://rive.app/docs/editor/ai/mcp)（`export_file` / `upload_rev` 行为）
- 第三节、第四节全部为本机实测（2026-10-26）
