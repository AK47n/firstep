# 模块功能化：led/beep 拆分 + 学生视角 API 扩展——功能规格

> 2026-08-15 grilling 定稿（用户逐轮确认："什么叫做0=亮"答疑后其余按推荐）。

## Problem Statement

模块是从旧工程提炼出来的，粒度与 API 受旧工程影响：led_beep 把灯和蜂鸣器捆成一个模块，学生只想要灯时也被拖进蜂鸣器；两平台同名模块 API 不统一；部分模块缺学生视角的高频函数。学生选模块时希望"要什么拿什么、两个平台写法一样"。

## Solution

1. **led / beep 拆分为独立模块（双平台）**：`led`（led_init/led_on/led_off/led_toggle + 通道宏 LED_RED/LED_YELLOW/LED_GREEN，灌电流 0=亮 封装在实现内）；`beep`（beep_init/beep_on/beep_off/beep_toggle/beep_beep）。
2. **led_beep 保留为组合模块**：deps = [led, beep, delay]，只做 led_beep_init/on/off/alarm（声光报警），不重复实现。
3. **stm32 led 实现内嵌母版 ml_led**（先例 oled/delay）：模块 stm32 侧空条目 verified；母版 ml_led 升级为统一 API（led_init(channel)/led_on/led_off/led_toggle + 通道宏）。
4. **mspm0 led 实现随模块**：PA15（LED_BEEP syscfg 组），led manifest 声明引脚角色 `led.LED`；LED_BEEP 实例消费者从 led_beep 改为 led。
5. **beep mspm0 为占位实现**（地猛星排针已满未接蜂鸣器），保留模块保证 API 统一；stm32 用 pin_config.h BUZZER 宏。

## User Stories

1. 作为学生，我只想点灯时选 `led`，不需要蜂鸣器。
2. 作为学生，我只想响蜂鸣器时选 `beep`，不需要灯。
3. 作为学生，我要声光报警时选 `led_beep`，一个调用同时控制灯和蜂鸣器。
4. 作为学生，我两平台写同一套 led/beep API，不用背平台差异。
5. 作为学生，`led_on(LED_RED)` 永远是亮，不用管 0=亮还是 1=亮。

## Implementation Decisions

- 组合模块不直接消费 syscfg LED_BEEP（转 led）；`syscfg_instances.LED_BEEP → ("led",)`。
- stm32 led 不声明引脚（引脚宏由 config 模块/母版 pin_config.h 单源）；mspm0 led 声明 `LED` 引脚 PA15。
- LLM 围栏兜底升级：`clex.strip_all_code_fences` 剥全部围栏行（首尾包裹形态仍由 strip_code_fences 负责，契约不变），skeleton 出稿双保险——真机 mspm0 冒烟曾三重围栏 400。

## Testing Decisions

- 新测试 `tests/test_module_led_beep.py` 真实库不变量：模块双平台/API 统一/组合依赖/内嵌母版/引脚宏。
- 更新 pin 相关测试（led_beep.LED_BEEP_LED → led.LED）。
- 真机回归：stm32/mspm0 冒烟 + 参考路径，slugs 含 led/beep/led_beep，UV4/gmake 0 错。

## Out of Scope

- 后续模块功能化清单（不在本批实现）：
  - motor(stm32) 补 `motor_set_direction / motor_set_duty / motor_encoder_read` 与 mspm0 对偶
  - key 补 stm32 版本
  - uart 发送模块补 stm32 版本
  - ntb_time 补 stm32 版本
  - ball_detect/digit_uart/uwb/zigbee 补 mspm0 版本

## Further Notes

- 真机 mspm0 冒烟曾因 LED_BEEP_LED_PORT 宏不存在编译失败——SysConfig 单端口 GPIO 组只生成 `<INSTANCE>_PORT`（LED_BEEP_PORT），已修正。
