# 02 — 编译/烧录步骤 + 验证顺序清单

**What to build:** README 增加到五章全量：新增「快速上手：编译 + 烧录」（平台静态步骤文本）与「验证顺序清单」（依赖拓扑序 + bring-up 模块前置的 checkbox 清单）。本工单不改变工单 01 的三章产出，只在其上追加两章。

**Blocked by:** 01 — README 渲染器核心 + 生成落盘

**Status:** resolved

2026-08-17：readme.py 增两章 + 纯函数，测试 8 例全过（全量 1795 绿 + mypy 47 文件干净）。

- [x] 快速上手章：平台静态步骤文本（mspm0 = CCS 打开工程/构建/下载；stm32 = Keil5 打开 uvprojx/编译/ST-Link 下载），渲染器内预写固定话术，不做逐模块拼装；生成不依赖 ccs_tools 探测结果（静态文本，与是否写 makefile 无关）。
- [x] 验证顺序清单章：以 manifest 集顺序为基底做**稳定**分区排序——bring-up 模块（delay / debug_uart / led / led_beep）前置并保持相互间依赖序（如 delay 在 led_beep 前），其余模块保持原序；渲染为 Markdown checkbox（`- [ ] <slug> — <description>`）；附固定引导语「按顺序逐个验证，前一个过了再接下一个」。
- [x] 排序规则抽成渲染器内纯函数（输入 manifest 集 → 输出排序后的清单），可直接单测：依赖序保持、bring-up 前置、无 bring-up 模块时原序不变、空集不崩。
- [x] 测试（走 `generate_project()` 流程级 seam + 纯函数直测）：生成一例断言 README 含两新章标题；带 led/delay/debug_uart 的选择断言它们排在非 bring-up 模块前且 delay 在 led_beep 前（若同选）；纯函数边界用例覆盖。
- [x] 全量测试绿 + mypy 干净（src 全部文件）。
