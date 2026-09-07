# 03 — joystick 双轴摇杆（ADC ×2 + SW，手册 control--two-axis-keystroke-rocker-module.md）

**要做什么：** 模块库 `joystick` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼双轴摇杆驱动为纯驱动切片（**双 ADC 通道 + 1 GPIO 开关**——页面 ADC 序列收敛 ml_adc），API 与 mspm0 版**同名同型完全对齐**（joystick.h 核对）：`joystick_init()` + `joystick_read_x()/read_y()`（uint16_t 12bit 原始值 0-4095）+ `joystick_read_x_percent()/read_y_percent()`（**uint16_t 整数 0-100%**——joystick.h L29-30，非 float；`(adc/4095)×100`，4 次快平均（`JOYSTICK_ADC_SAMPLES 4u`——mspm0 口径）+ 忙等超时）+ `joystick_read_sw()`（uint8_t，1=按下/0=松开——**SW 低有效**（`JOYSTICK_SW_PRESSED_LEVEL 0` 宏沿 mspm0 同名，joystick.h L24））。

**关键事实（%TEMP%\batch7-facts.md）：** F1；页面默认 VRX=PA1/VRY=PA2/SW=PA3（**全被既有角色占用不照抄**）；中心≈50%；**L149 注释函数名「Get_MQ2_Percentage_value」MQ2 串台**（notes）；页面每次 30×2ms=60ms + 2 次 ADC 校准无超时 → 4 次快平均+忙等超时（mspm0 批 1 修正沿用）。

**引脚与默认脚（同选概率最低推理）：**
- pins：`JOYSTICK_X`（adc，default **PA1**，macros `[JOYSTICK_X_CH]`）/ `JOYSTICK_Y`（adc，default **PA0**，macros `[JOYSTICK_Y_CH]`）/ `JOYSTICK_SW`（gpio_in，default **PA10**，macros `[JOYSTICK_SW_GPIO, JOYSTICK_SW_PIN]`）。
- pin_config.h 宏段：`#define JOYSTICK_X_CH ADC_Channel_1` / `#define JOYSTICK_Y_CH ADC_Channel_0`（注释：X/Y 默认 PA1/PA0 = 与 adc 模块 ADC_CH1/CH0 **ADC 共享组**（mspm0 MEM1/2 与 adc 共享同构）；`JOYSTICK_SW_GPIO GPIO_A`/`_PIN Pin_10`（注释：SW 默认 PA10 = 叠 DIGIT/COORD/UWB UART RX——摇杆与视觉/数传链路不同框（mspm0 SW=PA9 同款推理）；同选经绑定消解）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/joystick/code/joystick_stm32.c/.h`（独立 stm32 头；**API 全套与 mspm0 joystick.h L26-31 同名同型：`joystick_init()/joystick_read_x()/joystick_read_y()`（uint16_t 12bit 原始值）/`joystick_read_x_percent()/read_y_percent()`（uint16_t 整数 0-100%）/`joystick_read_sw()`（uint8_t）+ `JOYSTICK_SW_PRESSED_LEVEL 0` 宏沿名**；.c 用 adc_get ×2 快平均 + gpio_get SW；零引脚字面量）
- [x] manifest.json platforms 增 stm32：files `[code/joystick_stm32.c, code/joystick_stm32.h]`、dependencies ["adc","delay"]（照 mspm0 现状）、verified true、hardware_bound false、pins 3 行、kit/source_url（wiki 原页 `.../control/two-axis-keystroke-rocker-module.html`）、notes（手册路径+原页+网盘+MQ2 串台+60ms→4 次快平均+忙等超时+SW 低有效+共享组推理+未上板）
- [x] pin_config.h 增 4 宏（X_CH/Y_CH/SW_GPIO/SW_PIN）
- [x] 测试 `tests/test_module_joystick.py`：形状（3 pins）+宏存在+单选生成+mspm0 零改动+守卫（**API 全套 6 函数断言：`read_x()/read_y()` 返回 `uint16_t`（raw 0-4095）+ `read_x_percent()/read_y_percent()` 返回 `uint16_t`（同型——非 float）+ `read_sw()` uint8_t**、`JOYSTICK_ADC_SAMPLES 4u`、`JOYSTICK_SW_PRESSED_LEVEL 0`、无 MQ2 字面量（剥离后——注释记录除外）、SW 低有效注释、无 printf/GPIO_Init/RCC_——实现换算口径照 mspm0 joystick.c 逐行）
- [x] test_pins.py 补 4 宏；test_default_layout.py 白名单：PA1/PA0 组 +1×2（adc 共享组）、PA10 +1
- [x] UV4 矩阵（init+read_x+read_y+read_x_percent+read_y_percent+read_sw——**六函数全调**，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-07）：全部完成。stm32 条目 = 双 ADC 通道 + 1 GPIO（页面 ADC 序列收敛 ml_adc + SW ml_gpio 上拉输入）；默认脚 = X=ADC_Channel_1（PA1）/Y=ADC_Channel_0（PA0）——与 adc 模块 ADC_CH1/CH0 **ADC 共享组**（mspm0 MEM1/2 与 adc 模块共享实例同构；PA0/PA1 同时叠 motor PWM 主脚为母版现状性质）+ SW=PA10（gpio_in——叠 DIGIT/COORD/UWB UART RX：摇杆与视觉/数传链路不同框、同选概率最低——mspm0 SW=PA9 同款推理；页面默认 VRX=PA1/VRY=PA2/SW=PA3 全占不照抄；白名单 PA1/PA0/PA10 登记）；JOYSTICK_X_CH/Y_CH/SW_GPIO/SW_PIN 4 宏入 pin_config.h；**API 全套 6 函数与 mspm0 joystick.h L26-31 同名同型**（read_x/read_y = uint16_t 12bit raw、percent = uint16_t 整数 = raw×100/4095——非 float、read_sw = uint8_t；JOYSTICK_SW_PRESSED_LEVEL 0 宏沿名；SW 低有效语义归一 1=按下——页面 Get_SW_state 0=按下原样）；**页面缺陷/修正**：① 30×2ms≈60ms/轴 + 每次读轴 2 次 ADC 校准无超时 → 4 次快平均（JOYSTICK_ADC_SAMPLES 4u——mspm0 批 1 口径）+ 校准移 init（ml_adc 等价）；② **忙等超时口径差异**：mspm0 自持 DL_ADC12 + JOYSTICK_ADC_TIMEOUT 50 超时、stm32 走母版 ml_adc 的 adc_get（内部 while 等 EOC——无显式超时参数，母版实现——notes 记录）；③ L149「Get_MQ2_Percentage_value」MQ2 串台——notes 记录不落码（.c 注释含记录）；④ 页面无中心死区/零偏置处理（中心≈50%——±死区归调用方，notes）；verified=true（UV4 0 error/0 module warning——**初版 #188-D 枚举混用警告（helper 参数 uint8_t vs ADCINx_enum）已修复**，2026-09-07）+ kit/source_url + notes；wordlist 零补录（joystick 已在词表遥控接收分类）；mspm0 零改动；description 双平台化；**顶层 dependencies=() 保持 mspm0 现状**（工单文本「dependencies [adc,delay] 照 mspm0 现状」与 mspm0 实际 [] 不符——照现状 []，stm32 侧 ml_adc/ml_gpio 内嵌母版无需显式依赖——notes 说明）；test_pins 宏表 +4、test_default_layout 白名单 PA1/PA0 +1×2 + PA10 +1。**

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
