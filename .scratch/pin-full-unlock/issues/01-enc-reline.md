# 01 — stm32 enc 换线（类型级 + EXTI 线冲突门禁 + motor 条件 handler）

**What to build:** 编码器 EXTI 中断脚解锁到任意 exti 能力脚——pin_bindings 对 enc 类型级化（线号随绑定推导喂 _LINE 宏，渲染器尾形已有零改动）；motor_stm32.c 的写死 handler 名（EXTI2/EXTI4）重构为 7 个按 _LINE 宏条件编译的 handler；ml_exti 枚举扩线 0-15；新门禁拦异口同线。

**Blocked by:** 无（链首；前置 01-04 解锁轮已合 main）

**Status:** 待实施

## 需求

1. **pin_bindings.py enc 类型级**：enc 角色入类型级分支（绑定脚须有 `enc` token；线号 = 脚号 mod 16，与 token 数字一致；实例/线号推导喂渲染器既有 `_EXTI`/`_LINE` 尾形）。渲染器零改动。
2. **motor_stm32.c 条件 handler 重构**：删 EXTI2_IRQHandler(:50)/EXTI4_IRQHandler(:62) 写死定义；改 7 个条件定义——`#if MOTOR_A_ENC_LINE == 2 || MOTOR_B_ENC_LINE == 2` → `void EXTI2_IRQHandler(void)`（内部分派 A/B：查 EXTI->PR 对应线位 + 原计数逻辑 + 清 PR），线 0/1/3/4 同款各自 handler；线 5-9 一个 `EXTI9_5_IRQHandler`（#if 任一编码器线号 ∈ [5,9]，内部按线位分派 A/B）；线 10-15 一个 `EXTI15_10_IRQHandler` 同款。默认路径（PA2 线 2 / PA4 线 4）行为与现逐字节等价。注释同步（46-49 行"handler 名绑定引脚线号"旧注释改）。
3. **ml_exti.c 枚举扩 48 项**：EXTI_PA0-15 / EXTI_PB0-15 / EXTI_PC0-15（现 24 项 PA0-7/PB0-7/PC0-7，:13-36）；NVIC 通道公式改（:68-71）：线 ≤4 → 各自 EXTI0-4_IRQn、5-9 → EXTI9_5_IRQn、10-15 → EXTI15_10_IRQn。
4. **板定义数据扩**：boards/stm32-min-system.json——PA8-15 / PB8-15 / PC13-15 加 `exti:PAx`/`exti:PBx`/`exti:PCx` token + `enc:8..15` 线号 token（既有 token 逐项不动）。
5. **门禁 `_check_exti_line_conflicts` 入 GENERATION_GATES**：绑定 enc/exti 角色两两，线号（脚号 mod 16）相同 ∧ 引脚不同 → 400 中文（errors.py 登记，如"编码器 MOTOR_A_ENC(PA2)、MOTOR_B_ENC(PB2) 同 EXTI 线 2，异口同线互斥"）。同脚共享不查（提示语义）。
6. **index.html pinCanHost 镜像**：enc 类型级——有 `enc` token 的脚全可选。
7. **测试**：红证先行（类型级分支缺位时绑 PA5 被拦 / 异口同线 400 / 枚举缺线 8-15 时配不动作）；绿证——绑 PA5/PA6 → pin_config.h `MOTOR_A_ENC_EXTI EXTI_PA5` + `MOTOR_A_ENC_LINE 5` 等 + 默认不配输出 == 母版逐字节 + 条件 handler 各线号展开编译；tests/test_pins.py enc 类型级豁免 + EXCEPTION_REGISTRY 如涉同步；新增 tests/test_pin_unlock_enc.py。
8. **真机**：2026C `--reuse-recommend --bindings '{"motor.MOTOR_A_ENC":"PA5","motor.MOTOR_B_ENC":"PA6"}'` → UV4 -r 0 错 0 警 + 产物 pin_config.h 仅 ENC 相关行变 + handler 符号（EXTI9_5_IRQHandler 存在、EXTI2/EXTI4 不存在）；不配回归 == 母版逐字节；HTTP 层 PA2+PB2 同线 400 零产物。运行级（编码器真转）用户上板自验。

## 文件边界

- `src/contest_generator/pin_bindings.py`、`src/contest_generator/generator.py`（门禁表）、`src/contest_generator/errors.py`、`src/contest_generator/boards/stm32-min-system.json`
- `library/modules/motor/code/motor_stm32.c`、`library/masters/stm32/ml_libs/ml_exti.c`
- `index.html`（pinCanHost）
- `tests/test_pin_bindings.py`、`tests/test_pins.py`（豁免同步）、`tests/test_pin_unlock_enc.py`（新）
- 零 pinwriter.py / ml_uart / isr.c 改动；铁律：独立 worktree（从最新 main 建）

## 验收

- [ ] pytest 全绿 + mypy src 干净
- [ ] 红证已验（类型级缺位 / 同线 400 / 枚举缺项）+ 绿证（宏值 + 默认逐字节 + 条件 handler 展开）
- [ ] 真机：绑 PA5/PA6 UV4 0 错 0 警 + handler 符号断言 + 不配回归逐字节 + HTTP 400 零产物
- [ ] 独立 worktree + 提交 + 推送开 PR

## 实施提示词（复制到新会话）

```
实施 enc 换线工单 .scratch/pin-full-unlock/issues/01-enc-reline.md：
1. 读工单 + .scratch/pin-full-unlock/spec.md（关键事实节必读）+ ADR 0012 + 最新 main
2. pin_bindings.py：enc 入类型级分支（有 enc token 即合法；线号=脚号 mod 16 推导喂 _LINE/_EXTI 尾形）；渲染器零改动
3. motor_stm32.c：删两个写死 handler，改 7 条件 handler（#if MOTOR_A/B_ENC_LINE 值域，共线组内 PR 位分派）；默认路径行为等价
4. ml_exti.c：枚举扩 48 项（PA/PB/PC × 线 0-15）+ NVIC 通道公式（5-9 / 10-15 共线组）
5. 板定义：PA8-15/PB8-15/PC13-15 加 exti + enc 线号 token
6. generator.py：_check_exti_line_conflicts 入 GENERATION_GATES（异口同线 400 中文，errors.py 登记）
7. index.html pinCanHost：enc 类型级镜像
8. 红证先行（缺类型级被拦/同线 400/枚举缺项）+ 绿证（绑 PA5/PA6 宏值断言 + 默认逐字节 + 条件 handler 编译）+ test_pins 豁免同步
9. 真机：2026C --reuse-recommend --bindings '{"motor.MOTOR_A_ENC":"PA5","motor.MOTOR_B_ENC":"PA6"}'
   → UV4 -r 0 错 0 警 + EXTI9_5_IRQHandler 符号断言 + 不配回归 + HTTP 400（PA2+PB2 同线）
10. 提交 + 推送开 PR
注意：独立 worktree；文件边界见工单；零 pinwriter/ml_uart/isr.c 改动
```
