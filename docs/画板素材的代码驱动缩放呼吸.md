# 画板素材的代码驱动（缩放呼吸）

"用素材的效果"最轻量的实现方式：**素材一行不改，在它所在画板的空时间线上打缩放关键帧**。本文来自 2026-11 车机充电呼吸灯交付板（003 充电中）实测。

## 一、什么时候用这条路线

| 需求 | 路线 |
|---|---|
| 循环类呼吸/脉动（固定周期） | **本篇：素材 + 空时间线关键帧**（最简，无脚本依赖） |
| 逐帧实时公式、非循环、与输入联动 | 组件画板 + `Input<Artboard>` + 脚本 transform（重） |
| 自绘几何（无素材） | Node 脚本自绘（见《程序化动画Luau脚本》） |

循环呼吸效果用关键帧**更简单且零运行时依赖**——之前"素材代码化必须组件画板"的结论只对非循环实时公式成立，循环类不必上组件。

## 二、找到素材与它的锚点

辉光在交付板上是**一张 Image**（不是脚本、不是形状）：

```
充电图标 [Node]
充电图标_辉光 [Image]   ← 就是它
bg_plate   [Image]
```

**动手前必查 origin**（缩放锚点）：

```python
keys = query_property_keys(obj)["properties"][obj]
# 关注：originx(380) / originy(381) / computedwidth(810) / computedheight(811)
```

- 本例实测 `originx=50, originy=50`（中心）→ 直接改 scale，光心不偏移；
- 若 origin 是 0,0（左上），改 scale 会让中心偏移——必须先改 origin 或补偿 x/y；
- Image 的尺寸没有直接键，用 `computedwidth/height`（当前缩放下的显示尺寸）反推。

## 三、找到画板的状态机

画板属性键 **`defaultStateMachineId`（键 236）** 存的是状态机 id：

```python
r = query_property_values({artboardId: [236]})   # → {"236": "40-11444"}
queryStateMachine(stateMachineId=r)              # 看层与动画
```

注意 `queryStateMachine` 必须经 `animation_editor` 调（`command="queryStateMachine"`），直接调会报 Tool not found。

## 四、空时间线复用（零冲突打法）

交付板上常有一条**空时间线**（如 `Timeline 1`：60 帧、无关键帧、未循环）——直接改造成呼吸动画，不建新层、不动结构：

```python
# 1) 改时钟：57=时长(帧)，59=1(循环)
set_property_values { timelineId: {57: 144, 59: 1} }

# 2) 打呼吸键（Image 的 sx/sy = 键 16/17）
# 3 次心跳 × 0.8s，2.4s(144帧) 循环；origin=中心，sx=sy 同值
frames = []
for k in range(3):                     # 每周期 48 帧
    b = 48 * k
    for f in (0, 6, 12, 18, 24):       # 峰在 b+12（sin 峰在 1/4 周期处）
        t = f / 60.0
        p = max(0.0, math.sin(2*math.pi*t/0.8)) ** 3
        frames.append((b + f, base * (1 + amp * p)))
frames.append((144, base))             # 循环尾 = 循环头
```

实测打点结果（base=50.034，amp=0.15，即 +15%）：

```
(0,50.03) (6,52.69) (12,57.54) (18,52.69) (24,50.03)
(48,…) (54,…) (60,57.54) … (96,…) … (144,50.03)
```

验证：`f0 == f144`（循环无缝）、峰间有过渡点（linear 插值即柔和）、sx 与 sy 键值相同。

## 五、呼吸灯的三层语义（无论哪条路线都成立）

| 层 | 周期 | 实现 |
|---|---|---|
| 常亮底光 | — | alpha 恒定（关键帧路线=素材本身常亮；脚本路线=去掉 early return） |
| 心跳胀缩 | 0.75~0.8s | sin³ 打点 / 脚本半径公式 |
| 慢呼吸 | 2.4s | ±5% 半径（脚本）或把循环设计成 2.4s（关键帧天然成立） |

## 六、多画板文件的操作纪律（本轮翻车点）

一个文件里存在 `003 充电中` 和 `003 充电中 呼吸灯` 两块近名板，**改错对象一次、全链路返工**。纪律：

1. 动手前 `list_artboards` + 名称过滤确认目标 ID，**写进命令注释**；
2. 区分不开就改名（`open_file_editor` → `command="renameArtboard"`，`data` 是**数组**，字段名是 **`newName`** 不是 `name`）：

```python
open_file_editor {"command":"renameArtboard","data":[{"artboardId":"50-18803","newName":"003 充电中 · 脚本原型"}]}
```

3. 本轮命名方案：交付板保留原名，原型板加 `· 脚本原型` 后缀；
4. 改完 `list_artboards` 回读确认。
