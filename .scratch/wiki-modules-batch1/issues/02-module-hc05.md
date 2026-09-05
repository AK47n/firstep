# 02 — hc05 模块（蓝牙串口透传，手册 rf--hc05-bluetooth-module.md）

**要做什么：** 模块库新增 `hc05` 条目（仅 mspm0）：从手册提炼完整蓝牙驱动为纯驱动切片——`hc05_init()`（9600 波特、RX 中断缓冲）+ 收发服务函数（send_string/char/buffer、读接收缓冲）+ 连接状态查询 + AT 模式切换；选中后生成工程打开即可编译、可调用，手机/上位机可经蓝牙串口与主控双向通信。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。HC05_UART 挂 UART2（与 DEBUG+UWB 同外设共享先例——UART0-3 全占，UART2 是唯一 TX 脚 PA23 方案；targetBaudRate=9600 独立于其余 115200 实例）；STATE/KEY 并入单个 HC05 GPIO 实例（STATE=PA8 输入高有效、KEY=PB24 输出，默认与 DIGIT_UART TX/IR_BEAM OUT、STEP_MOTOR RST2/SR04 TRIG 重叠——同选经引脚绑定消解）；RX 中断环形缓冲（zigbee_uart 先例、依赖 config 已去除）；单选生成 → gmake 0 error / 0 warning（PASS）。未上板。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/rf--hc05-bluetooth-module.md` 「代码块」章节抽完整 `bsp_*.c/h` → 改造为 `code/hc05.c` + `code/hc05.h`：去 main/printf、API 规范化（`hc05_init/send_*/receive_*/is_connected`）、RX 中断 + 环形缓冲（zigbee_uart 先例，注意其依赖 `config` 模块对齐——本件不需要 config 则去掉）、AT 模式切换/连接状态定为服务函数
- [x] 母版 `mspm0.syscfg`：新 UART 实例 `HC05_UART`（targetBaudRate 9600、RX 中断、FIFO 关闭）——挂靠哪台 UART 外设：UART0-3 均已被占（IMU601/DIGIT_UART/DEBUG+UWB/ZIGBEE），按 DEBUG+UWB 同 UART2 共享先例挂**同选概率最低**外设并在注释说明依据；默认脚按"同选概率最低重叠"分配，与既有 UART 模块默认脚重叠登记 `test_pin_bindings` 刻意表
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记（含 UART 外设共享消解规则说明）
- [x] `manifest.json`：`dependencies: []`（用库内 delay 则 ["delay"]）；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+编译记录+**9600 波特率说明**）；pins：TX = uart_tx、RX = uart_rx（default 按分配）；简介判据：能力方向（无线串口通信/手机遥控/上位机通信）+ 无题绑定
- [x] wordlist.json 补录：「通信」类加「HC05 蓝牙串口」方案挂 `lib_modules: ["hc05"]`
- [x] 测试：`tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射；`test_syscfg_prune.py` 增 HC05_UART 实例断言；新增 `tests/test_module_hc05.py`（单选生成 → syscfg 含实例 + 文件落盘 + main.c 调 init/收发过静态门禁）
- [x] 编译验证：module-polish 编译矩阵配方 gmake 真编译 0 error、模块自身 warning 0；结果回写 manifest verified=true + notes 记录；code-review 后提交
