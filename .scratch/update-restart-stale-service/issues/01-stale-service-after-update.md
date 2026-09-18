# 01 — 从 v1.1.1 点「一键更新」：文件换了，**跑着的服务还是旧版本**

**Type:** task
**Status:** open
**发现于：** 沙箱真机演练 B1（`sandbox-drill/01`，2026-09-18 22:40，脚本 `.scratch/verify-gate-drills/drill-01-upgrade.py`）

## 现象（真机实测，非推断）

沙箱「模拟用户机」（`C:\Users\luoji\Desktop\firstep-sim`，盘上 v1.1.1）走**产品自己的**小发版更新到 v1.2.1：

| 环节 | 实测 | 判据 |
|---|---|---|
| 检查更新 | `latest=1.2.1 size=304729724 sha256=ec9921fc…` | ✅ |
| 真下载 + 校验 | 304,729,724 B，14.65 MB/s，sha256 与线上清单一致 | ✅ |
| 替换 | 落位 4329 文件、删 727、备份 4312、盘上 `src/contest_generator/__init__.py` = **1.2.1** | ✅ |
| **跑起来的服务** | `GET /api/health` → `version = 1.1.1` | ❌ |
| 重启 | `updates\launcher.log` 只有一行 `reason=already_running port=8020`（启动器认为「本应用已在运行」，只开了浏览器） | ❌ |

用户视角：点完更新、进度条走完、工具「重启」了，但打开的还是**旧版本**（`/api/health` 与设置页都还是 1.1.1），必须自己关掉再重开一次才到 1.2.1（**已验证**：收掉 8020 旧进程 + 重起 → `1.2.1`，见 `verify-01-upgrade-aftercare.txt`）。

## 根因（证据链完整，不是猜）

1. **发起更新的那一代代码没传停服端口。** 备份里那份 v1.1.1 的 `webapp.spawn_updater`（`%USERPROFILE%\.contest_generator_sim\updates\backup\20260918-224039\src\contest_generator\webapp.py`）构造的命令是
   `[python, update-app.py, --zip, …, --root, …, --data-dir, …]`——**没有 `--port`**；
2. 于是更新器按默认端口停服：`updates\updater.log` 写着 **「端口 8000 无监听进程，跳过停服」**（8020 上的旧进程原封不动）；
3. 更新器照常覆盖文件、写了 `pending`→清 `pending`、拉起 `start-app.vbs`；
4. `start-app.bat` 的端口探测看到 8020 上有**合法**的 `/api/health`（旧进程应答）→ 走 `:already_running` → 只 `start "" http://127.0.0.1:8020` 就退出——**新版永远不会起来**。

**这一条在产品里已经修过**（v1.2.0 `ba32e95a` 起两条更新路径都显式传端口；v1.2.1 的 `src/contest_generator/webapp.py:384` 已是 `"--port", str(resolve_launcher_port())`）。本单记录的不是「新代码还有这个 bug」，而是：
**修复只对「发起更新的那一代 ≥ v1.2.0」有效；而 README/发布说明承诺的正是「老用户点一次检查更新就能升级」——那批人（≤ v1.1.1）现在会得到「说更新成功、其实是旧版」的结果，且没有任何提示。** 这个后果此前只有推断，本轮首次真机跑实。

## 待定修法（择一或组合，动代码前先 spec）

| # | 修法 | 代价 | 覆盖谁 |
|---|---|---|---|
| ① | 发布说明 / README 明写「v1.1.1 及更早：更新后请手动重开一次」 | 零代码 | 现有老用户（立刻） |
| ② | 启动器加**版本一致性检查**：端口上服务的 `version` < 盘上 `__version__` → 判为「旧进程」，停掉再起 | 改 `start-app.bat` + 守卫 | 以后所有「旧进程存活」的情形 |
| ③ | 重启协议不依赖「发起更新的那一代代码」：更新器只清 lock，由**启动器轮询 lock 消失**后自己拉起 | 改更新器 + 启动器，面较大 | 同上，且对更老的版本也有效 |

倾向：①（立刻止血，本单可只做这条）+ ②（正向护栏）。③ 留作后续评估。

## 验收

在任一修法落地后，用一台 v1.1.1 沙箱重跑：

```
python .scratch/verify-gate-drills/drill-01-upgrade.py
```

判据：`RESULTS.endpoint.served == "1.2.1"` 且 `restarted_by_updater == true`（现在分别是 `"1.1.1"` / `false`）。
