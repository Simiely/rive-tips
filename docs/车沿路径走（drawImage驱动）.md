# 车沿路径走（drawImage 驱动）

让场景里的图片素材（车）沿一条路径行驶、带影子、起点/终点按百分比控制——全程 Luau 脚本，**不用 VM、不用组件画板**。来源：2026-11 车机地图"车沿路走 + 电流跟随"项目实测（含两次编辑器闪退的事故复盘）。

## 一、架构选型（为什么是这条路线）

| 路线 | 结论 |
|---|---|
| VM 绑定（脚本写 VM 数值 → 节点 x/y 绑定） | ❌ **放弃**：`viewmodel_editor` 写路径三次写三次闪退（坑位 34，契约内调用也崩） |
| 组件画板 + `Input<Artboard>` | 可行但要编辑器手动转组件 |
| ✅ **脚本按名取图片资产 + drawImage** | **零前置**：`context:image('资产名')` 官方契约，车保持普通场景节点不动 |

关键认知：脚本不能改场景节点的 transform，但可以**自己把素材画出来**——车在场景里的原节点保留（停着），移动的车由脚本逐帧绘制。

## 二、核心契约（官方文档原文核对，勿猜）

```lua
-- init 里取资产（按名，取不到返回 nil）
self.car = context:image('003_img_04')
self.sampler = ImageSampler('clamp', 'clamp', 'bilinear')

-- draw 里组合变换（renderer:transform() 会叠加矩阵，逐次调用即可）
renderer:save()
renderer:transform(Mat2D.withTranslation(x, y))              -- 位移
renderer:transform(Mat2D.withRotation(math.rad(deg)))        -- 旋转（弧度！）
renderer:transform(Mat2D.withScale(sx, sy))                  -- 缩放
renderer:transform(Mat2D.withTranslation(-w/2, -h/2))        -- 中心锚定（图尺寸的一半）
renderer:drawImage(img, sampler, 'srcOver', 1)
renderer:restore()
```

- Mat2D 全家桶：`identity / values(xx,xy,yx,yy,tx,ty) / withTranslation / withRotation(rad) / withScale(1~2参) / withScaleAndTranslation(sx,sy,tx,ty) / invert`，支持 `m * Vector`。
- **类型收窄坑**：`self.shadow` 声明为 `Image?` 时 `drawImage(self.shadow,…)` 报错 `Expected 'Image', got 'Image?'` → `local sh = self.shadow; if sh then … end` 收窄。

## 三、路径几何：从哪来、怎么烘

两条来源，都已实测：

| 来源 | 做法 |
|---|---|
| 参考 HTML 的 SVG 路径字符串 | Python 解析（M/C 逐段 flatten，12 段/条）→ 弧长均匀重采样（~3px/点）→ 角度**解卷绕** → 烘成 Lua 表 |
| **Rive 画板里的路径对象**（用户手绘） | 读 `PointsPath` 的子对象（顶点）：`x(24) / y(25) / inrotation(84) / indistance(85) / outrotation(86) / outdistance(87)`；控制柄 = `顶点 + dist*(cos(rot), sin(rot))`，**MCP 返回的 rot 是度**（2026-11-05 实测；Lua 里先 `math.rad`）；逐段 flatten 后同上 |

**坐标系三坑（本次最大教训）**：

1. **Shape 顶点坐标是它父级的局部坐标，不是画板坐标**——`移动路径` 挂在地图区域（位于画板 `(1639,682)`）下，直接当画板坐标用，整条路整体偏移 1639,682；
2. 修法优先级：**把脚本节点挪到与路径父级同位置**（`set_property_values` 一次调用），让两个局部坐标系重合——比逐行改 300 个烘焙坐标优雅得多；
3. 查父级链别只看 Shape 自己的 x/y（是 0,0 也可能父级有偏移）——沿 `parentId` 往上爬，每层叠加偏移。

## 四、脚本骨架（起点/终点百分比 + 影子成对）

