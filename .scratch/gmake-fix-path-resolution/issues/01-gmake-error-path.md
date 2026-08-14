# 01 — gmake 报错路径 `../main.c` 无法定位（mspm0 修复循环端到端闭环被阻）

**Type:** task

**Status:** resolved

**Blocked by:** 无（src 侧工单，与 gen-check-fix-loop/01、fix-loop-progress/01 已并行收尾）

## 背景（2026-08-13 gen-check-fix-loop/01 真机验收发现）

mspm0 线注错（main.c 首行 `#include "nonexistent_probe_fixloop.h"`）→ gmake 编译报错
`../main.c:1:10: fatal error: 'nonexistent_probe_fixloop.h' file not found` →
`/api/fix-errors` 解析后 `collect_candidate_paths` 定位不到 main.c → 三轮全降级
（degraded，0 applied），修复未落盘，闭环被阻。

**根因（已核实，fix_errors.py）：** tiarmclang 报错路径相对 gmake 工作目录（Debug/），
源码在工程根、报错路径带 `../` 前缀；`_resolve_in_root` 只试两种基准——工程根
（`is_unsafe_path` 拒 `..` 形态）与 `_report_benchmarks` 的工程文件父目录
（.cproject/.uvprojx 所在处，mspm0 产物 .cproject 在工程根）——`../main.c`
对工程根越界、对工程根基准同样越界 → None → 降级。UV4 线无此问题：报错路径
`..\main.c(N)` 相对 user/ 子目录（uvprojx 所在处），基准命中即可回退工程根。
web 修复中心 mspm0 线同病（同一解析域，此前从未在 mspm0 上跑过修复）。

## 决策记录（代决，用户可 grilling）

1. **修复点在解析域，不在 CLI**：CLI 修复循环（gen-check-fix-loop/01）行为完全符合
   规格（3 轮执行、降级如实提示、剩余错误如实报告）——本工单只修 src 侧路径定位。
2. **基准补充方式**：`_report_benchmarks` 增补"构建工作目录"基准候选（探测产物下
   含 `subdir_rules.mk` 的目录 = Debug/，或 .cproject 的 Debug 子目录）；对仍带
   `../` 前缀的路径，逐级剥前缀后按工程根重试（`../main.c` → main.c）。二选一或
   双保险，实施时定；`_resolve_in_root` 两基准分支后加兜底，containment 不变。
3. **回归面**：stm32 UV4 路径（`..\main.c(N)` 相对 user/）不受影响——既有基准
   已命中；真机复验 2024H mspm0 注错 → fix → gmake 0 错闭环 + 2026C stm32 注错
   回归不破。

## 验收标准

- [x] pytest 全绿 + `mypy src` 干净
- [x] 真机：mspm0 注错 → /api/fix-errors 定位到 main.c（degraded=False）→
      重编译 gmake 0 错（可经 gen-check-fix-loop/01 的 CLI 修复循环跑）
- [x] 回归：stm32 UV4 注错修复不破（2026C 修复循环仍闭环）
- [x] `git status` 只出现预期文件

## Comments

### 2026-08-14 实施 + 真机验收（Status resolved）

**实施（决策记录 2 的"二选一"→ 代决双保险，文件边界内 fix_errors.py 只动三处）：**

1. `_report_benchmarks` 增补构建工作目录基准：`output_dir.rglob("subdir_rules.mk")`
   的父目录（mspm0 产物 Debug/ 根构建规则 + 逐模块目录）加入 benchmarks（去重保序，
   工程文件基准之后）——`(Debug / "../main.c").resolve()` = 工程根/main.c 直接命中
   当前形态。
2. `_resolve_in_root` 两基准 miss 后走新兜底 `_resolve_dotdot_stripped`：path 带
   `../`（或 `..\\`，仅兜底分支归一为 POSIX）前缀时逐级剥前缀按工程根解析（每剥
   一级试 `(root / stripped).resolve()`），containment（is_relative_to(root)）+
   is_file 判定与两基准一致；剥到无前缀仍不中 → None。覆盖更深层级 / 未知构建
   目录形态。
3. UV4 通路零改动：`..\main.c(N)` 由既有 parse/uvprojx 基准先命中，兜底只在两
   基准全 miss 后才走，反斜杠归一不改变既有行为。模块 docstring / collect 与
   resolve 的 docstring 同步三层解析语义。

**测试（红证先写，tests/test_fix_errors.py +3）：**

- `test_collect_gmake_dotdot_resolves_via_build_dir_benchmark`——tmp 树 Debug/
  subdir_rules.mk（空文件）+ 根 main.c，报错 `../main.c` → 候选 ("main.c",)
  （修复前返回空 → 红证已验）。
- `test_collect_dotdot_prefix_strip_fallback_without_benchmarks`——无任何工程文件 /
  构建目录，`../main.c`、`../code/mod.c` 剥前缀兜底命中（未知形态）。
- `test_collect_gmake_dotdot_escape_still_rejected`——`../outside.c`（工程内不存在）、
  `../../outside.c`、绝对路径照旧降级（剥前缀不得把工程外文件骗进候选）；
  既有 UV4 用例（uvprojx 基准 / 逃逸拒绝 / CCS 相对）不动保持绿。
- 全量 **1349 绿**（1346+3）+ `mypy src` 37 文件干净。

**真机验收（服务 8001 跑本 worktree src，证据日志留档主检出
.scratch/real-run/real_fix_gmake_2024H.log + real_fix_uv4_2026C.log）：**

- **mspm0 2024H 闭环**：复制 gmake 已验证的 out_2024H_mspm0_bak →
  out_2024H_mspm0_fixprobe，用生产 `write_makefile_set` 按新路径重渲染 makefile 集
  （SDK/编译器/SysConfig CLI 路径自原 makefile 提取，零手工改 makefile）；基线
  全量重建 **0 错误 10.9s** → 注错 main.c 首行 → 首编报
  `../main.c:1:10: fatal error: 'nonexistent_probe_fixloop.h' file not found`
  （真机原形态复现）→ `/api/fix-errors` **degraded=False**、parsed `../main.c`、
  **applied main.c:1** → 复编 **gmake 0 错误 5.9s**。修复前同形态三轮全降级 0
  applied，闭环打通。
- **stm32 2026C 回归不破**：复制 out_2026C_stm32（uvprojx 全相对路径，复制即用）；
  基线 UV4 0 错误 → 注错 → 首编 `..\main.c(1): error: #5: cannot open source input
  file "nonexistent_probe_fixloop.h"` → /api/fix-errors **degraded=False**、applied
  main.c:1（uvprojx 基准既有通路命中，非新兜底）→ 复编 **UV4 0 Error(s)**。

**git status** 只出现 fix_errors.py / test_fix_errors.py / 本文件三个预期文件
（真机驱动脚本与产物在 .scratch/real-run/，gitignore 覆盖）。
