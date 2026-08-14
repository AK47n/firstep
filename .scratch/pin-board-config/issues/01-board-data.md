# 01 — 板定义数据 + manifest pins 声明 + stm32 硬编码迁移（数据层）

**What to build:** 板级引脚配置的数据地基，三块：
- **A 板定义**：`src/contest_generator/boards/*.json` 两块板（板图坐标/丝印/类型/能力集）+ `boards.py`（模型、读取、能力判定）+ `GET /api/boards`。schema 与能力 token 格式见 spec.md。
- **B manifest pins 声明**：`manifest.py` 加 pins 模型（`platforms.<p>.pins: [{id, type, label, default, required}]`），角色类型词表单源；全部有引脚模块补声明，默认值 = 迁移后 pin_config.h / 地猛星化后 syscfg 现值。
- **C stm32 硬编码迁移**：把散落的引脚字面量全部收进 pin_config.h（兑现 ADR 0010 单源契约）。

**Blocked by:** mspm0-master-dimx/01（声明默认值取地猛星化后 syscfg 值）

**Status:** 已实施待合 main（分支 pin-board-config-01 已推远端）

## 需求

### A 板定义

1. `boards/stm32-min-system.json`：蓝药丸双排 20×2（公开标准布局重建；**芯片级引脚数据已入库**——`sources/materials/2026_08_STM32F103手册/`（引脚定义 xlsx 48 脚全表 + 数据手册 + 参考手册），提取表 `.scratch/pin-board-config/stm32f103c8t6-pinmap.tsv`（含默认 AF 与 remap 列，可逐脚核对）。固定项：PC13 板载 LED、PA11/12 USB、PA13/14 SWD、PD0/PD1 晶振、BOOT0/BOOT1、NRST、VBAT。能力集口径 = **ml_libs 支持表**：ml_uart（UART_1→PA9/10、UART_2→PA2/3、UART_3→PB10/11）、ml_pwm（TIM2_CH1..4→PA0..3、TIM3_CH1..4→PA6/PA7/PB0/PB1、TIM4_CH1..4→PB6..9 等，逐条照 ml_pwm.c 表）、ml_exti（EXTI_PA0~PC7 全表）、ml_adc（Channel→引脚表）、软 I2C（ml_i2c PB10/11、ml_oled PB8/9）→ 编码成能力 token（`uart_tx:UART_1`、`pwm:TIM2_CH1`、`exti:PA2` 等）；GPIO 角色任意 io 脚；**enc 角色 v1 限同 EXTI 线号引脚**（motor 的 EXTI2/EXTI4 handler 名绑定线号，换线号 = 遗留候选）。
2. `boards/mspm0-dimx.json`：地猛星 2×20 排针 + 独立 SWD（PA19/20）/BSL 排针；**排针共 32 个 IO 脚，PB4/PB5 不在排针上**（工单 mspm0-master-dimx/01 自检表实证）；固定占用（CH340E PA10/11、Flash PB14-17、晶振 PA3-6、NRST）；**PA21 固定不可用**（VREF- 原理图直连地，R25 NC）；板载共享注：PA0/PA1 = 板载 LED（I2C_0 共用，微闪副作用；PA1 板载 4.7k 上拉、PA0 上拉位未焊依赖 MPU 板自带）、PA2 = ROSC 偏置 100k 到地、PA14 = LED2 + 15k 到地（PWM 微亮可忽略）、PA18 = 47k 到 BSL 排针（输出无碍）。能力集 = 引脚图 PDF 每脚复用标注行（UART/I2C/SPI/TIMA/TIMG/ADC/COMP/OPA/CAN/DAC 逐脚录入，pdftotext 提取）+ GPIO 任意。
3. `boards.py`：板定义模型（Board / BoardPin / capability 解析与判定 `pin_supports(pin, role_type, instance)`）+ 加载；`webapp.py` 加 `GET /api/boards`（返回 `{boards: [...]}`）。生成门禁与前端同吃此数据——单源。

### B manifest pins 声明

