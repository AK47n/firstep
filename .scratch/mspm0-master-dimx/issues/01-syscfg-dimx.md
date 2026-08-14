# 01 — mspm0 母版 syscfg 地猛星化 + 孤儿实例补齐（板级引脚配置前置工单）

**What to build:** 现母版 syscfg 按 TI LaunchPad 配置，两处在地猛星真板上接线错误：LED_BEEP LED=PA3（板上 PA3 = 32.768k 晶振脚，排针上根本没有 PA3）、IMU601=UART0 PA11/PA10（板上被 CH340E USB 串口占用）；DC_MOTOR AIN1/AIN2=PA0/PA1 与板载 LED 冲突。另有**两个模块引用的 syscfg 实例在母版不存在，选中即编译失败**（现状 bug）：step_motor（STEP_MOTOR GPIO×4 + DCC_100_PWM2 PWM）、ml_mpu6050（I2C_0）。本工单把母版 syscfg 重分配为地猛星合法接线 + 补齐孤儿实例 + 修注释漂移，为板级引脚配置（.scratch/pin-board-config/）铺路。

**Blocked by:** 无

**Status:** 待实施

## 现状证据

- `library/masters/mspm0/mspm0.syscfg`（184 行）：PWMAB（TIMG0，PA12/PA13）、MOTOR_PID（TIMG6）、NTB（TIMG7）、DC_MOTOR（AIN1=PA0 AIN2=PA1 BIN1=PB18 BIN2=PA7 + 编码器中断 AA=PA16 AB=PA17 BA=PB19 BB=PB20）、HUIDU（8 路 PA22-27/PB4/PB5）、KEY（PA2）、LED_BEEP（PA3）、IMU601（UART0，RX 中断，PA11/PA10）、DIGIT_UART（UART1，PA9/PA8）、OLED（I2C1，PB3/PB2）。文件头注释："实例名/宏名与模块库代码一一对应……实际接线不同时改引脚名即可，实例名与宏名勿动"。
- 地猛星排针清单（引脚图 PDF 提取，工单 spec 同款）：左排 `PA0, PA1, PA28, PA31, NRST, PA2, PB24, PB20, PB19, PB18, PA7, PB2, PB3, PA8, PA9, PB6, PB7, +5V, 3V3, GND`；右排 `GND, PA27, PA26, PA25, PA24, PA23, PA22, PA21, PB9, PB8, PA18, PA17, PA16, PA15, PA14, PA13, PA12, +5V, 3V3, GND`。PA19/PA20（SWD）只走独立 DEBUG 排针。
- 板上固定占用（原理图 PDF）：CH340E→UART0 PA10/11（USB Type-C 串口）、W25Q32 Flash PB14-17（SPI0）、40MHz 晶振 PA5/PA6、32.768kHz 晶振 PA3/PA4、板载 LED2=PA1 / LED=PA0、NRST 复位。
- 孤儿实例：`library/modules/step_motor/code/step_motor.c:5-9,28-84` 引用 `STEP_MOTOR_PORT / RST2 / SLP2 / DIR2 / DCY2_PIN` 与 `DCC_100_PWM2_INST`、`GPIO_DCC_100_PWM2_C0_IDX`；`library/modules/ml_mpu6050/code/mpu_port.c:26-91` 引用 `I2C_0_INST`。
- 注释漂移：`library/modules/huidu/code/huidu.h:8-18`（PA26-21/PB9/PB8 旧值）、`library/modules/imu_uart/code/imu.h`（PA28/PA31 旧值）、`library/modules/led_beep/`（manifest note "=PA14" / code 注释 "PA15" / syscfg "PA3" 三处不一致）、`library/modules/ntb_time/manifest.json`（note 说 TIMG12，syscfg 实为 TIMG7）、`library/modules/motor/code/motor.h`（mspm0 接线注释）。
- 素材：`sources/materials/2026_04_地猛星电赛控制题配套资料/00_立创·地猛星MSPM0G3507开发板引脚图.pdf`（每脚复用标注行）+ 原理图 PDF（pdftotext 可提取全文）。

## 需求

