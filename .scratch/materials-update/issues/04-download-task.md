# 04 — 用户侧：下载任务与 apply/status/cancel 端点

**要做什么：** 用户点「开始下载」后网页能持续显示真实下载进度；弱网失败 / 取消 / 重启后重试只补未完成的卷；不阻塞页面请求。

**被谁阻塞：** 03

**状态：** resolved

- [x] `POST /api/update/materials/apply`：所选批次 slug 白名单校验（仅限 check 返回批次，防注入）→ 磁盘剩余空间校验（≥ 下载总量 + 备份余量，不足 400 中文）→ 启动后台线程（webapp 进程内）→ 返回 `started`
- [x] 下载器：urllib 流式下载（256 KB 分块，先例 `webapp.download_to`）+ 每卷下载后 SHA256 校验；Content-Length 无（个别 CDN）时用已读字节数
- [x] 卷级断点续传：卷完成即持久化标记（`updates\materials-task.json`），取消 / 失败 / 重启后重试自动跳过已完成卷
- [x] `GET /api/update/materials/status`：`{state: idle|downloading|applying|done|failed|partial, current_part_name, parts: [{name, downloaded_bytes, total_bytes, ok}], total_downloaded_bytes, total_bytes, speed_bps, error, message}`；内存态 + 落盘节流（~2 s）供重启恢复
- [x] `POST /api/update/materials/cancel`：置取消标记，任务在分卷边界停止；已完成卷保留
- [x] 测试：monkeypatch 下载函数（先例 `tests/test_update_apply.py`）→ 卷级断点（卷 1 成功卷 2 失败 → 重试只下卷 2）、取消、空间不足 400、非法 slug 400、status 各状态

## Answer

`src/contest_generator/materials_task.py`：TaskState（idle/downloading/applying/done/failed/cancelled/partial）、ApplyTask（构造吃 check 批次形状，part 名 = zip_name → URL 尾段 → `<slug>.zip` 兜底；run() 逐卷下载 + SHA256 校验 + 快照落盘（2s 节流）；恢复时按「本地文件实际哈希 == 清单期望」跳过已完成卷——断点续传；cancel 在分卷边界生效）、download_part（256 KB 分块流式）、task_status（含 speed_bps 窗口估算）、write_task_snapshot。webapp 端点：check 结果缓存模块级 `_MATERIALS_LAST_CHECK` → apply 白名单 / 磁盘空间 1.5× 下载量 + 16MB 余量校验 / 启动 daemon 线程；status / cancel 薄调。测试 `tests/test_materials_task.py` 11 项全绿（断点 / 取消 / 状态机 / 端点）；mypy 的 8 个报错为 HEAD 既有（stash 对照确认），非本次引入。
