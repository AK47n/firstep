# 03 — 用户侧：完整包下载任务与 apply / status / cancel

**要做什么：** 用户点「下载完整 firstep」后，网页能持续显示真实下载进度（总进度 / 当前卷 / 速度 / 剩余时间），中途取消或失败、甚至关掉页面重启工具，**已经下好并校验通过的卷都不再重下**；磁盘不够或请求里塞了非法卷名时给中文 400，不白屏、不卡死。

**被谁阻塞：** 02（分卷表与下载地址来自检查端点）

**状态：** ready-for-agent

- [ ] `POST /api/update/full/apply`：所选分卷白名单校验（仅限检查返回的分卷，防注入）→ 磁盘剩余空间校验（≥ 下载总量 + 备份余量，不足 400 中文）→ 起后台线程流式下载（256 KB 分块）→ 立即返回 `started`，不阻塞请求
- [ ] 每卷下载完做 SHA256 校验，通过后写持久化标记；失败 / 取消 / 重启后重试只补未完成的卷
- [ ] 字节进度来自实际已读字节（Content-Length 缺失时同样成立），并据此算速度与剩余时间
- [ ] `GET /api/update/full/status` 契约落地：
      `{state: idle|downloading|applying|done|failed, parts: [{name, downloaded_bytes, total_bytes, ok}], total_downloaded_bytes, total_bytes, speed_bps, error, message}`
- [ ] 状态快照节流落盘（约每 2 s），进程重启后能恢复任务视图（不重复下载已校验卷）
- [ ] `POST /api/update/full/cancel`：任务在分卷边界停止，已完成卷标记保留，状态回 `idle` 且带中文说明
- [ ] 全部卷就绪 → 状态推进到 `applying`（本工单不执行替换，替换由 04 的更新器完成）
- [ ] 下载目录落在用户数据目录的 `updates\` 下（工具根之外），文件名与清单一致（防重复后缀导致应用器找不到）
- [ ] 测试：monkeypatch 下载函数断言卷级断点（第 1 卷成功、第 2 卷失败后重试只下第 2 卷）、取消、空间不足 400、非法卷名 400、status 各状态与速度字段
- [ ] 测试：下载文件名与清单 `zip_name` 逐字节一致（回归「双后缀」类缺陷）
