# 红外对射传感器模块（ir_beam）——规格

## 问题陈述

模块库（`library/modules`）目前没有"红外对射传感器"（三线制 VCC/GND/OUT 的遮挡检测）模块。用户在做需要"检测门内/门洞是否有物体遮挡"的赛题时，只能把这类传感器当"需自备"处理：选模块时 AI 不知道库里有现成驱动，引脚分配也要靠手动接线。用户希望库里有这个简单模块：三脚（正/负/输出），只分配输出引脚，接口约定"遮挡 → 0/1"。

## 方案

在模块库新增 `ir_beam` 模块（双平台）：

- `ir_beam_init()`：初始化输入（stm32 内部上拉输入；mspm0 由 SysConfig 输入实例就绪）。
- `ir_beam_read()`：返回 `1` = 遮挡（对射光束被挡住），`0` = 无遮挡。极性以 2021F 旧工程药位检测为据（`sources/contest/2021F/21F/user/main.c`：放药 = PB5 高电平，取药 = 低电平；`gpio_init(GPIO_B, Pin_5, IU)` 内部上拉）——有遮挡 = 高电平 = 1。代码内提供 `IR_BEAM_BLOCKED_LEVEL` 宏（当前 1），实际模块极性相反时改一处即可。
- 三线制接线：VCC → 3V3/5V（板上电源脚，不占 GPIO）、GND → GND、OUT → 分配的唯一输出引脚。
- 默认输出引脚：**mspm0 与 stm32 均为 PA8**（用户确认）。两板排针在母版默认布局下已无空闲脚，PA8 是共享默认：mspm0 仅与 DIGIT_UART（K230 视觉）默认重叠、stm32 仅与 pid GRAY_D5（巡线灰度）默认重叠——同选时经引脚绑定消解；两平台同脚便于记忆。

## 用户故事

1. 作为做题用户，我在模块列表里能看到"红外对射传感器"，无需当作"需自备"。
2. 作为做题用户，我选中该模块后工具自动分配 OUT 引脚（默认 PA8），生成工程里直接可编译、可调用。
3. 作为做题用户，我在主循环调用 `ir_beam_read()` 得到 0/1，0/1 语义（有遮挡=1）与 2021F 药位检测一致，不需要再读传感器资料。
4. 作为做题用户，当我的实际传感器极性相反或引脚不同时，改一个宏（`IR_BEAM_BLOCKED_LEVEL`）或经引脚绑定换脚即可。

## 实现决策

- 模块名 `ir_beam`（红外对射），目录 `library/modules/ir_beam/`。
- 文件命名沿用最新模块（zigbee_link/uwb_uart）惯例：stm32 = `code/ir_beam.c` + `code/ir_beam.h`；mspm0 = `code/ir_beam_mspm0.c` + `code/ir_beam_mspm0.h`。
- manifest 平台条目：
  - stm32：`pins = [{id: IR_BEAM_OUT, type: gpio_in, default: PA8, required: true, macros: [IR_BEAM_GPIO, IR_BEAM_PIN]}]`，宏写入母版 `pin_config.h`（接线单源，ADR 0010）。
  - mspm0：`pins = [{id: IR_BEAM_OUT, type: gpio_in, default: PA8, required: true}]`；母版 `mspm0.syscfg` 新增 GPIO 输入实例 `IR_BEAM`（引脚名 `OUT`，PA8），生成宏 `IR_BEAM_PORT` + `IR_BEAM_OUT_PIN`（KEY 单引脚实例先例：`KEY_PORT` + `KEY_START_PIN`）。
- `syscfg_instances.py` 登记 `IR_BEAM → ("ir_beam",)`（裁剪/槽位身份/共享判据单源表）。
- 无 multi_instance（单传感器）；无 exclusive_group；无依赖。
- 简介与代码注释遵守判据④（无题绑定：不出现 2021F/2024H/2026C/2026H/钥匙/锁）。
- 不新增 AI 词表/参考库条目（scope 外，另行考虑）。

## 测试决策

- 数据层不变量（防回退，先写后红转绿）：
  - `tests/test_pins.py::MSPM0_DEFAULT_MAP` 增 `("ir_beam","IR_BEAM_OUT") → ("IR_BEAM","OUT")`（默认值 = 母版 syscfg $assign）；
  - `tests/test_default_layout.py::WHITELIST` 增 `PA8 = {pid.GRAY_D5, ir_beam.IR_BEAM_OUT}`（stm32 默认共享白名单）；
  - `tests/test_syscfg_prune.py` 增 IR_BEAM 实例保留/裁剪断言。
- 端到端生成（真实库 + 真实母版，无 LLM）：新增 `tests/test_module_ir_beam.py`——
  - stm32 单选生成：模块文件落盘、uvprojx 注册 ir_beam.c、main.c 调 ir_beam_init/ir_beam_read 过静态门禁；
  - mspm0 单选生成：syscfg 含 IR_BEAM 实例（module 输入）、模块文件落盘。
- 编译级验收：mspm0 用 gmake（C:/ti/ccs2050 自带）真编译 0 error；stm32 视 Keil UV4 可用性，可用则 UV4 编译，不可用则 verified=false + notes 注明无工具链环境（zigbee_link 先例）。

## 范围外

- 不新增 wordlist.json 词条/买件方案（如"红外对射"类别挂 lib_modules）——后续单独工单。
- 不做多实例（多路对射）支持。
- 不动 2026C 等赛题 manifest 的 hint_module_groups 推荐配置。
- 不做防抖（消抖归骨架/用户轮询循环，与 key 模块同策略）。

## 补充说明

- 2021F 旧工程证据（用户提供）：`sources/contest/2021F/21F/user/main.c` 278 行注释"PB5 消抖（连续3次 HIGH = 300ms 确认（药物放上→高电平））"，CLAUDE.md 硬件架构"PB5 药物检测 → 放药启动(HIGH)/取药返程(LOW)"；初始化 `gpio_init(GPIO_B, Pin_5, IU)`。
- 验证方式说明：mspm0 编译矩阵脚本复用 `.scratch/module-polish/compile_matrix.py` 的既定配方（generate → collect_build_log → compile_passed）。
