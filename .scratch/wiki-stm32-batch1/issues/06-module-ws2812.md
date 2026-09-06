# 06 — ws2812 幻彩灯带（GPIO 位时序，手册 control--ws2812-color-rgb-led.md）

**要做什么：** 模块库 `ws2812` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼 WS2812 单总线驱动为纯驱动切片（1 × GPIO 强推挽输出，800kHz 位时序忙等——不占 TIMER、不注册中断），API 与 mspm0 版完全对齐：`ws2812_init()`（清缓冲+复位电平）、`ws2812_set_led_count(uint8_t)`（≤WS2812_MAX 8）、`ws2812_led_count()`、`ws2812_set_color(uint8_t id, uint32_t 0xRRGGBB)`（内部按 GRB 发送序存缓冲——R/G 换位在 set_color 里做，日常写 0xFF0000=红）、`ws2812_set_rgb(id, r, g, b)`、`ws2812_refresh()`（缓冲整体下发 + ≥280us 复位脉冲）。

**关键事实（已取证）：**
- 页面 = **F1 标准库**：`RCC_APB2PeriphClockCmd(RCC_DIN)`、`GPIO_Mode_Out_PP`、`RGB_PIN_L/H = GPIO_WriteBit(PORT_DIN, GPIO_DIN, Bit_RESET/SET)`（注释「需要配置为强推挽输出」）、`WS2812_MAX 8`、`LedsArray/ledsCount/nbLedsBytes` 全局、`delay_0_30us()` 自旋 + `delay_us(285)`、默认宏 `RCC_DIN=GPIOB / GPIO_DIN=GPIO_Pin_12`（页面默认 PB12）。
- 页面结构：bsp_ws2812.c（重）/bsp_ws2812.h/main（4 代码块；main 演示呼吸灯序列——剔除；演示数据（颜色数组）不入库）。
- **页面缺陷清单（已取证，全部 notes 记录 + 守卫防回潮）**：
  1. **延时循环条件写反 ×4**：`for(k = 0; i < 0; i++);`（L74/L83 示例段、L225/L234 实现段）——0 次迭代、脉宽全丢（照抄灯不亮；j/k 计数变量错乱）；实现按正确写法重写（k < N）。
  2. **越界**：`LedId > ledsCount`（L155）应为 `>=`——LedId=8 时越界写 `LedsArray[24..26]`；修正为 ` >= ` 并同 mspm0 版「越界忽略」语义。
  3. **时序按 12MHz 标注**（L52/L280：NOP×5≈69ns）而本工程 **72MHz**（SystemInit）——页面脉宽标注作废；**按时序手册重写**：位 1 = 高 1us 级（580ns-1us）+ 位 0 = 高 220-380ns，位周期 ≈1.25us；实现照 mspm0 版结构（`delay_us(1)` + 0.25us 精确换算，f = 72MHz 换算宏；真机微调留 notes）。
  4. **.h 声明无定义**：`setLedCount/getLedCount/RGB_LED_Write1`（L281-282/L289）页面上游残留——不声明不实现（实现 = 本模块 mspm0 对齐 API）。
- 颜色 0xRRGGBB + **GRB 发送序** 页面正确（与 mspm0 版实现一致——set_color 内 R/G 换位）。
- mspm0 版 API（对齐目标）：ws2812.h 见库内（init/set_led_count/led_count/set_color/set_rgb/refresh；WS2812_MAX 8；GRB 缓冲序）。

**换算实现**：`gpio_init(WS2812_GPIO, WS2812_PIN, OUT_PP)`（强推挽——ml_gpio OUT_PP 即推挽；页面注释「强」= 速度/驱动能力，F1 GPIO_Speed_50MHz 由 ml_gpio 内定）+ `gpio_set` 位操作（L/H 宏）+ 忙等延时（delay_us + 自旋换算，**按 72MHz 重写**——页面 12MHz 标注弃用、反写循环弃用，照 mspm0 ws2812.c 结构）；依赖 "delay"（delay_us）。

