# 01 — relay 继电器模块（GPIO 迷你驱动，手册 control--relay-module.md）

**要做什么：** 模块库 `relay` 新增 **stm32 平台条目**（mspm0 条目零改动）：从地阔星页面「代码块」提炼 1 路 5V 继电器驱动为纯驱动切片（GPIO 输出 1 脚），API 与 mspm0 版完全对齐——`relay_init()`（初始断开）+ `relay_set(uint8_t)`（1=吸合/0=断开，页面 `Set_Relay_Switch` 0=吸合/1=断开 → `Set_Relay_Switch(s) ≡ relay_set(1-s)` 对照注释）+ 极性单宏 `RELAY_ON_LEVEL 0u`（默认 0=引脚低=吸合，与页面「低电平吸合」一致；实物高电平吸合改 1 即可）。选中 stm32 生成工程打开即可编译、可调用，不再「需自备」。

**关键事实（已取证）：**
- 页面 = **F4 口径，与 F103 标题自相矛盾（甄别样本）**：`#include "stm32f4xx.h"`、`RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOA,)`、`GPIO_Mode_OUT`+`GPIO_OType_PP`+`GPIO_PuPd_UP`+`GPIO_Speed_100MHz`、`GPIO_WriteBit`（RELAY_OUT 宏）——疑似从 F4 板页面复制未迁移。
- F1 换算表：`RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOx)`→`RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOx)`；`GPIO_Mode_OUT+OType_PP+PuPd+Speed_100MHz`→`GPIO_Mode_Out_PP+GPIO_Speed_50MHz`（F1 无 OType/PuPd 字段）；`GPIO_WriteBit` 同名。
- 页面结构：bsp_relay.c（52 行）/bsp_relay.h（27 行）/main（36 行，`board_init()+uart1_init(115200)+printf("Demo Start")+while(1){Set_Relay_Switch(0);delay_ms(1000);...}`——整体剔除）；页面默认脚 GPIOA/Pin_2。
- mspm0 版 API（对齐目标）：relay.h 见库内（RELAY_ON_LEVEL 0u、relay_init/relay_set）。
- 页面缺陷：无器件级 bug（3 块简单驱动）；F4 移植问题即「F4→F1 换算」本身，notes 记录。

**换算实现**（ml_* 母版 API，零寄存器级字面量）：`gpio_init(RELAY_GPIO, RELAY_PIN, OUT_PP)`（推挽输出）+ `gpio_set(...)`；`delay` 不依赖（本件无延时）。

**引脚与默认脚（stm32「同选概率最低」推理）：**
- pins：`RELAY_OUT`（type `gpio_out`，default **PB4**，required true，macros `[RELAY_GPIO, RELAY_PIN]`）。
- pin_config.h 新宏段：`#define RELAY_GPIO GPIO_B` / `#define RELAY_PIN Pin_4`（注释：默认 PB4 = 叠 `MOTOR_A_ENC_DIR`（PB4 编码器方向输入）——继电器与「带编码器闭环的电机控制」不同框、同选概率最低；PB4 非 PWM/ADC 主用脚，推挽输出无扰；**同选时经引脚绑定消解**；mspm0 侧 relay 默认 PA1 先例同理）。
- 设计依据：刻意不叠声光/执行件（LED PC13-15、BUZZER PA15、电机 PWM/方向、DIP/GRAY 组）——继电器+蜂鸣报警/电灯控制为常见组合。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/relay/code/relay_stm32.c/.h`（UTF-8；.h include `<stdint.h>` 不动 mspm0 头；.c include 本模块 .h + `pin_config.h` + `headfile.h`；页面原式注释保留（`Set_Relay_Switch(s) ≡ relay_set(1-s)`、F4 页面甄别记录）；零引脚字面量）
- [x] `manifest.json` platforms 增 stm32：files `[code/relay_stm32.c, code/relay_stm32.h]`、verified false（矩阵过转 true）、hardware_bound false、pins 如上、kit `1路5V继电器模块 光耦隔离/低电平吸合 智能小车`、source_url `https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/relay-module.html`、notes（手册路径 `sources/materials/lckfb-地阔星移植手册/control--relay-module.md` + 原页 + 网盘链接 + 采购链接 + **F4 页面甄别记录**（整页 F4 口径与 F103 标题矛盾，按 F1 换算表翻译）+ 极性对照 + 默认脚推理 + 与 mspm0 条目分工 + 未上板）
- [x] `library/masters/stm32/pin_config.h` 增 `RELAY_GPIO/RELAY_PIN` 宏段（注释如上）
- [x] 测试 `tests/test_module_relay.py`：manifest 形状（stm32 条目/files 存在/pins 元组/kit+source_url=wiki 原页/notes 子串「F4」）+ 母版宏存在断言（`#define RELAY_GPIO\s+GPIO_B`、`#define RELAY_PIN\s+Pin_4`）+ **stm32 单选生成全流程**（resolve_selection+generate → modules/relay/code/relay_stm32.c 落盘 + .uvprojx modules 组含 relay_stm32.c + pin_config.h 在工程根）+ 守卫（无 `printf`/`main`/`GPIO_Init`/`RCC_`/`stm32f4xx`/`stm32f10x`；RELAY_ON_LEVEL 0u；`relay_set(1-s)` 对照注释存在）
- [x] `tests/test_pins.py` `STM32_MACRO_VALUES` 补 RELAY_GPIO/RELAY_PIN（若钉值表需要）；`tests/test_default_layout.py` 白名单登记 relay×motor（PB4 重叠，注释理由）
- [x] 编译矩阵：`UV4.exe -j0 -r -b`（C:/Keil5，照 .scratch/ir-beam-module/verify_compile.py 配方改 slug；MAIN_C 调 relay_init+relay_set(1)+relay_set(0) 并 (void) 化）→ 0 error/0 module warning → verified=true + notes 回写
- [x] wordlist.json 补录（执行机构分类 lib_modules 挂 relay——沿用 mspm0 批次口径，不重复挂）→ 实测词表预算链（本件 slug 已挂接，零改动）
- [x] 中文提交（`.githooks/commit-msg`；**新增 .ps1 必须 UTF-8 with BOM**——本件无）→ 状态 resolved → 结论回填（提交号+矩阵 PASS+甄别要点）

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`；编译日志 `.scratch/wiki-stm32-batch1/matrix/relay/build.log`。
- 甄别要点回填：页面整页 F4 口径（stm32f4xx.h + RCC_AHB1PeriphClockCmd + GPIO_Mode_OUT/OType_PP/PuPd_UP/Speed_100MHz）与 F103 标题自相矛盾——按 F1 换算表翻译（AHB1→APB2、OType/PuPd 删、100MHz→50MHz、GPIO_WriteBit 同名）；模块代码直接走母版 ml_gpio（gpio_init 内部使能 APB2 时钟），零标准库调用，换算式在代码注释 + manifest notes 双重记录。
- 极性对照：页面 Set_Relay_Switch(s) 0=吸合/1=断开 ≡ relay_set(1-s)；RELAY_ON_LEVEL 0u（低电平吸合=页面模块），初始断开。
- 测试：test_module_relay 7 passed（双平台形状 + 宏存在 + stm32/mspm0 单选生成 + 守卫）；test_pins/test_default_layout 全绿（27 passed 组合跑）。

**验收标准：** 全部 checkbox 完成；pytest 相关测试绿；矩阵 exit 0；工单结论含提交号。
