# 路径几何与坐标系映射

把"一条路径"变成脚本可驱动的采样表：两条来源、顶点模型、弧长烘焙、以及**坐标系映射三坑**（本轮事故主因）。

## 一、路径的两种来源

| 来源 | 做法 |
|---|---|
| 参考 HTML 里的 SVG 路径字符串 | Python 解析 `M/C/…` → 每段贝塞尔 flatten（12 段）→ 弧长重采样 |
| **Rive 画板里的路径对象**（用户手绘，推荐） | 读 `PointsPath` 顶点 → 同样 flatten → 烘表 |

用户手绘的好处：**路径即所见**，起点/走向直接在编辑器里调（把想要的起点顶点放第一位），改完重烘一次表即可。

## 二、顶点模型（PointsPath 的子对象）

顶点是 PointsPath 的**子对象**（不是属性），每个顶点的键：

| 键 | 名 | 含义 |
|---|---|---|
| 24 / 25 | x / y | 顶点坐标 |
| 84 / 85 | inrotation / indistance | 入控制柄：角度+距离 |
| 86 / 87 | outrotation / outdistance | 出控制柄：角度+距离 |

控制柄坐标 = `顶点 + 距离 * (cos(角度), sin(角度))`。**MCP `query_property_values` 返回的 84/86 是「度」**（2026-11-05 实测：按度计算 cos/sin 得总长 2701.79px，与脚本 `TOTAL=2700.9` 吻合；按弧度算得 3140px，明显偏离）。Lua 里若要喂给 `math.cos/sin`，先 `math.rad`。相邻顶点的出柄/入柄构成三次贝塞尔 → 每段 flatten 12 步。

⚠️ **顶点坐标是路径对象父级的局部坐标，不是画板坐标**——见下节。

## 三、坐标系映射三坑（本轮事故主因）

**症状**：车走的路线整体偏移/形状对了位置不对。

| 坑 | 说明 | 修法 |
|---|---|---|
| ① 父级局部 ≠ 画板 | 路径 Shape 挂在地图区域（画板 (1639,682)）下，顶点是地图区域局部 | 沿 `parentId` 往上爬父级链，**逐层叠加偏移** |
| ② 只查 Shape 自身 x/y 不够 | Shape 自己是 (0,0) 也会因父级偏移而错 | 同上，必须爬链 |
| ③ 修坐标要改 300 行？ | 烘焙表整表平移 | **把脚本节点挪到与路径父级同位置**（`set_property_values` 一次），两个局部坐标系重合，表零修改 |

坑①②叠加的典型现场：路径起点顶点 (551,480)——当画板坐标是地图左上（错），当地图区域局部时 = 画板 (551+1639, 480+682) = (2190,1162)，恰在充电图标旁（对）。

## 四、烘焙算法（Python → Lua 表）

```python
# flatten: 每条三次贝塞尔 12 步
for j in range(1, 13):
    t = j/12; mt = 1-t
    pts.append((mt**3*x0 + 3*mt*mt*t*x1 + 3*mt*t*t*x2 + t**3*x3, ...))

# 弧长累计 → 均匀重采样（~3px/点，上限 300）
cum = [0]
for a, b in zip(pts, pts[1:]): cum.append(cum[-1] + hypot(b[0]-a[0], b[1]-a[1]))

# 角度解卷绕（避免 ±180 跳变，Lua 端才能线性插值）
ang = degrees(atan2(dy, dx))
if samp and ang - samp[-1][2] > 180: ang -= 360
if samp and samp[-1][2] - ang > 180: ang += 360
```

生成的 Lua 表：`{x, y, 角度}` ×N + `TOTAL`（总弧长）。运行时 `sampleAt(d)`：二分/均匀定位 → 线性插值。

## 五、起点/终点百分比 + 超终点延长线

```lua
local START_PCT, END_PCT = 0.02, 1.01
self.dist = TOTAL * START_PCT                          -- 起点百分比
-- advance: self.dist += CAR_SPEED*dt; 超 TOTAL*END_PCT 回 START_PCT
-- sampleAt 超 TOTAL：沿末段切线外推
if d > TOTAL then
    local a = PATH[#PATH]; local ang = math.rad(a[3])
    return { a[1] + math.cos(ang)*(d-TOTAL), a[2] + math.sin(ang)*(d-TOTAL), a[3] }
end
```

调起点 = 改一个数（0.02→0.03→…），终点延长同理——不用重烘表。

## 六、定稿参数（003 原型板）

「移动路径」24 顶点、总长 **2700.9px**、300 采样；车速 160px/s（一圈 ≈16.9s）；起点 2%、终点 101%。
