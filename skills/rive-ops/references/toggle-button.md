# 按钮开关与按压动效

**TL;DR**：一个图标就是一个开关按钮：按下缩放 96% + 叠加 `B4B4B4 35%` 浮层，200ms；抬起回到 100% + 浮层淡出，**300ms**；总时长 **500ms**。激活态用 `#33e6e6e6` 底色 + 右上角 `#ff5d00` 橙点。按钮状态用 ViewModel boolean，点击由 **Listener Action Script** 取反，状态机用**一按钮一层**保证多个按钮可以同时激活。

> 更新时间：2026-10-27 ｜ 已验证：Rive 桌面版 1.9.415.6404（Windows）+ 本地 MCP 40 工具

## 一、先把时间读对

动态文档里写的是「按下 200ms / 抬起 500ms」，但 **500ms 是整条时间轴的总长度**，不是抬起段再持续 500ms：

```
0ms ───── 200ms ───────────── 500ms
  按下 200ms      抬起 300ms
```

按 60fps 换算：

| 阶段 | 帧 | 时长 |
|---|---|---|
| 按下 | 0 → 12 | 200ms |
| 抬起 | 12 → 30 | 300ms |
| 总时长 | 0 → 30 | 500ms |

动画对象的属性键：

| 属性 | 键 | 值 |
|---|---|---|
| fps | `56` | 60 |
| duration | `57` | 30 |
| speed | `58` | 1.0 |
| loop | `59` | 0 = oneShot |

> 如果按「200ms + 500ms」做成 42 帧，效果会明显偏长。这是本条最容易被误读的地方。

## 二、曲线

| 用途 | 名称 | cubic-bezier |
|---|---|---|
| 按下 | Quart-2 | `(0.25, 0.1, 0.25, 1.00)` |
| 抬起 | ease | `(0.42, 0.00, 0.58, 1.00)` |

`modifyKeyFrames` 的写法：

```json
{
  "objectId": "<对象 id>",
  "propertyKey": 16,
  "frame": 0,
  "value": 100,
  "interpolationType": "cubic",
  "cubicParams": { "x1": 0.25, "y1": 0.1, "x2": 0.25, "y2": 1.0 }
}
```

- frame 0 的 keyframe 用 Quart-2，负责 0→12 帧
- frame 12 的 keyframe 用 ease，负责 12→30 帧
- frame 30 是终点，用 linear 即可

## 三、单按钮的完整结构

以「屏幕清洁」为实测样板：

| 部件 | 实测 ID / 值 |
|---|---|
| 按钮组 | `2-1`，原点 `(216, 576)` = 按钮中心 |
| 背景 Shape | `15-1055`，256×256 |
| 背景 SolidColor | `15-1065`，未激活 `#14e6e6e6`，激活 `#33e6e6e6` |
| 按压浮层 | `2-193`，复制背景，`#B4B4B4`，opacity 0，最上层 |
| 激活橙点 | `2-205`，26×26，`#ff5d00`，局部 `(86, -86)`，opacity 0 |
| 激活动画 | `2-223`，30 帧 / 500ms / oneShot |
| 取消激活动画 | `2-224`，同上 |
| ViewModel | `2-217`，属性 `isActive` = `2-219` |
| toggle 脚本 | `2-801`，类型 `listenerAction` |
| click 监听器 | `2-802`，目标 `2-193` |
| 状态机 | `15-6`，层 `15-7` |
| 状态 | `15-11` Idle、`2-805` Activating、`2-806` Deactivating |
| 转换 | `2-807` / `2-808` / `2-809` |

### 1. 准备按钮

- 按钮组原点必须在按钮中心；组缩放 100%/100%。
- 背景是 256×256 圆角 Shape，填充 `#14e6e6e6`（未激活）。
- 激活底色是 `#33e6e6e6`，橙点是 26×26 `#ff5d00`，相对组原点 `(86, -86)`。