1. **重分配 syscfg 引脚**（实例名 / 宏名 / 通道名一律不动，只动 `$assign` 引脚值）：
   - LED_BEEP：离 PA3 → 空闲排针脚（如 PA14；避开固定占用与其余实例）。
   - IMU601：离 UART0/PA10/PA11 → 板上空闲 UART 实例（查引脚图复用标注定新 UART 与引脚；注意 PB2/PB3 已被 OLED 占）。
   - DC_MOTOR：AIN1/AIN2 与板载 LED PA0/PA1 冲突——移开（如 PA14/PA15）或保留（LED 闪烁副作用）自行裁决并记入 Comments。
   - 其余实例（PWMAB / HUIDU / KEY / OLED / DIGIT_UART / NTB / MOTOR_PID）已在排针合法脚上，不动。
2. **补齐孤儿实例**：STEP_MOTOR（GPIO 输出×4：RST2/SLP2/DIR2/DCY2）+ DCC_100_PWM2（单通道 PWM）——读 step_motor.c 定引脚名与通道约定；I2C_0——读 mpu_port.c。新实例引脚同样只用地猛星排针空闲脚。
3. **修注释漂移**：huidu.h / imu.h / led_beep（manifest note + code 注释）/ ntb_time（manifest note）/ motor.h mspm0 接线注释 → 全部与 syscfg 一致。
4. **CONTEXT.md**：平台词条补一句"母版 syscfg 已地猛星化"（如改动真的发生了；措辞贴现状）。

## 文件边界

- `library/masters/mspm0/mspm0.syscfg`：唯一数据改动（引脚重分配 + 新实例）
- 模块文件：`library/modules/{huidu,imu_uart,led_beep,ntb_time,motor}/` 下注释行（huidu.h / imu.h / motor.h / led_beep 的 code+manifest / ntb_time 的 manifest）——**只改注释与 note，零代码语义改动**
- `CONTEXT.md`：一句
- **零 src 改动**；勿动 `~/.contest_generator/`

## 验收

- [ ] 2026H 全管线生成产物 gmake 0 错（`--add imu_uart,led_beep`，复用既有 clarify 映射）
- [ ] **含孤儿模块用例**：`--add step_motor,ml_mpu6050` 生成产物 gmake 0 错（补齐实证）
- [ ] 每个实例引脚都在地猛星排针清单内且互不重复（对照表进 Comments）
- [ ] 注释漂移 grep 复查：huidu/imu/led_beep/ntb_time/motor 的引脚注释与 syscfg 逐一致
- [ ] pytest 全绿 + mypy src 干净（零 src 改动应无扰动）
- [ ] 独立 worktree + 独立提交（`data:` 前缀）+ 推送

## 实施提示词（复制到新会话）

```
实施 mspm0 母版 syscfg 地猛星化工单 .scratch/mspm0-master-dimx/issues/01-syscfg-dimx.md：
1. 读工单文件 + .scratch/pin-board-config/spec.md（排针清单与固定占用）+ library/masters/mspm0/mspm0.syscfg +
   引脚图/原理图 PDF（sources/materials/2026_04_地猛星电赛控制题配套资料/，pdftotext 提取）
2. 重分配 syscfg 引脚（只动 $assign 引脚值；实例名/宏名/通道名不动）：
   LED_BEEP 离 PA3、IMU601 离 UART0/PA10-11、DC_MOTOR AIN1/AIN2 与板载 LED 冲突裁决；
   新脚必须在地猛星排针清单内、不被其他实例占用（查引脚图复用标注）
3. 补齐孤儿实例：STEP_MOTOR（GPIO×4）+ DCC_100_PWM2（读 step_motor.c 定引脚名/通道约定）；
   I2C_0（读 ml_mpu6050/code/mpu_port.c）
4. 修注释漂移：huidu.h / imu.h / led_beep（manifest+code）/ ntb_time（manifest note）/ motor.h 接线注释
5. 验收：2026H --add imu_uart,led_beep gmake 0 错 0 警；--add step_motor,ml_mpu6050 用例 gmake 0 错；
   实例引脚对照排针清单自检表进 Comments；pytest 全绿 + mypy src 干净
6. 提交（data: 前缀）+ 推送
注意：零 src 改动；勿动 ~/.contest_generator/；独立 worktree 与其他会话隔离
```

## Comments

- 2026-08-14 立项（板级引脚配置 grilling 定稿派生；原为工单 08 遗留"母版 .syscfg 地猛星化"）。
