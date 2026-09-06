# 05 — vl53l0x 激光测距传感器（B 类新 slug · 仅 stm32 条目 · 待网盘资料）

**要做什么：** 模块库新增 **`vl53l0x`**（库内无此模块——B 类，**仅 stm32 平台条目**，mspm0 缺条目标 missing 警告——B 类拍板口径）：从地阔星页面 + **网盘资料包**提炼 VL53L0X ToF 激光测距驱动（I2C 0x52/8bit=0x29/7bit，mm 输出，量程 2m，6Pin：VCC/GND/SDA/SCL/XSHUT/GPIO）。预期 API（资料到位后按驱动定，对齐 mspm0 风格）：`vl53l0x_init()`（XSHUT 复位序列 + I2C 模式配置——按网盘驱动初始化序列）+ `vl53l0x_read_mm(float *dist_mm)`（单次测量；0=成功/失败码）。**状态：待资料（blocked）**。

**为什么待资料（已取证，%TEMP%\batch4-facts.md）：** 页面仅 **1 个代码块（60 行 main 演示）**——驱动不自洽：全部驱动符号页外（网盘「VL53L0X 文件夹」+ sys.h 位带）；**无引脚表、零寄存器事实**（寄存器/初始化序列/测量时序全缺）。页内另有名实不符：Status 错误粘滞 L103-111、`vl53l0x_data` 无声明 L106、L22「温度范围:2m」串台（记录，不落码）。与地猛星线 nrf24l01（页外符号但页内驱动主体够、人工复核剔除分支后入库）不同——本页**纯演示**，无驱动主体可提炼。

**需要用户下载的资料（下载清单）：**
1. 页面网盘链接 2 条（见 `sources/materials/lckfb-地阔星移植手册/网盘索引.md` 的 `vl53l0x-laser-distance-sensor` 行——新式/旧式各 1）。
2. 必需内容：**VL53L0X 驱动源码**（ST 官方 API 或立创封装：vl53l0x.c/h + I2C 读写钩子——看它用的是标准库/位带）、**VL53L0X 寄存器表/初始化序列说明**、**接线图（含 XSHUT/GPIO 用途）**。
3. 放置建议：`sources/materials/lckfb-地阔星移植手册/网盘下载/vl53l0x/`（解压后目录结构保留），下载完成告知后实施本工单。

**被谁阻塞：** 用户下载资料（网盘包）。01-04 不依赖本件，可并行开工。

**状态：** blocked（待资料——下载到位后可见）

**批次 4 收尾记录（2026-09-06）：** `sources/materials/lckfb-地阔星移植手册/网盘下载/vl53l0x/` 目录**不存在**（`网盘下载/` 目录尚未建立——用户未下载网盘资料包）。本工单保持 **blocked（待资料）**，不阻塞批次 4 验收（01-04 件已完成）。下载清单见上（网盘 2 条链接：`网盘索引.md` 的 `vl53l0x-laser-distance-sensor` 行——新式/旧式各 1；必需内容 = VL53L0X 驱动源码 + 寄存器表/初始化序列 + 接线图含 XSHUT/GPIO 用途）；用户下载并放入 `sources/materials/lckfb-地阔星移植手册/网盘下载/vl53l0x/` 后通知，即按本工单实施清单逐项完成。

**实施清单（资料到位后逐项）：**
- [ ] 解压资料 → 确认驱动自洽：提炼驱动（去 main/printf、API 规范化、ADC 无、I2C 原语族照批次 2 模式——若立创驱动自带 I2C 位操作则换算为静态 `_iic_*`；XSHUT/GPIO 脚 = 附加 gpio_out 角色或走绑定）
- [ ] `library/modules/vl53l0x/` 新目录：code/vl53l0x_stm32.c/.h + manifest.json（**仅 platforms.stm32**：files/pins（I2C_SCL/SDA + 可选 XSHUT，default 低同框分配——参考 dht11/ds18b20 推理，待资料后按接线图定）/verified 初 false/kit/source_url=wiki 原页/notes 手册路径+网盘+驱动来源+页面缺陷记录（main-only 页面、Status 粘滞等）+未上板）
- [ ] pin_config.h 宏段（照资料引脚定）
- [ ] 测试 test_module_vl53l0x.py（形状+宏存在+单选生成全流程+守卫）
- [ ] UV4 矩阵 0/0 → verified=true
- [ ] wordlist 补录（感知传感器/测距分类 + lib_modules 挂接——**B 类口径：与其它新模块同批补**）
- [ ] 中文提交 → resolved → 结论回填（含资料来源与提取要点）

**验收标准：** 资料下载 → 实施 → 全部 checkbox；pytest 绿；矩阵 exit 0。资料未到 = 本工单保持待资料，不阻塞批次 4 验收（01-04 件完成即批 4 可收尾，本件随资料到位单件收尾）。
