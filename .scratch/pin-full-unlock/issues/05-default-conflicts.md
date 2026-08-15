# 05 — stm32 默认 5 组同脚冲突重排（数据工单）

**What to build:** pin_config.h 默认基线里 5 组同脚冲突归零——改 manifests 默认 pins + pin_config.h 母版默认值（纯数据工单，不动门禁与机制）；主链最后做（机制稳定后重排，全量默认回归）。

**Blocked by:** 04（tests/test_pins.py 宏值表 / 真机默认产物断言同缝——04 合 main 后再开）

**Status:** 待复核（实施完成，PR 待开）

## 需求

1. **冲突清单**（现状）：BUZZER×MOTOR_B_DIR（PB0）、DEBUG_UART×MOTOR_A_ENC/DIR（PA2/3）、LED×GRAY_D6-8（PC13-15）、DIP×GRAY_D1-4（PB12-15）、ZIGBEE×软 I2C（PB10/11）。
2. **重排约束**：新默认脚能力兼容（pwm 须 TIM 通道 / enc 须 exti 线 / uart 须实例对——按板定义 token）；尽量避开骨架 TIM2/3 占用；不制造新的同脚冲突；**每角色 default 改动 = manifest default 值 + pin_config.h 母版宏值 + 相关 macros 双向同步**。
3. **候选空脚**（供参考）：PA11/PA12（USB 共用脚，gpio）、PA15、PB3/4/5（exti 线 3-5）。若某组物理不可达（全排针无兼容空脚）→ 最小化并在工单 Comments 明示保留项及理由。
4. **测试同步**：tests/test_pins.py STM32_MACRO_VALUES 宏值表逐项更新；test_boards.py 如涉能力表不动（token 不变）；新增/更新默认布局不变量测试（全模块默认引脚两两互异断言，按"同角色共享合法"白名单——如 zigbee 与 mpu6050 若维持共享须白名单注明）。
5. **真机回归**：2026C `--reuse-recommend` 不配 bindings → UV4 -r 0 错 0 警 + pin_config.h == 新母版逐字节 + 默认布局冲突断言脚本跑过（复用 build_output_tree_corpus 同源谓词）；2021F 抽跑一题同验。
6. **验收注意**：默认产物形态变化 = 用户已验收形态的变化——验收记录写明新旧默认对照表。

## 文件边界

- `library/modules/{motor,pid,config,digit_uart,debug_uart,uwb_uart,zigbee_uart,zigbee_uart_key,ml_mpu6050,oled}/manifest.json`（涉重排角色的 default 值）
- `library/masters/stm32/pin_config.h`（默认宏值同步）
- `tests/test_pins.py`（宏值表）、`tests/test_default_layout.py`（新，默认布局不变量）
- 零 src/ 改动（门禁/渲染器/校验器不动）；铁律：独立 worktree（04 合 main 后从最新 main 建）

## 验收

- [x] 默认布局不变量测试（两两互异 + 白名单共享）全绿——tests/test_default_layout.py 3 用例
- [x] pytest 全绿 + mypy src 干净（1538 passed + mypy 41 文件 Success）
- [x] 真机：2026C / 2021F 不配回归 UV4 双 0 错 0 警 + pin_config.h == 新母版逐字节（证据 .scratch/real-run/tier05_realrun.log）
- [x] 新旧默认对照表入验收记录
- [x] 独立 worktree（.claude/worktrees/pin-full-unlock-05，04 合 main 后从 ee9c3fc 建）+ 提交 + 推送开 PR（待开）

## 新旧默认对照表（2026-08-15，工单 05）