**引脚与默认脚（同选概率最低推理）：**
- pins：`WS2812_DIN`（type `gpio_out`，default **PA8**，required true，macros `[WS2812_GPIO, WS2812_PIN]`）。
- pin_config.h 新宏段：`#define WS2812_GPIO GPIO_A` / `#define WS2812_PIN Pin_8`（注释：默认 PA8 = 叠 `IR_BEAM`（对射）+ `GRAY_D5`（巡线灰度）——幻彩灯带与「红外对射/巡线」不同框、同选概率最低；**页面默认 PB12 不采用**（PB12-15 本批已派 ttp224 四脚 + DIP/GRAY 三重叠，且灯带与拨码/巡线同框概率低于 ttp224）；刻意不叠灯族（LED PC13-15 板载灯——彩灯常代替板载灯做指示，同框概率高）与声光件；同选经绑定消解）。
- 位时序性能：PA8 无特殊引脚阻塞；F103 72MHz 忙等 1.25us/位（24 位/灯 × 8 灯 ≈ 240us/刷新）——不占 TIM/PWM，与调度共存安全。

**被谁阻塞：** 无——可立即开始（本批最重件，可后做）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/ws2812/code/ws2812_stm32.c/.h`（UTF-8；.c include 本模块 .h + pin_config.h + headfile.h；零引脚字面量；时序常量与换算宏与 mspm0 版同构；GRB 缓冲序注释保留；页面 WS2812_MAX 8 保留）
- [x] manifest.json platforms 增 stm32：files `[code/ws2812_stm32.c, code/ws2812_stm32.h]`、dependencies `["delay"]`（stm32 侧）、verified false、hardware_bound false、pins 如上、kit（8 位 WS2812 RGB 全彩 LED 模块）、source_url `https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/control/ws2812-color-rgb-led.html`、notes（手册路径+原页+网盘+采购 + **页面缺陷清单 4 条**（反写循环 ×4/越界 >=/12MHz 时序弃用/.h 声明无定义）+ 时序实现（800kHz 忙等/72MHz 换算）+ 页面默认 PB12 弃用理由 + 默认脚推理 + 演示数据不入库 + 未上板——真机时序精度留验证）
- [x] pin_config.h 增 `WS2812_GPIO/WS2812_PIN`
- [x] 测试 `tests/test_module_ws2812.py`：形状 + 母版宏存在 + stm32 单选生成全流程 + 守卫（`delay_us` 出现、GRB 换位注释、WS2812_MAX 8、无 printf/main/GPIO_Init/RCC_/TIM/PWM 调用、无 IRQHandler、**无 `for(k = 0; i < ` 页面反写式、无 `LedId > ` 越界式**、编译产物无 `setLedCount`/`RGB_LED_Write1` 残留）
- [x] test_pins.py STM32_MACRO_VALUES 补两宏；test_default_layout.py 白名单 ws2812×ir_beam+pid（PA8 重叠）
- [x] 编译矩阵 UV4 0/0（MAIN_C 调 init+set_led_count+set_color(0,0xFF0000)+refresh，(void) 化）→ verified=true
- [x] wordlist 显示模块分类；词表预算链（slug 已挂接，零改动）
- [x] 中文提交 → resolved → 结论回填

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`；编译日志 `.scratch/wiki-stm32-batch1/matrix/ws2812/build.log`。
- 页面缺陷清单回填（全部 notes + 守卫防回潮）：① 反写延时循环 `for(k = 0; i < 0; i++);` ×4（原理示例 L74/L83 + 实现段 L225/L234——0 次迭代脉宽全丢）→ 时序整体重写；② `LedId > ledsCount`（L155）off-by-one → 修正 `>=`（越界忽略）；③ 时序按 12MHz 标注（NOP×5≈69ns@72MHz）全部作废 → 按数据手册 + mspm0 版结构重写（位 1 = 高 delay_us(1)+低 0.25us、位 0 = 高 0.25us+低 delay_us(1)；0.25us@72MHz = 18×__NOP()；位周期 ≈1.25us）；④ .h 声明 setLedCount/getLedCount/RGB_LED_Write1 无定义 → 不声明不实现（实现 = set_led_count/led_count/refresh 对齐 API）。
- 颜色/GRB 位序正确（0xRRGGBB + set_color 内 R/G 换位，与 mspm0 版一致）；演示数据（buff 数组/流水灯）不入库；页面全局非 static（LedsArray 等）→ static 收敛。
- 默认脚 PA8（页面默认 PB12 弃用——ttp224 四脚 + DIP/GRAY 已占；PA8 叠 ir_beam + GRAY_D5，同选经绑定消解；72MHz 忙等 1.25us/位 × 24 位 × 8 灯 ≈ 240us/刷新不占 TIM/PWM）。
- 测试：test_module_ws2812 7 passed（双平台形状 + 宏存在 + stm32/mspm0 单选生成 + 缺陷守卫）；test_pins/test_default_layout 全绿（26 passed 组合跑）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