4. `manifest.py`：Pins 模型 + 校验（id 唯一、type 在词表内、default 必填、label 缺省 = id）。角色类型词表（gpio_out / gpio_in / uart_tx / uart_rx / pwm / enc / adc / i2c_scl / i2c_sda / spi_* / exti）**单源定义**（boards 与 manifest 共用）。
5. 补声明清单（默认值 = 现值）：
   - **stm32**：motor（MOTOR_A_PWM/A_DIR/A_DIR2/B_PWM/B_DIR/B_DIR2/A_ENC/A_ENC_DIR/B_ENC/B_ENC_DIR，pin_config.h 宏）、pid(gray_track)（D1-D8：PB12-15/PA8/PC13-15）、digit_uart（uart，UART_1）、debug_uart（uart，UART_2）、ball_detect（uart，UART_1）、uwb_uart（uart，UART_1）、zigbee_uart + zigbee_uart_key（uart，UART_3）、config（LED×3 / BUZZER / DIP×4）、ml_mpu6050（i2c，软 I2C PB10/11）。
   - **mspm0**（默认值 = 地猛星化后 syscfg 现值，工单 mspm0-master-dimx/01 cef70de 已合 main）：motor（PWMAB_C0=PA12/C1=PA13、AIN1=PB9、AIN2=PA18、BIN1=PB18、BIN2=PA7、AA=PA16、AB=PA17、BA=PB19、BB=PB20）、huidu（L1=PA22/L2=PA23/L3=PA24/L4=PA25/R1=PA26/R2=PA27/**R3=PB4/R4=PB5 默认板外**——PB4/PB5 不在排针，见新增规则）、pid(gray_track_mspm0)（同 HUIDU 8 脚）、xunji（P1-P8 同 HUIDU——**同引脚共享合法**，不拦）、key（KEY START=PA2 + 编码器组）、digit_uart（DIGIT_UART TX=PA8/RX=PA9）、imu_uart（IMU601 TX=PA28/RX=PA31）、led_beep（LED=PA15）、oled（OLED I2C1 SCL=PB2/SDA=PB3）、step_motor（RST2=PB24/SLP2=PB6/DIR2=PB7/DCY2=PB8 + DCC_100_PWM2 C0=PA14）、ml_mpu6050（I2C_0 SCL=PA1/SDA=PA0）。
6. **板外默认规则（新增）**：角色默认引脚不在板图引脚集内（HUIDU R3/R4=PB4/PB5）→ 角色仍出现在清单，状态标注"默认板外"；**不因默认板外而禁止绑定**——用户可绑到板内空闲脚；未绑 = 默认照写（syscfg 不动）。板定义 pins 集只含排针上的脚；绑定到 PB4/PB5 等板外脚 → 未知引脚校验拒绝（工单 02）。
   - filter / delay / uart / ntb_time 无引脚，不声明。

### C stm32 硬编码迁移

6. 全部迁入工程根 `pin_config.h`（宏名沿用现名，值 = 现硬编码值——**默认行为零变化**）：
   - `gray_track.c`（PB12-15/PA8/PC13-15）→ 宏；`digtal()` 内二次硬编码同改。
   - `digit_uart.c`（UART_1 + USART1 寄存器）→ UART 实例宏（寄存器引用随之宏化或保留实例宏 + 注释说明）。
   - `debug_uart.c`（UART_2）、`ball_detect_stm32.c`（UART_1）→ 宏。
   - `config.h` 引脚宏（LED_PORT/PIN×3、BUZZER_GPIO、DIP_GPIO、UWB_UART、ZIGBEE_UART）→ 并入 pin_config.h；config.h 保留非引脚宏（波特率等）+ `#include "pin_config.h"`（既有消费方如 uwb_uart.c 不改引用）。**注意**：ml_led.h 有 LED_GPIO 宏（GPIO_A）——macro_conflicts 门禁有撞名判例，命名避让。
   - `key.c`（mspm0）硬编码 GPIOB/GPIOA 中断组 → 宏（syscfg 生成宏可推导处用之）。

## 文件边界

- 新增：`src/contest_generator/boards/{stm32-min-system,mspm0-dimx}.json`、`src/contest_generator/boards.py`
- `src/contest_generator/manifest.py`（pins 模型 + 词表）、`src/contest_generator/webapp.py`（/api/boards 路由）
- `library/modules/*/manifest.json`（补 pins 声明）+ 上述模块 code 文件（迁移改动）
- `library/masters/stm32/pin_config.h`（新增宏）
- `tests/`：manifest pins 校验、boards 数据不变量（引脚唯一 / 能力集与 ml_libs 表一致 / 坐标在板界内）、迁移后模块代码 grep 零硬编码残留

## 验收

- [ ] pytest 全绿（新测试 + 回归）+ mypy src 干净
- [ ] 真机 UV4：2021F / 2026C 双题生成 0 Error(s)（迁移回归——默认值零变化，产物行为与迁移前一致）
- [ ] 真机 gmake：2026H mspm0 0 错（回归）
- [ ] `grep -n "GPIO_A\|GPIO_B\|Pin_[0-9]\|UART_[123]\|PA[0-9]\|PB[0-9]"` 模块 code 无引脚字面量残留（宏名与注释除外）
- [ ] `/api/boards` 返回两块板，curl 校验字段齐全
- [ ] 独立 worktree + 提交（代码 `refactor:` / 数据 `data:` 前缀）+ 推送

## 实施提示词（复制到新会话）

```
实施板级引脚配置数据层工单 .scratch/pin-board-config/issues/01-board-data.md：
1. 读工单 + .scratch/pin-board-config/spec.md + docs/adr/0010-board-pin-configuration.md
2. A 板定义：boards/{stm32-min-system,mspm0-dimx}.json（schema/能力 token 见 spec）+ boards.py + /api/boards；
   stm32 能力集照 ml_libs 映射表逐条编码（ml_uart.c/ml_pwm.c/ml_exti.c/ml_adc.c/ml_i2c.h/ml_oled.h）；
   mspm0 能力集照引脚图 PDF 复用标注（sources/materials/2026_04_地猛星电赛控制题配套资料/，pdftotext 提取）；
   enc 角色 stm32 限同 EXTI 线号引脚
