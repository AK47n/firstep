# 02 — jy61p 六轴姿态传感器（软 I2C，手册 sensor--jy61p-measurement-sensor.md）

**要做什么：** 模块库新增 `jy61p` 条目（仅 mspm0）：从手册提炼 JY61P 姿态驱动为纯驱动切片——软 I2C（页面 IIC_Start/IIC_Stop/IIC_Send_Ack/I2C_WaitAck/Send_Byte/Read_Byte 原语 + writeDataJy61p/readDataJy61p，照 sht30/aht10 先例不占硬件 I2C 外设/TIMER），`jy61p_init()`（器件初始化序列按页面：解锁→Z 轴归零→保存 ×2 轮，各步 200ms）+ `jy61p_read_angles(&roll,&pitch,&yaw)`（页面 get_angle 换算保留：raw/32768×180 ±180° 回绕）+ `jy61p_read_raw` 原始数据读取（可选）；页面 I2C_WaitAck 未拉高 SCL 的时序微瑕照正确版修正并记 notes；选中后生成工程打开即可编译、可调用。

**被谁阻塞：** 无——可立即开始（与 01/03/04 独立；软 I2C 先例同 01）。

**状态：** resolved

**结论：** 2026-09-11 完成并提交。软 I2C 照 sht30 先例；默认 SCL=PA28/SDA=PA31（与 IMU601/FINGERPRINT_UART/HX711/SHT30/MICROWAVE 重叠——姿态与身份/称重/温湿度/微波不同框、同选概率最低；刻意不叠姿态惯配的电机/舵机/显示/无线件与 I2C_0 硬 I2C 的 PA0/PA1）；初始化序列按页面原样（寄存器写使能 0x69←{0x88,0xB5}、Z 轴归零 0x01←{0x04,0x00}、角度归零 0x01←{0x08,0x00}、保存 0x00，各步 200ms——页面「官方 3s 实验 200ms 也行」取页面值）；get_angle 换算保留（raw/32768×180 + ±180 回绕，页面 unsigned 原式 0x8000 恰值 180 不分 ±180 按页面自一致）；人工复核修正：页面 I2C_WaitAck 未在采样前拉高 SCL（时序微瑕）照正确版实现 + 页面 writeDataJy61p 注释「返回 0 则写入成功」与代码返回 1 矛盾统一 0=成功；与 ml_mpu6050（I2C 原始数据）/imu_uart（UART 601 帧）分工写入 notes（JY61P 器件内卡尔曼融合直接出角度、取用姿态角场景首选）；单选生成 → SysConfig CLI → gmake 0 error/0 warning（PASS，verified=true）；词表感知传感器 +JY61P。未上板。code-review（随批次 10 收尾两轴评审）。

- [x] 代码提炼：手册「代码块」抽 `bsp_gyro.c/h` → `code/jy61p.c` + `code/jy61p.h`：去 main/printf、`jy61pInit` → `jy61p_init`、`get_angle` → `jy61p_read_angles`（出参 p 指针）、`Gyro_Structure` 全局收敛静态出参、`writeDataJy61p` 私有化（I2C 寄存器写原语）、`YAW_REG_ADDR 0x3F` 未用宏不声明（标注有误：0x3F 为 Pitch 低字节）
- [x] 母版 `mspm0.syscfg`：新 GPIO 实例 `JY61P`（SCL/SDA 2 associatedPins；默认 PA28/PA31——与 IMU601/FINGERPRINT_UART/HX711/SHT30/MICROWAVE 重叠：姿态与身份/称重/温湿度/微波不同框、同选概率最低；刻意不叠 motor/servo/step/显示/无线/触摸/语音/气体/报警/红外件——平衡车/云台惯配组合；不叠 I2C_0 硬 I2C PA0/PA1），注释写明
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"JY61P": ("jy61p",)`
- [x] `manifest.json`：dependencies ["delay"]；mspm0 平台条目；pins JY61P_SCL/JY61P_SDA（gpio_out，default PA28/PA31）；kit+source_url；notes 含手册路径+原页+网盘链接+改造要点+I2C_WaitAck 时序修正+与 ml_mpu6050（I2C 原始数据）/imu_uart（UART 601 帧）分工：JY61P 是模块化姿态传感器直接出角度（卡尔曼融合在器件内），取用姿态角场景首选——verified 转 true
- [x] wordlist.json：「感知传感器」models 加 JY61P + 方案挂 `lib_modules: ["jy61p"]`
- [x] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增 2 行；`test_pin_bindings.py` 刻意表 PA28/PA31 计数注释更新；`test_syscfg_prune.py` 增 JY61P 断言；新增 `tests/test_module_jy61p.py`：manifest 结构 + 单选生成 + 初始化序列守卫（0x69/0x01/0x00 寄存器 + 0x88B5/0x0400/0x0800 数据 + 6×200ms）、换算守卫（32768.0f/180.0f/±360 回绕）、0x3D/6 字节读取、统一 0=成功约定、无 printf/IRQHandler
- [x] 编译验证：`run_jy61p_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error/0 warning；回写 verified=true + notes
