# text_editor 批量编辑边界

`text_editor` 是**唯一安全**的脚本源码更新方式（不触发"删 ScriptAsset 连带删节点"、不触发"改 scriptAssetId 不重绑"），但它有明确的边界。本文全部实测（2026-11，含一次 620 错误的事故复盘）。

## 一、能力边界（实测）

| 操作 | 结果 |
|---|---|
| `view`（path=脚本名） | ✅ 返回完整源码 |
| `str_replace` 小锚点（<1KB） | ✅ |
| `str_replace` 整文件（4783 字符 old） | ❌ "Could not find old_string"——**old_string 有长度上限** |
| `new_string` 大小 | ✅ 1.9KB old → 4.7KB new 一次成功（new 可以很大） |
| `view_range` | ✅ 有效，返回带行号的分段；**`end_line` 超过文件实际行数时返回空**（不会截断到 EOF）；单次分段建议 ≤300 行 |

## 二、大段更新的标准流程

脚本大改（如重写整个 PATH 表 300 行）：

1. **新内容先生成在本地文件**（tools/*.luau，也是存档）；
2. `view` 拿当前源码 → 与新内容**按行对比**，找出差异行；
3. **逐行/分块 str_replace**（每块 <1KB，old 行内容唯一），循环 tolerable "Could not find"（可能已修）；
4. `script_diagnostics` 复查归零。

行构造**避免 Python 的 %/f-string 模板**——模板里的花括号与 Lua 表的花括号互相打架（`unsupported format character` / `Single '}' encountered`），改用**字符串拼接**：

```python
def row(x, y, a):
    return "  {" + "{:.1f}, {:.1f}, {:.1f}".format(x, y, a) + "},"
```

## 三、占位符标记法要双向核对

用 `AT{…}AT` 之类标记批量替换时，**标记的闭合方向必须与实际文本一致**——本轮标记写成 `{AT902.2AT}` 而 replace 找的是 `AT{`/`}AT`（反序），静默漏替换，直到 script_diagnostics 冒出 620 条语法错误才被抓到。教训：**生成后立即 `script_diagnostics` 复查**，别等用户报错。

## 四、原地编辑 vs 删了重建

| 方式 | 后果 |
|---|---|
| ✅ `text_editor` 改源码 | 绑定/实例零变动，编辑器自动重编译（诊断秒级刷新） |
| ❌ 删 ScriptAsset 重建 | **连带删除引用它的节点**；重建后还要手动重挂 |
| ❌ 改 `scriptAssetId`(键 848) | 运行时实例不重绑（init 跑 draw 不来） |

## 五、长任务与 SIGTERM

沙箱会掐超时命令（大文件 `recompile_all_scripts` 400s+ 被杀）：

- Bash 调用**设 timeout 参数**（最高 540s）；
- 编辑（快）与编译（慢）**拆开**——编辑落盘后编辑器自动重编译，多数情况不需要手动 recompile；
- `script_diagnostics` 偶发返回子集/缓存——以两次连查一致为准。

## 六、崩溃-恢复-重放纪律

MCP 批量编辑中途客户端崩溃 + 用户恢复历史 = **回滚到中间态**（桌面/网页错误数不一致：桌面 1、网页 615，桌面是恢复后的源真）。

1. 每次大编辑前，完整源码存档本地（tools/*.luau）；
2. 恢复后先 `script_diagnostics` + 关键绑定回读，确认回滚点；
3. 丢失的修复按存档**一键重放**（同一套 str_replace 循环）；
4. 编辑后主动触发同步（Ctrl+S），避免桌面与云端错位。
