# 03 — ml_led.h 双 LED 定义并存修复（现状雷，grilling 顺带立项）

**What to build:** 母版 ml_led.h 写死 `LED_GPIO GPIO_A` / `LED_RED_Pin Pin_11` / `LED_GREEN_Pin Pin_12`（PA11/PA12 = 蓝药丸 USB DM/DP），与 pin_config.h 的 LED_PORT/LED_RED/YELLOW/GREEN_PIN（PC13-15 板载 LED）**两套定义并存**——生成骨架调 `LED_RED_ON()` 点的是 USB 脚，编译全绿灯不亮（硬编码扫描实证）。改为 pin_config.h 派生 + 低电平点亮翻转。

**Blocked by:** 无（与 01 并行，文件不重叠）

**Status:** 待实施

## 需求

1. **ml_led.h 派生自 pin_config.h**：`#include "pin_config.h"` + `#define LED_GPIO LED_PORT`、`#define LED_RED_Pin LED_RED_PIN`、`#define LED_GREEN_Pin LED_GREEN_PIN`；ON/OFF 电平按板载低电平点亮翻转（`LED_RED_ON()` = set 0 / `LED_RED_OFF()` = set 1，LED_GREEN 同）；补 `LED_YELLOW_Pin LED_YELLOW_PIN` 宏族（实施时 grep 消费方先例——骨架/模块有无 `LED_YELLOW_*` 调用，有则必补 ON/OFF 宏）。ml_led.c 无需改（经宏消费）。
2. **消费方核对**：grep 全库 `LED_RED_ON/LED_GREEN_ON/LED_GPIO/LED_RED_Pin`——确认除 ml_led.c 与生成骨架（LLM 产出，不可控）外无模块代码依赖旧电平语义；debug_uart.c 的 LED 用法走 pin_config.h 宏直用，不受影响（实施时确认）。
3. **测试**：红证先行——断言 ml_led.h 含 `GPIO_A` 硬编码（红）→ 修复后转绿 + 断言派生关系（LED_GPIO 定义值 == LED_PORT 文本）与电平翻转；若 test_master_embedded 或其它母版守卫测试钉了 ml_led 内容需同步。
4. **真机**：2026C `--reuse-recommend --add motor`（默认全绑定，不动 bindings）→ UV4 0 错 0 警回归；产物 ml_led.h 含派生宏断言。

## 文件边界

- `library/masters/stm32/ml_libs/ml_led.h`（主改；ml_led.c 如需注释同步）
- 测试文件自定（建议 tests/test_pin_unlock_led.py 新文件 + 既有守卫测试按需同步）
- 零 src/ 改动、零 pin_config.h 改动（宏已存在）；铁律：独立 worktree（从最新 main 建）

## 验收

- [ ] pytest 全绿 + mypy src 干净
- [ ] 红证已验（GPIO_A 硬编码断言红 → 绿）+ 派生/翻转断言
- [ ] 真机：2026C 全默认 UV4 0 错 0 警；产物 ml_led.h 派生宏核对
- [ ] 独立 worktree + 提交 + 推送（PR）

## 实施提示词（复制到新会话）

```
实施 ml_led 双 LED 修复工单 .scratch/pin-unlock-stm32/issues/03-ml-led-dual-def.md：
1. 读工单 + spec 关键事实节 + 最新 main 的 library/masters/stm32/ml_libs/ml_led.h
2. ml_led.h 改为 include "pin_config.h" 派生（LED_GPIO→LED_PORT、LED_RED_Pin→LED_RED_PIN、
   LED_GREEN_Pin→LED_GREEN_PIN）+ 低电平点亮翻转 ON/OFF + 补 LED_YELLOW 宏族（grep 消费方定）
3. grep 核对消费方：除 ml_led.c 与生成骨架外无模块依赖旧电平语义；debug_uart.c 直用
   pin_config.h 宏不受影响
4. 红证先行（ml_led.h 含 GPIO_A 硬编码断言红）→ 修复转绿 + 派生/翻转断言；
   母版守卫测试按需同步
5. 真机：2026C --reuse-recommend --add motor（全默认）UV4 0 错 0 警 + 产物断言
6. 提交 + 推送开 PR
注意：独立 worktree（从最新 main 建）；文件边界见工单；只改仓库 library/masters/stm32/
（~/.contest_generator/masters/stm32 旧部署副本勿碰）；与 01/04 并行（文件不重叠）
```
