# 01 — gmake 报错路径 `../main.c` 无法定位（mspm0 修复循环端到端闭环被阻）

**Type:** task

**Status:** claimed

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

- [ ] pytest 全绿 + `mypy src` 干净
- [ ] 真机：mspm0 注错 → /api/fix-errors 定位到 main.c（degraded=False）→
      重编译 gmake 0 错（可经 gen-check-fix-loop/01 的 CLI 修复循环跑）
- [ ] 回归：stm32 UV4 注错修复不破（2026C 修复循环仍闭环）
- [ ] `git status` 只出现预期文件

## Comments
