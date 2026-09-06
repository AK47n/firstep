# 06 — tp_xpt2046 独立模块（XPT2046 电阻触摸，1.8 寸配套件）

**要做什么：** 模块库新增 `tp_xpt2046` 条目（仅 mspm0，独立件——spec 决策 A：不作 lcd 依赖/可选配套，用户按需单选，lcd 零触摸耦合）。厂家例程 1.8 带触摸版 `HARDWARE\TOUCH\touch.c/h`（XPT2046，与 LCD 共用 SCLK/MOSI + 独立 TCS）提炼：软 SPI 位操作（CLK/DIN 输出 + DOUT 输入 + CS 输出 + IRQ 输入可选——**轮询读坐标不注册 GPIO 中断**，GROUP1 先例；dependencies ["delay"]）；API：`xpt2046_init()` + `xpt2046_read_xy(u16 *x, u16 *y)`（5 次读取升序排序 + 去头尾中值滤波，vendor TP_Read_XY 归一——**上游缺陷记录**：vendor TP_Read_XY2 的判定方向与坐标换算按厂家原式，逐字核对 CMD_RDX/RDY 与 USE_HORIZONTAL 分支）+ `xpt2046_set_calibration(xfac,yfac,xoff,yoff)`（出厂预设校准宏 XPT2046_CAL_* 单源，Adujust=1 语义）；坐标换算 = 0-4095 原始值 + 校准系数宏（与 lcd 分辨率映射由用户/骨架按屏型自配，驱动不绑屏）。母版 syscfg 新 GPIO 实例 `TP_XPT2046`（CS/CLK/DIN 输出 + DOUT 输入 + IRQ 输入，IRQ 不配中断）+ INSTANCE_CONSUMERS `"TP_XPT2046": ("tp_xpt2046",)` + wordlist 显示模块 solution lib 挂接（01 已挂）+ `tests/test_module_tp_xpt2046.py`（manifest 形状/单选生成/坐标函数门禁/无 IRQHandler 守卫/无平台依赖守卫）+ test_pins/test_pin_bindings/test_syscfg_prune 增断言 + 编译矩阵（0 error/0 warning）→ verified → 中文提交 → code-review。

**默认脚（spec 倾向，工单落死）：** CS←PA8/CLK←PA13/DIN←PA16/DOUT←PA17/IRQ←PA27 档（触摸与增量编码/视觉/温湿度不同框、与 LCD 六脚不同组但同选可绑——触摸+彩屏是常见组合，默认不撞 LCD 默认更稳；按 test_pin_bindings 刻意重叠表定稿）。

**被谁阻塞：** 无（与 05 并行——触摸源码独立于 lcd 文件；实现顺序按 spec 建议在 05 后）。本件时把 wordlist「IPS 彩屏」solution 的 lib_modules 由 ["lcd"] 补为 ["lcd", "tp_xpt2046"]（01 工单暂只挂 lcd——词表引用必须命中库内 slug，结构测试约束）。

**状态：** pending

**验收：**

- [ ] 提炼：厂家 1.8 例程 TOUCH/touch.c/h → code/tp_xpt2046.c/h（UTF-8）：去平台依赖（GPIO 位操作宏化、delay 走库、去 printf/main）、去 TP_Adjust/扫描演示逻辑（ADR 0009 纯驱动；校准走 set_calibration 接口）
- [ ] API：xpt2046_init/read_xy/set_calibration；中值滤波 5 次；软 SPI 忙等不占 TIMER/硬件 SPI；无 IRQHandler
- [ ] 母版 syscfg TP_XPT2046 实例（5 脚）+ INSTANCE_CONSUMERS 登记
- [ ] manifest.json：dependencies ["delay"]；pins 5 角色（CS/CLK/DIN/DOUT/IRQ 按能力 gpio_out/in）；kit=1.8 寸带触摸屏配套组（ZJY180S120TTG01）/source_url=screen--1-8-touch-color-screen.md 原页；notes 含 wiki 页+网盘+厂家目录+与 lcd 共用总线说明+校准宏说明+上游 CMD_RDX/RDY 分支核对记录+未上板
- [ ] 测试 test_module_tp_xpt2046.py + test_pins/test_pin_bindings/test_syscfg_prune 断言
- [ ] 编译矩阵 PASS 0 error/0 warning → verified + notes；中文提交、工单 resolved
