# 05 — vl53l0x 激光测距传感器（B 类新 slug · 仅 stm32 条目 · 待网盘资料）

**要做什么：** 模块库新增 **`vl53l0x`**（库内无此模块——B 类，**仅 stm32 平台条目**，mspm0 缺条目标 missing 警告——B 类拍板口径）：从地阔星页面 + **网盘资料包**提炼 VL53L0X ToF 激光测距驱动（I2C 0x52/8bit=0x29/7bit，mm 输出，量程 2m，6Pin：VCC/GND/SDA/SCL/XSHUT/GPIO）。预期 API（资料到位后按驱动定，对齐 mspm0 风格）：`vl53l0x_init()`（XSHUT 复位序列 + I2C 模式配置——按网盘驱动初始化序列）+ `vl53l0x_read_mm(float *dist_mm)`（单次测量；0=成功/失败码）。**状态：待资料（blocked）**。

**为什么待资料（已取证，%TEMP%\batch4-facts.md）：** 页面仅 **1 个代码块（60 行 main 演示）**——驱动不自洽：全部驱动符号页外（网盘「VL53L0X 文件夹」+ sys.h 位带）；**无引脚表、零寄存器事实**（寄存器/初始化序列/测量时序全缺）。页内另有名实不符：Status 错误粘滞 L103-111、`vl53l0x_data` 无声明 L106、L22「温度范围:2m」串台（记录，不落码）。

**✅ 资料已到位（2026-09，用户下载并解压）**：`sources/materials/lckfb-地阔星移植手册/网盘下载/vl53l0x/STM32F103C8T6_ProjectTemplate/`——**立创 F103C8T6 移植成功工程**（0.5MB）：
- `bsp/VL53L0X/bsp_VL53L0X.c/h`：BSP 封装——**`VL53L0X_Addr 0x52`（8bit = 0x29/7bit）、`VL53L0X_Xshut PBout(7)`（**XSHUT=GPIOB Pin7——位带宏**）、模式枚举（Default 0 / HIGH_ACCURACY 1 / LONG_RANGE 2 / HIGH_SPEED 3）、API = `vl53l0x_reset(dev)/vl53l0x_info()/One_measurement(mode)`（单次测量封装）+ print_pal_error/mode_string/vl53l0x_test（演示——剔除）
- `bsp/VL53L0X/core/inc+src/`：**ST 官方 VL53L0X API 全套**（api/core/ranging/calibration/strings + device/tuning/def）
- `bsp/VL53L0X/platform/inc+src/`：`vl53l0x_i2c.c/h`（**I2C 平台钩子——提炼换算为模块内静态 `_iic_*` 原语族**（批次 2 模式）+ 引脚宏）+ `vl53l0x_platform.c`（日志钩子）
- 工程模板（app/board/sys.h（位带——**换算 ml_gpio 不引入 sys.h**）/bsp_uart/CMSIS/标准库）

**被谁阻塞：** ~~用户下载网盘包~~ **资料已到位——可立即开始**（随批次 10 ili 两件同批收尾节奏）。

**状态：** resolved（2026-09 实施完成——实施与收尾随批次 10 收官，见实施清单全勾 + 结论回填）

