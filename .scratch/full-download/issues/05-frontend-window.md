# 05 — 前端：全量弹窗 + 无基线入口 + 设置页常驻按钮

**要做什么：** 用户不用理解「基线」「增量」这些词也能走通：检查更新发现本地缺基线时，弹窗主按钮直接就是「一键下载完整 firstep（约 1.0 GB）」；设置页常驻一个「下载完整 firstep」入口，供修损坏 / 换机器 / 主动重下；点下去看到真实进度（进度条 / 当前卷 / 速度 / 剩余时间 / 后台继续 / 取消），完成后明确告知已更新到哪个版本、工具即将重启，失败给中文原因与重试（已完成卷跳过）。

**被谁阻塞：** 03（进度与结果来自全量状态端点）

**状态：** resolved

- [x] 无基线弹窗（资料库增量侧）主按钮从「去下载完整包」改为「一键下载完整 firstep」，量级与当前版本用真实数字填充
- [x] 设置页新增「完整包」行：当前版本 + 「下载完整 firstep」常驻按钮 + 结果区（离线提示不影响既有增量区）
- [x] 全量弹窗：版本头（当前 → 最新）+ 下载总量 + 分卷数 + 「开始下载 / 稍后」
- [x] 下载中视图：总进度条 + 已下 / 总量 + 当前卷 + 速度 + 剩余时间 + 「后台继续（关闭弹窗）」+ 「取消」；轮询期间页面不卡、可关闭
- [x] 终态文案：完成（已更新到 vX，工具即将重启） / 失败（中文原因 + 重试） / 取消（已完成卷保留，可继续）
- [x] 已是最新且用户主动点重下时给出确认语义（不静默重复下载）
- [x] 纯函数进 `fx/`、DOM 胶水进 `ui/`，与既有 auto-update / materials-update 结构同构（fx-guard 登记）
- [x] 测试（`tests/js`，node）：弹窗 HTML、进度文案（含速度 / 剩余时间格式化）、终态文案、双轨选路（有基线 → 增量，无基线 → 全量）、XSS 转义

## 实施记录（2026-09-13）

**实现面**
- 新增 `src/contest_generator/static/js/fx/full-update.js`（纯函数）：`fullCheckCardHTML`（未知版本 / 有新版 / 已是最新三态 + 错误态走中文 message）、`fullConfirmHTML`、`fullProgressHTML`、`fullStateText`、`fullResultText`、`fullPlanText`（GB/MB 自适应）。
- 新增 `ui/full-update.js`（DOM 胶水）：`initFullUpdate` 接线自检、确认弹窗、`apply` → 2s 轮询 status → 进度 / 终态 toast；**资料库区无基线时的「一键下载完整 firstep」按钮也接到这里**（双轨选路的落点）。
- `fx/materials-update.js` 的 `baseline-missing` 分支改为「错误说明 + 一键下载完整 firstep 主按钮」（此前只有一句文字指引）。
- `index.html`：设置页新增「完整包下载」卡（检查按钮 + 说明 + 结果容器）+ `initFullUpdate()` 调用。
- 测试：`tests/js/full-update.test.mjs` 13 例；`fx-guard` 登记 6 个新导出；全量前端测试 **1550 pass / 0 fail**。

**真机冒烟（CDP + 真浏览器，`.scratch/full-download/smoke-full-update.mjs`，9/9 PASS）**
- 设置页出现「完整包下载」卡；点检查 → 结果区渲染「下载完整 firstep」+ 版本体积（`v1.1.0（1.0 GB · 1 卷）`）。
- 点按钮 → 确认弹窗（版本 / 体积 / 卷数 / 重启语义 / 开始下载）。
- 资料库区无基线 → 主按钮就是「一键下载完整 firstep」。
- 下载中：`256.0 MB / 1.0 GB（25%）· 速度 5.0 MB/s · 剩余 154 秒` + 当前卷 + 取消按钮。
- apply 请求体逐字断言：`{"parts":["firstep-full-v1.1.0.zip"]}`（前端把 check 的分卷名原样传回）。
- 截图：`.scratch/full-download/shot-full-update-window-dark.png`。
- 冒烟用 8011 临时实例（不打扰用户在用的 8000 实例），打完即停。

**过程中修掉的真问题**
- **后端 apply 白名单过期 → 「点下载就 400」**：白名单来自后端「上次 check」，后端重启或前端拿的是旧结果时直接拒绝。改为：白名单为空**或请求分卷不在其中**时，端点先自己重查一次再判定（真机器上「重启后点下载」不再报错）。
- 弹窗按钮重复（骨架取消 + 内容区取消都渲染）：内容区去掉重复取消，取消统一由弹窗骨架承担。

**额外留的测试缝**
- `POST /api/update/full/apply` 支持 `dry_run: true`（演练模式：不下载、不起进程、只回成功文案）——给真机冒烟用，让浏览器能把「检查 → 确认 → 已开始下载」走完而不产生副作用。

## Comments

- 冒烟里 apply 走桩而非真端点：后端 apply 的白名单来自**服务端自己的 check**，而本机没有真实完整包资产（真实 GitHub 上 `v1.0.0` 还没传完整包），所以服务端的兜底自查必然返回 no-asset。下载 / 替换 / 重启链路由 Python 侧 `test_full_apply.py` / `test_full_updater.py` 与工单 06 的 e2e 覆盖。