```lua
local CAR_SPEED = 160        -- px/s
local START_PCT  = 0.02      -- 起点 2%
local END_PCT    = 1.01      -- 终点 101%：沿末段切线延长线冲出去
local CAR_SCALE  = 0.5       -- 与场景显示一致（节点原缩放50%）
local ROT_OFF    = 90        -- 车图朝上(-Y)，切线角补 90°
local SHADOW_DX/DY = 3.25/5.75  -- 影子中心偏移（两图静态相对位置）
local SHADOW_SCALE = 1.0

type Car = { car: Image?, shadow: Image?, sampler: ImageSampler?, dist: number }

local function init(self, context): boolean
    self.car    = context:image('003_img_04')   -- 车
    self.shadow = context:image('003_img_03')   -- 影子（一对素材）
    self.sampler = ImageSampler('clamp','clamp','bilinear')
    self.dist = TOTAL * START_PCT               -- 起点百分比
    return true
end

local function advance(self, seconds): boolean
    local dt = math.min(seconds, 0.05)
    self.dist = self.dist + CAR_SPEED * dt
    if self.dist > TOTAL * END_PCT then self.dist = TOTAL * START_PCT end   -- 循环
    return true
end

-- 超过 100% 沿末段切线外推（101% 的"延长线"）
local function sampleAt(d): { number }
    if d > TOTAL then
        local a = PATH[#PATH]; local ang = math.rad(a[3])
        return { a[1] + math.cos(ang)*(d-TOTAL), a[2] + math.sin(ang)*(d-TOTAL), a[3] }
    end
    d = math.max(0, math.min(TOTAL-0.001, d))
    -- 二分查弧长 → 线性插值 x/y，角度插值（烘表时已解卷绕，无 ±180 跳变）
end

local function draw(self, renderer)
    if self.car == nil or self.sampler == nil then return end
    local s = sampleAt(self.dist)
    local sh = self.shadow
    if sh then                                   -- 影子先画（垫车下）
        renderer:save()
        renderer:transform(Mat2D.withTranslation(s[1]+SHADOW_DX, s[2]+SHADOW_DY))
        renderer:transform(Mat2D.withRotation(math.rad(s[3]+ROT_OFF)))
        renderer:transform(Mat2D.withScale(SHADOW_SCALE, SHADOW_SCALE))
        renderer:transform(Mat2D.withTranslation(-wS/2, -hS/2))
        renderer:drawImage(sh, self.sampler, 'srcOver', 1)
        renderer:restore()
    end
    renderer:save()                              -- 车身
    renderer:transform(Mat2D.withTranslation(s[1], s[2]))
    renderer:transform(Mat2D.withRotation(math.rad(s[3]+ROT_OFF)))
    renderer:transform(Mat2D.withScale(CAR_SCALE, CAR_SCALE))
    renderer:transform(Mat2D.withTranslation(-wC/2, -hC/2))
    renderer:drawImage(self.car, self.sampler, 'srcOver', 1)
    renderer:restore()
end
```

## 五、text_editor 大段更新的坑与解法

| 坑 | 现象 | 解法 |
|---|---|---|
| `old_string` **有长度上限** | 整文件替换（4783 字符）报"Could not find old_string"；25 字符小锚点成功 | 大改拆**逐行/分块**循环（每块 <1KB） |
| `new_string` 可以很大 | 1.9KB old → 4.7KB new 一次成功 | 删旧（小块）+ 插新（一大块）组合 |
| Python `%` 格式化撞花括号/全角字符 | `unsupported format character` | 模板改**拼接或 .replace()**，别用 %/f-string 模板 |
| 沙箱 SIGTERM 掐长命令 | 重编译/大循环跑一半被杀 | Bash 调用设 `timeout` 参数；编辑与编译拆开发 |

**原地改源码是唯一安全的脚本更新方式**：不触发"删除 ScriptAsset 连带删节点"、不触发"改 scriptAssetId 不重绑"。

## 六、事故纪律（本次闪退复盘）

