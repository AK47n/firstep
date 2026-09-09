# 03 — gp2y1014au 模块（GP2Y1014AU 粉尘传感器，手册 sensor--gp2y1014au-dust-sensor.md）

**要做什么：** 模块库新增 `gp2y1014au` 条目（仅 mspm0）：从手册提炼粉尘驱动为纯驱动切片——ADC 模拟量读 AOUT + GPIO 输出脉冲驱动模块红外 LED。**ADC 薄封装**（依赖库内 adc 模块共享 ADC12_0 MEM0 槽位，默认 PA24/A0_3——无新 ADC 通道/实例）＋**新 GPIO 输出实例 `GP2Y1014`/LED（薄封装的器件必需例外：GP2Y1014AU 必须由主控按页面时序脉冲驱动 LED（clear→280us→采样→40us→set→9680us 的 10ms 周期），无 LED 脚传感器不工作——人工复核记 notes）**。`gp2y1014_init()` + `gp2y1014_read_dust()`（float 出粉尘浓度**估算**——页面 Read_dust_concentration 原式 `0.17×value − 0.1`；页面 Filter（10 点静态滑动平均）**内嵌为模块内静态环形缓冲**（页面滤波逻辑简单——照库依赖先例取舍内嵌并记 notes，不依赖库内 filter 可选配套件）；页面 SAMPLES 30×2ms 改 5 次快平均（页面 30×2ms ≈ 60ms 远超 10ms LED 周期、时序本就不自洽，改后单次读 ~0.3ms 级）；LED 脉冲时序走 delay 模块（delay_us，`dependencies: ["adc", "delay"]`——忙等不占 TIMER）；页面 ADC 中断改经 adc 模块 API 轮询（共享实例 IRQHandler 强符号唯一）；notes 写明粉尘浓度估算非精标（页面公式对演示值/ADC 量程标定不明确——读数为相对参考值、烟/尘区分不能、需标准粉尘标定）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-09 完成并提交（cfeafd8f）。GP2Y1014AU 粉尘 = ADC 模拟量薄封装（依赖 adc 模块共读 ADC12_0 MEM0、默认 PA24）+ **LED 驱动 GPIO 输出实例 GP2Y1014/LED 默认 PA1（薄封装唯一例外：器件必需——内置红外 LED 必须主控脉冲驱动（页面 Read_dust_concentration 时序：LED 亮→280us→采样→40us→LED 关→9680us 的 10ms 周期），无此脚传感器不工作；PA0/PA1 不可作 GPIO 输入（2026-09-06 实证），GPIO 输出可配 PA0——ir_remote_tx 先例，PA1 同型经编译矩阵 SysConfig CLI 实证合法；默认 PA1 与 I2C_0 SCL 重叠——粉尘与姿态不同框、同选概率最低）**；`gp2y1014_init` + `gp2y1014_read_dust` 出浓度估算值（页面原式 0.17×value−0.1——相对估算非精标：页面公式对演示值/ADC 量程标定不明确（0.17×4095−0.1≈696 超出常规 mg/m³ 量程）、红外漫反射对烟尘/水汽同样响应（烟/尘区分不能）、绝对浓度需标准粉尘标定）；页面 Filter（10 点静态滑动平均、首次以首值填满窗口）内嵌为模块内静态环形缓冲（照库依赖先例取舍不依赖库内 filter 可选配套件）；页面 SAMPLES 30×2ms（≈62ms 远超 10ms LED 周期——页面时序本不自洽）改 5 次快平均；页面 ADC 中断改轮询（共享实例强符号唯一）；dependencies [adc, delay]（LED 时序走 delay 模块忙等不占 TIMER）；词表感知传感器 +粉尘传感器；单选生成 → SysConfig CLI（PA1 合法）→ gmake 0 error/0 warning（verified=true）；i2c_bus_share 测试按 ir_distance/ttp224 绑走先例恢复纯 I2C 共享组（gp2y1014au LED 默认 PA1 混入 I2C 总线组时）；code-review 通过。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--gp2y1014au-dust-sensor.md` 「代码块」章节抽完整 `bsp_dust.c/h` → 改造为 `code/gp2y1014au.c` + `code/gp2y1014au.h`：去 main/printf、函数名规范化（`gp2y1014_init/read_dust`，去 `Dust_Init/ADC_GET/Get_ADC_Value/Filter/Read_dust_concentration` 命名）、页面 ADC 中断改轮询、LED 脉冲时序按页面原样（clearPins = LED 亮 + delay_us(280) + 5 次快平均采样 + delay_us(40) + setPins = LED 关 + delay_us(9680)）、Filter 10 点滑动平均内嵌（static 环形缓冲，首次 10 份填充——页面语义保留、`sum / 10` 整数截断语义保留）
- [x] 母版 `mspm0.syscfg`：新 GPIO 输出实例 `GP2Y1014`/LED（direction OUTPUT、initialValue SET——LED 空闲 = 关（引脚高，页面 clear=亮/set=关极性原样）、默认 `PA1`——PA1 现状仅 I2C_0 sclPin（ml_mpu6050）1 个默认用户：粉尘监测与姿态采集不同框、同选概率最低；GPIO 输出可配 PA0/PA1（2026-09-06 实证仅输入不可，ir_remote_tx PA0 先例）；编译矩阵 SysConfig CLI 实证，拒绝则改次选脚；与 PA0 IR_TX 刻意错开）；实例注释写薄封装例外与器件必需性
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：`ADC12_0` 元组增 `"gp2y1014au"` + 新 `"GP2Y1014": ("gp2y1014au",)` 登记
- [x] `manifest.json`：`dependencies: ["adc", "delay"]`；mspm0 平台条目（files/verified 初始 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（案例 jclk——页面无资料链接）+改造要点+**LED 时序/极性说明+薄封装例外+滑动平均内嵌+非精标（0.17×value−0.1 相对参考、烟/尘区分不能、需标定）**）；pins：`GP2Y1014_AO_CH0` = adc 默认 PA24 + `GP2Y1014_LED` = gpio_out 默认 PA1（照 IR_TX/PA0 声明方式）；简介判据：能力方向（粉尘/PM2.5 监测）+ 无题绑定 + ADR 0009
- [x] wordlist.json 补录：「感知传感器」加「GP2Y1014AU 粉尘传感器（PM2.5）」方案挂 `lib_modules: ["gp2y1014au"]`，models 加 "粉尘传感器"
- [x] 测试：新增 `tests/test_module_gp2y1014au.py`（照 test_module_mq2.py：manifest 结构（deps ["adc","delay"]、双角色）+ 单选生成（syscfg 保留 ADC12_0 + `const GP2Y1014`、模块文件落盘 + delay 依赖文件落盘、main.c 调 init/read_dust 过静态门禁）+ 公式守卫（`0.17f`/`0.1f`、`280u`/`40u`/`9680u`、`GP2Y1014_FILTER_WINDOW` 10、`delay_us`、`ADC_Channel_0`）+ 无 IRQHandler 守卫 + notes 守卫（「非精标」「LED」「滑动平均」））；`tests/test_pins.py` 豁免元组增 `"gp2y1014au"` + `MSPM0_DEFAULT_MAP` 增 (`gp2y1014au`, `GP2Y1014_LED`) → (`GP2Y1014`, "LED")；`tests/test_syscfg_prune.py` ADC12_0 新消费方 + GP2Y1014 实例断言；`tests/test_pin_bindings.py` 刻意表新增 `"PA1": 2` 条目（I2C_0 sclPin + GP2Y1014 LED）+ PA24 注释补本批共读
- [x] 编译验证：`run_gp2y1014au_matrix.py` 单选生成（含 GPIO 实例 → SysConfig CLI 验证 PA1）→ gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交、工单 resolved


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
