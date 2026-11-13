# CONTRIBUTING.md — 新增一篇文档的入库清单

> 这份文件存在的理由：入库标准原本散在三个地方——`AGENTS.md` 的「约定」、
> `tools/sync-skill.ps1` 的头部注释、`CHANGELOG.md` 的历史惯例。
> 靠拼三处才能拼出完整流程，结果就是**漏步骤**（2026-11-13 实测：提议新增两篇文档时
> 漏掉了「进映射表」和「跑 -Install」，而这两步不做，`-Check` 直接失败）。
> 本文把三处合成一条可执行路径。

---

## 一、先理解三层结构

```
README.md              门面：主题索引（唯一枚举"主题"的地方）+ 快速开始
AGENTS.md              给 AI：结论先行（62 条）+ FAQ 路由 + 约定
CHANGELOG.md           版本历史：每版记清数字增减
docs/                  正文：一主题一篇，中文文件名
tools/sync-skill.ps1   同步 + 校验：docs/ → skills/rive-ops/references/
skills/rive-ops/       可安装的技能包：references/ 是 docs/ 的快照，不手改
```

**核心约束**：`skills/rive-ops/references/` 是 `docs/` 的**生成物**。
改正文只能改 `docs/`，然后跑同步脚本生成快照。手改 references 一定会被 `DRIFT` 抓出来。

---

## 二、新增一篇文档：7 步

以新增 `docs/效果-某某.md` → `references/some-effect.md` 为例。

### 1) 写正文

`docs/效果-某某.md`，结构固定为 **TL;DR → 主体 → 来源**（见第三节）。

### 2) 进映射表（最容易漏，漏了必失败）

编辑 `tools/sync-skill.ps1`，第 90 行起的 `$map` 加一行：

```powershell
$map = [ordered]@{
    ...
    '效果-某某.md' = 'some-effect.md'
}
```

文件名写**中文原名（含 `.md`）**，右侧写 references 里的英文名。
没有这一行，`-Check` 会报 `UNMAPPED: docs/效果-某某.md (add it to the map)` 并非零退出。

### 3) 生成快照

```powershell
tools/sync-skill.ps1 -Install
```

`-Install` 同时刷新 `~/.workbuddy/skills/rive-ops` 安装目录；只想要仓库内快照用不带参数的
`tools/sync-skill.ps1`。同步时会按映射表把 `](中文名.md)` 重写成 `](英文名.md)`，
所以正文里可以放心用中文链接。

### 4) 登记入口（两处，看它属于哪种）

| 文档类型 | 登记位置 |
|---|---|
| **效果类**（`效果-*.md`） | `docs/效果索引.md` 加一行（表格：效果 / 文档 / 一句话）；同时在《效果索引》的选型树里看是否需要新增分支 |
| **主题类**（其余） | `README.md` 的「这是什么」主题表加一行（`#` 序号递增） |

### 5) 补 AGENTS.md

- 「结论先行」清单末尾追加 1~3 条**能一句话说清的结论**（编号递增，并在本文档末尾注明总条数）；
- 「FAQ 路由」加一行：`- "用户会怎么问" → 相对链接指向新文档`。

### 6) 补 CHANGELOG.md

新版本条目写在最上面，固定三段式：**更新 / 实测 / 计数**。
计数必须写清四个数字的前后值（见第四节）。

### 7) 校验

```powershell
tools/sync-skill.ps1 -Check
```

必须 `EXIT=0` 且输出 `OK: N references + M scripts in sync, 0 dead links.`。

---

## 三、内容规范

> 适用于 `docs/` 下的**主题文档**。根目录的 `DEVELOPMENT.md` / `CHANGELOG.md` / 本文件是流程与历史记录，不套这个结构。

| 规则 | 说明 |
|---|---|
| 标题 = 文件名 | 文档首个 `#` 标题与文件名（去扩展名）一致；中文命名，**不带空格** |
| 固定结构 | **TL;DR → 主体 → 来源**。TL;DR 用编号列表，5 条以内，每条一句话讲完 |
| 来源必须可追溯 | 官方文档链接，或「本机实测 + 日期 + 版本」。**不写「据说」「一般」** |
| 未验证的不进正文 | 确需提及就标「暂未收录」，并写明为什么没收（没环境 / 没验证） |
| 数字要注采集日期 | 工具数、画板数、状态数在 Early Access 阶段会变，不注日期等于埋雷 |
| 不写敏感信息 | 不写 token、本机绝对路径、账号邮箱、公司名 |
| 枚举只在 README | `DEVELOPMENT.md` 的目录树**只写层级与职责，不列文件名**——v1.0.0→v1.4.0 期间那棵树上腐化了 5 篇 |
| 结论先行，解释在后 | 读者是来解决问题的，不是来读推导的。推导放主体，结论放开头 |