### 2. 加浮层与橙点

```text
复制背景 Shape -> <Overlay>
  fill = #B4B4B4
  opacity = 0 (键 18)
  reorder sendToFront

复制橙点 Shape -> <ActiveDot>（如果按钮原本没有橙点）
  reparent 到按钮组
  x = 86, y = -86（注意 reparent 后要重新设，reparent 会保留世界坐标）
  opacity = 0
```

- 浮层放最上层时，橙点会被 35% 浮层轻微压灰；这是预期。
- 如果按钮原本已有橙点（如蓝牙当前是激活态），**复用已有橙点**，只动画它的 opacity，不要再复制一个。

### 3. 两条动画

**Activate（未激活 → 激活）**

| 帧 | 组缩放 sx/sy | 浮层 opacity | 橙点 opacity | 背景颜色 |
|---|---|---|---|---|
| 0 | 100 / 100 | 0 | 0 | `#14e6e6e6` |
| 12 | 96 / 96 | 35 | 100 | `#33e6e6e6` |
| 30 | 100 / 100 | 0 | 100 | `#33e6e6e6` |

**Deactivate（激活 → 未激活）**

| 帧 | 组缩放 sx/sy | 浮层 opacity | 橙点 opacity | 背景颜色 |
|---|---|---|---|---|
| 0 | 100 / 100 | 0 | 100 | `#33e6e6e6` |
| 12 | 96 / 96 | 35 | 100 | `#33e6e6e6` |
| 30 | 100 / 100 | 0 | 0 | `#14e6e6e6` |

- 属性键：组缩放 `16/17`，opacity `18`，SolidColor 颜色 `37`。
- 两条动画 `loop` 键 `59` 必须写 `0`（oneShot），fps 60、duration 30。
- 播完停在最后一帧，这样激活/未激活状态能保持住。

### 4. ViewModel

- 每个按钮一个 boolean 属性（如 `bluetoothActive`），全部放在同一个 ViewModel 里。
- 创建实例并 `bindViewModelToArtboard` 绑定到 Artboard。
- 属性名用英文、稳定，代码侧会原样使用。

### 5. toggle 脚本

```lua
type Toggle = { context: Context }

function init(self: Toggle, context: Context): boolean
    self.context = context
    return true
end

function perform(self: Toggle, pointerEvent: PointerEvent)
    local vmi = self.context:viewModel()
    if vmi then
        local active = vmi:getBoolean("isActive")
        if active then
            active.value = not active.value
        end
    end
end

return function(): ListenerAction<Toggle>
    return { init = init, perform = perform, context = late() }
end
```

- 每个按钮一个脚本，只改 `getBoolean("...")` 里的属性名。
- `manage_scripts create` 会根据返回类型识别成 `listenerAction`。
- 创建后必须跑 `script_diagnostics`，返回 `[]` 才算过。

### 6. click 监听器

```json
{
  "stateMachineId": "15-6",
  "listeners": [{
    "name": "BT_Toggle",
    "targetId": "<overlay id>",
    "listenerTypes": ["click"],
    "actions": [{ "type": "scripted", "scriptAssetId": "<script id>" }]
  }]
}
```

- 目标必须是可见 Shape（浮层），不要挂在组 Node 上。
- 如果 opacity 0 的浮层不参与命中测试，加一个同尺寸透明命中层，监听器挂命中层。

### 7. 状态机：一个按钮一层

**多按钮必须一层一按钮。** 如果所有按钮都塞在同一个 Layer：

- 只有一个 Layer 的活动状态，A 按钮激活后，点 B 按钮无法进入 B 的 Activating；
- 多个按钮不能同时保持激活。

正确结构：

```text
State Machine 1
  ├─ Layer 1: 屏幕清洁（已有）
  ├─ Layer BT: 蓝牙
  ├─ Layer WIFI: 无线网络
  ├─ ...
```

