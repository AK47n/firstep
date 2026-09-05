# 02 — tcs34725 颜色识别传感器（软 I2C，手册 sensor--tcs34725-color-recognition-sensor.md）

**要做什么：** 模块库新增 `tcs34725` 条目（仅 mspm0）：从手册提炼 TCS34725 RGB 颜色识别驱动为纯驱动切片——软 I2C 位操作（照 aht10 先例）：`tcs34725_init()`（ID 判定 0x44/0x4D + 积分时间/增益配置）+ `tcs34725_read_rgb(&rgbc)`（STATUS AVALID 判定出 c/r/g/b 16bit）+ `tcs34725_rgb_to_hsl(&rgbc,&hsl)`（页面 RGBtoHSL 保留）+ 配置服务函数（set_integration_time/set_gain/enable/disable + 底层 write_reg/read_reg）；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 01/03/04 独立）。

**状态：** resolved

**验收：**

- [x] 代码提炼：`code/tcs34725.c/h`（IIC 原语静态化 `tcs34725_iic_*` 照 aht10；全局 `rgb/hsl` 收敛为出参；页面 `if(id==0x4D | id==0x44)` 按位或改 `||`（语义等价写法修正，notes 记录）；GetRawData→`tcs34725_read_rgb`；RGBtoHSL→`tcs34725_rgb_to_hsl` 保留原式（max3v/min3v 宏保留）；地址 0x29<<1=0x52 + COMMAND_BIT 0x80 按页面）
- [x] 母版 `mspm0.syscfg`：`TCS34725` GPIO 实例（SCL/SDA 输出，默认 PA23/PA24——与 HUIDU L2/L3 + UART 无线族 + NRF CSN/CE + ADC12_0 MEM0 重叠，同选经引脚绑定消解；颜色识别与显示件（OLED/MAX7219）刻意不叠）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"TCS34725": ("tcs34725",)`
- [x] `manifest.json`：dependencies ["delay"]；pins SCL/SDA；notes 含手册路径+原页+网盘链接（资料+代码两个）+改造要点+按位或写法修正记录；verified=true
- [x] wordlist.json「感知传感器」类补录 TCS34725 方案（lib_modules 挂接）+ models 词条
- [x] 测试：test_pins 双角色映射 / test_pin_bindings PA23/PA24 计数 / test_syscfg_prune 断言 / 新增 test_module_tcs34725.py（ID 判定 `||` 守卫 + RGBtoHSL 公式文本守卫）——全部通过
- [x] 编译验证：run_tcs34725_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录
- [x] 中文提交 + 工单 resolved + code-review

**结论：** 2026-09-06 完成并提交。软 I2C 位操作（AHT10 先例）；`tcs34725_init（ID 判定 0x44/0x4D + 24ms 积分 + 1X 增益 + 使能）/read_rgb（STATUS AVALID 判定出 RGBC）/rgb_to_hsl（页面原式保留）/set_integration_time/set_gain/enable/disable/底层 write_reg/read_reg`；页面按位或写法改 `||`；默认 PA23/PA24；code-review 修复 rgb_to_hsl NULL 守卫（入参非法/c==0 时出参不动）+ write_reg 栈缓冲越界防护；单选生成 → SysConfig CLI → gmake 0 error / 0 warning（PASS）。未上板。
