# 04 — 全库编译矩阵（verified/notes 刷新）

**What to build:** 对每个模块 × 已有平台生成最小工程并真编译（stm32 UV4 / mspm0 gmake）；按结果刷新 manifest verified/notes。0 error 硬门槛；模块自身 warning=0；syscfg 基线 warning（ovsRate 等）允许并记录。失败项在工单 Comments 逐条留痕，不静默标 verified。

**Blocked by:** 01, 02, 03

**Status:** resolved（2026-08-15）

## Comments

- 结果：41/41 平台条目 PASS；全部条目 verified 已翻 true，notes 记录编译矩阵留痕。
- 基线 warning：mspm0 的 7 个 UART 模块各 1 条 syscfg ovsRate 建议，非模块代码，已在 notes 记录。
- 产物：`.scratch/module-polish/matrix_results.md` + `matrix/<platform>/<slug>/build.log`（原始日志，本地证据）。
- 首次运行误把 stm32 “0 Warning(s)” 当警告，已由 `summarize_matrix.py` 从日志重算修正。

- [x] 生成矩阵脚本（只读模块 + 最小 main，循环编译）
- [x] 全库 41 个平台条目跑完，0 error 的条目按日志刷 verified/notes
- [x] 失败条目如实记录，不标 verified（本次 0 失败）
- [x] pytest 全绿 + mypy src 干净
