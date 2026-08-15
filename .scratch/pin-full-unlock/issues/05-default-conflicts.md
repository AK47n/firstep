# 05 — stm32 默认 5 组同脚冲突重排（数据工单）

**What to build:** pin_config.h 默认基线里 5 组同脚冲突归零——改 manifests 默认 pins + pin_config.h 母版默认值（纯数据工单，不动门禁与机制）；主链最后做（机制稳定后重排，全量默认回归）。

**Blocked by:** 04（tests/test_pins.py 宏值表 / 真机默认产物断言同缝——04 合 main 后再开）

**Status:** 待实施

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

- [ ] 默认布局不变量测试（两两互异 + 白名单共享）全绿
- [ ] pytest 全绿 + mypy src 干净
- [ ] 真机：2026C / 2021F 不配回归 UV4 双 0 错 + pin_config.h == 新母版逐字节
- [ ] 新旧默认对照表入验收记录
- [ ] 独立 worktree + 提交 + 推送开 PR
