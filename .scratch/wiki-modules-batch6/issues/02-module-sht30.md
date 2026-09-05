# 02 — sht30 温湿度传感器（软 I2C，手册 sensor--sht30-temp-humi-sensor.md）

**要做什么：** 模块库新增 `sht30` 条目（仅 mspm0）：从手册提炼 SHT30 驱动为纯驱动切片——软 I2C 位操作（照 aht10/批次 5 先例，2 GPIO，SDA 方向运行时切换，延时走 delay 模块，不占硬件 I2C 外设/TIMER）：`sht30_init()` + `sht30_read(&t,&h)` / `sht30_read_temperature(&t)` / `sht30_read_humidity(&h)`（出参，0.01 系数换算按页面，CRC8 校验保留）；notes 写明与库内 aht10/dht11 的分工；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 01/03/04 独立）。

**状态：** resolved

**结论：** 2026-09-07 完成并提交。软 I2C 位操作（AHT10 先例，SDA 方向运行时切换，延时走 delay 模块）；`sht30_init`（0x2130 周期模式）+ `sht30_read(&t,&h)`（0xE000 读命令、应答重试 ≤20×2ms、6 字节回包、CRC8 0x31/0xFF 原式、0.01 系数换算；返回 0=成功/1-5=页面失败码）+ `sht30_read_temperature/read_humidity`（出参封装）；页外 `extern double Temperature, Humidity` 全局收敛为出参；页面 `IIC_Stop` 注释掉（重复起始）按页面原样；与库内 aht10/dht11/mlx90614 分工写 notes；默认 PA28/PA31；单选生成 → SysConfig CLI → gmake 0 error/0 warning（PASS）；code-review 双轴通过。未上板。

**验收：**

- [x] 代码提炼：`code/sht30.c/h`（去 main/printf；函数名规范化 `sht30_init/read/read_temperature/read_humidity`；IIC 原语静态化 `sht30_iic_*` 照 aht10；页外 `extern double Temperature, Humidity` 全局收敛为出参；`SHT31_Write_mode` → `sht30_write_mode` 保留页面不补 STOP）
- [x] 协议按页面：地址 0x44<<1；init 写周期模式 0x2130；read = 发读命令 0xE000 → 重发读地址应答重试 ≤20×2ms → 6 字节（温度/湿度各 2 字节 + CRC）→ CRC8（0x31/0xFF 原式）两组校验 → 换算 `t=(d/65535.0)*175.0-45`、`h=(d/65535.0)*100.0`；失败返回 1-5（0=成功；1/2/3 = 命令/地址应答失败、4 = 读地址应答超时、5 = CRC 校验失败——页面失败码）；页面规格 ±0.3℃/±2%RH、数据手册典型 ±0.2℃/±2%RH，notes 注明
- [x] 母版 `mspm0.syscfg`：`SHT30` GPIO 实例（SCL/SDA 输出，SDA 运行时切换——AHT10 先例）；默认 SCL=PA28/SDA=PA31（与 IMU601 UART0/HX711/FINGERPRINT_UART 重叠——温湿度与姿态/称重/身份不同框同选概率最低；不与批次 5 八脚相撞），重叠对登记 test_pin_bindings 刻意表
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"SHT30": ("sht30",)`
- [x] `manifest.json`：dependencies ["delay"]；pins SCL/SDA；notes 含手册路径+原页+网盘链接+改造要点+与 aht10（软 I2C 0.1 级）/dht11（单总线 ±2℃）/mlx90614（非接触）分工+页面不补 STOP 记录+编译记录；verified=true
- [x] wordlist.json「感知传感器」类补录 SHT30 方案（lib_modules 挂接）+ models 词条
- [x] 测试：test_pins MSPM0_DEFAULT_MAP 增 SHT30_SCL/SDA；test_pin_bindings PA28/PA31 计数 3→4；test_syscfg_prune SHT30 断言；新增 test_module_sht30.py（CRC8 0x31/0xFF 守卫 + 0.01 公式守卫 + 0x2130/0xE000 常量守卫）
- [x] 编译验证：run_sht30_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录
- [x] 中文提交 + 工单 resolved + code-review
