# B1 — 沙箱 v1.1.1 → v1.2.1 真机升级

**要做什么：** 沙箱「模拟用户机」走产品自己的小发版更新（线上真实 Release，真下 305 MB）→ 替换 → 重启，判据 = **跑起来的服务 `/api/health`.version == 1.2.1**。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-09-18，**判据不成立/暴露真缺陷**，已开单 `update-restart-stale-service/01`）

- [x] 演练前核对前置事实（沙箱根 / 数据目录 / 端口 8020 / 真身 8000 只读）——脚本零节逐项打印，全部成立
- [x] 起点版本自证：盘上 `1.1.1` + 跑起来的服务 `1.1.1`（**两处都实测**；顺带更正 `local-environment` 记的「盘上钉在 1.1.0」——实测是 1.1.1）
- [x] 走产品端点：检查更新 → apply（**真下 304,729,724 B / 19.8 s / 14.65 MB·s⁻¹ / sha256 与线上清单一致**）→ 更新器替换（落位 4329 / 删 727 / 备份 4312 / `pip install -e .`）→ 重启
- [ ] 判据：替换后 `/api/health`.version == `1.2.1` —— **不成立**：替换后服务仍报 **1.1.1**（旧进程没被停掉；启动器 `launcher.log` = `reason=already_running port=8020`）。**善后复测**：收掉旧进程重起 → **1.2.1**（用户自救口径成立）。根因 = 发起更新的那一代（v1.1.1）`spawn_updater` **没传 `--port`** → 更新器按 8000 停服（`updater.log`：`端口 8000 无监听进程，跳过停服`），详见缺陷单
- [x] 盘上 `__init__.py` = 1.2.1；更新器日志留痕（本次增量 727 删除 / 4329 落位 / 4312 备份）
- [x] 保命项：DeepSeek key / 任务记录 / 资料库内容原样、第三方安装包未被误删、包外文件保留、备份生成、`pending-update.json` 已清、`updating.lock` 已释放 —— **十三条全成立**
- [x] 隔离与洁净：真身 8000 未被触碰（数据目录 mtime / `updates/` 条目 / 工作树 tree_stamp / `launcher.log` 四条判据全成立）、收尾 8020 已释放、无残留 python 进程
- [x] 脚本 `.scratch/verify-gate-drills/drill-01-upgrade.py` + 原始输出 `verify-01-upgrade.txt/.json`（主跑）与 `verify-01-upgrade-aftercare.txt/.json`（善后复测 + 构成复算）
- [x] 沙箱没被弄坏，故未触发重建

## 顺手量出来的两件事（都在证据里）

1. **升级后构成**：沙箱 tracked 树 vs 官方 v1.2.1 完整包清单——逐字节一致 3057 / 内容不同 3（全是 `src/contest_generator.egg-info/*`，被更新器自己的 `pip install -e .` 重写）/ **孤儿 1483**（`library/` 1482、`sources/` 1）/ 缺 0 → 已开单 `update-orphan-files/01`。
2. **本机副作用**：沙箱无 `.venv` → 更新器的依赖重装把 `contest-generator` 装进**全局 site-packages**（`1.1.1` + `1.2.1` 两份 editable 元数据并存）。演练收尾已全部卸载（现在零全局 editable 安装），`local-environment.md` 第 2.5 节已记账。
