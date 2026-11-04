# 编辑器2026界面变更对照

2026 版 Rive 编辑器（1.9.x / Early Access）里，老教程说的东西都搬了家。本文是"找不到"时的对照表。

## 一、Effects 面板（最影响脚本工作流）

| 老版本 | 现版本 |
|---|---|
| Trim Path / Dash 直接在描边选项里，一次只能一个 | 都搬进 **Effects 面板**，可**叠加多个**（Trim + Dash + 脚本效果同一形状） |
| 无 Feather | **Feather 在 Effects 面板**（可做模糊/辉光/矢量阴影） |
| 脚本效果无入口 | 挂载点：**选中 Shape → 右面板 Stroke 区 → Options(⋯) → Effects → `+` → Script Effects** |

**找不到 Effects 的最常见原因**：选中的是 **Group/Node**（`Style: Group`）而不是 **Shape**（`Style: Shape`）。只有 Shape 的属性里才有 Fill/Stroke，进而才有 Effects。

层级里**不会出现 Fill/Stroke 子行**——官方文档："Expanding a shape layer will reveal the paths it's using"，只有 Path。样式在右面板。

## 二、左侧面板：Tab 变 Panel

| 老版本 | 现版本 |
|---|---|
| Hierarchy / Assets / Data / Agent 是互斥 Tab | **Panel 并列**，可同时开、可拖位置、可折叠 |
| — | 每个面板有**内置搜索** |
| — | 老教程里的"看不到的选项"多半收进了 **⋯（三点菜单）**：Assets 的类型过滤、Data 的结构/值切换都在那里 |

**脚本节点的创建入口**：Hierarchy 里**右键画板那一行**（不是组、不是形状）→ 菜单里选脚本。脚本 `type: node` 且无编译错误才会出现。

## 三、Animate 模式

| 老版本 | 现版本 |
|---|---|
| inputs / listeners 独立面板常驻 | 状态机右侧的**小 Tab，默认折叠**；Animation 面板内也能进，带搜索 |
| Layer 是状态机上方一排 Tab | **独立 Panel，纵向排列**（Layer 顺序更直观），可显示/隐藏 |
| 老的横向 layers 条 | 变成 **timeline history**（打开过的时间线自动收集成 tab，类似 PR 的项目切换） |

## 四、Console 挪了

| 老版本 | 现版本 |
|---|---|
| 时间线右侧 | **底部**；分 **State Machine** 与 **Script** 两个页签——脚本 `print()` 在 Script 页签 |

调脚本动画必开：`View → Console`。

## 五、命名变更对照

| 老教程说法 | 现在叫 |
|---|---|
| Nested Artboards（嵌套画板） | **Components**（组件）——且必须显式标记为组件才出现在 Component 工具列表 |
| Export（导出） | **Publish**（发布，含共享库/跨文件组件） |
| Invite | 邀请协作者（editor/guest/view-only） |
| 画板裁剪图标 | 画板属性里的**复选框**（关掉可看到出界内容） |
| Import/Export 文件 | **付费计划功能**（免费版不能导入导出；但自定义字体/音频免费版反而新增了） |

## 六、新东西（值得知道）

| 功能 | 说明 |
|---|---|
| **Split stage** | 画布顶部选择器，可同屏开 2~3 个 stage——左边放项目、右边调脚本，天然适合脚本开发 |
| Speed Graph | Early Access，控制数值加减速 |
| **clip 跟踪脚本路径效果** | 0.8.5376 起，被脚本改写几何的形状可以当裁剪源（以前 clip 只认原始几何） |
| Listener 预设 | 新建 Listener 时可选预设动作，不必从空白开始 |

## 七、UI 操作诊断口诀

```
找不到 Effects？
  → 选中的是 Group？换 Shape（Style: Shape）
  → 是 Fill 不是 Stroke？Effects 挂在 Stroke 上
  → 在 Design 模式吗？
  → 面板滚到底了吗？Effects 在属性面板末尾
  → 三点菜单(⋯)翻了吗？2026 版很多入口收进去了

找不到脚本节点创建入口？
  → get_scripts 里 type==node 吗？（utility 不出现在菜单）
  → 右键的是画板行还是组？
```
