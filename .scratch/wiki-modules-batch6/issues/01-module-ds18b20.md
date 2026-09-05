# 01 — ds18b20 单总线温度传感器（1-Wire，手册 sensor--ds18b20-temp-sensor.md）

**要做什么：** 模块库新增 `ds18b20` 条目（仅 mspm0）：从手册提炼 DS18B20 驱动为纯驱动切片——单总线位时序（1 GPIO 双向，方向运行时切换，延时走 delay 模块，不占 TIMER）：`ds18b20_init()`（复位检测器件）+ `ds18b20_read_temp()`（出 float ℃，±0.5℃ 精度、0.0625 系数按页面）；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 02/03/04 独立）。

**状态：** claimed

**验收：**

- [ ] 代码提炼：`code/ds18b20.c/h`（去 main/printf；函数名规范化 `ds18b20_init/read_temp`；DQ_OUT/IN/GET/SET 宏参数化 `<实例>_<引脚名>_PIN/_IOMUX`；页面 DS18B20_Check/Start/Write_Byte/Read_Byte/GetTemperture 归一；全局无状态 = 纯函数 + 出参；`DS18B20_Reset` 页面声明无定义 → 剔除并记 notes）
- [ ] 时序：复位 750us+15us+200×1us/240×1us；写位 1 = 2+60us、写位 0 = 60+2us；读位 = 2us 拉低+释放+输入 12us 采样+50us 尾部——全部按页面原值，走 `delay` 模块（依赖声明）忙等，不占 TIMER；位槽总时长 62-64us 落页面 60-70us 区间；源码只引用头文件常量（12us/60us 时间轴守卫）
- [ ] 母版 `mspm0.syscfg`：`DS18B20` GPIO 实例（DATA 输出，initialValue SET=空闲高，运行时 DQ_OUT/IN 切换——DHT11 先例）；默认 PA7（与 DC_MOTOR BIN2/SERVO_PWM/RC522 CS 重叠——接触测温与运动控制/读卡不同框同选概率最低；刻意不叠温湿度/显示/语音件与 I2C_0 的 PA0/PA1——i2c_bus_share 测试互扰批次 5 先例；不与批次 5/同批相撞），重叠对登记 test_pin_bindings 刻意表
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"DS18B20": ("ds18b20",)`
- [ ] `manifest.json`：dependencies ["delay"]；pins DATA = gpio_out PA1；notes 含手册路径+原页+网盘链接+改造要点+`DS18B20_Reset` 未定义缺陷+未读 CRC 记录+编译记录；verified=true
- [ ] wordlist.json「感知传感器」类补录 DS18B20 方案（lib_modules 挂接）+ models 词条
- [ ] 测试：test_pins MSPM0_DEFAULT_MAP 增 DS18B20_DATA；test_pin_bindings PA7 计数 3→4；test_syscfg_prune DS18B20 断言；新增 test_module_ds18b20.py（位槽时序常量守卫 12us/60us/750us + 0.0625 负温守卫 + 无 Reset 声明守卫）
- [ ] 编译验证：run_ds18b20_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录
- [ ] 中文提交 + 工单 resolved + code-review
