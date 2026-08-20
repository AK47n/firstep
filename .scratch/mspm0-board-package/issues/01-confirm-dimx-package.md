# 01 — 收口地猛星实物封装与 PA13/PA14 可用性

**要做什么：** 把地猛星 mspm0 板卡的实物核验结论写回文档和测试：`PA13` / `PA14` 是 2×20P 上的普通可用脚，`PA19` / `PA20` 继续作为 SWD/DEBUG 锁脚；旧的“包型号悬案”不再悬着。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] ADR 0012 不再说 mspm0 包型号悬案未核实，而是记录 2026-08-20 实物核验结论
- [x] mspm0 母版 syscfg 顶部注释不再保留“疑 LQFP-48 / 留待核实”的未闭环表述
- [x] 板定义测试钉住 `PA13` / `PA14` 在 2×20P、`PA19` / `PA20` 不在 2×20P 的事实
- [x] `tests/test_boards.py` 通过

## 实施记录

- 2026-08-20：按用户实物核验收口：主控丝印可见 `42WG4` / `ABDL`，芯片外周为 48 脚，2×20P 排针分布正确，`A13` / `A14` 在板上，未找到 `A19` / `A20`。
- 保持 SysConfig `LQFP-64(PM)` / LP-MSPM0G3507 模型不变；该模型在 SysConfig 中可工作，不以它反推实物脚数，实际可引出范围继续由 `mspm0-dimx` 板定义约束。
- 验证：`python -m pytest tests/test_boards.py tests/test_repo_language.py`，22 passed，1 个既有 StarletteDeprecationWarning。
