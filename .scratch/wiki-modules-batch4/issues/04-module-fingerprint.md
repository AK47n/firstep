# 04 — fingerprint 指纹识别传感器（真实 UART 轮询，手册 sensor--fingerprint-recognition-sensor.md）

**要做什么：** 模块库新增 `fingerprint` 条目（仅 mspm0）：从手册提炼 AS608 指纹模块驱动为纯驱动切片——真实 UART（双向，`FINGERPRINT_UART` 独立实例，**轮询接收**不注册 IRQHandler）+ 触摸检测 GPIO：`fingerprint_init()` + `fingerprint_check_device` + `fingerprint_is_touched` + 采集/合成/比对/录入/删库等服务函数（帧封装 = 包头 0xEF 0x01 FF FF FF FF + 指令/参数/校验和按页面原样）；流程控制（先触摸→采集→比对、菜单 Yes/No）归生成骨架（ADR 0009）；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（本件与 01/02/03 独立）。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。真实 UART 独立实例（FINGERPRINT_UART 默认 UART0，57600 按页面注释；enabledInterrupts=[] 轮询接收——无 IRQHandler 强符号）；帧封装/命令数组/校验和按页面原样；流程控制（触摸时序/按键菜单）归生成骨架；默认 PA28/PA31/PA12（与 IMU601/HX711 同外设/同脚消解 + 与双电机/光照重叠）；单选生成 → SysConfig CLI → gmake 0 error / 0 warning（PASS）。未上板。

- [x] 代码提炼：`code/fingerprint.c/h`（真实 UART 忙等发送 + DL_UART_isRXFIFOEmpty 轮询接收精确收齐；FPM10A_* 命令数组/校验和按页面原样；key_scanf/printf/中断缓冲剔除——流程归骨架）
- [x] 母版 `mspm0.syscfg`：FINGERPRINT_UART（UART0, 57600, 无中断）+ FINGERPRINT GPIO（TOUCH 输入 PA12）
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"FINGERPRINT_UART"`/`"FINGERPRINT"` + 顶部注释更正 UART 共享实证结论
- [x] `manifest.json`：dependencies ["delay"]；pins TX/RX/TOUCH；notes 含 UART 决策依据/57600 说明/帧格式/流程归骨架；verified=true 回写
- [x] wordlist.json「感知传感器」类加 AS608 方案（lib_modules 挂接）
- [x] 测试：test_pins 三角色映射 / test_pin_bindings PA28/PA31/PA12/UART0 计数 / test_syscfg_prune 断言 / 新增 test_module_fingerprint.py（命令数组校验和镜像 + 轮询无 ISR 源码守卫）——全部通过
- [x] 编译验证：run_fingerprint_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning（PASS）；verified=true + notes 记录；中文提交
