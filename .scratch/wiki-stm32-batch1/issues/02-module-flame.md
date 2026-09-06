# 02 — flame 火焰传感器（ADC 通道 + 反向映射，手册 sensor--flame-sensor.md）

**要做什么：** 模块库 `flame` 新增 **stm32 平台条目**（mspm0 条目零改动）：从地阔星页面提炼红外火焰驱动为纯驱动切片，API 与 mspm0 版完全对齐——`flame_init()`（经库内 adc 模块初始化对应通道）+ `flame_read_percent()`（返回 0-100% 火焰相对强度，**反向映射** `(1 - value/4095)×100`——红外光越强 ADC 值越小百分比越高，页面原式；5 次快速平均，页面 SAMPLES 30 次改 5 次快平均先例）。

**关键事实（已取证）：**
- 页面 = **F1 标准库**：`RCC_APB2PeriphClockCmd(RCC_FLAME_GPIO/RCC_FLAME_ADC)`、`RCC_ADCCLKConfig(RCC_PCLK2_Div6)`、`GPIO_Mode_AIN`（AO 模拟输入）+ `GPIO_Mode_IPU`（DO 上拉输入）、ADC 序列（RegularChannelConfig/SoftwareStartConvCmd/GetConversionValue）、`stm32f10x.h`。
- **页面默认脚 = AO:PA5（ADC1_CH5）/ DO:PA6**（自洽：反向映射、红外越强 ADC 越小）。
- 页面双通道：AO（模拟）+ DO（数字，LM393 阈值比较）；**DO 按 mspm0 先例「未用不声明」**——不落 pins（需要时骨架经 gpio 直读/阈值由模块可调电阻控制），notes 写明。
- **页面缺陷清单（notes 记录）**：① `delay_1ms(20)`——ml_delay 无 delay_1ms，换算 `delay_ms(20)`；② `printf("%d", Get_FLAME_Percentage_value())` 用 %d 打 unsigned int（演示段剔除，不落码）；③ SAMPLES 30×25ms 过慢——改 5 次快平均（mspm0 批先例，真机行为差异 notes）。
- mspm0 版 API（对齐目标）：flame.h 见库内（FLAME_ADC_MAX 4095、FLAME_ADC_SAMPLES 5、flame_init、flame_read_percent；默认独立 ADC MEM6/PA22）。

**换算实现**（ml_* 母版 API）：`flame_init` = adc 模块通道初始化（`adc_init(ADC_1, FLAME_AO_CH)`，依赖 ["adc"]）；`flame_read_percent` = 5 次 `adc_get(ADC_1, FLAME_AO_CH)` 累加平均 → `(1 - avg/4095)×100`。

**引脚与默认脚（stm32「同选概率最低」推理）：**
- pins：`FLAME_AO`（type `adc`，default **PA5**，required true，macros `[FLAME_AO_CH]`——adc 角色渲染照 test_module_adc 先例（PAx→ADC_Channel_N））。
- pin_config.h 新宏段：`#define FLAME_AO_CH ADC_Channel_5`（注释：默认 PA5 = **页面原脚**（用户照页面接线即插即用）；**独立通道** ADC_Channel_5——与 adc 模块 ADC_CH0/1 不共读（与 mspm0 版独立 MEM6 语义同构；薄封装共读是 MEM 满后的回退，本件有通道可取）；PA5 现状叠 `MOTOR_B_ENC_DIR`（编码器方向输入，gpio_in）——火焰与编码器闭环不同框、同选概率最低，同选经引脚绑定消解（换其它 ADC 脚 PA0-7/PB0-1））。
- 设计依据：stm32 ADC 可达脚仅 PA0-7/PB0-1 且全被既有角色占用；选 PA5 避让 motor PWM 主脚（PA0/1）与 debug（PA2/3）、编码器线（PA4/PB5/EXTI）——PA5 为最「不同框」的 ADC 脚。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/flame/code/flame_stm32.c/.h`（UTF-8；.c include 本模块 .h + `pin_config.h` + `headfile.h`；零引脚字面量、无 `ADC_Channel_N` 字面量（用 FLAME_AO_CH 宏）——若测试字面量扫描报红按「API 对偶枚举豁免」先例（mq2/us016/adc 白名单）登记并注明理由（本件直接用宏，无需豁免新增）
- [x] `manifest.json` platforms 增 stm32：files `[code/flame_stm32.c, code/flame_stm32.h]`、dependencies `["adc"]`（stm32 侧依赖，mspm0 侧已有）、verified false、hardware_bound false、pins 如上、kit（页面「模块来源」套件名）、source_url `https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/flame-sensor.html`、notes（手册路径+原页+网盘+采购 + 页面缺陷清单①②③ + 「AO 独立通道/DO 未声明」决策 + 反向映射保留页面原式（相对强度非绝对值）+ 与 mspm0 分工 + 未上板）
- [x] `library/masters/stm32/pin_config.h` 增 `FLAME_AO_CH` 宏段（注释如上）
- [x] 测试 `tests/test_module_flame.py`：形状 + 母版宏 `#define FLAME_AO_CH\s+ADC_Channel_5` + stm32 单选生成全流程（依赖 adc 展开；.uvprojx 含 flame_stm32.c）+ 守卫（反向映射原式 `(1 - .../4095)`、无 `printf`/`main`/`GPIO_Init`/`RCC_`/`delay_1ms`、FLAME_ADC_SAMPLES 5）
- [x] `tests/test_pins.py` STM32_MACRO_VALUES 补 FLAME_AO_CH；test_default_layout.py 白名单登记 flame×motor（PA5 重叠——MOTOR_B_ENC_DIR）
- [x] 编译矩阵：UV4 0 error/0 module warning（MAIN_C 调 flame_init+flame_read_percent，(void)flame_read_percent() 化）→ verified=true 回写
- [x] wordlist 感知传感器分类（沿用 mspm0 批次口径）；词表预算链实测（slug 已挂接，零改动）
- [x] 中文提交 → resolved → 结论回填

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`（依赖 adc 展开——adc stm32 条目 files=[] 内嵌母版 ml_adc）；编译日志 `.scratch/wiki-stm32-batch1/matrix/flame/build.log`。
- 页面缺陷清单回填（全部 notes + 守卫）：① `delay_1ms(20)` → ml_delay 无此 API（换算 delay_ms(20)；本实现按快平均语义省略采样延时）；② main 演示 `%d` 打 unsigned int（演示剔除）；③ SAMPLES 30×25ms 过慢 → 5 次快平均（真机行为差异 notes）。
- AO 独立通道：FLAME_AO_CH = ADC_Channel_5（PA5，页面原脚）——与 adc 模块 ADC_CH0/1 不共读（ml_adc 的 adc_get 每次先写 SQR3 选通道，顺序调用互不干扰）；DO 未用不声明（LM393 阈值 = 可调电阻，mspm0 先例）。
- 测试：test_module_flame 7 passed（双平台形状 + 宏存在 + stm32/mspm0 单选生成 + 公式守卫）；test_pins/test_default_layout 全绿（27 passed 组合跑）。

**验收标准：** 全部 checkbox 完成；pytest 相关测试绿；矩阵 exit 0。
