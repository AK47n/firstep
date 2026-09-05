# 03 — sgp30 模块（SGP30 气体传感器，手册 sensor--sgp30-gas-sensor.md）

**要做什么：** 模块库新增 `sgp30` 条目（仅 mspm0）：从手册提炼 SGP30 驱动为纯驱动切片——软 I2C 位操作（2 GPIO，SDA 方向运行时切换，照 AHT10/批次5/批次6 SHT30 先例：不占硬件 I2C 外设/TIMER）。`sgp30_init()`（0x2003 初始化空气特征值/基准）+ `sgp30_read(&tvoc_ppb, &co2_ppm)`（0x2008 测量 + 6 字节回包 + **CRC8 校验补齐**——器件正确性修正，ir_remote 先例，notes；页面缺 CRC 且只读 5 字节漏 TVOC CRC）。默认脚按「同选概率最低」且不叠 PB6/PB7（aht10）、批次 5 八脚、sht30 的 PA28/PA31。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-08 完成并提交（687f82ec）。软 I2C 位操作（2 GPIO，SDA 方向运行时切换，不占硬件 I2C 外设/TIMER，延时走 delay 模块）；`sgp30_init` 发 0x2003 初始化空气特征基准 + `sgp30_read` 出 TVOC（ppb）/CO2 当量（ppm）双出参（0x2008 测量命令 + 6 字节回包 + 状态码 0/1-5）；**CRC8 器件正确性修正**：数据手册要求 CRC8（0x31/0xFF）——页面缺校验且只读 5 字节漏 TVOC CRC 字节（crc = crc 即弃），按 ir_remote 修正先例补读满 6 字节 + 两组校验（notes 记录）；上电预热 15s（CO2=400/TVOC=0 恒定）判定归调用方循环；默认软 I2C 脚 PA18/PB9（与双电机/大数字显示/读卡重叠——同选概率最低；刻意不叠温湿度/光照/OLED/语音/按键/报警/无线/批次5八脚）；词表感知传感器 +SGP30；单选生成 → SysConfig CLI → gmake 0 error/0 warning（verified=true）；code-review 双轴通过（**修正 2 项**：sgp30.h 返回码文档与实现不一致——收尾提交 136b982d 对齐为 1/2/3=写命令地址/命令字节应答失败、4=读地址应答失败、5=CRC 校验失败；IIC send_ack 加 0=应答 1=非应答页面语义注释）。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/sensor--sgp30-gas-sensor.md` 「代码块」章节抽完整 `bsp_sgp30.c/h` → 改造为 `code/sgp30.c` + `code/sgp30.h`：去 main/printf、函数名规范化（`sgp30_init/sgp30_read`，去 `SGP30_Init/SGP30_Read/SGP30_Write_cmd` 命名）、IIC 原语静态化（`sgp30_iic_start/stop/send_ack/wait_ack/send_byte/read_byte`，半周期 5us 页面原值）、延时走 delay 模块（`dependencies: ["delay"]`）、**CRC8 补充**（多项式 0x31/初值 0xFF——同 SHT30/AGS10 系；读满 6 字节 + 两组校验；页面 `crc = crc` 丢弃缺陷 + 只读 5 字节漏 TVOC CRC 缺陷按数据手册修正，notes：器件正确性修正，非页面语义变化）、全局打包值 `uint32_t` 收敛为双出参（`tvoc_ppb`/`co2_ppm`）+ 状态码（0=成功；1/2/3=写命令地址/命令字节应答失败；4=读地址应答失败；5=CRC 校验失败）
- [x] 母版 `mspm0.syscfg`：新 GPIO 实例 `SGP30`/SCL+SDA（照 SHT30 先例）——默认 SCL=PA18 / SDA=PB9（含避让原则注释）；跨端口（PA18/PB9）宏按 `<实例>_<引脚名>_PORT/PIN/IOMUX` 分派（max7219 先例）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS：增 `"SGP30": ("sgp30",)`
- [x] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（files/verified true/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接（资料 1vds/案例 1x3e）+改造要点+与库内同类分工（**温湿度/气体**）+**CRC8 器件正确性修正记录**+编译记录）；pins：`SGP30_SCL`/`SGP30_SDA` = gpio_out PA18/PB9；简介判据：能力方向（空气质量 TVOC/CO2e 检测、甲醛检测）+ 无题绑定
- [x] wordlist.json 补录：「感知传感器」加「SGP30 空气质量传感器（TVOC/CO2e）」方案挂 `lib_modules: ["sgp30"]`，models 加 "SGP30"
- [x] 测试：`tests/test_pins.py` MSPM0_DEFAULT_MAP 增 SGP30_SCL/SGP30_SDA 映射；`tests/test_pin_bindings.py` 刻意表更新（PA18 3→4、PB9 2→3 注释补 sgp30）；`tests/test_syscfg_prune.py` SGP30 实例保留/裁剪断言；新增 `tests/test_module_sgp30.py`（manifest 结构 + 单选生成 + 命令常量守卫（0x2003/0x2008）+ CRC8 原式守卫（0x31/0xFF）+ **读满 6 字节两组校验守卫**（防回潮页面 5 字节缺陷）+ 双出参守卫）
- [x] 编译验证：`run_sgp30_matrix.py` 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录；code-review 后中文提交（code-review 修正见 136b982d）
