# 04 — infra_ir 模块（红外遥控接收解码，手册 rf--infrared-receiving-module.md）

**要做什么：** 模块库新增红外接收解码条目（slug = `ir_remote`；仅 mspm0）：从手册提炼完整驱动为纯驱动切片——红外信号低/高电平时宽测量 → NEC/兼容协议解码（地址码 + 命令码 + 重复码校验）→ `ir_remote_init()` + 读取最近一次解码结果 + 收到标志；选中后生成工程打开即可编译、可调用，配合红外遥控器实现按键遥控。

**被谁阻塞：** 无——可立即开始（与 01/02/03 独立）。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。slug 定为 `ir_remote`；GPIO 输入实例 IR_REMOTE（OUT=PA26 上拉）；**计时用 CPU 忙等（delay 模块 20us 步进）不占 TIMER**；**手册 GROUP1 中断内解码整帧改主循环轮询解码**——MSPM0 全部 GPIO 中断共用 GROUP1 一个向量且被 motor 编码器独占（红外+电机是经典组合，无法共存第二个 GROUP1_IRQHandler），poll 的「等待空闲高→等待下降沿」替代中断触发时机，解码行为等价（同步忙等 ~50ms/帧、无信号时单次 ≤10ms）；**修正原版 infrared_data_true_judgment 反码校验错乱**（命令反码不等时竟返回 1 并落库）——严格校验后才保存；单选生成 → gmake 0 error / 0 warning（PASS）。

- [x] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/rf--infrared-receiving-module.md` 「代码块」章节抽完整驱动 → 改造为 `code/ir_remote.c` + `code/ir_remote.h`：去 main/printf、API 规范化（`ir_remote_init/ir_remote_get_code/ir_remote_has_data` 等，另增 get_address），解码状态机收敛为驱动内部静态 + 出参结果（ADR 0009 无外部调度）
- [x] **计时方案**：脉宽测量（NEC 位 560us 级）用 CPU 忙等 + delay 换算（**不占 TIMER 实例**——TIMG 全占，sr04 先例）；**GROUP1 中断改主循环轮询**（GROUP1 被 motor 编码器独占——轮询与中断解码行为等价，原手册 TIMER 捕获不适用，见结论与 manifest notes）
- [x] 母版 `mspm0.syscfg`：新 GPIO 实例 IR_REMOTE（OUT 输入，上拉；不配 interruptEn——轮询方案）；默认脚按"同选概率最低重叠"分配（PA26——与 ZIGBEE_TX/joystick X/NRF CLK 重叠），重叠登记 `test_pin_bindings` 刻意表
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记
- [x] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+编译记录）；pins：1 × gpio_in；简介判据：能力方向（红外遥控接收/无线遥控/免接触按键）+ 无题绑定
- [x] wordlist.json 补录：「遥控」类加「红外遥控接收」方案挂 `lib_modules: ["ir_remote"]`（同名配对发射模块在后续批次，wordlist 注明）
- [x] 测试：`tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射；`test_syscfg_prune.py` 增实例断言；新增 `tests/test_module_ir_remote.py`（单选生成 → syscfg 含实例 + 文件落盘 + main.c 调 init/读码过静态门禁）
- [x] 编译验证：module-polish 编译矩阵配方 gmake 真编译 0 error、模块自身 warning 0；结果回写 manifest verified=true + notes 记录；code-review 后提交