1. MCP 批量编辑中途 + 客户端崩溃 + 用户恢复历史 = **回滚到中间态**（桌面/网页错误数不一致：桌面 1、网页 615）——桌面是恢复后的源真，云端是中途存档；桌面同步后网页错误消失；
2. **每次大编辑前把完整源码存档到本地**（tools/*.luau），恢复后一键重放；
3. 编辑后主动触发一次同步（Ctrl+S / 小改动），避免桌面与云端错位；
4. 闪退取证：Flutter 零取证，配 WER LocalDumps（见《速查表·桌面版闪退取证》）。

## 七、定稿参数（车沿路走 · 003 原型板）

| 参数 | 值 |
|---|---|
| 车 / 影 | `003_img_04`（车，原生 95×229，场景缩放 50%）/ `003_img_03`（影，84×145，100%） |
| 路径 | 用户手绘「移动路径」Shape：24 顶点、总长 2700.9px、300 采样点烘表 |
| 速度 | 160px/s（一圈 ≈16.9s） |
| 起点/终点 | 2% → 101%（终点沿末段切线延长） |
| 影子偏移 | +3.25, +5.75（画板系），影子缩放 1.0 |
| 朝向 | 车头 = 切线角 + 90°（ROT_OFF） |

**遗留**：场景里停着的原车 `003_img_04` 是否隐藏（opacity 0）未定；电流效果（沿同一路线的三层描边流光、末端咬车尾）待做。

## 八、换车：替换脚本里的车素材（2026-11-11 实测）

**TL;DR**：车是脚本画的、不在场景节点上。换车 = 改脚本里的五个常量，**不要**往画板里加 image 节点——那只是张不会动的死图。

先确认驱动方式：`get_scripts` 里有 `car_probe_003/004`，源码里是 `context:image(...)` + `renderer:drawImage`。确认后再按下面五项改：

| # | 改什么 | 判据 / 算法 | 本次实例（952×512 新图） |
|---|---|---|---|
| 1 | `context:image('旧名')` | 按**资产名**取，**不带扩展名**；改完 `read_console` 里必须是 `userdata`，`nil` = 名字不对 | `003_img_04` / `004_car_v2` → `006_car_top_hi` |
| 2 | `CAR_SCALE` | `目标显示长 ÷ 新图里车身像素长` | 车身 337px、要 57.8 → **0.1715** |
| 3 | 中心锚点 `-w/2, -h/2` | 车身不在图心时换成**车身 bbox 中心**，否则整台车沿车头方向整体偏出去 | `(-95/2,-229/2)` → **`(-277,-253)`** |
| 4 | `ROT_OFF` | 看车头在图里朝哪：朝上(-Y) → 90；朝右(+X) → 0 | 90 → **0** |
| 5 | `self.shadow` / `SHADOW_*` | 新图已把影子烘进去就置 `nil`，否则重影 | `003_img_03` → **nil** |

**量车身 bbox 别靠眼睛**：读 PNG 里「alpha 不透明且偏暗」的像素（`A>200 且 亮度<100`）取 min/max。本次车身在图里偏左（图心 x=476，车身中心 x=277），直接写 `-w/2` 会让车头探出路面、车尾拖在路外。

**三个坑**：

1. **加静态 image 节点不继承动画**：路径跟随、切线转向、车速全在脚本 `draw()` 里，图片节点只是场景里一张静止的图（本次先按图片节点换过，白做一遍才删掉）。
2. **`capture_artboard` 不执行脚本**，所以静态截图里永远没有车（只剩路面）。判据换成三件套：`script_diagnostics == []`、`read_console` 里 init 的 `print` 返回 `userdata`、编辑器预览里肉眼看。
3. **同名上传会返回假 `0-0`**：`upload_asset` 的 `name=` 只能 ASCII，重名先换唯一名；落库后扩展名会被去掉，所以 `context:image` 里写的是纯名字。

**验收**：预览里车沿路走、车头朝行进方向、车身压在路面上、影子只有一份；换图后如果"车不动了"，先回看第 1 项是否取到 `nil`。

本机实测：2026-11-11，Rive 桌面版 Early Access，充电桌面 003/004 两个画板。
