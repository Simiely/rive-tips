# Context 取素材与 drawImage

脚本按名取文件内素材并绘制的完整契约。官方文档原文核对（2026-11 实测通过），是"脚本驱动场景素材"路线（路线 B）的地基。

## 一、取素材

```lua
self.car = context:image('003_img_04')   -- 按名取 Image 资产，取不到返回 nil
-- 同族：context:blob('name') 取二进制；context:font？→ ViewModel:getFont('name')
-- 资产名 = 资产面板里的名字。实测 '003_img_04' 命中、'003_img_04.png' 返回 nil（不带扩展名）
```

探针先行：`print('[p]', context:image('名字'))` —— `userdata` 即命中，`nil` 换名再试。

## 二、绘制三件套

```lua
self.sampler = ImageSampler('clamp', 'clamp', 'bilinear')   -- 采样器：寻址x, 寻址y, 过滤
renderer:drawImage(img, sampler, 'srcOver', 1)              -- 图, 采样器, 混合, 不透明度
```

## 三、Mat2D 全家桶（rive/mat2d 主题原文）

```lua
Mat2D.identity()
Mat2D.values(xx, xy, yx, yy, tx, ty)
Mat2D.withTranslation(x, y)            -- 或 withTranslation(Vector)
Mat2D.withRotation(math.rad(deg))      -- ⚠️ 弧度
Mat2D.withScale(s) / withScale(sx, sy)
Mat2D.withScaleAndTranslation(sx, sy, tx, ty)
Mat2D.invert(inv, m)
m.xx / m.xy / m.yx / m.yy / m.tx / m.ty   -- 分量可读写
m * Vector.xy(10, 20)                     -- 矩阵变换向量
```

**组合变换不要用 Mat2D×Mat2D（未验证），用 `renderer:transform()` 逐次叠加**——每次调用叠加到当前矩阵，语义等价且全部有文档：

```lua
renderer:save()
renderer:transform(Mat2D.withTranslation(x, y))          -- 到路径点
renderer:transform(Mat2D.withRotation(math.rad(deg)))    -- 转向
renderer:transform(Mat2D.withScale(sx, sy))              -- 缩放
renderer:transform(Mat2D.withTranslation(-w/2, -h/2))    -- 中心锚定
renderer:drawImage(img, sampler, 'srcOver', 1)
renderer:restore()
```

## 四、类型收窄

`drawImage` 要求非空 `Image`，而 `self.shadow` 声明为 `Image?` → 直接传报
`Expected this to be 'Image', but got 'Image?'`。

```lua
local sh = self.shadow
if sh then renderer:drawImage(sh, ...) end   -- 局部变量 + 判空 → 收窄为 Image ✓
```

## 五、素材对（车 + 影子）

| 项 | 车 | 影子 |
|---|---|---|
| 资产 | `003_img_04`（原生 95×229） | `003_img_03`（84×145） |
| 场景缩放 | 50%（显示 47.5×114.5） | 100% |
| 绘制顺序 | 后（上层） | **先（垫底）** |
| 中心偏移 | 车心 + (3.25, 5.75) | —— |

影子中心 = 车心 + 固定偏移（画板系），影子图与车**同转向**；绘制顺序影子在前。

## 六、验证探针（复用模板）

```lua
function init(self, context): boolean
    self.car = context:image('003_img_04')
    print('[p]', self.car)                 -- userdata=命中, nil=换名
    return true
end
function draw(self, renderer)
    if self.car == nil then return end
    renderer:save()
    renderer:transform(Mat2D.withTranslation(1639, 682))   -- 画在地图中心
    renderer:drawImage(self.car, ImageSampler('clamp','clamp','bilinear'), 'srcOver', 1)
    renderer:restore()
end
```

一次验证两件事：资产能否按名取到 + drawImage 是否真的出像素（Console print 与画布同时确认）。

## 七、换素材（三步，2026-11-11）

1. **上传**新图：`upload_asset` 用 data URI、`name=` 纯 ASCII；返回 id 不是 `0-0` 才算真成功（重名会返假 id）。
2. **改名字**：脚本里 `context:image('旧名')` 换成新资产名——**不带扩展名**（落库会去掉）。
3. **改绘制参数**：缩放 = `目标显示长 ÷ 新图里素材像素长`；中心锚点用**素材本体的 bbox 中心**（图心有留白就会偏）；
   图里已经烘了影子/光效，就把 `self.shadow` 置 `nil`，别叠第二层。

改完的判据：`script_diagnostics == []`，`read_console` 里 init 的 `print` 返回 `userdata`（`nil` = 名字不对）。
静态截图看不到——`capture_artboard` 不执行脚本。

完整清单与实例见 [车沿路径走（drawImage驱动）](车沿路径走（drawImage驱动）.md) §八。
