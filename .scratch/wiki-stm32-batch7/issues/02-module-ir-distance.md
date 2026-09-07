# 02 — ir_distance 红外测距（ADC 薄封装 + 3.3V 宏化，手册 sensor--Infrared-distance-sensor.md）

**要做什么：** 模块库 `ir_distance` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼红外测距驱动为纯驱动切片（ADC 薄封装），API 与 mspm0 版完全对齐：`ir_distance_init()` + `ir_distance_read_distance_cm()`（float 厘米——**与 mspm0 同名（ir_distance.h L21）**；采样 = **`IR_DIST_ADC_SAMPLES 10`**（宏名照 mspm0 ir_distance.c L20——**无 ANCE**；值 10 = 手册 Get_Adc_Value(10.f) 原值，页面 30 次→10 次，**非 5 次**）；`V=(sum/10)/4095×3.3`（**页面硬编码 3.5V、mspm0 已改 3.3 宏化**——3.3V 供电下页面换算系统偏低约 6%；整数平均 sum/SAMPLES 照 mspm0）→ `Distance=60.374×V^(-1.16)`（cm；20-150cm 段；<15cm 电压跌落非线性区——notes 不保证））。

**关键事实（%TEMP%\batch7-facts.md）：** F1；页面默认 AO=PA5；页面 L44「下图曲线图」实为 0 图（无查表——按公式）；互替 us016（同脚——互替同脚先例）；出参 cm。

**引脚：** pins `IR_DISTANCE_AO`（adc，PA5，macros `[IR_DISTANCE_AO_CH]`）；pin_config.h：`#define IR_DISTANCE_AO_CH ADC_Channel_5`（注释：AO 默认 PA5 与 us016 互替同脚（二选一）；ADC 共享组；同选经绑定换 PA0/PA1）。

**被谁阻塞：** 无——可立即开始（与 us016 对仗）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/ir_distance/code/ir_distance_stm32.c/.h`（独立 stm32 头；adc_init/adc_get + 10 次快平均；`IR_DIST_VREF_V 3.3f` 宏化——照 mspm0 宏名（无 CE）；math.h powf（`-1.16f`）——ARMCC 标准库自动含；全 0 防护）
- [x] manifest.json platforms 增 stm32：files、dependencies ["adc"]、verified true、hardware_bound false、pins 1 行、kit/source_url（wiki 原页 `.../sensor/Infrared-distance-sensor.html`——**大小写敏感**）、notes（手册路径+原页+网盘+**3.5→3.3 宏化记录**+无查表+<15cm 非线性+互替 us016+ADC 共享组+未上板）
- [x] pin_config.h 增 `IR_DISTANCE_AO_CH`
- [x] 测试 `tests/test_module_ir_distance.py`：形状+宏存在+单选生成+mspm0 零改动+守卫（`3.3f`（**无 3.5f**）、`60.374f`、`-1.16f`、**`IR_DIST_ADC_SAMPLES 10`**（宏名无 ANCE、值 10——守卫断言，防回写成 5）、无查表数组、全 0 防护、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补宏；test_default_layout.py 白名单 PA5 组 +1
- [x] UV4 矩阵 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**结论回填（2026-09-07）：全部完成。stm32 条目 = ADC 薄封装件（页面 ADC 序列收敛 ml_adc）；默认 AO = ADC_Channel_5（PA5——页面原脚即共读点，ADC 共享组并入 batch5 PA5 共读组——flame+8+7+2 = 18 ADC 角色同脚；与 us016 **互替件同脚**——同一物理脚只能接一件，互替同脚先例语义（二选一接入无需另消解），罕见同选经绑定其一换 PA0/PA1；白名单 PA5 组登记）；IR_DISTANCE_AO_CH 宏入 pin_config.h；API 与 mspm0 全对齐（ir_distance_init + ir_distance_read_distance_cm——同名 ir_distance.h L21；出参 cm——页面 main L258 直接打印即 cm）；换算 V=raw/4095×IR_DIST_VREF_V（**3.3f——页面硬编码 3.5V 宏化修正（3.3V 供电下页面换算系统偏低约 6%）**）+ Distance=60.374×V^(-1.16)（stm32 用 powf 单精度——C8T6 无硬件 FPU 软浮点省栈，与 mspm0 double pow 同精度级，notes 记录）+ **页面 L44「下图曲线图」实为 0 图——无查表按公式**；**<15cm 电压跌落非线性区注释**（安装勿入盲区）；全 0 采样返回 0.0f（防 pow(0,-1.16) 溢出——原版输出 inf，mspm0 先例）；**IR_DIST_ADC_SAMPLES 10**（宏名照 mspm0 无 ANCE、值 10 = 手册 Get_Adc_Value(10) 原值——页面 30 次连续累加改 10 次、非 5 次快平均口径）；3Pin 无 DO 不声明；verified=true（UV4 0 error/0 module warning，2026-09-07）+ kit/source_url+notes；wordlist 零补录（ir_distance 已在词表）；mspm0 零改动；description 双平台化；**两平台不同口径说明（notes）**：mspm0 本件独立 MEM3 有槽位、stm32 无空闲通道共读 PA5；test_pins 宏表 +IR_DISTANCE_AO_CH、test_default_layout PA5 白名单 +ir_distance.IR_DISTANCE_AO。**

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
