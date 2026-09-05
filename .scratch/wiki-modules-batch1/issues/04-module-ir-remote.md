# 04 — infra_ir 模块（红外遥控接收解码，手册 rf--infrared-receiving-module.md）

**要做什么：** 模块库新增红外接收解码条目（slug 实现时定，如 `ir_remote`；仅 mspm0）：从手册提炼完整驱动为纯驱动切片——GPIO 输入中断捕获红外信号低/高电平时宽 → NEC/兼容协议解码（用户码 + 按键码 + 重复码）→ `ir_rx_init()` + 读取最近一次解码结果 + 收到标志；选中后生成工程打开即可编译、可调用，配合红外遥控器实现按键遥控。

**被谁阻塞：** 无——可立即开始（与 01/02/03 独立）。

**状态：** ready-for-agent

- [ ] 代码提炼：从 `sources/materials/lckfb-地猛星移植手册/rf--infrared-receiving-module.md` 「代码块」章节抽完整驱动 → 改造为 `code/ir_remote.c` + `code/ir_remote.h`：去 main/printf、API 规范化（`ir_remote_init/ir_remote_get_code/ir_remote_has_data` 等）、解码状态机收敛为驱动内部静态 + 出参结果（ADR 0009 无外部调度）
- [ ] **计时方案**：脉宽测量（NEC 位 560us 级）用 GPIO 中断 + CPU 忙等/delay 换算（**不占 TIMER 实例**——TIMG 全占，sr04 先例；如手册用 TIMER 捕获则改写为忙等采样，注释说明）；输入中断走 GROUP1 IIDX 分发（KEY/DC_MOTOR 先例），与既有消费方共存
- [ ] 母版 `mspm0.syscfg`：新 GPIO 实例（IR 输入，1 associatedPin，中断使能）；默认脚按"同选概率最低重叠"分配，重叠登记 `test_pin_bindings` 刻意表
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS 登记
- [ ] `manifest.json`：`dependencies: ["delay"]`；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含手册路径+原页+网盘链接+改造要点+编译记录）；pins：1 × gpio_in（irq）；简介判据：能力方向（红外遥控接收/无线遥控/免接触按键）+ 无题绑定
- [ ] wordlist.json 补录：「遥控」类加「红外遥控接收」方案挂 `lib_modules: ["ir_remote"]`（同名配对发射模块在后续批次，wordlist 注明）
- [ ] 测试：`tests/test_pins.py::MSPM0_DEFAULT_MAP` 增映射；`test_syscfg_prune.py` 增实例断言；新增 `tests/test_module_ir_remote.py`（单选生成 → syscfg 含实例 + 文件落盘 + main.c 调 init/读码过静态门禁）；解码路径可加纯函数单测（伪脉冲序列 → 码值，最高既有接缝）
- [ ] 编译验证：module-polish 编译矩阵配方 gmake 真编译 0 error、模块自身 warning 0；结果回写 manifest verified=true + notes 记录；code-review 后提交
