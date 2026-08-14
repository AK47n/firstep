# 板级引脚配置（板图点击配引脚）——功能规格

> 2026-08-14 grilling 定稿（用户逐轮确认）。领域词表已入 CONTEXT.md（板定义 / 引脚角色 / 角色类型 / 引脚绑定），决策已入 ADR 0010。

## 愿景

CubeMX 式引脚配置，但显示**开发板本体**而非芯片封装：stm32 = 最小系统板（蓝药丸），mspm0 = 地猛星。选好模块后在板图上点击引脚，弹出该引脚能担任的**模块引脚角色**（标签 = `模块_用途`，如 `TB6612_STBY`），点一下即完成绑定。

## 流程（v1 = 生成前锁定）

```
推荐（选模块）→ 引脚配置卡片（预填默认布线）→ 骨架 → 生成（请求携带 bindings）
→ 生成器写 pin_config.h（stm32）/ 改写 .syscfg（mspm0）→ 门禁 → 编译
```

- 未绑定的角色按声明默认值生成——不配也能生成，保持"打开就能编译"。
- v1 配置不持久化（随生成请求走，会话内前端 state）；生成后编辑 / 配置持久化 / ml_libs 映射扩展 = 遗留候选。

## 数据契约

### 板定义（boards/*.json，后端单源）

```json
{
  "board_id": "mspm0-dimx", "name": "地猛星 MSPM0G3507", "platform": "mspm0",
  "pins": [
    {"name": "PA12", "kind": "io", "x": 0, "y": 12, "side": "right",
     "capabilities": ["gpio_out", "gpio_in", "pwm:TIMG0_CCP0", "adc:A0_0", "i2c_scl:I2C1"]},
    {"name": "3V3", "kind": "power", "x": 0, "y": 17, "side": "right", "capabilities": []}
  ],
  "fixed": [{"name": "CH340E USB串口", "occupies": ["PA10", "PA11"], "note": "板上 USB Type-C"}]
}
```

- `kind`: io / power / gnd / reset / swd / osc / boot / fixed（固定资源）。**板载共用警示约定（2026-08-14 用户定）**：io 引脚带 `notes` = 与板载资源共用（BSL 烧录脚 / 板载 LED / ROSC 偏置 / USB 插座等）——前端必须渲染**可见警告**（焊盘橙虚环 + 板图下方 ⚠ 警示清单），不只悬停；notes 措辞必须写明共用对象与可用条件（如"作输出无碍；用 BSL 烧录时勿占用"）；新增板载共用脚必须照此写 notes，不得只放悬停。
- 能力 token 格式 `<角色类型>[:<实例>]`；类型词表单源：`gpio_out / gpio_in / uart_tx / uart_rx / pwm / enc / adc / i2c_scl / i2c_sda / spi_mosi / spi_miso / spi_sck / spi_cs / exti`。
- 能力集口径：**stm32 = ml_libs 支持表**（ml_uart.c / ml_pwm.c / ml_exti.c / ml_adc.c / ml_i2c.h / ml_oled.h 的"实例→引脚"映射逐条编码）+ GPIO 任意 + enc 限同 EXTI 线号引脚（motor 的 EXTI2/EXTI4 handler 名绑定线号，v1 不换线）；**mspm0 = 地猛星引脚图 PDF 复用标注**（真任意，芯片级过滤）。
- 两块板：`stm32-min-system`（蓝药丸双排 20×2，公开标准布局重建；固定项 = PC13 板载 LED、PA11/12 USB、PA13/14 SWD、PD0/1 晶振、BOOT0/1、NRST、VBAT）、`mspm0-dimx`（2×20 排针 + 独立 SWD/BSL 排针；固定项 = CH340E PA10/11、Flash PB14-17、晶振 PA3-6、板载 LED PA0/PA1、NRST）。
- API：`GET /api/boards` → `{boards: [...]}`（按 platform 过滤入参可选）。

### manifest pins 声明

`manifest.json` 平台条目下加 `pins`（per-platform——motor 双平台引脚不同）：

```json
"platforms": {"stm32": {"pins": [
  {"id": "MOTOR_A_PWM", "type": "pwm", "label": "MOTOR_A_PWM", "default": "PA0", "required": true},
  {"id": "MOTOR_A_ENC", "type": "enc", "label": "MOTOR_A_ENC", "default": "PA2", "required": true}
]}}
```

- 默认值 = 单源化后 pin_config.h / 地猛星化后 syscfg 的现值。
- stm32 声明带宏名映射（写侧渲染要：如 enc 角色一个绑定产出 `MOTOR_A_ENC_EXTI / _LINE / _DIR` 三个宏值——具体渲染机制由工单 02 定，契约 = 确定性 + 默认绑定输出与迁移后 pin_config.h 逐字节一致）。

### 引脚绑定（bindings）

- 载荷格式：`/api/generate` 请求体加可选字段 `bindings: {"<slug>.<role_id>": "<PIN>"}`（如 `{"motor.MOTOR_A_PWM": "PA0"}`；缺省 = 全默认，向后兼容）。
- **板外默认**：角色默认引脚不在板图引脚集内（HUIDU R3/R4=PB4/PB5——地猛星排针未引出，工单 mspm0-master-dimx/01 实证）→ 清单标注"默认板外"、仍可绑定到板内脚；未绑 = 默认照写（syscfg 不动）；绑定到板外脚 = 未知引脚 400。
- 同引脚多角色**允许**（xunji/huidu 共享灰度传感器先例）：门禁不拦重复，前端对同引脚多角色叠加标注。
- 门禁校验（工单 02）：能力合法（绑定引脚的能力集含该角色类型实例）/ 未知角色或引脚 / 缺省走默认；另加骨架门禁——clex 注释剥离后 main.c 不得含引脚字面量（守住现状性质）。

