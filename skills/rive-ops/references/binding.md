# 数据绑定与状态机驱动

**TL;DR**：Rive 有**两套**驱动模型——老的 State Machine Input 和新的 ViewModel + 数据绑定。同一个文件里两者可以并存，但代码侧要写两套适配。**接入前先确认目标画板用的是哪套**，这是最容易白干一天的坑。

> 更新时间：2026-10-26

## 一、两套模型对照

| | State Machine Input | ViewModel + Data Binding |
|---|---|---|
| 出现时间 | 早期 | 较新，官方主推 |
| 定义在哪 | 状态机里 | 文件级的 Data 面板 |
| 有什么类型 | Trigger / Boolean / Number | Trigger / Boolean / Number / String / **Enum** / **Color** |
| 能不能改属性 | 只能触发状态切换 | 能直接驱动属性（文本、颜色、坐标、可见性……） |
| 跨画板复用 | 每个状态机各自一套 | 一个 ViewModel 可绑多个画板 / 组件实例 |
| 代码侧 | `stateMachineInputs()` | ViewModel 实例 + 属性路径 |

判断一个画板用的哪套，看两个数：

```
inputs > 0            → 有 State Machine Input
dataBinds > 0         → 走 ViewModel
两个都是 0            → 没有任何外部驱动入口（见下）
```

## 二、State Machine Input

状态机上的 `inputs` 是给外部用的把手，`listeners` 是内部自触发的（hover / click / drag）。

一个坑值得单独说：**listener 必须有 target**。没指定目标组件的 listener 在导出后**不会生效**，因为运行时不知道该把指针事件发给谁。做整屏指针输入时，标准做法是：画一个铺满画板的透明背景形状，把 listener 挂在它身上（画板本身不提供指针输入）。

## 三、ViewModel

### 结构

```
ViewModel（文件级，可多份）
  └─ 属性：name + type（trigger/boolean/number/string/enum/color）
       ↓ 绑定
     对象属性（文本内容、颜色、坐标、透明度、可见性……）
```

### 数据绑定（data bind）的三个方向

| direction | 含义 | 典型场景 |
|---|---|---|
| `toTarget` | 数据 → 画面 | 温度值 → 显示文本 |
| `toSource` | 画面 → 数据 | 拖拽滑块 → 写回数值 |
| `twoWay` | 双向 | 可编辑输入框 |

实盘里最常见的是 `toTarget`，滑块类控件会有一个 `toSource`。

### 三个高频坑

1. **字符串绑文本，要绑到 Text Run，不是 Text 对象**
   绑错层级时值能写进去，但不显示——不报错，查起来很费时间。

2. **Converter 删不掉**
   创建了错误的 converter 只能留在 Data 面板里等人工清理。所以**先 `listConverters` 看有没有能复用的**，别再新建一个。数字转文本（`convertToString`）是最常见的一个。

3. **重复绑定同一个属性会"重定向"，不是叠加**
   对已绑定的对象再 bind 一次，会改掉原绑定目标而不是新增一条。想要两个对象读同一个值，是**两个对象各绑一次**，不是给它俩建一条共享绑定。

### 嵌套与相对路径

ViewModel 可以套 ViewModel。当一个属性有多条路径能到达时，必须显式给 `path`；`isRelative` 让绑定从当前实例往下按名字解析（对应编辑器里的 relative 开关）。

## 四、没有入口的画板

审计里最容易被忽略的一类：

```
inputs == 0 且 dataBinds == 0 且 动画状态 ≥ 2
```

在编辑器里手点能播——因为状态机内部可能有 exit time 自动流转，或者默认转换直接进第一个动画。但**从代码只能整体播放，无法触发指定分支**。

一个滑动手势画板如果长这样：两个动画状态（`上滑`/`下滑`）、三条转换、零输入——运行时永远只会播第一个。看起来"做完了"，实际只能演一半。

**判定**：给这种画板补一个 ViewModel trigger（或 Boolean + 状态转换条件），然后跑一次 `simulateStateMachine` 确认它真的会跳到另一个状态。

## 五、验证：别靠肉眼看

`animation_editor` 的 `simulateStateMachine` 可以**无头跑**一台状态机：

- 输入：`[{frame, property, value}]`，按 ViewModel 属性驱动
- 输出：trace —— 进入的 state、走过的 transition、触发的事件、每层停在哪
- **跑完会还原写入的值**，文件不变
- **不渲染像素**，只验逻辑

典型判据：

```
驱动一次 → transitionsObserved > 0 且最终停在预期状态   ✅
驱动一次 → trace 为空                                  ❌ 条件没连上 / 目标错了
```

注意它不能在有时间轴或状态机打开编辑时运行，先退出编辑态。

## 六、代码侧最小接入

以 Web 运行时为例（State Machine Input 路线）：

```js
const r = new rive.Rive({
  src: "/assets/ui.riv",
  canvas: document.getElementById("canvas"),
  stateMachines: "主状态机",
  autoplay: true,
  onLoad: () => {
    r.resizeDrawingSurfaceToCanvas();
    const inputs = r.stateMachineInputs("主状态机");
    const open = inputs.find(i => i.name === "打开");
    open.fire();                    // Trigger：一次性
    const temp = inputs.find(i => i.name === "温度");
    temp.value = 24;                // Number：持续设值
  }
});
```

ViewModel 路线的 API 随版本演进较快，**以上机时的官方文档为准**，别照抄旧教程。

## 七、给设计侧的约定（省开发时间）

1. **一个功能一个 ViewModel**，别把整屏塞进一个
2. **属性名用英文、稳定**——拼写错误会原样进代码（`tempertrue` 这种改起来要动两端）
3. **trigger 只用于"发生了一次"**，需要持续状态用 boolean
4. **同义参数统一命名**：`swipeUp` / `SwipeUp` / `Swipeup` 在代码里是三个不同的字符串
5. **交付前跑一遍指纹采集**，确认每个交互画板都有入口

## 来源

- 官方文档：[Data Binding](https://rive.app/docs/editor/data-binding)
- 官方文档：[Rive MCP Integration](https://rive.app/docs/editor/ai/mcp)（读取 inputs / dataBinds / 模拟状态机）
- 官方文档：[Web Runtime](https://rive.app/docs/runtimes/web)
- 第二、四节的判据来自实盘审计（2026-10-26）
