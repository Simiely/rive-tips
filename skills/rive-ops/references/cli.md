# CLI 与 RML：把 Rive 变成代码工程

**TL;DR**：`rive` 命令行把 `.riv` 变成**一堆文本**（`scene.rml` + 脚本 + 资产），本地开着实时预览窗口改一处刷一处，最后再编回 `.riv` 或 `.rev`。适合"让 AI 从零建一套动效""进 Git 做版本管理""批量生成变体"。

> 更新时间：2026-10-26 ｜ 状态：CLI 为技术预览 / Early Access

## 一、为什么需要它

编辑器和 MCP 解决的是"改现有文件"，CLI 解决的是另外三件事：

1. **从零生成**——AI 写 RML 文本，不碰 GUI
2. **版本管理**——文本能 diff、能 review、能回滚；`.riv` 是二进制，只能整体替换
3. **无头验证**——不开窗口截图、跑测试、跑性能基准，可以进 CI

代价：RML 是一门新语法，得学；而且它描述的是**文件结构**，不是画布上的手感。

## 二、安装

| 平台 | 命令 |
|---|---|
| Windows | `irm https://releases.rive.app/cli/install.ps1 \| iex` |
| macOS / Linux | `curl -fsSL https://releases.rive.app/cli/install.sh \| sh` |
| Homebrew | `brew install --cask rive-app/tap/rive-cli` |

装完 `rive doctor` 自检五项：版本、更新、登录、实时链路、项目。

> Homebrew 装的版本不支持 `rive update` / `switch` / `uninstall`，那些得用 installer 版（在 `~/.rive/bin`）。

## 三、最小流程

```bash
rive create myproject     # 生成项目骨架
cd myproject
rive .                    # 开预览窗口，改文件自动重建重载
```

`rive create` 会写这几个文件：

| 文件 | 作用 |
|---|---|
| `rive.yaml` | 项目配置（名字、默认画板、构建日志） |
| `scene.rml` | 场景本体，XML |
| `AGENTS.md` / `CLAUDE.md` | **给 AI 的作业说明**——教它怎么查类型、怎么自检 |
| `.gitignore` | 忽略 `build/` |

改完任意文件保存，预览窗口自动重建，同时写出 `build/<name>.riv`——**这就是能喂给运行时的产物**。

## 四、三种自检，缺一不可

```bash
rive . --verify              # 能编译吗（RML / Luau / shader）
rive inspect . --json        # 编出来是什么，problems 空不空
rive . --screenshot=out.png  # 长什么样
```

官方文档明确说了：**编译通过不代表效果对**。绑定接错属性、图形画了但不可见，前两项都照样过。所以第三项不能省。

AI 协作时这三条就是它的反馈回路——写、验、看、改。

## 五、RML 长什么样

XML，每个元素是一个 Rive 类型，每个属性是它的一个属性，嵌套即关系。最小可用片段：

```xml
<Rive version="1" kind="fragment">
  <Artboard defaultStateMachineId="0:7" width="500" height="500" name="Artboard" id="0:2">
    <Fill name="Background">
      <SolidColor colorValue="FF1D1D1D" name="Color"/>
    </Fill>
    <Shape x="250" y="250" name="Triangle" id="0:14">
      <Triangle originX="0.5" originY="0.5" width="220" height="200" name="Path"/>
      <Fill name="Fill">
        <SolidColor colorValue="FF57A5E0" name="Color"/>
      </Fill>
    </Shape>
    <LinearAnimation loopValue="loop" duration="120" name="Spin" id="0:6">
      <KeyedObject objectId="0:14">
        <KeyedProperty propertyKey="15">
          <KeyFrameDouble value="0" interpolationType="linear"/>
          <KeyFrameDouble value="6.2831855" interpolationType="linear" frame="120"/>
        </KeyedProperty>
      </KeyedObject>
    </LinearAnimation>
  </Artboard>
</Rive>
```

几条硬规则：

- `Rive` 必须是唯一根元素；`kind="fragment"`（自己写的项目）或 `bundle`（编辑器导出的整包）
- **id 形如 `0:12`**，全文档唯一；只有被引用时才需要写 id，引用用 `xxxId` 属性
- **颜色是 ARGB 十六进制，不带 `#`**：`colorValue="FFFF5A3C"`
- **旋转是弧度**，整圈 `6.2831855`
- **时间是帧**，默认 60fps；转换时长是毫秒
- 一个项目可以拆多个 `.rml`，跨文件能互相引用，但 id 不许重复

别背属性名，查：

```bash
rive schema Rectangle --animatable    # 哪些属性能被 K 帧
rive schema Shape --bindable          # 哪些能被数据绑定
rive docs --search gradient           # 全文搜文档
```

## 六、和编辑器互通

| 方向 | 命令 | 说明 |
|---|---|---|
| 编辑器 → 项目 | `rive create proj --from-rev=file.rev` | 把编辑器导出的 `.rev` 转成 RML + 独立脚本/资产文件 |
| 项目 → 编辑器 | `rive . --rev` | 写出 `.rev`，双击能在编辑器里继续手工调 |
| 项目 → 账号 | `rive push` | 推到 Rive 云端某个文件，可绑 revision 标签 |
| 账号 → 项目 | `rive pull` | 把编辑器的改动拉下来（**会覆盖本地**，先确认） |

`--rev`、`--publish`、`push`、`pull` 都要 `rive login`；创建、预览、`--verify`、`--screenshot` 全都能离线跑。

## 七、签名与水位印

这条容易踩：

- 带**脚本**的文件要上 Web，必须 `--publish` 构建——**CDN 和 Web 运行时会拒绝未签名的脚本**
- `--publish` **可能给画面加水印**。干净输出需要两个条件：项目绑定到账号里的文件（`rive push` 会写入 `push.fileId`），且该文件在 **Cadet 及以上**套餐的工作区里
- 纯本地 `--once` 出的 unsigned `.riv` 能跑，适合开发期

## 八、什么时候用 CLI、什么时候用 MCP

| 场景 | 选 |
|---|---|
| 改一个已有的云端文件，边看边调 | MCP |
| 从零生成一套动效 | CLI |
| 需要 diff / review / 回滚 | CLI |
| 需要批量生成 N 个变体 | CLI |
| 要拿到真实像素做验收 | 两个都行（MCP 的 `capture_artboard` 更轻） |
| 要在 CI 里跑 | CLI（`--verify` / `--test` / `--screenshot` / `--bench`） |

两者不冲突：CLI 出的 `.rev` 可以在编辑器打开，编辑器改完再 `--from-rev` 转回来。

## 来源

- 官方文档：[Rive CLI 概览](https://rive.app/docs/cli/overview)
- 官方文档：[Getting Started](https://rive.app/docs/cli/getting-started)
- 官方文档：[Command Reference](https://rive.app/docs/cli/reference/commands)
- 官方文档：[RML](https://rive.app/docs/runtimes/advanced-topic/rml)
- 官方文档：[Working with AI Agents](https://rive.app/docs/cli/agents)
