# 无清空合并文件：用 CLI 把两个工程合成一个

**TL;DR**：要把一个 Rive 文件的全部画板并入另一个**已有内容**的文件，MCP 走不通（`upload_rev` 要求目标为空）。正解是 `.rev` → 两个 CLI 工程 → `rml_merge.py` → `fill_assets.py` → `gate.py --verify` → `rive push`。实测 35 画板 / 67 资产 / 21343 元素，`0 errors, 0 warnings`。

> 更新时间：2026-10-28 ｜ 已验证：rive CLI 1.8.0（Windows）

## 一、为什么不用 MCP

| 路线 | 结果 |
|---|---|
| 桌面 MCP `upload_rev(target=open_file)` | 要求目标文件**一块画板都没有**，等于清空，不可接受 |
| 画板级复制粘贴 | 跨文件粘贴随机丢图片/嵌套/状态机 |
| CLI 工程合并后 `push` | 目标文件保留原内容，新增内容作为新 revision 写入 |

CLI 是唯一能"读全量 + 写全量"又不碰编辑器的路径（用户要求不控制电脑）。

## 二、四步管线

前置：`rive` 已登录；两边各有一个 `.rev`，先各自拆成 CLI 工程。

```powershell
rive create work\tgt --from-rev=目标.rev
rive create work\src --from-rev=来源.rev

rive rml_merge.py --target work\tgt --source work\src --out work\out `
    --target-rev 目标.rev --source-rev 来源.rev --prune-orphans

rive fill_assets.py --dir work\out --rev 目标.rev --rev 来源.rev --from work\src

rive gate.py --dir work\out --fix --verify     # 通过后才是可交付工程
rive push work\out --project=<文件 id> --name=<ASCII 名>
```

脚本都在 `skills/rive-ops/scripts/rive-merge/`（`rmlcore.py` 是共享库，`python rmlcore.py --selftest` 自检）。

## 三、合并语义

顶层元素（画板 / ViewModel / 枚举 / 组件）按 id 判冲突，`--on-conflict` 三档：

| 值 | 行为 |
|---|---|
| `replace`（默认） | 同 id → 来源版覆盖目标版，占同一槽位 |
| `skip` | 同 id → 保留目标版，丢弃来源版 |
| `keep` | 同 id → 两份都留，来源副本重新分配 id 并改名 `xxx (2)` |

资产按四级匹配，任一级命中就不再复制字节：同 id 同字节 → 丢来源声明；同 id 不同字节 → 分配新 id（`re-id`）；文件名相同且字节相同 → 复用目标资产；文件名相同字节不同 → 改名 `xxx__2`。

`--prune-orphans` 在合并后按引用计数删掉没人引用的资产（实测一次合并能剪掉 34 个）。

## 四、三个会静默失败的坑

| 现象 | 根因 | 处置 |
|---|---|---|
| `rive --verify` 直接 `exit 3221226505`（0xC0000409），无任何输出 | **资产文件名含非 ASCII**（中文、全角括号） | `gate.py --fix-names` 或合并时保留默认改名；同一份字节改成 `asset_012.ttf` 就 `0 errors` |
| 同上，0xC0000409 | `FontAsset exportTypeValue="referenced"`（缺属性=embedded，不算坑） | `gate.py --fix-fonts` |
| 合并后动画绑错对象 / 编辑器里重复 id | 同一 id 在目标是顶层、在来源是画板内嵌套（本案例 10 个 `CubicEaseInterpolator`） | 合并脚本已对"拷贝子树内任何已占用 id"重新分配并重写引用 |

判定 0xC0000409 的方法：`$LASTEXITCODE` 为 `-1073740791` / `3221226505`，且 stdout/stderr 全空。它不是内存不足，是 Rust 侧 panic=abort，**不会给任何提示**。

```powershell
# 逐类缩小：只剩声明、没有内容，也能复现
rive rml_merge.py ...   # 先合并
rive gate.py --dir work\out --fix-names --fix-fonts --verify
```

## 五、回写云端

- `rive push` 需要 ASCII 的 `--name`；中日韩名字会被拒绝或产生不可控文件名。
- push 是**新增 revision**，不是覆盖；目标文件原有内容与历史都保留。
- CLI 1.8.0 **没有删除远程文件的命令**，联调过程产生的草稿只能留在云端（`rive ls` 可查）。
- push 之后的验收：目标文件里应有的画板数量、指纹与本地一致，再截图确认不是空画板。

## 六、已知限制

- `.luau` 脚本不在 `.rev` 的 `d4` 记录里（`c7 07` 文本记录不带脚本 id），只能靠 CLI 工程根目录里的松散 `.luau` 文件；`fill_assets.py` 会按 `name` 匹配回填，`rev_assets.py` 把它们标为 `text` 而不是缺失。
- id 里的负号（`-0:144114`、`-2:839`）指外部/代码文件，不是悬空引用，校验时跳过。
- `ComponentAsset` 是**画板容器**（被 `expandedComponents` 引用），不是文件资产；按文件资产处理会被孤儿剪枝误删。
- `assetId` 的裸数字形态（如 `6020142`）和声明的 `scope:oid` 不在同一命名空间，不能互相查表。
- 来源文件自身的 `NestedArtboard` 可能指向自己（画板内含指向本画板的嵌套实例），编辑器和运行时都能打开，但会让 CLI 构建栈溢出——这类内容应在来源侧修掉。

## 七、来源

- 2026-10 实战：`测试文档`（8 画板）+ `系统类动效`（33 画板，74 MB 资产）合并，产出 35 画板 / 67 资产 / 21343 元素，`rive --verify` `0 errors, 0 warnings`，push 回写后云端指纹一致。
- 0xC0000409 的定性来自三组对照：原始工程（中文文件名）崩、改成 `asset_NNN` 后通过、仅把字体改回中文名再崩。
- 相关：`docs/CLI与RML工作流.md`（RML 结构）、`docs/跨文件搬运画板.md`（编辑器路线）。
