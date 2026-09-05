# 04 — at24c02 EEPROM 存储器（软 I2C，手册 control--at24c02-eeprom-memory.md）

**要做什么：** 模块库新增 `at24c02` 条目（仅 mspm0）：从手册提炼 AT24C02 EEPROM 驱动为纯驱动切片——软 I2C 位操作（照 aht10 先例）：`at24c02_init()` + `at24c02_write_byte(addr, data)` + `at24c02_read_byte(addr)`（页面原式：伪写定位 + 重 start + 0xA1 读 1 字节 NACK）+ `at24c02_wait_write_done()`（写周期等待封装 ~5ms 走 delay 模块）+ 页 API `at24c02_write_page`（16 字节页缓冲，防跨页翻转）+ `at24c02_read_block`（连续读）；地址宏纠正（页面 READ/WRITE 宏名颠倒，notes 记录）；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 01/02/03 独立）。

**状态：** resolved

**验收：**

- [x] 代码提炼：`code/at24c02.c/h`（IIC 原语静态化 `at24c02_iic_*` 照 aht10；`AT24C02_ADDR_WRITE 0xA0`/`AT24C02_ADDR_READ 0xA1` 命名纠正（页面颠倒，notes 记录）；`wait_write_done` = delay_ms(AT24C02_WRITE_CYCLE_MS 5)；页写/连续读按页面正文实现（页面无代码，notes 记录），字节读写按页面原式；写周期等待不自动内嵌（调用方控制）；WP 写保护不管理（notes 说明））
- [x] 母版 `mspm0.syscfg`：`AT24C02` GPIO 实例（SCL/SDA 输出，默认 PB24/PB8——与 STEP_MOTOR RST2/DCY2 + SR04 TRIG/ECHO + HC05 KEY 重叠，同选经引脚绑定消解）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"AT24C02": ("at24c02",)`
- [x] `manifest.json`：dependencies ["delay"]；pins SCL/SDA；notes 含手册路径+原页+网盘链接+改造要点+地址宏颠倒缺陷记录+页写/连续读按正文实现记录；verified=true
- [x] wordlist.json 新分类「存储/数据记录」补录 AT24C02 方案（lib_modules 挂接 + models 词条含 AT24C02）
- [x] 测试：test_pins 双角色映射 / test_pin_bindings PB24/PB8 计数 / test_syscfg_prune 断言 / 新增 test_module_at24c02.py（0xA0/0xA1 宏名守卫 + 5ms 写周期常量守卫）——全部通过
- [x] 编译验证：run_at24c02_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录
- [x] 中文提交 + 工单 resolved + code-review

**结论：** 2026-09-06 完成并提交。软 I2C 位操作（AHT10 先例）；`at24c02_init（空实现占位）/write_byte（页面原式）/read_byte（页面原式，无应答 0xFF）/wait_write_done（5ms）/write_page（16 字节页写跨页拒收）/read_block（连续读）`；页面宏名 READ/WRITE 颠倒纠正（0xA0=写/0xA1=读）记 notes；默认 PB24/PB8；code-review 修正 read_block 注释 len 上限（uint8_t ≤255）；单选生成 → SysConfig CLI → gmake 0 error / 0 warning（PASS）。未上板。
