# 效果：能量光圈

从图标边缘向外扩散、逐渐变淡消失的圆环，周期性触发。来源：参考 HTML 的 `waveTimer` 段。

## 效果分解（参考语义）

| 层 | 参考代码 | 说明 |
|---|---|---|
| 触发 | `waveTimer += dt; if waveTimer > 周期: 重置并发出一圈` | 每 1.4s 一圈 |
| 生命 | 0.656s | 从发出到消失 |
| 半径 | `IR*0.95 → IR*3.1`（29 → 90） | 从图标边缘扩散到 3 倍 |
| 淡出 | alpha 随生命进度衰减 | 出现即最亮，逐渐消失 |
| 混合 | `lighter` | additive |
| 同时数量 | 最多 2 圈（周期 1.4s > 寿命 0.656s×2 ≈ 1.31s） | 相邻两圈错开 |

## 路线 A：脚本（定稿）

```lua
for slot = 0, 1 do                                    -- 两个槽位，错开半周期
    local tt = self.t - slot * WAVE_LIFE
    local u  = (tt % WAVE_PERIOD) / WAVE_LIFE         -- 0..1 生命进度
    if u > 0 and u <= 1 then
        local rad = IR*0.95 + (IR*3.1 - IR*0.95) * u
        self.ringPath:reset()
        addCircle(self.ringPath, 0, 0, rad)
        local p = self.wp4                            -- 4 档 alpha 按进度切换
        if u < 0.25 then p = self.wp1
        elseif u < 0.5 then p = self.wp2
        elseif u < 0.75 then p = self.wp3 end
        renderer:drawPath(self.ringPath, p)
    end
end
```

定稿参数：`WAVE_PERIOD=1.4`、`WAVE_LIFE=0.656`、alpha 四档 `110/70/40/18`（0–255）、thickness `2.4→1.2` 随进度变细。

## 路线 B：关键帧（MCP）

一个圆环形状，打两组键：

| 键 | 帧 0 | 帧末（0.656s×60≈39 帧） |
|---|---|---|
| scale (16/17) | `IR*0.95/圆环原始半径 ×100` | `IR*3.1/… ×100` |
| opacity (18) | 100 | 0 |

循环周期 1.4s：在 1.4s×60=84 帧的时间线上，环动画占前 39 帧，后 45 帧 opacity=0。要两圈错开就再复制一个环、相位差 0.656s。

## 注意事项

1. **透明度量纲 0–255**（`Color.rgba`，见《脚本颜色与透明度量纲》）；
2. **Path 铁律**：`ringPath:reset()` 只在绘制前；两圈用**两个槽位分别 reset+draw**，不能共用一次 reset；
3. alpha 档位切换是"跳变"——四档在 additive 混合下肉眼近似连续；要更平滑就加档（每加一档 = init 里多一支 Paint）；
4. 关键帧路线的环**必须独立 Shape**（不能和别的效果共用电感路径），否则 scale 会带着别的元素一起动。

## 验收

1. 播放：每 1.4s 一圈从图标边缘扩散，0.66s 内淡出；任意时刻最多两圈；
2. 圈与圈错开半周期，不重叠出现；
3. 扩散过程中图标像素不变（圈画在图标之后、pure stroke 无填充）。