| 角色 | 旧默认 | 新默认 | 宏变化 |
|---|---|---|---|
| config.BUZZER | PB0 | PA15 | BUZZER_GPIO GPIO_B→GPIO_A、BUZZER_PIN Pin_0→Pin_15 |
| motor.MOTOR_A_ENC | PA2 | PB5 | MOTOR_A_ENC_EXTI EXTI_PA2→EXTI_PB5、MOTOR_A_ENC_LINE 2→5 |
| motor.MOTOR_A_ENC_DIR | PA3 | PB4 | MOTOR_A_ENC_DIR_PORT GPIO_A→GPIO_B、PIN Pin_3→Pin_4 |
| pid.GRAY_D6 | PC13 | PB3 | GRAY_D6_PORT GPIO_C→GPIO_B、PIN Pin_13→Pin_3 |
| pid.GRAY_D7 | PC14 | PB6 | GRAY_D7_PORT GPIO_C→GPIO_B、PIN Pin_14→Pin_6 |
| pid.GRAY_D8 | PC15 | PB7 | GRAY_D8_PORT GPIO_C→GPIO_B、PIN Pin_15→Pin_7 |
| ml_mpu6050.MPU6050_SCL | PB10 | PA11 | I2C_GPIO GPIO_B→GPIO_A、I2C_SCL_GPIO_Pin Pin_10→Pin_11 |
| ml_mpu6050.MPU6050_SDA | PB11 | PA12 | I2C_GPIO GPIO_B→GPIO_A、I2C_SDA_GPIO_Pin Pin_11→Pin_12 |

其余角色默认不变（MOTOR_B_DIR 留 PB0、DEBUG 留 PA2/PA3、LED 留 PC13-15、
DIP 留 PB12-15、GRAY_D1-4 留 PB12-15、ZIGBEE 留 PB10/11）。

## 实施记录（2026-08-15，worktree pin-full-unlock-05）

- **重排结果**：五组冲突归零四组——① BUZZER 离 PB0（MOTOR_B_DIR 独占）；
  ② MOTOR_A_ENC/DIR 离 PA2/PA3（DEBUG_UART 独占）；③ GRAY_D6-8 离
  PC13-15（LED 独占）；④ 软 I2C 离 PB10/11（ZIGBEE 独占）。**残留一组**：
  ⑤ DIP×GRAY_D1-4 仍共享 PB12-15——全库 stm32 42 角色声明 vs 排针 32 脚，
  既有设计共享（UART1 三模块 6 角色、zigbee_uart/key 4 角色）已占满白名单
  空间，全互异数学上不可达；保留并白名单入 tests/test_default_layout.py
  （两组均为输入角色，同选时由用户绑定改脚）。
- **文件改动**：motor/pid/config/ml_mpu6050 四个 manifest 的 default 值 +
  pin_config.h 母版宏值同步（其余 manifest 零改动）；spec 关键事实与 ADR
  0012 决策 7 补工单 05 结果。
- **测试**：tests/test_pins.py STM32_MACRO_VALUES 更新 8 宏 + 增钉
  MOTOR_A_ENC 四宏；tests/test_default_layout.py 新 3 用例（白名单精确钉死
  + 四组冲突已解断言）；test_pin_unlock_i2c.py 默认 no-op 与六宏值基线更新；
  test_pin_unlock_enc.py 渲染器用例改新基线（A_ENC 默认线 5）；
  test_master_embedded.py 21F 基线用例更新。全量 1538 passed + mypy src 41
  文件 Success。
- **真机**（直接 generate + UV4，证据 .scratch/real-run/tier05_realrun.log，
  KEIL_UV4=C:\Keil5\Core\UV4\UV4.exe）：2026C 六模块不配回归——pin_config.h
  == 新母版逐字节 + UV4 0 错 0 警；2021F 四模块不配回归——同左（旧 2021F
  main.c 自带的 `#define DEBUG_UART UART_1` 陈旧行已剥离，与 pin_config.h
  UART_2 的 #47-D 重定义警告非本工单数据改动引入）。
- **文件边界实际改动**：另加 spec.md 与 ADR 0012 两处事实更新（工单结果
  留痕所必需）；零 src/ 改动。

## Comments

- 2026-08-15 开工（Status claimed，主检出 ee9c3fc 建 worktree）。
- 残留 C4 的理由与白名单见上；后续若要彻底归零，只能等排针扩展或删减
  模块角色（不在本轮范围）。
