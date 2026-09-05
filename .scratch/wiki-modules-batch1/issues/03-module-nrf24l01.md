# 03 — nrf24l01 模块（2.4G 无线收发，手册 rf--nrf24l01-2-4-g-control-module.md）

**要做什么：** 模块库新增 `nrf24l01` 条目（仅 mspm0）：从手册提炼完整 NRF24L01 驱动为纯驱动切片——软 SPI 位操作（CLK/MOSI/MISO）+ CSN/CE + IRQ，`nrf24l01_init()` + 配置（地址/速率/功率/动态包长）+ TxPacket/RxPacket 收发服务函数；选中后生成工程打开即可编译、可调用，双车无线遥控/遥测可用。

**被谁阻塞：** 无——可立即开始（与 01/02/04 独立）。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。软 SPI 位操作 6 脚全 GPIOA（单 NRF24L01_PORT 宏：CLK=PA26/MOSI=PA25/MISO=PA9/CSN=PA24/CE=PA23/IRQ=PA22）；**上游缺陷处理**：`#if DYNAMIC_PACKET==0` 分支引用页外 L01_WriteSingleReg——整枝剔除、动态包长归一 1，另修正页内多处 `Write_Reg(FLUSH_*, 0xff)` 误把 FLUSH 命令当寄存器地址（改显式 flush 命令）；**IRQ 用轮询不注册 GPIO 中断**（MSPM0 GPIO 中断共 GROUP1 一个向量且被 motor 编码器独占——NRF+电机双车标配无法共存第二个 handler，按手册轮询方式接收）；单选生成 → gmake 0 error / 0 warning（PASS）。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/rf--nrf24l01-2-4-g-control-module.md` 「代码块」章节抽完整驱动 → 改造为 `code/nrf24l01.c` + `code/nrf24l01.h`：去 main/printf、软 SPI 原语静态化（spi_read_write_byte 等）、API 规范化（`nrf24l01_init/set_channel/set_address/set_speed/set_power/tx_packet/rx_packet/irq_clear` 等，页内 30+ 函数收敛为库风格子集）、IRQ 中断或轮询二选一（**改为轮询**——GROUP1 中断被 motor 编码器独占，NRF+电机双车组合无法共存第二个 handler；轮询 STATUS.RX_DR 位，IRQ 脚只读状态）
- [x] **上游缺陷处理**：`#if DYNAMIC_PACKET==0` 分支引用页外 `L01_WriteSingleReg`（上游残留 bug）→ **整枝剔除**（DYNAMIC_PACKET 归一为 1 动态包长路径），缺陷记入 manifest notes（spec 范围外条款：按手册源码提炼、编译过即可，缺陷只记录不修复上游）
- [x] 母版 `mspm0.syscfg`：新 GPIO 实例 `NRF24L01`（6 associatedPins：CLK/MOSI 输出 + MISO 输入 + CSN/CE 输出 + IRQ 输入，全 GPIOA 单口；IRQ 不配 interruptEn——轮询方案）；默认脚按"同选概率最低重叠"分配，重叠登记 `test_pin_bindings` 刻意表
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记
- [x] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+**DYNAMIC_PACKET 缺陷记录**+编译记录）；pins：6 × GPIO（type gpio_out/gpio_in，default 按分配）；简介判据：能力方向（2.4G 无线遥控/无线数据传输/多机通信）+ 无题绑定
- [x] wordlist.json 补录：「通信」类加「NRF24L01 2.4G 无线模块」方案挂 `lib_modules: ["nrf24l01"]`
- [x] 测试：`tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射；`test_syscfg_prune.py` 增 NRF24L01 实例断言；新增 `tests/test_module_nrf24l01.py`（单选生成 → syscfg 含实例 + 文件落盘 + main.c 调 init/收发过静态门禁）
- [x] 编译验证：module-polish 编译矩阵配方 gmake 真编译 0 error、模块自身 warning 0；结果回写 manifest verified=true + notes 记录；code-review 后提交
