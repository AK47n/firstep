# 02 — 覆盖率守卫：真实题库钉住「关键模块可见」

**要做什么：** 模块库继续长大时，「小车类赛题的关键执行/交互模块在提示词里彻底消失」这种退化会被一条可复跑的测试抓住，而不是靠人工审计发现。本轮这条断言以预期失败（xfail）落盘，记录现状缺口；下一批修好预筛后自动转绿并锁住成果。

**被谁阻塞：** 无——可立即开始（与 01 并行）。

**状态：** resolved

- [x] 新增覆盖率测试：用真实题库（`library/topics/*/topic.md`）与真实模块库跑预筛，断言指定题面 × 平台下的一组关键模块出现在预筛结果内（首例：2024H / stm32 的 `motor`、`pid`、`servo`、`led`、`key`）。
- [x] 该断言当前以 `pytest.mark.xfail(strict=True, reason=...)` 标记为预期失败，reason 写清「预筛评分/预算截断导致关键模块落在截断线外，待下一批修复」。
- [x] `strict=True` 生效：若断言将来意外通过（预筛被改好却忘了摘标记），测试变红提醒。
- [x] 测试只断言外部行为（哪些 slug 在预筛结果内），不断言内部得分/排序实现。
- [x] 断言失败信息可读：直接列出「缺哪些模块、可见条数 / 总条数」。
- [x] `pytest` 全绿（含该 xfail 计入预期失败，不出现 xpass 报错）。

## Comments

**新增文件**：`tests/test_preselect_coverage.py`。

**用例集**（真实题面 × 真实模块库，与网页路由同参：`MODULE_SUMMARY_BYTES` + 真实词表）：

| 题面 / 平台 | 现状可见 | 断言必需 |
|---|---|---|
| 2024H / stm32 | 34/86 | motor、pid、servo、led、key |
| 2024H / mspm0 | 34/84 | motor、pid、servo、led、key |
| 2021F / stm32 | 33/86 | motor、pid、xunji、key、oled |
| 2026C / stm32 | 33/86 | led、beep、key、oled |
| 2026A / mspm0 | 41/84 | motor、servo、led、key |
| 2022C / stm32 | 35/86 | motor、oled |

**运行结果**：`python -m pytest tests/test_preselect_coverage.py -q -rX` → `1 passed, 6 xfailed`（6 条覆盖率断言按预期失败，1 条结构不变量通过）。

**结构不变量（现在就绿，与预筛是否修好无关）**：`test_preselect_subset_is_contained_in_full_library` 断言「子集 ⊆ 全量、子集无重复、`truncated` 与条数自洽、`total == len(full)`」——守住工单 01 引入的 `full` 契约，防重构时被破坏。

**下一批的收尾动作**：预筛评分与匹配粒度修好后，这 6 条会自动 XPASS；`strict=True` 会让它们变红提醒摘掉 `xfail` 标记（摘标记即变成常规守卫）。复测工具：`.scratch/library-audit/probe_guard_cases.py`（只读，打印各用例当前可见条数与缺口）。

**为什么用 xfail 而不是降级断言**：本轮范围明确不含预筛评分（spec「范围外」），若把断言降级成「关键模块在平台库内」，它就永远不会红——守卫价值归零。xfail 让缺口在测试报告里持续可见，且修复后自动转绿。

**xfail 的可见性代价（评审整改留痕）**：xfail 形态下 pytest 默认只打印 reason，断言里的「缺哪些模块、可见 N/M」看不见。复看缺口用：

```
python -m pytest tests/test_preselect_coverage.py --runxfail -q
```

`strict=True` 保证修复后（XPASS）立即报错，提醒摘掉标记；摘掉后本组就是常规守卫。

**契约测试与实现细节的边界（评审整改留痕）**：`test_preselect_subset_is_contained_in_full_library` 断言的是 `PreselectResult` 的公开形状（子集 / 总数 / 是否截断 / 平台全量四元契约），属契约测试；不断言得分、排序、内部函数调用。覆盖率用例只断言「哪些 slug 在结果内」。
