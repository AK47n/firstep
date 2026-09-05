# 01 — ads1115 四通道 16bit 外扩 ADC（软 I2C，手册 sensor--ads1115-multichannel-a-to-d-sensor.md）

**要做什么：** 模块库新增 `ads1115` 条目（仅 mspm0）：从手册提炼 ADS1115 驱动为纯驱动切片——软 I2C 位操作（照 aht10 先例，2 GPIO，SDA 方向运行时切换，延时走 delay 模块，不占硬件 I2C 外设/TIMER）：`ads1115_init()` + `ads1115_read(ch)`（16bit 有符号原始值，MUX 通道选择 0-3）+ `ads1115_read_voltage(ch)`（换算电压）+ 配置服务函数（set_config/set_gain/set_data_rate/set_address）；与库内 adc 模块（板载 12bit 单通道）在 notes 写明分工；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 02/03/04 独立）。

**状态：** resolved

**验收：**

- [x] 代码提炼：`code/ads1115.c/h`（IIC 原语静态化 `ads1115_iic_*` 照 aht10；WriteADS1115→`ads1115_write_register`；ReadADS1115→`ads1115_read(ch)` 原始值 + `ads1115_read_voltage`；页面负数换算缺陷剔除记 notes；地址 0x90 宏保持页面原式 + set_address 服务函数）
- [x] 母版 `mspm0.syscfg`：`ADS1115` GPIO 实例（SCL/SDA 输出，SDA 运行时切换类照 AHT10 注释；默认 PA16/PA17——与 DC_MOTOR 编码器 AA/AB + RC522 MOSI/MISO 重叠，同选经引脚绑定消解）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"ADS1115": ("ads1115",)`
- [x] `manifest.json`：dependencies ["delay"]；pins SCL/SDA；notes 含手册路径+原页+网盘链接+改造要点+与 adc 模块分工说明+负数换算缺陷记录；verified=true
- [x] wordlist.json「感知传感器」类补录 ADS1115 方案（lib_modules 挂接）+ models 词条
- [x] 测试：test_pins 双角色映射 / test_pin_bindings PA16/PA17 计数 / test_syscfg_prune 断言 / 新增 test_module_ads1115.py（电压公式源码守卫）——全部通过
- [x] 编译验证：run_ads1115_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录
- [x] 中文提交 + 工单 resolved + code-review

**结论：** 2026-09-06 完成并提交。软 I2C 位操作（AHT10 先例）；`ads1115_init/read(ch)（16bit 有符号原始值，MUX 切换）/read_voltage/写配置服务（write_register/write_config/set_gain/set_data_rate/set_address）`；页面 `(65535-num)*0.000125` 负数换算缺陷修正（int16_t 补码 `raw/32768×FSR`）；与库内 adc（板载 12bit MEM0）分工记 notes；默认 PA16/PA17；单选生成 → SysConfig CLI → gmake 0 error / 0 warning（PASS）；code-review 双轴通过。未上板。
