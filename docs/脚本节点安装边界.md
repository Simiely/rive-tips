# 脚本节点安装边界

MCP / CLI 在脚本节点"安装"这件事上能做什么、不能做什么。全部实测（2026-11，MCP 40 工具 + CLI 1.8.0）。

## 一、能力矩阵

| 操作 | MCP | CLI | 说明 |
|---|---|---|---|
| 建 / 删 / 改名 / 移动脚本**文件** | ✅ `manage_scripts` | ✅ RML `<ScriptAsset file="x.luau" name="x" id="0:80"/>` | 只管文件；**内容修改用 `text_editor`**（支持 str_replace 增量改） |
| 查脚本协议类型 | ✅ `get_scripts` → `type: node/utility/pathEffect/…` | `rive inspect` | `type: node` 才会出现在画板右键菜单 |
| **新建脚本节点** | ❌ 无接口 | ✅ RML `<ScriptedDrawable scriptAssetId="…" x="…" y="…"/>` | 编辑器：右键**画板行** → 菜单选脚本 |
| **给 Stroke 挂 Path Effect** | ❌ Stroke 属性键无 effects/script 槽 | ✅ RML `<ScriptedPathEffect scriptAssetId="…"/>` | 编辑器：选中 Shape → 右面板 Stroke 区 → Options → Effects → `+` |
| 修改已有节点的 `scriptAssetId`（键 848） | ⚠️ 能写 | — | **运行时实例不重绑**：init 能跑、draw 一次不来 |
| 复制脚本节点再改指向 | ❌ 同上 | — | 实测两次失败，数据全对但绑定不刷新 |
| 删除 ScriptAsset | ⚠️ **连带删除引用它的节点** | — | 换脚本内容用 `text_editor` 改源码，不要删了重建 |
| 整包重建后回传 | — | ⚠️ `upload_rev` 要求目标**零画板**；`push` 是整包覆盖 | 90MB/43 画板的文件不建议走，资产/字体偏差风险大 |

## 二、"改 848 不重绑"的完整证据链

```
1. duplicate 已有 Node Script 节点 → 新节点 id ✓
2. reparent 到目标画板 ✓
3. set_property_values {848: 新脚本id} → 回读正确 ✓
4. recompile_all_scripts → success ✓
5. Console: [script] init 出现 ✓（说明脚本加载了）
6. draw 一次不来 ✗（播放/重绘均无）
结论：运行时实例在节点创建/复制那一刻按原脚本绑定，848 只是数据字段。
```

**正确姿势**：脚本 `type: node` 后，让用户在编辑器右键菜单里正经创建一次（5 秒），之后所有参数修改都可以由 MCP 完成。

## 三、右键菜单出现脚本的条件

1. `get_scripts` 里该脚本 `type` 为 **node**（加载成功）；
2. 脚本无编译错误（**有错就不会出现在菜单里**，且不报错提示）；
3. 工厂返回包含 `init`（有 `draw` 才渲染，但菜单出现只要求结构合法）。

排查顺序：

```
CLI: rive <dir> --verify          ← 带行号的类型错误（script_diagnostics 不可信，恒返回 []）
MCP: get_scripts → type           ← utility = 加载失败
编辑器: View → Console            ← print 输出 + 运行时错误
```

## 四、典型加载失败（都是实测）

| 错误 | 症状 |
|---|---|
| 作用域：`if` 块内 `local x` 在块外引用 | 加载失败 → `type: utility`，**编辑器与 MCP 都不报错** |
| 工厂缺字段 | 类型检查报 `Key 'x' not found`（CLI 可见） |
| 模块级 `local X: { number } = {...}` | **Luau 编译器段错误**（CLI exit 139 零输出） |
| Layout 协议 `resize` 签名 | 必须是 `(self, size: Vector, scale: number)` 三参 |
| `Color.rgba` alpha 写 0–1 | 编译通过、运行"看不见"（透明度量纲，见专篇） |

## 五、安装后的标准配置（MCP 可完成）

```python
# 位置：图标中心（脚本内部以节点原点为圆心画）
set_property_values { node: {13: 2227, 14: 1170, 18: 100} }
# 层级： sendToBack → bringForward ×N 微调；z 序 index 0 = 最前
# 命名： {4: "粒子脚本"}
```

层级参考（本画板定稿）：`充电图标 → 粒子脚本 → 充电动效 → bg_plate`。

## 六、决策树

```
要在画板上加一个脚本节点？
├─ 是全新文件/小工程 → CLI RML 直写（一次到位）
├─ 是已有的大文件
│   ├─ 用户在编辑器旁 → 让用户右键画板创建（最稳，脚本必须 type:node）
│   └─ 用户不在 → 复制同类节点改 848？ ❌ 死路（不重绑）
└─ 只想改已有节点的行为 → text_editor 改脚本源码（节点不动，自动生效）
```
