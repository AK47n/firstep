# 01 — 批跑器自助复判：红即单支复跑一次 + 自动落盘事件序列

**要做什么：** 跑一批 CDP 冒烟时，红的支不用人再手工判断与手工取证——
`.scratch/cdp-smoke-run.mjs` 对每支非绿结果**自动单支复跑一次**（复跑前重建标签页），
给出「偶发（首红复绿）/ 真红（两次都红）」的终局判定并把这支单独列进汇总；
同时由批跑器的**常驻 CDP 监听**采集 `Runtime.exceptionThrown` / `Page.javascriptDialogOpening`
/ 导航事件，**仅在非绿时**把该支次的事件序列落盘成可读文件。判定口径做成纯函数放进共用件
`.scratch/cdp-harness.mjs`，配 `tests/js` 单测；端到端用真实 Chrome(9251) + webapp(8000)
跑通「真红 / 偶发 / 挂死」三类现场。

**被谁阻塞：** 无——可立即开始（第十二轮「下一轮建议」第 1 项的落地；共用传输层
`connect()` 已在第十二轮补齐事件上报能力）。

**状态：** resolved

- [x] `.scratch/cdp-harness.mjs` 新增纯函数：`classifyAttempt(rec)`、`runVerdict(first, retry)`、
      `retryDecision(a, {retry, attemptIndex})`、`digestEvents(events, {t0Ms})`、`diagFileName(script, round)`、
      `renderDiagText({...})`（判定口径只此一处定义，`TRANSPORT_SIGNAL_RE` 亦随之外露）
- [x] `.scratch/cdp-smoke-run.mjs` 新参数 `--retry=<N>`（默认 1，0 = 关闭）与 `--no-diag`；
      非绿即复跑一次，复跑走**同一套**「重建标签页 → spawn」路径（另加 `--debug-watch` 排查口子）
- [x] 记录 schema 扩展 `attempts[]`（逐支次 exit/timedOut/hung/pass/reasons/diag）/ `verdict` / `flake` /
      `retry` / `diagFile` / `diagFiles`，且顶层 `exit`/`pass`/`tail` 语义不变（= 最后一次尝试；
      批跑器按第十二轮记录「每支前重建标签页」的既有约定继续复用）
- [x] 常驻监听采集事件、按支次切片：**非绿支次**落盘 `.scratch/cdp-smoke-runs/` 的
      `<时间戳>-r<轮>-<脚本>.json` + 同名 `.txt`（时刻 / 折叠计数 / 关键事件 / 一行摘要）；
      绿支次不落盘。实测实录 4 条关键事件（异常 → 对话框 → 对话框关闭 → 异常）
- [x] 汇总输出偶发计数与偶发支清单；退出码语义不变（真红 → 1，只有偶发 → 0）
- [x] `tests/js/cdp-harness-verdict.test.mjs` **13 条全绿**：三类非绿判定、偶发 vs 真红、挂死优先、
      `--retry=0` 永不复跑、digest 折叠与关键事件保留、落盘命名、现场文本
- [x] 真机取证（Chrome 9251 + webapp 8000）：四支确定性探针（偶发 / 真红带事件 / 永远红 / 挂死）
      + `--retry=0` 对照，证据存档 `.scratch/batch-runner-self-heal/verify-*.txt`
- [x] 无回归：`refine` 批 10/10、库 UI 批 4/4、库 UI 连跑 2 轮 8/8 全绿；
      `python -m pytest -q` → **3928 passed**、`node --test tests/js/*.test.mjs` → **1416 pass / 0 fail**
      （1403 + 本轮 13 条新增，零删除）

## Comments

- 2026-09-10 第十三轮（按第十二轮「下一轮建议」第 1 项）：自助复判落地 + 真机取证。
  两个口径按用户确认执行：**复跑前重建标签页**；**事件序列由批跑器自身常驻监听采集**、仅非绿落盘。

  **落地过程中挖出并修掉的四条机制缺口**（详见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`
  第十三轮「本轮定位过程」）：① 脚本自己换标签页 ⇒ 旁听恒 0 事件（新增 `watchTargets` 跟随 + `targetId`）；
  ② 跟随挑到残留孤儿标签页（改为优先挑新出现的页面）；③ `spawnSync` 阻塞主线程 ⇒ 事件到过没被解析
  （新增 `settleEvents()` 解析窗口）；④ 批跑器自身崩过一次（exit `0xC0000409`，偶发）⇒ 监听加防崩护栏
  （重挂 try/catch、连续失败 3 次放弃跟随、close 后不再改挂）。

  **给后续写冒烟脚本的约定**：脚本可读 `CDP_BATCH_TARGET` 复用批跑器的标签页，从而与自己（如脚本也连 CDP）
  和旁听监听落在同一 target 上，事件一条不漏；不支持该约定的脚本行为不变，批跑器以「支次后追挂 + 反射现场」兜底
  （落盘文件注明「反射非实录」）。

  **已知限制（写下来免得下次重踩）**：跟随是 300ms 级轮询，且批跑器用同步 spawn，故脚本**换标签页那一刻**
  产生的事件仍可能漏；要一条不漏就得让脚本走 `CDP_BATCH_TARGET` 约定。
