# 04 — 器件级参考条目入库、死映射复活

**要做什么：** 把 `beep` / `key` / `led` / `led_beep` / `oled` / `servo` 这 6 个「死映射」救活——它们的词项在参考库 148 条标题里 0 命中，选中这些模块时骨架关联不到任何例程。做法是把 Markdown 资料库里已有的器件级移植手册（`sources/materials/lckfb-地猛星移植手册/`，含 0.96 寸 IIC/SPI 单色屏、0.96/1.3 寸彩屏、8 位 LED 数码管、WS2812 幻彩灯带、SG90 舵机、按键摇杆等）做成参考条目入库，使这些词项在标题里命中。做完后 `tests/test_skeleton_mapping_coverage.py` 的「每个有映射的模块至少一个词项命中」那条 xfail 转 XPASS。

**被谁阻塞：** 03 — 骨架映射判据与显式豁免（契约 + 机制）。

**状态：** resolved

- [x] 盘点：6 个死映射模块 → 手册/素材对应关系（见下方「盘点」表）
- [x] 参考条目入库（走 `add_reference`，素材 = 手册 markdown 原文 / beep 模块代码切片，锚定 none，平台 any；脚本 `.scratch/preselect-visibility/add_device_manuals.py`，幂等可重跑）——库内新增 5 条条目，库自动提交 5 笔 `lib: add reference …`
- [x] 6 个模块的词项在新条目标题里命中：`beep`/`key`/`led`/`servo`/`oled` 直接命中（`led_beep` 经 `led` 命中）
- [x] `tests/test_skeleton_mapping_coverage.py` 该条 xfail 摘掉转常规守卫（`6 passed, 1 xfailed`——余下 1 条 = 全库覆盖，归工单 05）
- [x] 新增条目过全库不变量与既有预算断言（`test_reference_library.py` / `test_llm.py` / `test_webapp.py` 全绿）
- [x] `python -m pytest -q` 全绿；`probe_term_effect.py` 复测：beep→1、key→1、led→1、led_beep→1/1、oled→1、servo→1（原 0）

## 盘点（手册 → 条目 → 救活模块）

| 救活模块 | 参考条目（新） | 素材 |
|---|---|---|
| `oled` | 0.96 寸 OLED 单色屏器件手册（oled / IIC 与 SPI） | screen--0-96-iic-single-screen.md、screen--0-96-single-spi-screen.md |
| `led` / `led_beep` | WS2812 幻彩灯带与 8 位 LED 数码管器件手册（led） | control--ws2812-color-rgb-led.md、screen--8-bit-led-tube.md |
| `key` | 按键摇杆器件手册（key / button） | control--two-axis-keystroke-rocker-module.md、sensor--grayscale-sensor.md |
| `servo` | SG90 舵机器件手册（servo） | control--sg90-steering-engine.md、control--16-ch-servo-drive-module.md |
| `beep` | 蜂鸣器驱动例程（beep / buzzer） | 库内 beep 模块代码切片（beep.c / beep.h / beep_stm32.c / beep_stm32.h） |

`beep` 无对应 lckfb 手册（手册列表里没有蜂鸣器篇），故条目素材取库内 beep 模块代码切片（类型 = 参考例程）——「选中 beep 时能关联到一份可读的蜂鸣器例程」这一目标达成。

## 答复（2026-09-08）

- 条目标题里显式带英文 slug 词（`oled` / `led` / `key` / `servo` / `beep`），因为骨架关联只认条目标题；中文名同时保留（人读）。
- 条目 `anchor_kind = none`（器件手册不锚定赛题/套件），平台 `any`（stm32 与 mspm0 通用）。
- 库自动提交与软件仓库同仓（ADR 0008），故本工单的库侧改动是 5 笔 `lib:` 提交，测试与脚本在本工单的软件侧提交里。
