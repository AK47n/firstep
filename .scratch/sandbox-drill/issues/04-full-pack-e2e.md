# B4 — 完整包换装：从线上真下 802 MB → 替换 → 重启

**要做什么：** 新用户那条路的最后一格——**真从线上下载完整包**（不是复用本机缓存）走完检查 → 下载 → 校验 → 替换 → 重启，并证明演练没碰真身。

**被谁阻塞：** 无（用一次性工具根，不依赖 B1；刻意如此，避免升级失败就整轮停摆）。

**状态：** pending

- [ ] 一次性工具根（`%TEMP%`）+ `USERPROFILE` 重定向隔离（照 `verify-07-tier3-e2e.py` 的隔离手法）
- [ ] 走产品端点：`/api/update/full/check` → `/api/update/full/apply` → **真下载 802 MB** → sha256 校验 → 更新器替换 → 重启
- [ ] 判据：替换后 `/api/health`.version == 1.2.1；资料库基线写回（`sources/materials/.materials-manifest.json`，版本与批次对得上）；包外文件与第三方安装包未被动过；`full-installed.json` 落盘
- [ ] 隔离三判据：真身数据目录 mtime 未变、真身 `updates/` 条目未变、真身工作树未变（`tree_stamp` 排除 VCS/缓存/`.scratch`）
- [ ] 证据里**明写这一格是真下载**（记录耗时、速度、字节数、sha256 与线上清单一致），不许混用"复用缓存"的措辞
- [ ] 脚本 `.scratch/verify-gate-drills/drill-04-full-pack.py` + 原始输出 `verify-04-full-pack.txt/.json`
- [ ] 收尾：端口释放、无残留 python 进程
