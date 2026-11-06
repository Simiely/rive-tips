# 关键帧动画（MCP 实操）

用 MCP 工具做关键帧动画的完整经验。全部来自 2026-11 车机充电呼吸灯项目实测（含一次彻底翻车与回滚）。

## 一、核心工具与命令

| 工具 | 命令 | 用途 |
|---|---|---|
| `animation_editor` | `listLinearAnimations` / `queryStateMachine` / `createLinearAnimations` / `modifyKeyFrames` / `queryKeyFrames` / `updateStates` / `delete` | 关键帧全流程 |
| `queryStateMachine` | `data.stateMachineId` | 查层（`layerName`/`layerId`）与状态 |
| `modifyKeyFrames` | `add` / `change`（带 `keyframeId`）/ `delete` | 打点、改值、删点 |
| `animation_editor` 属性键 | `56`=frameRate、`57`=时长(帧)、`58`=WorkTime、`59`=LoopTime、`56..59` 组合控制循环 | 建 6s 循环：`{56:60, 57:360, 58:1, 59:1}` |

常用属性键（`set_property_values` / `query_property_values`）：

| 键 | 含义 | 键 | 含义 |
|---|---|---|---|
| 13 / 14 | x / y | 16 / 17 | scaleX / scaleY |
| 18 | opacity | 4 | name |
| 20 / 21 | path width / height | 23 | blendMode（12=plus） |
| 37 | solidColor | 41 | isVisible |
| 47 / 48 / 49 | stroke thickness / cap / join | 747 | blendmodevalue（12=additive） |
| 470 | stroke position | 848 | **scriptAssetId**（ScriptedDrawable） |
| 810 / 811 | computed width / height（只读） | 3 / 5 / 6 | dependentIds / parentId / childOrder |

## 二、行为红线（实测）

| 行为 | 说明 |
|---|---|
| **两段循环动画共用边界帧** | 上一趟终点与下一趟起点落在**同一帧**时，`modifyKeyFrames` 按帧去重，**起点覆盖终点** → "到达"关键帧丢失 → 插值器从倒数第二个采样直接飞向新出生点 → 可见的**倒飞/回弹**。修法：每趟占 `[base, base+L-1]`，下一趟从 `base+L` 起，归位压缩到 1 帧，且两端 opacity=0 |
| `simulateStateMachine` | 会**还原**通过 `set_property_values` 写入的值；不渲染像素；编辑态拒跑。验证动效不能靠它 |
| `capture_artboard` 陈旧渲染 | 设置后立刻截可能拿到**旧帧**（相邻两次截图完全一致）。对策：`sleep` 后连拍两张对比，或连拍多次取后一次 |
| `capture_artboard` 不执行脚本 | 脚本节点的内容永远不在截图里 |
| 关键帧插值 | `interpolationType: linear/cubic/hold`；采样 5~6 个点 + linear 已足够复刻缓动曲线（sin³、smoothstep 均可） |
| 层删除 | `delete_objects` 层 ID 即可；**删除层不删它引用的对象**，对象要单独清 |
| 删除对象 vs 层 | 先删层（解除动画引用）再删对象，顺序反了会留悬空引用 |
| 复制对象 | `duplicate_objects` **不返回新 ID**，且多对象副本全塞进最后一个对象的父级——只能靠"复制前后父级 children 差集"定位新 ID |

## 三、键值生成模式（代码烘关键帧）

对"沿路径运动 + 淡入淡出"这类效果，MCP 烘关键帧的固定套路：

```python
QS_XY = [0.0, 0.2, 0.45, 0.72, 1.0]      # 位移采样点
QS_A  = [0.0, 0.12, 0.66, 1.0]           # 透明度采样点（对应 smoothstep 拐点）
for trip in range(n):
    base = trip * L
    for q in QS_XY:
        f = base + round(t(q) / T * (L - 1))    # 注意 -1：给下一趟留 1 帧
        add(obj, 13, f, posX(q)); add(obj, 14, f, posY(q))
    for q in QS_A:
        f = base + round(t(q) / T * (L - 1))
        add(obj, 18, f, alphaAt(q) * 100)
```

- 速度/透明度公式来自设计稿时，**逐条抄公式**（如 `v = pace*(26+(120+280g)*q^1.7)`、`a = 0.88*min(smoothstep(0,0.12,q), 1-smoothstep(0.66,1,q))`），数值积分后打点即可，效果与 canvas 版一致。
- 循环尾帧必须与首帧衔接（位置相同或 opacity=0）。

## 四、验证清单（打完帧必查）

1. `queryKeyFrames` 导出某对象全部键，检查**相邻大位移段的帧间隔**：`Δf>2 且 |Δx|>12` 的段若出现在"归位"处即为倒飞 bug；
2. 全量扫描所有瞬移帧（`Δf<=2`），确认每一处 `opacity==0`；
3. 首尾帧衔接：`frame 0` 与 `frame 总长` 的 x/y/opacity 一致；
4. `duration / loop` 设置正确（`57`=总帧、`59`=1 循环）。

## 五、本画板最终分工（关键帧 vs 脚本）

| 效果 | 实现 | 原因 |
|---|---|---|
| 呼吸缩放 / 浮动 | 关键帧（`Layer 1`、`浮动`） | 作用于**图标本体**的 transform，脚本无 API 修改；代码化需转组件画板（见程序化文档第九节） |
| 粒子 / 光圈 / 脉冲辉光 / 描边流动 | **脚本**（`fx` + `stroke_fx`） | 纯程序化几何与真实路径 dash，参数化后无需重烘 |

## 六、踩坑记录（按损失排序）

| 坑 | 现象 | 教训 |
|---|---|---|
| 边界帧覆盖（见红线） | 40 颗粒子全部倒飞，像"来回弹" | 生成关键帧后必须做验证清单第 1 项 |
| 径向渐变单位 | `startX=50` 被当成 50 倍尺寸，光只剩边角余光 | MCP 写渐变不可靠，宁用多层叠加 |
| `setPaints` 清空 paint | 带 alpha 停靠点的渐变写入后 `paint: null`，形状不渲染 | 改样式优先 `addPaints`（新建）/ `addGradientStops`；改完 `query_property_keys` 回读验证 |
| 透明度量纲 | 以为没画出来，实际是 alpha=1/255 | 先排查量纲，再排查渲染 |
| 层级面板不刷新 | MCP 加的 Fill/Stroke 在编辑器层级里不显示 | 层级只显示 Path 子行（官方行为）；样式在右面板 |
| 删除 ScriptAsset | 连带删除引用它的节点 | 改脚本内容，别删了重建 |
