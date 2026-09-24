# 07 — 真机演练：在真实 Release 上发一次完整包并走通全链路

**要做什么：** 发布者按新流程真的发一次完整包（约 1.0 GB、1~2 卷），在一个「无基线」的环境里点「一键下载完整 firstep」走完整链路，并确认更新后的工具可正常使用、下次检查更新只提示变化的部分。

**被谁阻塞：** 06（端到端冒烟与文档就绪）+ 需要真实 Release 上传（人工）

**状态：** resolved（2026-09-24 收口；真机演练已由挂账单 G1 分三段跑完，逐项证据见下）

- [x] 跑一次 `pack-full` 产出真实四件套，核对体积与卷数（本机实测：包内 8764 文件 / 原始 1.07 GB；zip 后约 1.0 GB、1~2 卷）
  —— **真发了**：v1.1.0 / v1.1.1 两版线上各 **8 件资产**（完整包 4 件 `firstep-full-v1.1.1.{zip,manifest.json,removed.txt,sha256.txt}` + 小发版 4 件），
  线上实测 `gh release view v1.1.1 --json assets`；发布前四件套自检 **26 / 20 项全过**（`verify_release_assets.py` / `verify_release_assets_111.py`）。
- [x] 上传 Release 资产（zip 分卷 + 清单 + 删除清单 + 校验和），用 API 确认附件齐全
  —— 真机端点核对 `verify_live_endpoints.py` / `verify_live_v111.py`；发布后**从线上重新下载两个 zip 重算 SHA256** 与校验和一致（`verify_published_assets.py`）。
- [x] 无基线环境点「一键下载完整 firstep」→ 下载 → 校验 → 自动替换 → 自动重启
  —— 沙箱「模拟用户机」（`Desktop\firstep-sim` + 独立数据目录 + 端口 8020，`make_sim_sandbox.py`）：真下载 **783 MB（62 s）**
  → SHA256 校验 → 停服 → 备份 8536 文件 → 落位 8774 → **重启**；脚本 `trigger_and_watch.py` / `verify_sim_after_update.py`。
- [x] 更新后核对：工具可启动、DeepSeek key / 任务状态 / 对话记录 / 生成的工程原样保留、资料库内容齐全、第三方安装包未被误删
  —— 同轮 `verify_sim_after_update.py`：版本 **1.1.1**；保命项（第三方安装包未被误删 / 包外文件保留 / 备份生成 / `pending-update.json` 清除）逐条成立；
  小发版那半 `sim_small_update.py`：296 MB → 替换 5039 文件 → 记录 `mode=single / version=1.1.1`。
- [x] 核对基线已写回：再次检查更新只提示「变化的部分」（增量），不再要求完整包
  —— 写回资料库基线 **12 批次 / 5087 文件**；断点续传复跑 **0 秒**进替换（已校验卷跳过）。
- [x] 弱网演练：下载中途取消 / 断网重试，确认已校验的卷不重下
  —— 2026-09-18 沙箱真机（`sandbox-drill/02`，resolved）：弱网取消 **10/10 成立**（64 KB/s → 取消 → 半成品 524,288 B + 边车在 → 重试从 524,288 B 接着下）；
  断线重试 **12/12 成立**（`verify-gate-drills/verify-02-degraded.{txt,json}`）。
- [x] 失败演练：构造一次校验失败（改一个卷），确认中文错误 + 备份位置提示、旧版本仍可用
  —— 同轮拆两支跑：**不可重试支 11/13**，其中两条不成立是**真缺陷**（失败后残留整卷 3,961,701 B 半成品 + 73 B 边车）
  → 开单 `update-verify-failure-leftovers/01` → 已修（2026-09-19）并随 **v1.2.2** 发出；
  「中文错误（发布信息不一致…）+ `error_kind=verify` + 不重试 + 旧版本仍可用且未换掉」当轮即成立；可重试支按 spec 是**观察格**（另开决策单 `update-content-mismatch-retry-cap/01`，已修）。

## Comments

2026-09-13：本单所有**代码侧前置**已就绪并逐条登记到
`.scratch/real-acceptance/issues/01-real-machine-acceptance.md` 的 **G1**（含命令、怎么验、已就位证据）。
本机可验的部分已全部跑过：
- 端到端演练 `.scratch/full-download/e2e_full_download.py` → **7 步全通过**（含断点续传、删除清理、基线写回、第三方安装包原样）；
- 浏览器冒烟 `.scratch/full-download/smoke-full-update.mjs` → **9/9 PASS**（截图 `shot-full-update-window-dark.png`）；
- 全量回归 pytest **4307 passed / 1 skipped**、JS **1550 pass**。

**唯一剩下的**是「真的发一次 Release 并上传约 1 GB 资产」——需要发布者带宽与发版决定，
故本单保持 `ready-for-human`，进度看 G1。

- **2026-09-24 收口（标签没跟，本轮补勾翻牌）**：上面那句「唯一剩下的」**已于 2026-09-13 做掉**——
  挂账单 `real-acceptance/01` 的 **G1 三段全部 `[x]`**（前两步：v1.1.0 / v1.1.1 真发布并上传资产 + 沙箱模拟用户机走通全链；
  后三步：2026-09-18 沙箱真机跑完弱网取消 / 断线重试 / 校坏一个卷）。此后 2026-09-16 ~ 09-19 又连发了
  v1.2.0 / v1.2.1 / v1.2.2 三版（`gh release list` 可核，v1.1.0 与 v1.1.1 至今各带 8 件资产）。
  **本单自己的 7 个 checkbox 一个没勾**，于是每轮盘点都把它当未完成——本轮按 G1 的在盘证据逐条补勾
  （零新增演练：不重跑已经 PASS 且判据未被后续改动触及的项）。
  **判据有效性复核**：G1 后三步依赖的产品行为此后动过两处——`update-verify-failure-leftovers/01`
  （校验失败清半成品，2026-09-19）与 `update-content-mismatch-retry-cap/01`（连续 5 次转终态，2026-09-19），
  两条都把当轮判红修掉并随 v1.2.2 发出，方向与本单验收一致，不需要重跑。
  **顺带记下的流程事实**：`gh release create` 在服务端建 tag、本地 `git tag` 不会自动有 → 已 `git fetch origin --tags`
  并把「先本地打 tag 再建 Release」写进 `releasing.md`（另见 `full-download/08` 的空 `removed.txt` 坑）。
