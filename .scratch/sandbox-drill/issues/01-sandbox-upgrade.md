# B1 — 沙箱 v1.1.1 → v1.2.1 真机升级

**要做什么：** 沙箱「模拟用户机」走产品自己的小发版更新（线上真实 Release，真下 305 MB）→ 替换 → 重启，判据 = **跑起来的服务 `/api/health`.version == 1.2.1**。

**被谁阻塞：** 无——可立即开始。

**状态：** pending

- [ ] 演练前核对前置事实（沙箱根 / 数据目录 / 端口 8020 / 真身 8000 只读），照 `E2E-8020.md` 第 0 节的表
- [ ] 起点版本自证：沙箱盘上 `__version__` 与跑起来的服务都报 1.1.1（**不靠文档转述**）
- [ ] 走产品端点：检查更新 → apply（真下 305 MB）→ 等 update 任务终态 → 等更新器替换 → 服务重启
- [ ] 判据：替换后 `/api/health`.version == `1.2.1`；盘上 `__init__.py` 也是 1.2.1；更新器日志留痕
- [ ] 保命项：DeepSeek key / 任务记录 / 资料库内容原样（抽样比对）、第三方安装包未被误删、包外文件保留、备份生成、`pending-update.json` 已清、`updating.lock` 已释放
- [ ] 隔离与洁净：**真身 8000 未被触碰**（数据目录 mtime 与监听状态前后各查一次）、收尾 8020 已释放、无残留 python 进程
- [ ] 脚本落 `.scratch/verify-gate-drills/drill-01-upgrade.py` + 原始输出 `verify-01-upgrade.txt/.json`
- [ ] 沙箱被弄坏时用 `.scratch/full-download/make_sim_sandbox.py` 重建后重跑（重建过程如实记账）
