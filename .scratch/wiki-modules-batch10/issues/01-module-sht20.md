# 01 — sht20 温湿度传感器（软 I2C，手册 sensor--sht20-temp-humi-sensor.md）

**要做什么：** 模块库新增 `sht20` 条目（仅 mspm0）：从手册提炼 SHT20 温湿度驱动为纯驱动切片——软 I2C（SCL/SDA 两 GPIO，SDA 方向运行时切换，照 sht30/aht10 先例：不占硬件 I2C 外设/TIMER），单次测量模式（0xF3 温度/0xF5 湿度 no-hold），`sht20_init()` + `sht20_read(&t, &h)`（0.01 系数按页面原式：温度 raw/65536×175.72−46.85、湿度 raw/65536×125−6）；CRC 按页面取舍（页面无 CRC——数据 2 字节 + NACK，notes 说明）；器件正确性修正记 notes（14bit 状态位掩码 &0xFFFC——页面正文要求但代码未掩码；测量等待 ≤50×2ms 重试——页面 do-while 裸循环不覆盖 85ms 上限）；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 02/03/04 独立）。

**状态：** resolved

**结论：** 2026-09-11 完成并提交。软 I2C 位操作照 sht30 先例（半周期 5us ≈ 100kHz、SDA 运行时切换、delay 依赖不占 TIMER/硬件 I2C）；默认 SCL=PA16/SDA=PA17（与双电机编码器 AA/AB + RC522 MOSI/MISO + ADS1115 SCL/SDA 重叠——温湿度与闭环车/读卡/外扩模拟不同框、同选概率最低；刻意不叠温湿度互替件与光照件）；人工复核修正：14bit 状态位掩码 &0xFFFC（页面正文要求、页面代码未实现）、测量等待 ≤50×2ms（100ms 窗口覆盖页面 85ms 最长测量）、页面 IIC_Write 位延时归一 sht30 同款；CRC 按页面取舍无（notes 说明可补 CRC8 原式）；0.40 地址与 pca9685 同址提醒 + 与 aht10/dht11/sht30 分工（SHT2x 旧系列、单次测量低功耗）写入 notes；单选生成 → SysConfig CLI → gmake 0 error/0 warning（PASS，verified=true）；词表感知传感器 +SHT20。未上板。code-review（随批次 10 收尾两轴评审）。

- [x] 代码提炼：手册「代码块」抽 `bsp_sht20.c/h` → `code/sht20.c` + `code/sht20.h`：去 main/printf、`SHT20_Read` → `sht20_read(&t,&h)`、IIC 原语静态化（照 sht30 命名 `sht20_iic_*`）、全局静态 + 出参
- [x] 母版 `mspm0.syscfg`：新 GPIO 实例 `SHT20`（SCL 输出/SDA 输出初值 CLEARED，2 associatedPins；默认 PA16/PA17——与双电机编码器 AA/AB/RC522 MOSI/MISO/ADS1115 SCL/SDA 重叠：温湿度与闭环车/读卡/多路模拟不同框、同选概率最低；刻意不叠温湿度互替件与光照件——环境站常见搭配；PA0/PA1 不可作软 I2C SDA——既定事实④），注释写明
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"SHT20": ("sht20",)`
- [x] `manifest.json`：dependencies ["delay"]；mspm0 平台条目；pins SHT20_SCL/SHT20_SDA（gpio_out，default PA16/PA17）；kit+source_url（手册原页+采购链接）；notes 含手册路径+原页+网盘链接+改造要点+14bit 掩码修正/测量重试/无 CRC 取舍+与 aht10/dht11/sht30 分工（SHT2x 旧系列、地址 0x40、低功耗单次测量）+软 I2C 地址冲突提醒（0x40 与 pca9685 同址）——verified 转 true
- [x] wordlist.json：「感知传感器」models 加 SHT20 + 方案挂 `lib_modules: ["sht20"]`
- [x] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增 2 行；`test_pin_bindings.py` 刻意表 PA16/PA17 计数注释更新；`test_syscfg_prune.py` 增 SHT20 断言；新增 `tests/test_module_sht20.py`：manifest 结构 + 单选生成（syscfg 含 SHT20、文件落盘、main.c 调 init/read 过静态门禁）+ 公式/命令字/掩码/重试守卫 + 无 CRC/printf/IRQHandler 断言
- [x] 编译验证：`run_sht20_matrix.py`（.scratch/wiki-modules-batch10/），单选生成 → SysConfig CLI → gmake 0 error/0 warning；结果回写 manifest verified=true + notes