单层状态：

```text
Entry ──> Idle
Idle ──(bool == true)──> Activating
Activating ──(bool == false)──> Deactivating
Deactivating ──(bool == true)──> Activating
```

- `Activating` / `Deactivating` 用各自按钮的 500ms 动画。
- `Idle` 可以用一个空的共享时间轴（如 `ScreenClean_Idle`）。
- 动画 oneShot，播完停最后一帧；状态机停在 Activating/Deactivating，不回 Idle。

### 8. 初始就是激活态的按钮

蓝牙当前是激活态（底色 `#33e6e6e6` + 橙点可见）。不要把它强行改成未激活再套模板，而是：

- 复用现有橙点，不新建；
- ViewModel 初始值设为 `true`；
- Layer 的初始状态叫 `IdleActive`，用空时间轴持有当前激活画面；
- 转换改为：
  - `IdleActive → Deactivating`：bool == false
  - `Deactivating → Activating`：bool == true
  - `Activating → Deactivating`：bool == false
- 不要建 `IdleActive → Activating`，否则会从激活态又播一次激活。

### 9. 带档位条的按钮（主驾加热 / 主驾通风）

这类按钮图标下方有 3 格档位条，视觉上已经是激活态，但用户只要求开关效果：

- 按「初始激活」处理：`IdleActive`、ViewModel 初始 `true`；
- 橙点是原设计里已有且常亮的 Shape（主驾加热 `15-551`、主驾通风 `15-418`，局部 `(86,-86)`），**直接动画它的 opacity**，不新建；
- 3 格档位条保持设计稿现状，不参与动画（不做档位切换）；
- 背景 SolidColor 分别是 `15-712`、`15-550`，浮层从背景复制后固定 `#ffb4b4b4`。

## 四、验证

1. **时长**：动画 fps 60、duration 30、loop 0；`simulateStateMachine` 激活应约 30 帧完成。
2. **待机**：浮层/橙点 opacity 0 时，截图必须和修改前逐像素一致。
3. **激活态**：截图对比主驾加热的底色和橙点位置。
4. **按压态**：浮层 35% 应让按钮变亮。
5. **逻辑**：`simulateStateMachine` 驱动 boolean true/false，确认进入 Activating/Deactivating。
6. **真实点击**：MCP 没有 pointer 模拟，必须在预览里点一次；点击无效优先检查命中层。

## 五、复用手册

对每个新按钮准备：

| 参数 | 示例 |
|---|---|
| 按钮组 ID | `2-4` |
| 背景 Shape ID | `15-1449` |
| 背景 SolidColor ID | `15-1459` |
| 浮层 ID | 复制后新 ID |
| 橙点 ID | 已有则复用，没有则复制 |
| ViewModel 属性 | `bluetoothActive` |
| 动画 | `BT_Activate` / `BT_Deactivate` |
| 脚本 | `toggle_bluetooth` |
| 状态机层 | `BT_Layer` |

批量执行顺序：

1. 查组/背景/SolidColor 和初始状态；
2. 复制浮层，配置颜色/透明度/置顶；
3. 复制或复用橙点；
4. 建 2 条 30 帧动画 + 15 个关键帧；
5. 加 ViewModel 属性；
6. 建脚本 + 诊断；
7. 挂 click listener；
8. 建独立 Layer + 三个状态 + 四条转换 + 三个条件；
9. 逐按钮 simulate + 截图。

### 批量执行时的 API 陷阱（9 按钮实测）