---

## 四、必须维护的四个数字

每次增删都要对齐，`-Check` 只能自动查前两个：

| 数字 | 出现在 | 是否自动校验 |
|---|---|---|
| 坑位表行数（当前 **90** 行） | `docs/速查表.md` §七；`skills/rive-ops/SKILL.md` 两处（「完整 N 行对照表」「坑位速查（…N 行对照）」） | ✅ `STALE COUNT` |
| references 篇数（当前 **36** 篇） | `skills/rive-ops/SKILL.md` §6「N 篇 references 一一对应」 | ❌ 手查 |
| 结论先行条数（当前 **66** 条） | `AGENTS.md` §结论先行；`CHANGELOG.md` 当版条目 | ❌ 手查 |
| 铁律条数（当前 **61** 条） | `skills/rive-ops/SKILL.md` §2；`CHANGELOG.md` 当版条目 | ❌ 手查 |

> 坑位行数的算法：`docs/速查表.md` 里 `## 七、` 与 `## 八、` 之间的表格行数减 2（表头 + 分隔行）。

---

## 五、`-Check` 到底查什么

```
tools/sync-skill.ps1 -Check
```

| 代码 | 含义 | 怎么修 |
|---|---|---|
| `UNMAPPED` | `docs/` 下有文档没进 `$map` | 第 2 步 |
| `DRIFT` | `references/` 与 `docs/` 内容不一致 | 跑 `-Install`，**别手改 references** |
| `MISSING DOC` / `MISSING SNAPSHOT` | 映射表指向的文件不存在 | 补文件或删映射 |
| `MISSING SCRIPT` / `DRIFT`（scripts） | `scripts/` 顶层脚本与技能副本不一致 | 跑 `-Install`（脚本按字节复制，不做链接重写） |
| `SKILL-ONLY` | 技能里多了一个顶层脚本，仓库没有 | 通常意味着改名没同步回仓库 |
| `STALE COUNT` | `SKILL.md` 引用的坑位行数与实际不符 | 改 `SKILL.md` 的数字（两处） |
| `BOM IN SKILL.md` / `BAD FRONTMATTER` | PS 5.1 的 `Set-Content -Encoding UTF8` 写坏开头 `---` | 用能控制 BOM 的方式重写 |
| 死链 | 技能包内相对链接指不到 | 进映射表（链接会被重写）或改链接 |

`scripts/rive-merge/` 是**技能独有目录**，不参与同步，也不会被 `SKILL-ONLY` 误报。

---

## 六、脚本文件的两个特殊约束

1. **`tools/sync-skill.ps1` 自身必须保留 BOM**。PS 5.1 读无 BOM 文件时会把中文文件名当 ANSI，
   映射表全部查不到，`-Check` 会误报一大堆 `MISSING DOC`。
2. **不要用 `Set-Content -Encoding UTF8` 写 `SKILL.md`**。PS 5.1 会写 BOM，
   开头 `---` 变成 `\uFEFF---`，YAML 解析器看不到 frontmatter，而且**全程不报错**。
   这个坑真踩过一次。

---

## 七、已知的规范与现实偏差（待收敛）

| 偏差 | 现状 | 建议 |
|---|---|---|
| 枚举不再只有一处 | `README.md` 主题表 13 行，只覆盖「主题」；34 篇里效果类由 `docs/效果索引.md` 第二次枚举（15 行） | 可接受：按「主题 / 效果」两类分头维护，但两边都要改；`-Check` **不查篇数**，只能靠人 |
| 主题表序号连续性 | README 主题表是 `#1~#13`，新增主题要接 `#14` | 别插空号、别复用号 |
| 数字漂移无人查 | references 篇数、结论条数、铁律条数三个数字没有自动校验 | 改完自己 `grep` 一遍四个数字 |
