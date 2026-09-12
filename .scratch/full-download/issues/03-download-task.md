# 03 — 用户侧：完整包下载任务与 apply / status / cancel

**要做什么：** 用户点「下载完整 firstep」后，网页能持续显示真实下载进度（总进度 / 当前卷 / 速度 / 剩余时间），中途取消或失败、甚至关掉页面重启工具，**已经下好并校验通过的卷都不再重下**；磁盘不够或请求里塞了非法卷名时给中文 400，不白屏、不卡死。

**被谁阻塞：** 02（分卷表与下载地址来自检查端点）

**状态：** resolved

- [x] `POST /api/update/full/apply`：所选分卷白名单校验（仅限检查返回的分卷，防注入）→ 磁盘剩余空间校验（≥ 下载总量 + 备份余量，不足 400 中文）→ 起后台线程流式下载（256 KB 分块）→ 立即返回 `started`，不阻塞请求
- [x] 每卷下载完做 SHA256 校验，通过后写持久化标记；失败 / 取消 / 重启后重试只补未完成的卷
- [x] 字节进度来自实际已读字节（Content-Length 缺失时同样成立），并据此算速度与剩余时间
- [x] `GET /api/update/full/status` 契约落地：
      `{state: idle|downloading|applying|done|failed, parts: [{name, downloaded_bytes, total_bytes, ok}], total_downloaded_bytes, total_bytes, speed_bps, error, message}`
- [x] 状态快照节流落盘（约每 2 s），进程重启后能恢复任务视图（不重复下载已校验卷）
- [x] `POST /api/update/full/cancel`：任务在分卷边界停止，已完成卷标记保留，状态回 `idle` 且带中文说明
- [x] 全部卷就绪 → 状态推进到 `applying`（本工单不执行替换，替换由 04 的更新器完成）
- [x] 下载目录落在用户数据目录的 `updates\` 下（工具根之外），文件名与清单一致（防重复后缀导致应用器找不到）
- [x] 测试：monkeypatch 下载函数断言卷级断点（第 1 卷成功、第 2 卷失败后重试只下第 2 卷）、取消、空间不足 400、非法卷名 400、status 各状态与速度字段
- [x] 测试：下载文件名与清单 `zip_name` 逐字节一致（回归「双后缀」类缺陷）

## 实施记录（2026-09-13）

**实现面**
- 新增 `src/contest_generator/full_task.py`：`FullDownloadTask`（扁平**分卷表**，无批次分组、无 partial 态）、`full_task_status`、`start_full_update`、`write_full_snapshot`，以及状态单源访问器 `get_full_task` / `set_full_task` / `last_check` / `set_last_check`（webapp 与测试共用同一份模块级状态，避免两份单例漂移）。
- 复用 `materials_task` 的三样东西而不是重写：`TaskState` 枚举、`_file_sha256`（恢复期内容校验）、`download_part`（256 KB 流式下载）。状态机与快照节流形态与资料库任务同构，便于对照阅读。
- `webapp.py` 新增三端点：`GET /api/update/full/status`、`POST /api/update/full/apply`、`POST /api/update/full/cancel`；`check` 端点把结果写进 `full_task` 的白名单单源。
- 测试 `tests/test_full_task.py` 19 例（19 passed）。

**契约要点（与资料库增量端的差异，有意为之）**
- 分卷字段用 `{name, size, sha256, url}`（spec 口径），落盘文件名 = 清单 `zip_name` 逐字节一致（`updates\full\`），应用器按名找文件，杜绝「双后缀」类缺陷（专项断言文件名集合）。
- 磁盘预检：下载总量 × 1.5 + 16 MB（备份被覆盖文件的余量），与资料库端同量级口径。
- 校验失败 / 下载失败都会删掉半成品文件，不留「看起来已下好」的残卷。

**踩坑记录**
- **快照跨测试串味**：多个测试共用一个临时任务目录时，上一个测试写下的 `full-task.json` 会被下一个测试读成断点（续传逻辑真的生效，测试反而假失败）。修法：`_task` 助手加 `subdir`，每个测试独立任务目录。
- **端点测试必须注入下载函数**：`FullDownloadTask` 的默认下载实现是真 urllib，端点测试只注入 `start_full_update` 不够——会真的去请求 `https://example.com`（404）。修法：同时 patch `full_task.download_part`。
- 任务完成时 `current_part_name` 没清空（无 `on_complete` 的路径），会让前端一直显示「正在下载 X」；已修并加断言。

## Comments

- `on_complete` 目前是 webapp 里的占位（抛中文错误「完整包替换尚未接通」），由工单 04 接通更新器；届时该路径的终态从 `failed` 转为 `done`，本工单的端点测试已按此口径留了说明注释。
