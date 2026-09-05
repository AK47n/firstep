# 03 — mlx90614 非接触红外测温（软 I2C/SMBus，手册 sensor--mlx90614-non-contact-temp-sensor.md）

**要做什么：** 模块库新增 `mlx90614` 条目（仅 mspm0）：从手册提炼 MLX90614 红外测温驱动为纯驱动切片——软 I2C（SMBus 兼容）位操作（照 aht10 先例）：`mlx90614_init()` + `mlx90614_read_object_temp(&temp_c)`（寄存器 0x07）+ `mlx90614_read_ambient_temp(&temp_c)`（寄存器 0x06，0.01℃ 级，页面 `raw*0.02-273.15` 换算保留）+ 底层 `mlx90614_read_word(reg, &raw)`；notes 写明 SMBus 时序差异与页面实现取证（PEC 注释未启用剔除、函数注释名 MLX90615 更正、返回 0.0 语义缺陷改出参+状态）；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 01/02/04 独立）。

**状态：** resolved

**验收：**

- [x] 代码提炼：`code/mlx90614.c/h`（IIC 原语静态化 `mlx90614_iic_*` 照 aht10；`mlx90614_read` 底层读 2 字节低 8 位在前 + ACK/NACK 按页面；页面 `return 0.0` 失败语义改出参+uint8_t 状态（0=成功 1=失败），notes 记录；SMBus 无初始化——`mlx90614_init` 空实现占位注释说明；PEC_Calculation 注释块剔除；地址 0x5A<<1 按页面原式）
- [x] 母版 `mspm0.syscfg`：`MLX90614` GPIO 实例（SCL/SDA 输出，默认 PA9/PA8——与 DIGIT_UART RX/TX（K230 视觉）、IR_BEAM OUT、HC05 STATE、JOYSTICK SW、NRF24L01 MISO 重叠，同选经引脚绑定消解；不叠硬件 I2C I2C_0 脚——软 I2C×硬件 I2C 同脚为物理冲突分组，2026-09-06 实测调整）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"MLX90614": ("mlx90614",)`
- [x] `manifest.json`：dependencies ["delay"]；pins SCL/SDA；notes 含手册路径+原页+网盘链接+改造要点+SMBus 时序差异取证（PEC/命令字节/延时/函数名）；verified=true
- [x] wordlist.json「感知传感器」类补录 MLX90614 方案（lib_modules 挂接）+ models 词条
- [x] 测试：test_pins 双角色映射 / test_pin_bindings PA9/PA8 计数 / test_syscfg_prune 断言 / 新增 test_module_mlx90614.py（0.02-273.15 换算源码守卫 + 0x06/0x07 寄存器常量守卫）——全部通过
- [x] 编译验证：run_mlx90614_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录
- [x] 中文提交 + 工单 resolved + code-review

**结论：** 2026-09-06 完成并提交。软 I2C（SMBus 兼容）位操作（AHT10 先例）；`mlx90614_init（空实现占位）/read_object_temp（0x07）/read_ambient_temp（0x06）出参 + 状态（页面 return 0.0 语义已修正）`；换算 `RAW×0.02−273.15` 页面原式；SMBus 五点取证进 notes（PEC 注释剔除/命令字节/MLX90615 笔误/delay_ms(1)/失败语义）；默认 PA9/PA8（不叠硬件 I2C 脚）；code-review 修正半周期与 SMBus 100kHz 表述 + 出参 NULL 守卫；单选生成 → SysConfig CLI → gmake 0 error / 0 warning（PASS）。未上板。