3. B manifest pins：manifest.py 加 pins 模型 + 角色类型词表单源；按工单清单给全部有引脚模块补声明，
   默认值 = pin_config.h / 地猛星化后 syscfg 现值；xunji 与 huidu 同引脚共享合法
4. C stm32 硬编码迁移：gray_track/digit_uart/debug_uart/ball_detect_stm32 硬编码 → pin_config.h 宏；
   config.h 引脚宏并入 pin_config.h（保留非引脚宏 + include；避 ml_led.h LED_GPIO 撞名）；
   key.c（mspm0）硬编码 GPIO 组 → 宏。默认值零变化，编译行为不变
5. 验收：pytest 全绿 + mypy src 干净；真机 UV4 2021F/2026C 0 错（迁移回归）+ gmake 2026H 0 错；
   模块 code grep 零引脚字面量残留；/api/boards curl 校验
6. 提交（refactor:/data: 前缀）+ 推送
注意：独立 worktree；本工单不碰生成写侧（pin_config.h 渲染/syscfg 改写是工单 02），
     只保证默认值不变、编译不破
```

## Comments

- 2026-08-14 立项（板级引脚配置 grilling 定稿；原定 3 工单拆 4 工单——数据层与机制层分家，每张可独立验收）。
- 2026-08-14 实施完成（分支 pin-board-config-01）：A 板定义双 JSON + boards.py + /api/boards（stm32 能力集逐条照 ml_uart/ml_pwm/ml_exti/ml_adc/ml_i2c/ml_oled 映射表编码，与 .scratch/pin-board-config/stm32f103c8t6-pinmap.tsv 官方 AF 表核对；enc 实例 = EXTI 线号，限同线号引脚；mspm0 能力集照引脚图 PDF 复用标注 pdftotext 逐脚配出，与地猛星化后 syscfg $assign 全部互证——PWMAB TIMG0 PA12/13、DCC TIMG12 PA14、IMU601 UART0 PA28/31、OLED I2C1 PB2/3、I2C_0 PA0/1、DIGIT_UART UART1 PA8/9 均吻合）。B 模型：PIN_ROLE_TYPES 词表单源（boards 与 manifest 共用）+ PinDeclaration（id/type/default/label/required/macros，label==id 归一缺省保证序列化往返稳定）+ 17 个 manifest 补 93 条声明（stm32 带 pin_config.h 宏名映射；板外默认 PB4/PB5 按规则保留声明不拦）。C 迁移：gray_track（D1-D8 两处硬编码）→ GRAY_D* 宏、digit_uart/ball_detect/debug_uart → UART 实例宏 + *_INST 寄存器宏、uwb_uart/zigbee_uart 寄存器引用 → *_UART_INST、config.h 引脚宏并入 pin_config.h（保留波特率等参数 + include）、key.c GPIOA/GPIOB → DC_MOTOR_AA/BA_PORT（syscfg 生成宏）；宏名避让 ml_led.h LED_GPIO 撞名判例。验收：pytest 1413 绿 + mypy src 39 文件干净；真机 UV4 2026C（缓存复用）/2021F（clarify 12 条）双题 0 错 0 警、全迁移面直生成（motor/pid/digit_uart/debug_uart/ball_detect/config/uwb_uart/zigbee_uart/zigbee_uart_key/ml_mpu6050/filter 11 模块）UV4 全量重建 0 错 0 警（日志确认 gray_track.c/digit_uart.c 编译行俱在）；gmake 2026H_filt 10 模块 0 错（2 警 = 既有母版 IMU601/DIGIT_UART ovsRate 提示，clean 重建确认）；模块 code 注释剥离后零引脚字面量（pytest 化验收 grep）；/api/boards curl 双板 + platform 过滤校验。顺手修复：debug_uart.h DEBUG_PRINTF 宏 sprintf 缺 stdio.h 声明（全模块面编译暴露的既有潜伏告警 6 条，加一行 include 清零——本模块从未进过真机选题，迁移验收首编）。遗留：keil.py/webapp 有 SyntaxWarning（`"\."` 非 raw 串，既有）；工具链注意 generate_check 需 GMAKE 环境变量 + 先删旧 out 目录（历史教训复现两次）。
