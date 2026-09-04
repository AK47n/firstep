# 01 — 新增红外对射传感器模块 ir_beam（双平台驱动 + 库级测试）

**要做什么：** 模块库出现"红外对射传感器"模块，用户选中后生成工程直接可用：`ir_beam_init()` + `ir_beam_read()`（1=遮挡，0=无遮挡，极性以 2021F 药位检测为据）；三线制接线只分配 OUT 引脚（mspm0/stm32 默认均 PA8，同选冲突经引脚绑定消解）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `library/modules/ir_beam/` 存在：manifest.json（双平台）+ stm32（code/ir_beam.c/.h）+ mspm0（code/ir_beam_mspm0.c/.h），简介/代码无题绑定词（判据④）。
- [x] stm32 母版 pin_config.h 新增 `IR_BEAM_GPIO`/`IR_BEAM_PIN`（PA8）；mspm0 母版 mspm0.syscfg 新增 GPIO 输入实例 `IR_BEAM`（OUT=PA8）；syscfg_instances 登记 `IR_BEAM → ir_beam`。
- [x] 测试绿：test_pins 默认值=syscfg、test_default_layout PA8 白名单、test_syscfg_prune 实例保留/裁剪、test_module_ir_beam 双平台单选生成（uvprojx 注册 + syscfg 实例）、test_pin_bindings `$assign` 重叠表补 PA8。
- [x] mspm0 gmake 真编译 0 error（0 非基线 warning）；stm32 UV4 真编译 0 error / 0 warning；verified=true + notes 回填编译矩阵（2026-09-05）。
- [x] 中文提交信息，`tests/test_repo_language.py` 兜底通过。

**验收记录：**
- 生成宏实测：mspm0 SysConfig 产物 `IR_BEAM_PORT (GPIOA)` + `IR_BEAM_OUT_PIN (DL_GPIO_PIN_8)`（验证 KEY 单引脚实例先例命名）；全量 pytest 3189 passed + test_pin_bindings 修复后单跑 58 passed。
- 极性依据：`sources/contest/2021F/21F/user/main.c` 278 行（PB5 = 药位检测：`gpio_init(GPIO_B, Pin_5, IU)`，放药 = HIGH，取药 = LOW）——ir_beam_read 约定 1=遮挡；`IR_BEAM_BLOCKED_LEVEL` 宏（当前 1）支持极性翻转。
- 评审整改（code-review 双轴）：Spec 轴 (c)1 —— mspm0 侧无内部上拉（默认 `DL_GPIO_RESISTOR_NONE`，遮挡高电平会悬空），已按 TI 官方 GPIO-软件轮询例程语法补 `IR_BEAM.associatedPins[0].internalResistor = "PULL_UP"`，生成产物实测 `DL_GPIO_RESISTOR_PULL_UP`、重编译 0 error。
- 编译日志：`.scratch/ir-beam-module/verify_out/{stm32,mspm0}/ir_beam/build.log`。
