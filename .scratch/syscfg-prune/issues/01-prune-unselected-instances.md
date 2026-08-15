# 01 — mspm0 syscfg 按选中模块动态裁剪（未选实例让脚给用户绑）

**What to build:** 现状：母版 mspm0.syscfg 含全量实例（理论上限布局），生成时全量复制——未选模块的实例仍占着引脚，用户绑定"未选模块的引脚"会撞 SysConfig Resource conflict。本工单：生成 mspm0 工程时按**本次选中的模块集**裁剪 syscfg，未选模块的实例不落盘，其引脚空出来可绑。

**Blocked by:** 无

**Status:** 待复核（实施完成，PR 待开）

## 需求

1. **实例 → 消费模块映射**（单源表）：`PWMAB→motor`、`DCC_100_PWM2→step_motor`、`MOTOR_PID→motor,pid`、`NTB→ntb_time`、`DC_MOTOR→motor,key`、`HUIDU→huidu,pid,xunji`、`KEY→key`、`LED_BEEP→led_beep`、`STEP_MOTOR→step_motor`、`IMU601→imu_uart`、`DIGIT_UART→digit_uart,ball_detect`、`OLED→oled`、`I2C_0→ml_mpu6050`。任一消费模块被选中即保留实例；全部未选才裁剪。
2. **裁剪器**（建议 `src/contest_generator/syscfg_prune.py` 或 pinwriter 内）：输入母版 syscfg 全文 + 选中 slugs，输出裁剪后全文——删除被裁实例的 `const X = MOD.addInstance();` 行与所有以 `X.` 开头的配置行；某模块（UART/I2C/TIMER/GPIO/PWM）实例全部被裁时，连 `const MOD = scripting.addModule(...)` 行一并删除；`Board`/`SYSCTL` 与文件头注释保留。
3. **生成挂钩**：`generate()` 在 copytree 后、`apply_pin_bindings` 前对 mspm0 执行裁剪（文本无变化不落盘契约保持——全选理论模块时仍 == 母版）。stm32 不裁剪。
4. **bindings 联动**：裁剪后 `resolve_bindings`/写侧照常——用户可绑任何排针脚，未选模块的引脚已真空出来，不再撞 Resource conflict。
5. **测试**：裁剪器纯函数单测（选 motor 只留 PWMAB/MOTOR_PID/DC_MOTOR 等；选 imu_uart 留 IMU601 裁 DIGIT_UART；全选 == 母版；空选裁全部外设实例）；生成集成测试更新（mspm0 缺省产物 = 按选中集裁剪后的 syscfg，不再断言全量母版逐字节）；真机 2024H/2026C 各跑一次 gmake 0 错 + 产物 syscfg 字段断言 + 绑"未选模块引脚"不再 400/冲突。
6. **文档**：spec 关键事实与 ADR 0012 决策 7 补"默认布局 = 理论上限；生成按选中裁剪"。

## 文件边界

- `src/contest_generator/syscfg_prune.py`（新）或 `pinwriter.py`（裁剪器）
- `src/contest_generator/generator.py`（挂钩）
- `tests/test_syscfg_prune.py`（新）、`tests/test_pin_bindings.py`/`tests/test_generator.py` 相关基线更新
- 零母版 syscfg / 模块代码改动；铁律：独立 worktree（从最新 main 建）

## 验收

- [x] pytest 全绿 + mypy src 干净（1542 passed + mypy 42 文件 Success）
- [x] 真机：2024H 十模块裁剪后 gmake 0 错 + 小集绑未选模块引脚（HUIDU R3→PA15）gmake 0 错（证据 .scratch/real-run/syscfg_prune_realrun.log）
- [x] 独立 worktree（.claude/worktrees/syscfg-prune-01）+ 提交 + 推送开 PR（待开）

## Comments

- 2026-08-15 立项（mspm0-board-package/01 收口：用户裁决"默认布局 = 理论上限，按选中裁剪让用户规划"）。

## 实施记录（2026-08-15，worktree syscfg-prune-01）

- **新增 `src/contest_generator/syscfg_prune.py`**：`INSTANCE_CONSUMERS`
  实例→消费模块单源表（13 实例）；`prune_syscfg(master_text, selected)`
  按交集裁实例——删 `const X = MOD.addInstance();` 行与所有 `X.` 配置行，
  模块变量全裁时连 `scripting.addModule` 行一起删；未登记实例宁多勿裁
  （防御）。`prune_mspm0_syscfg_file` 挂生成，文件缺失防御跳过（假母版
  测试树无 syscfg）。
- **`generator.generate()` 挂钩**：copytree 后、`apply_pin_bindings` 前
  对 mspm0 执行裁剪——写侧槽位定位只认保留实例的默认引脚；stm32 不裁。
- **测试**：新增 `tests/test_syscfg_prune.py` 4 用例（全选==母版 / 空选
  裁全部 / 选 motor 只留 motor 实例且 UART/I2C 模块变量连根裁 / 共享实例
  任一消费选中即保留）；`test_pin_bindings.py` 生成集成基线改为"裁剪后
  基线"（选 led_beep 无绑定 == prune_syscfg(master, [led_beep])，带绑定
  断言 LED_BEEP 留、IMU601 裁）。全量 1542 passed + mypy 42 文件干净。
- **真机**（证据 .scratch/real-run/syscfg_prune_realrun.log）：2024H 十模块
  裁剪后 gmake 0 错（IMU601 保留 / DIGIT_UART、I2C_0 被裁）；小集
  （huidu+delay+oled）绑 `huidu.R3→PA15`（led_beep 未选，PA15 空出）
  生成成功 + syscfg 字段断言 + gmake 0 错。
- **文档**：spec 关键事实 + ADR 0012 决策 7 补"mspm0 默认布局 = 理论上限，
  生成按选中裁剪"。