**实施清单（资料已到位——可立即开工）：**
- [x] 提炼（**裁剪取舍：官方 core API 全套 ≈20+ 文件——按「最小切片」原则只留初始化/单次测量族**（传递闭包 **75 函数** + refArrayQuadrants 数据段：DataInit/StaticInit/PerformRefCalibration/PerformRefSpadManagement/SetDeviceMode/SetLimitCheckEnable/SetLimitCheckValue/SetMeasurementTimingBudgetMicroSeconds/SetVcselPulsePeriod/PerformSingleRangingMeasurement + 内部闭环；api.c/api_core.c/api_calibration.c 机械提取合并 vl53l0x_core.c/h——函数体原样零改动；数据表 DefaultTuningSettings/InterruptThresholdSettings extern 化防多 TU 重复定义链接错；LOG 宏空实现内联），notes 记录；**不引 sys.h 位带**（PBout 宏换算 ml_gpio）；`One_measurement(mode)` 封装为模块 API——**去演示**（vl53l0x_test/print_pal_error/mode_string/vl53l0x_info/Addr_set 0x54 地址重设返回值未判缺陷③/GetDeviceInfo ID 校验/校准缓存 AjustOK+24c02 路径/中断模式/XTalk/Offset 校准/GetVersion 等全部剔除——One_measurement 在网盘包内仅声明无实现，记录））
- [x] `library/modules/vl53l0x/` 新目录：code/vl53l0x_stm32.c/.h（**API = `vl53l0x_init()`（XSHUT 复位序列 + DataInit）+ `vl53l0x_set_mode(mode)`（页面 BSP 原式）+ `vl53l0x_read_mm(float *dist_mm)`（单次测量封装——0=成功/非0=ST 状态码）+ 模式宏（DEFAULT/HIGH_ACCURACY/LONG_RANGE/HIGH_SPEED——页面 BSP 枚举）**；I2C 钩子 = 模块内静态 `vl53l0x_iic_*` 原语族（批次 2 模式——**SCL OUT_OD 初始化+置高**回修口径 + 页面 Out_PP→OUT_OD/IU 换算（共总线件统一）+ char ack 死变量剔除 + write_word 奇地址 index+1 修正）+ ST 平台层契约函数（VL53L0X_WrByte/WriteMulti 等 10 件）+ 引脚宏 6 个（`VL53L0X_SCL_GPIO/_PIN/_SDA_GPIO/_PIN/_XSHUT_GPIO/_PIN`）；零引脚字面量）+ manifest.json（**仅 platforms.stm32**：files 4 件（core 2 + stm32 2）、dependencies **[]**（delay 走母版内嵌 ml_delay——B 类口径 esp01s/ec11 先例，批 10 死依赖门禁整改）、verified **true**、hardware_bound false、pins 3 行（SCL=PA6/SDA=PA7（共总线——**⚠ 0x29(7bit) 与 tcs34725 同址——互替不可同挂**，notes；与库内其余软 I2C 件地址全异）/XSHUT=PB0（叠 hx711 DT+EC11 SW+rc522 CS——ToF×称重/旋钮/读卡不同框；页面 PB7 弃用（human_ir/GRAY 组常备）））、kit/source_url（wiki 原页 + **立创移植代码来源（网盘路径记 notes）**）、notes（B 类口径+官方 API 全套来源+最小裁剪清单（75 函数闭包）+位带换算+**0x29 同址互替**+页面缺陷记录①-⑧+矩阵 0/0+未上板）+ description（能力方向：ToF 激光测距；无题绑定）
- [x] pin_config.h 宏段（6 宏）
- [x] 测试 test_module_vl53l0x.py（B 类模板：仅平台/形状/pins 3 行/macros/source_url/notes 子串「B 类」「0x29」/单选生成全流程/守卫：无 `PBout`/`PAin`/`sys` 位带、`0x52`/`0x29` 地址、init/read_mm/set_mode 断言、无 printf/GPIO_Init/RCC_、I2C 原语静态化 + 切片负向守卫（范围外演示件零泄露））
- [x] UV4 矩阵（init+set_mode(DEFAULT)+read_mm(&d)，(void) 化）→ **0 error/0 warning** → verified=true
- [x] wordlist 补录（感知传感器/测距 激光测距（VL53L0X）→ lib_modules ["vl53l0x"] + models + "VL53L0X"）
- [x] 中文提交（随批 10 收尾提交序列：工单提交 + 收官提交——见收尾报告）→ resolved → 结论回填（见下）

**结论回填（基于实施 + code-review 两轴 + 测试 + 矩阵）**：
- 资料源：wiki 原页（页内仅 1 个 main 演示块 60 行——驱动符号全页外）+ **立创 F103C8T6 移植工程**（网盘：sources/materials/lckfb-地阔星移植手册/网盘下载/vl53l0x/STM32F103C8T6_ProjectTemplate/bsp/VL53L0X/——BSP 封装 + ST 官方 API 全套 + I2C 钩子）。
- 裁剪清单：官方全套（api.c 82KB/api_core.c 65KB/api_calibration.c 37KB + 6 头 + 中断阈值表）→ 最小切片 = 传递闭包 **75 函数** + refArrayQuadrants 数据段（vl53l0x_core.c/h 单文件合并）——未裁剪演示族（见工单注释）全部范围外。
- 0x29 同址：0x52(8bit 写) = 0x29(7bit) 与 tcs34725 同址 → **互替不可同挂**（同址双选必冲突——选其一，同选经引脚绑定换独立总线或换件；bmp180×ms5611 0xEE 同款口径）。
- 默认脚：SCL=PA6/SDA=PA7（共挂批次 2/3/4 软 I2C 总线——电平口径 OUT_OD/IU 与共总线件统一 + SCL 置高回修）+ XSHUT=PB0（页面/移植工程默认 PB7 + PB8/PB9 均弃用）。
- 矩阵：.scratch/wiki-stm32-batch4/matrix/run_vl53l0x_matrix.py——UV4（ARMCC V5.06）0 error/0 warning（Code=15388/RO=332/RW=716/ZI=2012）；全量 pytest 绿（含 test_pins/test_default_layout 补录）。
- 未上板（软 I2C 时序/ToF 真机校准/量程验证留后续——notes）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。

**验收标准：** 资料下载 → 实施 → 全部 checkbox；pytest 绿；矩阵 exit 0。资料未到 = 本工单保持待资料，不阻塞批次 4 验收（01-04 件完成即批 4 可收尾，本件随资料到位单件收尾）。
