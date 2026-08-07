# 03 — 前端进度 UI：stepper + 批进度 + 双计时器 + 可折叠日志

**What to build:** 母版页提炼区的进度可视化（spec「显示」「完成 / 失败态」）。点击"AI 提炼报告"后进度区出现，替代现状的按钮静态转圈；用 fetch + ReadableStream 手动解析工单 02 的 SSE 流（EventSource 仅支持 GET，现状接口是 POST JSON；不需要自动重连——断线 = 放弃本次，刷新安全重试）。

显示要素（全部来自 spec，不得加调用内的假进度）：

- 4 步 stepper：开始 → 摘要 → 判定 → 完成（扫描 / 拼装是瞬间步骤，划过即可）
- 批进度条："摘要 第 2/5 批 · 已读 43/115"
- 双计时器：总用时 + 当前调用已等待，每秒跳动——模型单次调用期间后端无事件，计时器是"没卡死"的唯一证明
- 补问徽标：`retry` 事件 → "批 3 补问中"
- 可折叠事件日志：`batch_start` 列出该批文件清单（可展开）、批完成行、补问轮行；日志过长不撑爆页面
- 完成态：进度区折叠为一行"提炼完成，用时 12 分 34 秒"，`done` 载荷（完整报告）走现有报告渲染路径——报告形态不变，确认 / 预览逻辑原样复用
- 失败态：日志保留 + 红色错误行 + 按钮恢复可重试
- 不做取消按钮（刷新 = 安全放弃）；提炼期间切换页签不中断

**Blocked by:** 02

**Status:** resolved

**Reference:** `.scratch/distill-progress/spec.md`（User Stories 1-16、Implementation Decisions「显示」「存活证明」「完成 / 失败态」）、CONTEXT.md「进度事件」词条

## Comments

- 2026-08-06 工单 03 完成（分支 ticket-03-frontend-progress-ui，未合 main——02 并行
  开发中，验收待 02 合入后 git merge main 真机跑一遍）。实现：`static/index.html`
  单文件内改（CSS + 母版页进度区 + JS），btn-distill 从 apiPost 收 JSON 改为
  fetch POST + ReadableStream 手动解析 SSE；报告渲染 / 确认 / 预览逻辑零改动，
  done 载荷（与现状 /api/masters/distill 响应同构）原样走 renderReport()。
- SSE 解析器 = 纯函数 `parseSSE(Response, onEvent)`（不碰 DOM，输入 Response →
  逐事件回调），按工单 02 共享契约实现：event/data/空行分隔、容 CRLF 与任意
  分片边界、流末尾缺收尾空行也认、未知字段行（id/注释）忽略；不自动重连，
  流结束无 done/error = 断线 → 红行提示"刷新页面后可安全重试"并恢复按钮。
- 显示要素全部按 spec：4 步 stepper（扫描/拼装瞬间步骤划过——0 批次阶段由
  phase_done 直接标 done）、批进度条"摘要 第 2/5 批 · 已读 43/115"（processed_count
  为阶段内累计，阶段切换时计数归零；total = start 的 judgment_count，两阶段同）、
  双计时器每秒跳动（总用时 + 当前调用已等待，后者在每事件到达时重置——模型
  调用死寂期由它证明存活）、retry → "批 N 补问中"徽标 + 日志行（轮次/缺失数）、
  可折叠事件日志（batch_start 行可展开文件清单；上限 300 条丢最旧 + max-height
  滚动，不撑爆页面）、完成态折叠为一行"提炼完成，用时 X 分 Y 秒"、失败态日志
  保留 + 红色错误行 + 按钮恢复。零批次（无待判文件）不显示空批次进度、立即
  完成。不做取消按钮（刷新 = 安全放弃）。
- 自查（前端无单测基建，仓库惯例 UI 手动验收；本次用 headless 等价物先验）：
  ① 抽取 parseSSE 纯函数喂假流（new Response(new ReadableStream(...))，node 跑）
  13 例：契约形态 / 分片 / CRLF / 末尾 / 转义 / 完整序列 / error / 异常；② jsdom
  载入整页 + 脚本化 SSE 流驱动真实点击流程 50 断言：stepper 推进、批进度文本与
  进度条宽度、计时器跳动与事件后重置、补问徽标、日志行与文件清单展开、完成
  折叠与报告渲染、error 红行、断线提示、零批次、日志折叠。全部通过。真机验收
  待 02 合入 main 后 merge 过来用小规模导入（1 旧工程、少量文件、1 批瞬间完成）
  再跑一遍。
- 收尾：全量 pytest 424 绿 + mypy 全绿（未碰任何后端文件；webapp.py / master.py
  / tests/ 未动）。提交：feat: 工单 03——前端提炼进度 UI + docs: mark issue 03
  resolved。
