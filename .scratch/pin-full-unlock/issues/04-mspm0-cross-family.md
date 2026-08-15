# 04 — mspm0 跨族迁移（Tier B：数据裁决先行 + motor 双分支 + pin_family.h 渲染）

**What to build:** mspm0 PWM 跨外设族（TIMG↔TIMA）——排针上只挂 TIMA 通道的脚（如 PA28 仅 `pwm:TIMA0_C3`）可绑电机 PWM；模块 motor 代码 #if 双分支（DL_TimerG_* / DL_TimerA_*），族标志由生成器渲染 pin_family.h；pwm 门禁全类型级放开 + 两通道同实例门禁。

**Blocked by:** 03（pinwriter / pin_bindings / index.html 同缝——03 合 main 后再开）

**Status:** 待实施

## 需求

1. **数据裁决（第一步，决定成败）**：全表排针上 TIMA0/TIMA1 的 PWM 通道分布（boards/mspm0-dimx.json token 逐脚列 + 地猛星引脚图 PDF 交叉核对）。PWMAB 需 **C0+C1 同 TIMA 实例**两通道。裁决：
   - 若存在同实例 C0+C1 排针对 → 跨族可行，实施 2-8；
   - 若不存在（如 TIMA0 排针仅 C3）→ **跨族物理不可达**，本工单改为：pwm 门禁维持 03 同族口径，TIMA-only 脚的能力标注修正（pwm token 标注"无消费方实例"并灰显，前端加提示），记录裁决入 spec/ADR 补注，工单以数据修正闭环。
2. **pin_family.h 渲染（新机制）**：生成器在 copytree 后按绑定族渲染工程根 `pin_family.h`（`#define PWMAB_FAMILY_IS_TIMA 1/0`；未绑/同族 = 0，不变化不落盘）。母版 .cproject IncludePath 验证工程根可达（mspm0 工程根默认可达，工单验证）。
3. **motor.c 双分支**（library/modules/motor/code/motor.c）：PWMAB 相关 DL_TimerG_* 调用（:50/56 setCaptureCompareValue、:58-59 startCounter）改 `#if PWMAB_FAMILY_IS_TIMA` → DL_TimerA_* 对应（签名同形逐个映射）；IRQ 名（PWMAB_INST_IRQHandler 等实例名派生宏）随实例名不变零改动；include "pin_family.h"。
4. **pinwriter.py**：跨族迁移 = peripheral 字段 TIMG0→TIMA0（03 能力复用）+ 族标志计算喂 pin_family.h 渲染（绑定脚 token 族 != 默认族 → IS_TIMA=1）。
5. **pin_bindings.py**：mspm0 pwm 全类型级（删 03 同族限制）；新增 **PWMAB 两通道同实例门禁**（C0/C1 推导实例不同 → 400 中文）。
6. **index.html pinCanHost 镜像**：pwm 全类型级（有任意 pwm token 的脚可选；若数据裁决不可达则 TIMA-only 脚灰显 + 提示）。
7. **测试**：红证先行（族标志缺位编译错 / 两通道异实例 400 / 03 同族限制在位时跨族被拦）；绿证——绑 TIMA 脚对 → pin_family.h IS_TIMA=1 + syscfg peripheral=TIMA0 + 生成宏断言 + motor.c 双分支编译；默认不配 == 母版逐字节 + pin_family.h 不存在/为 0；新增 tests/test_pin_unlock_mspm0_cross.py。
8. **真机**：2024H ①不配回归 gmake 0 错；②绑 TIMA 同实例两通道脚对 → gmake 0 错 + 产物断言（pin_family.h / syscfg peripheral / ti_msp_dl_config.h PWMAB_INST 值）+ step_motor/其它模块回归不破；③两通道异实例 HTTP 400 零产物。运行级（电机真转）用户上板自验。

## 文件边界

- `src/contest_generator/pinwriter.py`、`src/contest_generator/pin_bindings.py`、`src/contest_generator/generator.py`（pin_family.h 渲染挂钩）、`src/contest_generator/errors.py`、`src/contest_generator/boards/mspm0-dimx.json`（能力标注修正）
- `library/modules/motor/code/motor.c`
- `index.html`（pinCanHost）
- `tests/test_pin_bindings.py`、`tests/test_pin_unlock_mspm0_cross.py`（新）
- 零母版 syscfg / stm32 侧改动；铁律：独立 worktree（03 合 main 后从最新 main 建）

## 验收

- [ ] 数据裁决记录（TIMA 通道排针全表 + 结论）入 Comments
- [ ] pytest 全绿 + mypy src 干净
- [ ] 红证已验 + 绿证（pin_family.h 断言 + peripheral 字段 + 双分支编译 + 默认逐字节）
- [ ] 真机：不配回归 + 跨族绑定 gmake 全 0 错 + HTTP 400 零产物
- [ ] 独立 worktree + 提交 + 推送开 PR

## 实施提示词（复制到新会话）

```
实施 mspm0 跨族迁移工单 .scratch/pin-full-unlock/issues/04-mspm0-cross-family.md：
1. 读工单 + .scratch/pin-full-unlock/spec.md（关键事实节必读）+ ADR 0012 + 最新 main（前置 01-03 已合）
2. 第一步数据裁决：TIMA0/TIMA1 通道排针全表（board json + 地猛星引脚图 PDF 交叉核对）；
   C0+C1 同实例排针对存在 → 实施；不存在 → 按工单改走能力标注修正闭环
3. generator.py：copytree 后渲染 pin_family.h（按绑定族算 PWMAB_FAMILY_IS_TIMA；不变化不落盘）
4. motor.c 双分支：#if PWMAB_FAMILY_IS_TIMA → DL_TimerA_*（setCaptureCompareValue/startCounter 逐映射）；
   IRQ 宏名随实例名不动
5. pinwriter.py：跨族 peripheral TIMG0→TIMA0（03 能力复用）+ 族标志计算
6. pin_bindings.py：mspm0 pwm 全类型级 + PWMAB 两通道同实例门禁
7. index.html pinCanHost 镜像
8. 红证先行 + 绿证（pin_family.h/peripheral/生成宏断言 + 默认逐字节）
9. 真机：2024H 不配回归 / 绑 TIMA 同实例两通道 / 异实例 HTTP 400（gmake 全 0 错）
10. 提交 + 推送开 PR
注意：独立 worktree；文件边界见工单；数据裁决结果决定本工单形态，勿跳过
```