## 前端（工单 03）

- 生成页新卡片插在"模块清单"与"main.c 骨架"之间（卡片序号顺延）。
- 左板图 SVG（由 boards JSON 坐标渲染：焊盘可点击、丝印、功能区、固定引脚灰色、按角色类型着色 + 图例——视觉参照 `sources/contest/2026H/26H/pin_config.html`），右待接角色清单（已绑 / 未绑 / 用默认三态）。
- 点引脚 → 锚定浮层菜单（复用 `.ref-files-overlay` 模式；只列能力支持的角色，不兼容灰显 + 原因）；点已占用引脚 → 显示占用者、可直接替换，被替换角色红显未绑；点清单条目 → 板图高亮可接引脚。
- 无静态路由：SVG 几何由 boards JSON 内联渲染，深色令牌用 `:root` 变量。

## 工单链（按序，每张独立 worktree + 独立会话）

| # | 工单 | 内容 |
|---|---|---|
| 前置 | `.scratch/mspm0-master-dimx/issues/01-syscfg-dimx.md` | 母版 syscfg 地猛星化 + 孤儿实例（step_motor/ml_mpu6050）+ 注释漂移 |
| 01 | `.scratch/pin-board-config/issues/01-board-data.md` | 板定义数据 + /api/boards + manifest pins + 全模块声明 + stm32 硬编码迁移 |
| 02 | `.scratch/pin-board-config/issues/02-binding-write-gates.md` | bindings 模型 + pin_config.h 渲染器 + syscfg 改写器 + 两条门禁 + errors + 真机 |
| 03 | `.scratch/pin-board-config/issues/03-board-ui.md` | 板图 SVG + 角色菜单 + 双视图 + payload 带 bindings + 浏览器验收 |

## 关键事实（grilling 调查，实施会话必读）

- stm32 母版 pin_config.h 现只含电机宏，generator 对它是 copytree 原样复制（generator.py:662-667），全 src 无读写代码。
- ml_libs 内部"实例→引脚"映射写死：ml_uart（UART_1→PA9/10、UART_2→PA2/3、UART_3→PB10/11）、ml_pwm（TIM2_CH1→PA0 等）、ml_exti（EXTI_PA0~PC7）、ml_adc（Channel→引脚）、软 I2C（ml_i2c PB10/11、ml_oled PB8/9）。
- stm32 硬编码面：gray_track.c（PB12-15/PA8/PC13-15）、digit_uart.c（UART_1+USART1 寄存器）、debug_uart.c（UART_2）、ball_detect_stm32.c（UART_1）、config.h（LED/BUZZER/DIP/UWB_UART/ZIGBEE_UART 宏）。key.c（mspm0）硬编码 GPIOB/GPIOA 中断组。
- mspm0 母版 syscfg 是 TI LaunchPad 配置：LED_BEEP=PA3（地猛星晶振脚）、IMU601=UART0 PA11/PA10（CH340E 占用）在地猛星真板接线错误；DC_MOTOR AIN1/AIN2=PA0/PA1 与板载 LED 冲突。
- step_motor（STEP_MOTOR + DCC_100_PWM2）、ml_mpu6050（I2C_0）引用的 syscfg 实例不存在——选中即编译失败（现状 bug，前置工单修）。
- 注释漂移：huidu.h（PA26-21 旧值）、imu.h（PA28/31 旧值）、led_beep（manifest "=PA14" / code 注释 "PA15" / syscfg "PA3" 三处不一致）、ntb_time（manifest note TIMG12 vs syscfg TIMG7）。
- 地猛星排针清单（引脚图 PDF 提取）：左排 PA0, PA1, PA28, PA31, NRST, PA2, PB24, PB20, PB19, PB18, PA7, PB2, PB3, PA8, PA9, PB6, PB7, +5V, 3V3, GND；右排 GND, PA27, PA26, PA25, PA24, PA23, PA22, PA21, PB9, PB8, PA18, PA17, PA16, PA15, PA14, PA13, PA12, +5V, 3V3, GND。PA19/PA20（SWD）只走独立 DEBUG 排针。
- 真实 main.c 产物从不内联引脚字面量（16 份历史产物验证）——骨架门禁守住此性质即可，无需"骨架虚拟模块"。
- 素材 PDF 在 `sources/materials/2026_04_地猛星电赛控制题配套资料/`（引脚图 + 原理图，pdftotext 可提取全文）；蓝药丸板级资料仓库内没有，需按公开标准布局重建。**2026-08-14 补**：芯片级引脚数据已入库 `sources/materials/2026_08_STM32F103手册/`（引脚定义 xlsx + 数据手册 + 参考手册），提取表 `.scratch/pin-board-config/stm32f103c8t6-pinmap.tsv`——能力集可与官方 AF 表逐脚核对；板形丝印仍需公开布局。
- **地猛星化后板事实（工单 mspm0-master-dimx/01 Comments，2026-08-14，cef70de 已合 main）**：排针 32 IO、无 PB4/PB5（HUIDU R3/R4 默认板外）；PA21/VREF- 直连地不可用；PA0/PA1 板载 LED 与 I2C_0 共享（微闪，PA1 板载 4.7k 上拉、PA0 上拉位未焊）；PA14 LED2+15k（PWM 微亮）；PA18 47k 到 BSL；排针 33 分配全满无空闲脚；原理图 48 脚与 TI LQFP-48(PT) 吻合、syscfg 声明 LQFP-64(PM) 系 LaunchPad 遗留——包型号待核实（工单 mspm0-board-package/01）；TIMG7 16 位回绕问题待核实（工单 ntb-time-wrap/01）。
