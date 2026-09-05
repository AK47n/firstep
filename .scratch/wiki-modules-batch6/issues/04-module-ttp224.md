# 04 — ttp224 4 路电容触摸按键（GPIO 薄封装，手册 sensor--ttp224-touch-sensor.md）

**要做什么：** 模块库新增 `ttp224` 条目（仅 mspm0）：从手册提炼 TTP224 驱动为纯驱动切片——4 路 GPIO 输入（上拉，页面极性 = 引脚高=触摸）：`ttp224_init()` + `ttp224_read(ch)`（ch 1-4，返回 1=触摸 0=未触摸）+ `ttp224_read_all()`（位掩码低 4 位）；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（与 01/02/03 独立）。

**状态：** resolved

**结论：** 2026-09-07 完成并提交。GPIO 薄封装（4 × 输入 + 内部上拉，无运行时初始化，SYSCFG_DL_init() 生效）；`ttp224_init` + `ttp224_read(ch 1-4)` 返回 1=触摸 + `ttp224_read_all` 返回 bit0-3 位掩码（支持多点）；页面 4 个 Key_IN1-4_Scanf 收敛为 read(ch)/read_all；**极性按页面资料（引脚高=触摸）**，TTP224_TOUCH_LEVEL 单点反相宏（TTP224N 实物若低有效改 0）；默认 OUT1-4=PA22/PA25/PA26/PA27（与巡线/无线/手动输入/测距重叠——同选概率最低，四脚与同批默认不撞）；单选生成 → SysConfig CLI → gmake 0 error/0 warning（PASS）；code-review 双轴通过。未上板。

**验收：**

- [x] 代码提炼：`code/ttp224.c/h`（去 main/printf；页面 4 个 `Key_IN1-4_Scanf` 收敛为 `ttp224_read(ch)/read_all`；引脚宏参数化 `<实例>_<引脚名>_PORT/PIN`——四脚跨 PA22/25/26/27 无合并 PORT 宏，max7219 先例）
- [x] 极性：页面「引脚高 = 触摸」原样（`TTP224_TOUCH_LEVEL` 宏单点反相，默认 1 = 高有效；read 返回 1 = 触摸；notes 记录 TTP224N 实际常低有效、改宏即可）
- [x] 母版 `mspm0.syscfg`：`TTP224` GPIO 实例（OUT1-4 输入 + internalResistor PULL_UP——页面「上拉输入」）；默认 OUT1=PA22/OUT2=PA25/OUT3=PA26/OUT4=PA27（与 HUIDU L1/L4/R1/R2、DEBUG_UART RX/NRF IRQ、ZIGBEE/joystick/IR_REMOTE/ADC MEM3 重叠——触摸按键与无线/手动输入互替、与巡线/测距不同框，同选概率最低；与同批默认不撞），重叠对登记 test_pin_bindings 刻意表
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"TTP224": ("ttp224",)`
- [x] `manifest.json`：无依赖（GPIO 薄封装）；pins 4 × gpio_in；notes 含手册路径+原页+网盘链接+改造要点+页面正文 TTP223B 描述与 TTP224N 实际极性差异+编译记录；verified=true
- [x] wordlist.json「感知传感器」类补录 TTP224 方案（lib_modules 挂接）+ models 词条
- [x] 测试：test_pins MSPM0_DEFAULT_MAP 增 TTP224_OUT1-4；test_pin_bindings PA22/PA25/PA26/PA27 计数 3→4/4→5/5→6/2→3；test_syscfg_prune TTP224 断言；新增 test_module_ttp224.py（4 角色 + read/read_all + 极性宏守卫 + 位掩码守卫）
- [x] 编译验证：run_ttp224_matrix.py 单选生成 → SysConfig CLI → gmake 0 error / 0 warning；verified=true + notes 记录
- [x] 中文提交 + 工单 resolved + code-review
