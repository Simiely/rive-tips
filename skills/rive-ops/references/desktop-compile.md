# 桌面端编译卡死排查

**TL;DR**：浏览器打开同一文件 0.6s、桌面端一直 `Compiling` → 先做三层对照（同文件 / 别的文件 / 空白文件），不要先怀疑文件数据。桌面端**不写运行日志**，只能量进程：CPU 持续增长 + IO≈0 = 本地在算，不是网络等待。清本地缓存、删 `editorProperties`、改 `fileSafeMode` 都不解决（实测）。本轮最终靠「彻底卸载 + 重装最新版」恢复，但**版本与安装方式两个变量同时改变**，不能断言是哪一项起效。

> 更新时间：2026-11-06 ｜ 已验证：Rive 桌面版 `rive_native@0.9.517+6506`（Windows MSIX，Windows 11 `10.0.26100`）+ 本地 MCP

## 一、先分层：文件、客户端、本机

按成本从低到高做三个对照，别一上来就审计文件：

| 对照 | 结果 | 结论 |
|---|---|---|
| 同一文件：浏览器 vs 桌面端 | 浏览器约 0.6s，桌面端一直 `Compiling` | 文件数据可解析；问题在桌面端特有路径（浏览器走 WASM，桌面走原生） |
| 桌面端打开**别的**文件 | 也卡 | 排除单文件，锁定客户端 / 本机环境 |
| 桌面端打开**空白**新文件 | 也卡 → 环境问题；正常 → 文件的编译量问题 | 切分"环境 / 内容" |

本轮实测：浏览器正常、桌面端连别的文件也卡 → 客户端层，**后面的文件审计全部不必做**。

## 二、桌面端没有运行日志

包数据目录里能读到的只有三类文件，没有任何 `.log` 或编译日志：

```
%LOCALAPPDATA%\Packages\<包族名>\LocalCache\
  Roaming\Rive Inc\Rive\shared_preferences.json   # 编辑器偏好 + 每文件状态
  Roaming\Rive Inc\Rive\telemetry_logs.jsonl      # 本轮为空
  Local\Rive\sentry-native\                       # 仅崩溃上报
```

- Sentry：`__sentry-breadcrumb1/2` 均为 **0 字节**，`session.json` 为 `status: ok, errors: 0`
- Windows 事件日志：没有 Rive 条目

→ **不要指望"读编译日志"定位**；Sentry 只在崩溃时才有内容，正常卡住时是空的。

## 三、用进程指标判"在算"还是"在等"

PowerShell 5.1 可直接量，不需要装工具：

```powershell
# CPU：5 秒内的增量（单核百分比 = 增量 / 5）
$p = Get-Process Rive; $c = $p.CPU; Start-Sleep 5; $p.Refresh()
'CPU delta in 5s: ' + [math]::Round($p.CPU - $c, 2)

# IO：进程级读写速率
(Get-Counter '\Process(Rive)\IO Data Bytes/sec').CounterSamples[0].CookedValue

# GPU：按进程 pid 过滤引擎实例
(Get-Counter '\GPU Engine(*)\Utilization Percentage').CounterSamples |
  Where-Object { $_.InstanceName -match "pid_$($p.Id)" }
```

本轮实测：CPU 5 秒内涨 **2.64s**（≈53% 单核，另有线程 46% / 15%），IO **0 KB/s**，GPU 3D 引擎 **2.1%**。

判据：

- CPU 持续增长 + IO≈0 → **本地计算**（编译/渲染），不是网络
- CPU 低 + IO 高 → 网络/磁盘等待，才去查代理与下载
- 关键：卡住时进程仍有约 600–750 MB 内存、CPU 持续走，说明不是死锁空转

## 四、网络与证书排除

同机实测（直连）：

- DNS：`rive.app` / `editor.rive.app` / `api.rive.app` / `cdn.rive.app` 均解析正常
- TCP 443：98–211ms；HTTPS 首页 0.67–0.72s（`rive.app` 770KB）
- TLS 证书验证正常；`HEAD` 返回 403 是 CDN 拒绝 HEAD 方法，**不是证书错误**
- 桌面进程曾有 44 条连接指向本机代理（`127.0.0.1:7890`）；卡住时 IO 0、连接降到 8 条空闲 → 不在下载
- 代理日志显示 `*.rive.app` 全部命中 DIRECT；只有 `telemetry.rive.app` / `api.rive.app` 有 `i/o timeout`，属于遥测失败，与编译无关

→ 网络正常时，别去改 DNS、关代理、换节点；这些都不是卡编译的原因。

## 五、试过但无效的操作（均为实测）

| 操作 | 结果 |
|---|---|
| 清空整个 `LocalCache` 目录 | 仍卡；该目录本来几乎为空，没有编译产物可删 |
| 删除 `editorProperties` 键 | 打开文件后**自动重建**（`shared_preferences.json` 4 864 → 463 → 4 868 字节），说明它是从文档生成的临时状态，不是可清理的持久缓存 |
| `fileSafeMode` 置 `true` | 打开文件后客户端又写回 `false`，用偏好文件做"安全模式 A/B"无效 |
| 删除 Console 报错的 `Blank Script 1`（utility） | 未恢复；报错消失 ≠ 编译恢复 |
| 清空/重置客户端、重启、重建 Space | 均无变化 |

## 六、最终恢复与归因边界

有效操作：

1. 卸载 Rive 桌面端
2. 删除包数据目录（`%LOCALAPPDATA%\Packages\<包族名>`）
3. 安装官网最新版（本轮安装的是**测试版**）

结果：恢复正常。

**归因边界**：这次同时改变了两个变量——**版本（测试版）** 与 **安装方式（彻底卸载重装）**。因此只能说"这套组合在本机有效"，不能写成"测试版修好了"或"重装修好了"。要分开归因，下次需先只做"干净重装到同版本"，再单独升级版本。

## 七、未验证线索（不计入结论）

- **双显卡 / 虚拟显示器**：本机为 Intel UHD 770（2023 年驱动）+ RTX 4070 SUPER，另有 3 个虚拟显示适配器（OrayIddDriver / RayLink / Zako）。官方 changelog 曾记录 Windows 双显卡下 Flutter 与 Rive Renderer 选到不同 GPU 导致编辑器不显示内容的修复；本轮**没有做**"强制高性能 GPU"和"禁用虚拟显示器"的 A/B，所以不能算已证实原因。
- **测试版 vs 正式版差异**：未单独验证。

## 来源

- 本机实测 2026-11-06（Windows 11 `10.0.26100`，Rive `rive_native@0.9.517+6506`）
- [Rive Changelog](https://www.rive.app/changelog)（仅作双显卡线索，未证实与本例相关）
