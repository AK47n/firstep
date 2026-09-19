# 05 — 真机 drill-01 验收（v1.1.1 → v1.2.2）+ 账本回填

**要做什么：** 已装旧版的用户「点检查更新 → 一键更新」能不能真的走到 v1.2.2，且升级后的
工具根**与全新安装该版本一致**；并把这一轮的事实（含新踩的坑）写回本机账本。

**被谁阻塞：** 01、04（修复要在包里、包要在线上，drill 才有东西可下）。**02 在本单之后执行**
（时序而非依赖，见 02 的 Comments）。

**状态：** resolved

- [x] 沙箱还原成真 v1.1.1（`rebuild-sandbox-v111.py --write`，**先收 8020**）
- [x] 真机跑 `drill-01-upgrade.py`（**drill 一字不改**，用包装脚本只覆盖目标版本参数）
- [x] 判据：`not_in_official` 的构成、起点/终点版本自证、保命项、四条隔离判据
- [x] 原始证据落盘（`.scratch/verify-gate-drills/verify-01-upgrade-v1.2.2.{txt,json}`）
- [x] 回填 `docs/agents/local-environment.md` 第 0/1/2/3 节
- [x] 回填 `.scratch/backlog.md` 第 8 节与 5.4
- [x] 真身端口与进程恢复原状（跑完挪回 8000）、8020/8021 释放、全局 pip 状态收干净

## Comments

### 真机结果（2026-09-19，第四轮为取证轮）

| 判据 | 实测 |
|---|---|
| 起点自证 | 盘上 `1.1.1` + 服务 `/api/health` `1.1.1` ✅ |
| 检查更新 | `latest=1.2.2` / `update_available=True` / `size=300820891` ✅ |
| 真下载校验 | 落盘 `300,820,891` B、sha256 与线上清单**逐位相同** ✅ |
| 更新器终态 | `done` / `version=1.2.2` ✅；日志 `停服 → 备份 2830 → 落位 2858 → 删 653 → pip → 重启` |
| **终点判据** | 盘上 `1.2.2`、**跑起来的服务 `1.2.2`**、`restarted_by_updater=true` ✅ |
| 启动器日志 | `reason=started tries=2 port=8020 stale=1 served=1.1.1 disk=1.2.2`（走「踢掉旧进程」那条路）✅ |
| 保命项 | **12/12 成立**（key / 任务记录 / 资料库三轴 / 第三方包 / 锁 / 备份）✅ |
| 隔离判据 | 真身数据目录 mtime / `updates/` 条目 / 工作树 11908 文件 / `launcher.log` **四条全未变** ✅ |
| 收尾 | 8020 已释放、无残留 python 进程 ✅ |
| **构成** | 官方 tracked 3064 / 沙箱 3070；**逐字节一致 3064、内容不同 0、官方有而沙箱缺 0**；`not_in_official = 6` |
| 总判 | **判红 0 条 / 卡住 0 条 → PASS** |

### `not_in_official = 6` 的定性（用户判据是「== 0」，所以这一格必须说清）

那 6 条全是 `src/contest_generator.egg-info/**`。**不是包发错的**，是**更新器第 7 步
`pip install -e .` 现写的**（更新器日志里那 6 条先被逐条删掉，紧接着才写
`pyproject.toml 已变化，重装依赖（pip install -e .）`）。

决定性实验 `.scratch/release-v1.2.2/measure-egginfo-origin-v2.py`（**判据与"树"无关**）：

```
① 解压官方完整包（226 个条目）→ egg-info 目录：[]      ← 官方包里没有它 ✓
② 照更新器原命令跑 `python -m pip install -e <root>`   ← 退出码 0 ✓
③ 跑完 → 6 个文件齐、路径与沙箱那 6 条一一对应 ✓
结论：egg-info 是更新器那一步 pip 现写的，不是包内容 —— 成立
```

> **v1 实验为什么不算数**（留档）：第一版多传了 `--no-deps --no-build-isolation`，
> `--no-build-isolation` 让 pip 走 PEP 660、**不碰源码树**，于是「一个都没长出来」。
> 更新器原命令一个参数都不加（`tools/update-app.py:285`），照它跑才复现。

**所以这一格的正确读法**：把 6 条 pip 产物算进去，`not_in_official` 是 **0**；
「官方有而沙箱缺」也是 **0**——工具根的**产品文件**与全新安装逐字节一致，这正是本版要的收益
（v1.2.1 时代同一支 drill 量到的是 **1482**：1481 个本机库备份 + 1 个 `*.exe`）。

### 真机踩到的三件事（都已写进 `local-environment` 第 0/1 节）

1. **drill（起点 v1.1.1）把真身杀了**：v1.1.1 的 `spawn_updater` 没有 `--port`，更新器按缺省
   8000 停服。实测 `updater.log` 记 `停服：结束本应用进程 PID 43960`（= 真身）。已按
   「先挪到 8021 → 跑 → 挪回 8000」做完，真身现为 v1.2.2 / 8000 在跑。
   **这条本身是 `update-restart-stale-service/01` 那个缺陷的真机复现**，v1.2.1 起已修，
   所以沙箱升到 ≥1.2.1 后不再咬人。
2. **重建沙箱前必须收 8020**：drill 结尾会把沙箱重新拉起来，占着目录 → `WinError 32`。
3. **drill 的证据名会被下一次运行覆盖**：`OUTPUT_STEM` 是模块级常量。包装层必须补
   **模块级那一处**（`--aftercare` 分支里的 `global OUTPUT_STEM` 是函数内部声明，补它没用），
   并且**代做 drill 跳过的 `__main__` 收尾**（漏掉它 = 演练跑完却一份证据都不落盘，踩了两次）。

### 包装层（drill 一字未改的证据）

`.scratch/release-v1.2.2/run-drill-01-v122.py`：`runpy` 式模块执行 + 源码文本补丁，
只覆盖 `TARGET_VERSION` / `OUTPUT_STEM` / 日志字面量。跑完复核 drill sha256
`52b6210061fde3974e3dcf8513f2609a26fa407a41336f1d09ef9bae994c7fe8` **逐字节未变**；
偏离记账落 `drill-01-deviation-*.json`。
