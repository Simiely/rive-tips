# 效果：车尾沙尘（沙粒 + 灰尘）

车沿路径移动，尾流持续喷出两层粒子：**沙粒**（4 色小点，快、短命）与**灰尘**（大而淡的柔边圆，慢、长命）。Rive 官方没有粒子系统与 compute，这个效果完全由 **Node Script（Luau）+ Renderer.drawPath** 组合实现，不依赖关键帧。

来源与语义对齐参考 HTML「沙漠行驶 · 湍流沙暴」；参数经多轮实机调参后定稿。

## 一、为什么必须写在车辆脚本里

粒子的出生点要跟着车，而车的位置/朝向只在 `car_probe` 里算得出来（`PATH` + `sampleAt(self.dist)` 返回 `{x, y, angleDeg}`）。

- 另一脚本里拿不到这个实时位姿；用固定坐标会让沙尘留在原地
- 把粒子节点重新挂到车下也不行：同一节点还画着别的东西，会一起被搬走
- 结论：**发射、更新、绘制都放进 `car_probe`**，坐标空间与车完全一致

## 二、实现骨架

```lua
-- car_probe
local s = sampleAt(self.dist)          -- s[1], s[2] 位置；s[3] 朝向（度）
sandStep(self, dt, s[1], s[2], s[3])   -- 沙粒
dustStep(self, dt, s[1], s[2], s[3])   -- 灰尘

-- 发射点：车尾反向 45 单位 + 横向抖动
local rear = math.rad(angDeg + 180)
x = sx + math.cos(rear) * 45 + (math.random() - 0.5) * jitter
y = sy + math.sin(rear) * 45 + (math.random() - 0.5) * jitter
```

每帧流程（与官方 Node Script 协议一致）：

1. `advance`：先推进时间（**必须在开关判断之前**），按 `rate × speedFactor × dt` 累积发射
2. 运动：指数阻尼 `v = v * exp(-drag*dt)`；可选 value noise 湍流力
3. `draw`：按「颜色 × 年龄桶」聚合成若干 `Path`，每桶一次 `renderer:drawPath`

## 三、定稿参数（2026-11 车机页实测）

| 参数 | 沙粒 | 灰尘 |
|---|---|---|
| 生成率 | 400/s | 320/s |
| 寿命 | 1.2 s（×0.6~1.4 抖动） | 1.0 s（×0.6~1.4 抖动） |
| 稳态数量 | ≈720 | ≈480 |
| 开角 | 1.4 rad（±0.7，约 80°） | 2.0 rad（±1.0，约 115°） |
| 初速 | (15~75) × power × speedFactor | (10~40) × power × speedFactor |
| 阻尼 | 1.5~3.0 | 0.6~1.1 |
| 尺寸 | (0.8~2.3) × 0.4 | (5~14) × 0.76，随生命 ×0.8→×2.6 |
| 透明度 | 0.6~1.0，包络 `(1-t)²` | 0.23 系数，包络 `(1-t)^1.5` |
| 绘制 | 4 色 × 5 年龄桶 = 20 条 `drawPath` | 5 个年龄桶 + `feather = 18` 软边 |

`speedFactor = 0.1 + speed/250`（默认车速 350 → 1.5），直接决定稳态数量。

## 四、绘制与透明度的官方约束

- `drawPath(path, paint)` 一次调用只有一个 `paint`，**整批共享透明度**；要逐粒渐隐只能：
  - 分年龄桶（本实现，桶数↑越平滑、调用数↑，5 桶即够用），或
  - 改用 `drawImageMeshInstanced` + `MeshInstances` 的 per-instance opacity（精确，但混合固定 `srcOver`）
- 灰尘不需要贴图：`Paint.feather` 就能出柔边（比 128px 径向渐变贴图省一个资产）
- 官方 WGSL 不支持 compute，湍流只能在 Luau 逐粒算（每帧 1920 粒噪声 ≈ 0.4ms，i7-14700 实测）

## 五、实测性能（`rive . --bench=600`，i7-14700 + RTX 4070 SUPER，800×600 原生 headless）

| 变体 | advance | render |
|---|---|---|
| 空画面 | 0.023 ms | 0.242 ms |
| 720 沙粒 · 20 桶批绘 | 0.024 ms | 0.725 ms |
| 720 沙粒 · 逐粒 720 次 drawPath | 0.024 ms | 0.786 ms |
| 1200 大圆（r=30，模拟灰尘填充） | 0.039 ms | 0.552 ms |
| 完整（1920 粒 + 每粒噪声） | 0.411 ms | 0.740 ms |

结论：整层 ≈ **1.15 ms/帧（约 60fps 预算的 7%）**；**批绘与逐粒调用只差 0.06 ms**，瓶颈是逐粒噪声与大面积 alpha 填充，不是 draw 次数。桌面 GPU 数据不能外推到车机，目标硬件需复测。

## 六、踩到的坑

1. **时间推进必须在开关判断之前**：`self.t += dt` 若放在 `if not SAND_ENABLED then return end` 后面，关掉沙粒后灰尘的噪声场会冻结——灰尘看起来"不动"。
2. **`Paint.with({ color = 0xFFFFF3D4 })` 静默画不出东西**：数字色值不报错但整批不可见，必须 `Color.rgba(r,g,b,a)`（本效果首次实现时踩到，截图全黑）。
3. **粒子尺寸要按画板尺度调**：参考 HTML 画布 800 宽、Rive 画板 2560 宽；直接照搬半径会小到看不见或大到糊住车。
4. **`capture_artboard` 对这块画板返回陈旧图**：连续三次 SHA256 完全相同，不能作为改动后的视觉证据；以编辑器播放为准。
5. **开关只控制一条线时，稳态数量按 `rate × life × speedFactor` 估算**：关掉沙粒后灰尘从 1200 → 480，是寿命与生成率共同作用，不是"少了一半"的直觉。

## 七、验收

1. `script_diagnostics` 为空、`recompile_all_scripts` 成功、`read_console(error)` 为 0
2. 编辑器播放：沙粒从车尾喷出、灰尘在其外围缓慢扩散，车沿路径一圈内粒子不卡顿、不横穿画面
3. 目标硬件跑一次 `rive . --bench=600`，确认 render 增量在帧预算内