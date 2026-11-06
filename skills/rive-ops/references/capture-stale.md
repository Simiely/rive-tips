# capture 与陈旧渲染

`capture_artboard` / CLI `--screenshot` 的行为边界，以及"截图骗人"的各种情况。

## 一、行为边界

| 工具 | 跑关键帧动画？ | 跑 Luau 脚本？ | 备注 |
|---|---|---|---|
| `capture_artboard`（MCP） | ❌ 静态、呈现**创作态** | ❌ 不执行 | 且要求画板是**活动画板**，否则返回空白图 |
| `rive <dir> --screenshot`（CLI） | ✅ 会推进 | ✅ 执行 | 无头渲染，脚本粒子可见 |
| `simulateStateMachine`（MCP） | 会**还原**写入值 | — | 不渲染像素；编辑态拒跑 |

**结论**：验证脚本内容只有两条路——编辑器里播 + Console print，或 CLI `--screenshot`。

## 二、陈旧渲染（截图骗人）

MCP 截图可能拿到**旧帧**：设置属性后立刻截，图还是改之前的。实测案例：

- 渐变改为 alpha=255 后截图，diff=0，误判"渐变不渲染"；
- 实际是 capture 命中了改属性前的那一帧。

**对策**：

```python
set_property_values(...)      # 改
time.sleep(1)                 # 等一帧
shot() → shot()               # 连拍两张，两张一致才算稳定
# 关键对比永远用"相邻两次截图 diff"而非"与记忆中的上一次对比"
```

判断截图是否新鲜：`len(np.abs(a-b).max(axis=2) > 3)`——两张完全一致（0 差异）反而可疑，可能是连续的陈旧帧。

## 三、截图拿不到脚本输出时的替代验证

| 手段 | 能验证什么 |
|---|---|
| 脚本里 `print()` + `read_console` | init/advance/draw **是否被调用**、调用频次（计数增长即播放中） |
| 调用计数对照 | 只增长一次 = 只有一次 repaint（未播放）；持续增长 = 播放中 |
| CLI `--screenshot --advance=N` | 脚本渲染 + 不同 N 的帧间 diff（≈2000 px 变化即粒子在动） |
| 不透明探针（纯色方块） | 节点是否参与渲染、坐标是否正确、是否被遮挡 |

**探针优先**：任何"看不到"先挂一个 200×200 不透明方块（见《脚本颜色与透明度量纲》），一步分清"没渲染"与"渲染了但太小/太淡/被挡"。

## 四、CLI 的坑

| 坑 | 现象 | 对策 |
|---|---|---|
| **段错误**（exit 139，零输出） | `--verify` / `--screenshot` 偶发直接崩 | 重试；若必现，查模块级 `local X: {number} = {...}`（Luau 编译器 bug，见脚本篇） |
| `rive docs <topic>` 段错误 | 个别 topic 必崩 | 换 WebSearch / `get_scripting_reference` |
| `rive schema <Type>` 段错误 | 个别类型（如 ScriptedDrawable） | 换 `rive docs --search` 或文档站 |
| `--advance` 语义 | 会改变产物（.riv 大小变化） | 对比帧时保持参数一致 |
| 渲染正常但 CLI 崩 | 崩在预览而非编译 | `--verify` 单独跑确认编译，再单独截图 |

## 五、推荐验证流水线（脚本动画）

```
1. rive --verify                 编译 0 error（拿行号）
2. get_scripts → type==node      协议识别成功
3. 编辑器 Console print          init/draw 被调用、调用频率
4. rive --screenshot --advance   渲染像素、帧间 diff
5. 编辑器播放肉眼验收             最终观感
```

第 1~4 步全自动，第 5 步才需要人。任何一步失败都不要跳到下一步调参数——先修通过再说。
