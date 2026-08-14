# 01 — CLI 首编超时即停：check_topic 初编译 timed_out 不丢，不进修复循环

**What to build:** cli-fix-loop-parity/01 的遗留收尾。该工单给循环内重编译补了超时停条件，但 check_topic 的**首次编译**仍丢弃 `CompileRun.timed_out`（解包 `_timed_out` 沿用旧路径）——`compile_passed(None)=False` → 进修复循环，把超时半截输出当 error_text 喂第 1 轮 LLM：白烧一次分钟级调用 + 误报修复结果。前端对偶已有：`startFixCenter` 初编译 `compile.timed_out` 即停（`index.html:1852-1856`），不进入 fixRounds。

**Status:** ready-for-agent

## 现状证据（cli-fix-loop-parity/01 Comments 遗留）

- `generate_check.py` check_topic：首编 `uv4_build`/`gmake_build` 现返回四元组（passed, 摘要, 原文, timed_out），check_topic 解包 `_timed_out` 丢弃；`passed is None`（含超时形态）→ `run_fix_loop` 进第 1 轮。
- 循环内超时停（上一工单已修）：`run_fix_loop` 重编译 `timed_out` → 「第 N 轮重编译超时，已停止循环——可修改工程后重新运行本脚本」即停，半截输出不进 error_text。
- 前端对偶：`index.html:1852-1856` 初编译超时停 + 超时文案，不进 fixRounds。

## 设计定案（已代决，实施会话不再重开）

1. **check_topic 首编 timed_out 即停**：首编 `run.timed_out` 为 True → 不进 `run_fix_loop`，打印停文案（核心短语对齐循环内文案，如「初次编译超时，已停止——可修改工程后重新运行本脚本」，实施时读循环内文案逐字对齐风格），汇总行按失败态处理（对齐既有失败路径的 exit 语义，不报修复轮结果）。
2. **不动**：工具链缺失（passed None 且非超时）既有路径、「前端状态机驱动循环」定案、run_fix_loop 内部、src/ 全部（webapp / fix_errors / compile_runner / 前端）。
3. 真机强制超时不可控（UV4 全量重建需 >180s 才自然触发）——以单元测试合成 `CompileRun(timed_out=True)` 覆盖分支为验收主体，真机留可选 probe（临时把 compile_runner 超时常量调小在 scratch 环境验证——不落库）。

## 实施边界

- 只动 `.scratch/real-run/generate_check.py` + `tests/test_generate_check_contract.py`。
- **零改动**：src/ 全部（本工单不碰任何 src 文件）。

## 验收标准

- [ ] 红证先行：合成首编 timed_out=True 用例（断言：不进 run_fix_loop / 停文案在场 / 无 fix_stream 调用）→ 现行必红（进循环 + 白烧第 1 轮）→ 实施后绿
- [ ] 全量 pytest 绿（基线 1377）+ 契约钉全绿
- [ ] （可选）真机 probe：临时调小 compile_runner 超时跑通停路径（记录不进库）
- [ ] `git status` 只出现预期文件

## 实施提示词（新会话粘贴）

> 工单：`.scratch/cli-init-compile-timeout/issues/01-stop-on-initial-timeout.md`（先读全文，设计已定案勿重开）。
> 环境：`cd C:\Users\luoji\Desktop\firstep` → 无并行工单，直接在主检出 `git checkout -b cli-init-compile-timeout-01`。
> 文件边界：只动 `.scratch/real-run/generate_check.py` + `tests/test_generate_check_contract.py`；src/ 全目录零改动。
> 关键：停文案与循环内超时文案（上一工单所加）风格逐字对齐；首编超时进失败态汇总，不报修复轮结果；工具链缺失旧路径不动。
> 验收：红证记录 → 实施绿 + 全量 pytest 绿（基线 1377）+（可选）probe；提交格式 `fix: ...（工单 cli-init-compile-timeout/01，N 绿——...）` + docs 一笔；`gh pr create --body-file`；不 force push；证据写本文件 Comments，Status → resolved，推送。

## Comments