| 环节 | 陷阱 | 正确做法 |
|---|---|---|
| 复制浮层 | `duplicate_objects` 一次传多个 ID 时，**所有副本都被塞到最后一个对象的父级** | 复制后逐个 `reparent_objects` 回各自按钮组 |
| 复制橙点 | 同一个 ID 重复写 8 次，只生成 **1 个副本**（自动去重） | 一次传一个 ID，循环调用 |
| 颜色关键帧 | 动画目标误写成浮层的 SolidColor，激活时底色不变 | 目标必须是**背景 Shape 的 SolidColor**；浮层 SolidColor 固定 `#ffb4b4b4` |
| 脚本类型 | `manage_scripts create` 后 `get_scripts` 显示 `utility` | 必须跑一次 `recompile_all_scripts`，才会识别成 `listenerAction` |
| 入口转换 | `createStateMachineLayers` 不建 Entry→初始状态 | 查询 Layer 拿 `entryStateId`，再 `createTransitions` 补一条 |
| 初始激活 | 只把底色画成激活，ViewModel 仍为 false | 实例属性对象（`ViewModelInstanceBoolean`）的 `propertyvalue` 键是 `593`，用 `set_property_values` 置 true |
| 模拟链 | `simulateStateMachine` 在动画结束即 `settled` 停止，之后的输入不再执行 | 两段式验证：①单次 true 看 Activating；②在动画中途改回 false 看 Deactivating |
| 截图取样 | 截图尺寸 = `longEdge / artboardWidth`（本画板 2560×1440，longEdge 1536 → 0.6） | 取样前先算比例，否则会读到按钮间隙而误判没生效 |

## 六、坑位

| 现象 | 原因 | 处理 |
|---|---|---|
| 效果明显偏长 | 把 500ms 当成抬起段，做成 42 帧 | 总时长 30 帧：200ms + 300ms |
| 按住时按钮没有保持 96% | 用了 click + 单条 press+release 时间轴 | 需要按住态就拆 down/up；当前模板是点击后播放完整 500ms |
| 多个按钮只能一个激活 | 所有按钮塞在同一个 Layer | 一按钮一层 |
| 点击没反应 | opacity 0 浮层不命中 / 监听器挂错组 | 监听器挂 Shape；加透明命中层 |
| 脚本不执行 | 脚本不是 listenerAction / ViewModel 没绑 | `get_scripts` 看类型；`script_diagnostics`；检查 `context:viewModel()` |
| 橙点位置跑偏 | reparent 保留世界坐标 | reparent 后重新写局部 x/y = 86,-86 |
| 激活按钮再点一次又播激活 | 初始激活态仍建了 Idle→Activating | 初始激活用 IdleActive，只建 IdleActive→Deactivating |

## 七、实测记录

- 屏幕清洁：按下 200ms、抬起 300ms、总 500ms；待机截图与修改前一致；激活态底色/橙点与主驾加热一致。
- `simulateStateMachine`：激活约 33 帧完成，取消激活约 52 帧完成。
- 脚本 `screen_clean_toggle` 诊断 `[]`，监听器 `2-802` 绑定在浮层 `2-193` 上。
- 蓝牙（初始激活）+ 无线网络、热点、专注模式、一键静音、系统清理、离车不下电、加油口盖、全车锁共 9 个按钮批量接入，状态机共 10 层。
- 9 个 toggle 脚本诊断均为 `[]`；`simulateStateMachine` 单按钮激活/取消激活均命中对应 Layer。
- 9 按钮改完后待机截图与改前**逐像素一致**（bbox 为空，0 差异像素），激活态统一为 `#33e6e6e6` + 橙点。
- 主驾加热 / 主驾通风：复用原橙点，按初始激活接入；`simulateStateMachine` 关闭/再开分别命中 Deactivating/Activating；关闭态底色 42/255、激活态 67/255（与其它按钮一致）。
- MCP 无 pointer 模拟，真实点击在预览里验证。

## 来源

- [Rive Listener Action Scripts](https://rive.app/docs/scripting/protocols/listener-action-scripts)
- [Rive Data Binding Scripting](https://rive.app/docs/scripting/data-binding)
- [Rive States](https://rive.app/docs/editor/state-machine/states)
- [Rive Listeners](https://rive.app/docs/editor/state-machine/listeners)
