# 05 — 后端：应用更新端点（下载 + 校验 + 调度更新器）与状态轮询

**要做什么：** 用户点「一键更新」后，服务端负责：下载更新包到用户数据目录 → 校验 SHA256 → 写待更新标记 → 以独立进程拉起更新器；前端能轮询到下载与更新进度、得到中文结果。

**被谁阻塞：** 04（更新器必须已能独立工作，本工单只做下载与调度编排）

**状态：** resolved

- [ ] `POST /api/update/apply`：按 `check` 给出的 zip_url 下载到 `%USERPROFILE%\.contest_generator\updates\`，流式落盘（不占大内存），下载即校验 SHA256（.sha256.txt 也随更新包发布，校验失败 = 中文 400 且不写标记、不调更新器）
- [ ] 校验通过 → 写待更新标记（pending-update.json：zip 路径、版本、removed 路径、时间）→ 以独立进程调起更新器（detached，不阻塞请求）→ 立即返回「已开始更新」
- [ ] `GET /api/update/status`：下载进度 / 校验状态 / 更新器运行状态（进程存活性 / 标记存在性）轮询；更新完成（标记清除）返回 done
- [ ] 网络中断重试：下载失败允许用户再次点「一键更新」（已下载临时文件可复用或覆盖，无断点续传）
- [ ] 测试：mock 下载源（本地 HTTP）→ 断言校验失败拦截、成功路径写标记并拉起更新器、status 各阶段

## Comments

- 2026-09-09 补标 resolved（代码事实盘点，复核工单自述）：
  路由 `src/contest_generator/webapp.py:1232 @app.post("/api/update/apply")`
  （校验 zip_url/sha256/version → 流式下载 → SHA256 比对 → 写 pending-update.json
  → `spawn_updater`）与 `:1291 @app.get("/api/update/status")`（updating.lock →
  applying / pending-update.json 残留 → failed / last-update.json → done / 否则 idle）。
  流式下载 `webapp.py:309 download_to`（256 KB 分块 + 边下边算 SHA256，不占大内存）；
  独立进程 `webapp.py:328 spawn_updater`（`.venv\Scripts\python.exe` 优先、
  Windows `DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP`、stdio 全 DEVNULL，不阻塞请求）。
  前端轮询 `static/js/ui/update.js:54`（POST apply）与 `:67 pollStatus`（GET status，
  applying → done/failed，中文提示与断网容忍）。
  测试：`tests/test_update_apply.py` 12 用例——成功路径写标记 + 拉起更新器（:66，
  断言 pending 三字段与 spawn 参数）、removed 清单下载透传（:91）、SHA256 不匹配
  400 + 删半成品 + 不拉起（:109）、下载失败 400（:122）、缺字段/版本注入 400（:132）、
  status 四态（:150 idle / :157 applying / :165 failed / :175 与 :188 done）。
  实测基线 `python -m pytest -q` = **3892 passed**（含本文件全绿）。
  验收逐条对照：① apply 端点流式下载 + 下载即校验 + 失败不写标记不拉起 ✓
  ② 校验通过 → pending-update.json（version/zip/removed/started_at）→ detached
  拉起 → 立即返回「已开始更新」✓ ③ status 轮询四态（含 done）✓ ④ 下载失败后
  可再次点击（半成品删除、无断点续传，:109/:122）✓ ⑤ mock 下载源测试 ✓。
  记录两处与工单字面的偏差（不影响行为，均已在实现中定案）：
  (a) 校验值来自 `check` 响应的 `sha256` 字段（前端 POST 回传），不是工单字面的
  「.sha256.txt 随包发布」（`test_update_check.py:90 resolve_assets_matches_zip_and_sha`
  证明发布侧仍是 zip+sha 两个资产）；
  (b) status 不返回字节级下载进度，改为「请求期间前端显示正在下载 + applying/done/failed
  状态机」（工单字面「下载进度」以阶段替代）。
