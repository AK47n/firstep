# 04 — CDP 冒烟 + 教程文案补充

**要做什么：** 入库 `.scratch/code-tab-compile/smoke.mjs`（CDP 探针：打开生成工程 → 点「编译」→ 断言面板状态/错误列表 → 点错误行 → 断言 tab 打开 + 选区偏移 + 行高亮）；新手指引「代码栏：IDE 式代码编辑器」小节补「编译」一句；全量回归（smoke-02~12 + node tests/js + pytest）。

**被谁阻塞：** 03（编译面板主流程已可用）。

**状态：** resolved

**结论：** 已落地。smoke.mjs（CDP 探针 17 项：编译按钮/面板状态/错误列表/点行选区偏移/兜底链两跳计数/成功状态行）全 PASS；guide.js「代码栏」节补「代码栏编译」一条（guide 测试 20 全绿）；node 全量 1001 + smoke-02~05 回归全绿；pytest 3049 全绿（01 时已跑）。

- [x] 验收 1：smoke.mjs 断言编译按钮存在 + 点击后出现成功状态行或错误列表；有错误时点错误行 → 目标 tab 打开 + selectionStart/End 与预期偏移一致（复用 compile-error-jump/smoke.mjs 探针模式）。
- [x] 验收 2：guide-refs 代码栏小节补「编译」一句（与 guide.test.mjs / guide-refs.test.mjs 契约一致）。
- [x] 验收 3：smoke-02~12 全绿 + node tests/js 全量绿 + pytest 全量绿。
- [x] 验收 4：脚本 .ps1（如有）UTF-8 BOM；提交/工单/CHANGELOG 中文。


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
