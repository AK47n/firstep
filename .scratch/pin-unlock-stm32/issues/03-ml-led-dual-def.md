# 03 — ml_led.h 双 LED 定义并存修复（现状雷，grilling 顺带立项）

**What to build:** 母版 ml_led.h 写死 `LED_GPIO GPIO_A` / `LED_RED_Pin Pin_11` / `LED_GREEN_Pin Pin_12`（PA11/PA12 = 蓝药丸 USB DM/DP），与 pin_config.h 的 LED_PORT/LED_RED/YELLOW/GREEN_PIN（PC13-15 板载 LED）**两套定义并存**——生成骨架调 `LED_RED_ON()` 点的是 USB 脚，编译全绿灯不亮（硬编码扫描实证）。改为 pin_config.h 派生 + 低电平点亮翻转。

**Blocked by:** 无（与 01 并行，文件不重叠）

**Status:** resolved（2026-08-15 实施 + 真机验收闭环，PR 待合 main）

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

- [x] pytest 全绿 + mypy src 干净（1467 绿 = 1464 基线 + 3 新；mypy src 41 文件）
- [x] 红证已验（GPIO_A 硬编码断言红 → 绿）+ 派生/翻转断言
- [x] 真机：2026C 全默认 UV4 0 错 0 警；产物 ml_led.h 派生宏核对
- [x] 独立 worktree + 提交 + 推送（PR）

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

## Comments

- 2026-08-15 立项（stm32 引脚解锁 grilling 定稿，189d9df）。
- 2026-08-15 实施完成（分支 pin-unlock-03，独立 worktree 从 origin/main d491891 建）：**ml_led.h 改派生**——`#include "pin_config.h"` + `LED_GPIO LED_PORT` / `LED_RED_Pin LED_RED_PIN` / `LED_YELLOW_Pin LED_YELLOW_PIN` / `LED_GREEN_Pin LED_GREEN_PIN` 四别名；**ON/OFF 低电平点亮翻转**——ON()=set 0 / OFF()=set 1（红绿同），注释同步"板载 LED 灌电流：0=点亮，1=熄灭"；ml_led.c 零改动（经宏消费，OUT_PP 推挽灌电流可行，init 熄灭语义不变）。**LED_YELLOW 宏族裁决**：全库 grep（library 模块+母版 / sources / tests，排除 references 与 scratch）零 `LED_YELLOW_ON/OFF` 消费方——debug_uart.c 直用 pin_config.h 宏（`gpio_set(LED_PORT, LED_YELLOW_PIN, x)`）不经 ml_led 层 → 按工单"有则必补、无则不补"只补 `LED_YELLOW_Pin` 别名，ON/OFF 宏不补（测试 docstring 留痕）。**消费方核对**：`LED_RED_ON/LED_GREEN_ON/LED_GPIO/LED_RED_Pin` 除 ml_led.c 与生成骨架（LLM 产出）外无模块代码消费；references 21F pid.c 的 LED_*_ON 调用属参考例程自有头文件非本母版；sources/contest 历史参考工程不动（文件边界）。**红证先行实录**：新测试 test_pin_unlock_led.py 3 断言对旧 ml_led.h 全红（GPIO_A 硬编码在 / 无 pin_config include 与派生 / ON=set 1）→ 修复后 3/3 绿；母版守卫 test_master_embedded.py 无 ml_led 断言无需同步（其 GPIO_A 钉子都在 pin_config.h / motor_stm32.c）。**真机**（worktree 服务 8000 + 缓存复用 + config masters_dir 临时指 worktree 已复原）：2026C `--reuse-recommend --add motor` → 缓存命中（clarifications 指纹警告非阻断，同 01 先例）+ 8 模块（缓存 7 + motor）→ 骨架 2839 字符 0 拦截 → 生成 49 文件门禁全过 → **UV4 exit=0 0 错 0 警**；产物 out_2026C_stm32/ml_libs/ml_led.h 与母版逐字节一致（diff 空）；骨架 main.c `led_init(); /* 板载 LED 初始化（低电平点亮） */`——LLM 骨架段已读到新头注释（骨架读母版头的实证）。1467 全绿 32.9s + mypy src 41 文件干净。
