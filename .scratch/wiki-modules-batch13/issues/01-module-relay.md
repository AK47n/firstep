# 01 — relay 继电器模块（GPIO 迷你驱动，手册 control--relay-module.md）

**要做什么：** 模块库新增 `relay` 条目（仅 mspm0）：从手册提炼 1 路 5V 继电器（光耦隔离/低电平吸合）驱动为纯驱动切片——**GPIO 迷你驱动**（1 脚输出，10 分钟级，照 human_ir/microwave_radar 先例）：`relay_init()`（初始断开）+ `relay_set(uint8_t state)`（**1=吸合（导通）/0=断开**——归一化拍板；页面 Set_Relay_Switch 0=吸合/1=断开，本件 `Set_Relay_Switch(s) ≡ relay_set(1−s)`，notes 写明对照）+ 极性单宏 `RELAY_ON_LEVEL`（照 ttp224 TTP224_TOUCH_LEVEL 先例，默认 **0u** = 引脚低电平吸合——与页面模块「低电平吸合」一致，实物高电平吸合改 1 即可）；页面 RELAY_OUT 宏原式保留为底层（relay_set 内 state×RELAY_ON_LEVEL 分发 setPins/clearPins）；选中后生成工程打开即可编译、可调用，不再"需自备"。

**被谁阻塞：** 无——可立即开始（本批 spec 已拍板；与 02/03/04 独立）。

**状态：** resolved

**结论：** 2026-09-06 完成并提交。relay 1 路 5V 继电器模块（仅 mspm0，无依赖）：GPIO 迷你驱动（relay_init 初始断开 + relay_set(1=吸合/0=断开)——页面 Set_Relay_Switch(s) ≡ relay_set(1-s) 对照；极性单宏 RELAY_ON_LEVEL 默认 0u=引脚低电平吸合（页面模块低电平吸合，实物高电平吸合改 1 即可）；页面 RELAY_OUT 宏原式保留为底层（state×RELAY_ON_LEVEL 分发 setPins/clearPins））；母版 syscfg RELAY 实例（OUT 输出 initialValue SET=初始断开，默认 PA1——与 I2C_0 scl/GP2Y1014 LED 刻意重叠，test_pin_bindings PA1 2→3）；INSTANCE_CONSUMERS 登记；wordlist 执行机构 models「继电器」+ 新 solution（lib_modules relay）；测试（test_module_relay.py + test_pins/test_pin_bindings/test_syscfg_prune 增断言）；词表预算链：全量 wire 7239→7374 → WORDLIST_PROMPT_BYTES 7500→7600、REFERENCE_FULLTEXT_BYTES 60400→60300（+40B 口径，batch12 先例）；编译矩阵 PASS（0 error/0 warning）→ verified；未上板（吸合/断开时序、低电平驱动真机验证留后续）。

**实施清单：**
- [x] 代码提炼：手册「代码块」抽 `bsp_relay.c/h` → `code/relay.c` + `code/relay.h`：去 main.c 演示与 printf、`Set_Relay_Switch` → `relay_set`（1=吸合/0=断开）、`RELAY_OUT` 宏保留为底层、`RELAY_ON_LEVEL` 极性宏（.h，默认 0u + 注释「低电平吸合——实物高电平吸合改 1」）、`relay_init`（初始断开 = relay_set(0)）；header 注释写明页面编码（Set_Relay_Switch(s) ≡ relay_set(1−s)、0=吸合/1=断开——页面注释原样引用）
- [x] 母版 `mspm0.syscfg`：新 GPIO 实例 `RELAY`/OUT（direction OUTPUT、initialValue **SET = 初始断开**（模块低电平吸合，吸合=引脚低），默认 **PA1**——与 I2C_0 scl（ml_mpu6050 姿态）/GP2Y1014 LED（粉尘）重叠：继电器与姿态/粉尘不同框、同选概率最低；PA1 可作 GPIO 输出（既定事实④仅禁输入——ir_remote_tx 先例）；刻意不叠声光/执行件 LED_BEEP PA15/电机类——继电器+报警/电灯控制为常见组合；同选时经引脚绑定消解），注释写明
- [x] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"RELAY": ("relay",)`
- [x] `manifest.json`：dependencies []；mspm0 平台条目；pins `RELAY_OUT`（gpio_out，default PA1）；kit（1 路 5V 继电器模块——光耦隔离/低电平吸合、4Pin 2.54mm 排针、可控 250V/10A AC + 30V/10A DC、5V 工作）+source_url（wiki 原页）；notes 含手册路径+原页+网盘链接（`https://pan.baidu.com/s/16Ls-5M1FOE3bxCDw6l9z2A?pwd=3tfd` 提取码 3tfd + 旧资料分享链接）+采购链接+改造要点（极性归一化决策/RELAY_ON_LEVEL 宏/`Set_Relay_Switch(s) ≡ relay_set(1−s)` 对照/初始断开）+模块特性（光耦隔离保护 MCU 引脚、三极管驱动、低压控制高压——继电器为感性负载，开关瞬态反电动势与触点电弧注意事项：线圈侧建议续流/触点侧外接负载，notes 记录）+与库内分工（执行机构类：电机 TB6612/L298N 为连续运动驱动、relay 为开关型执行机构——通断控制，按场景选用/组合，互不冲突）——verified 初始 false
- [x] wordlist.json：「执行机构」models 加「继电器」+ 新 solution「1 路 5V 继电器模块（光耦隔离/低电平吸合）」挂 `lib_modules: ["relay"]`（note 写明库内 relay 已打通 + 极性宏 + 默认 PA1 + 250V/10A 能力）
- [x] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增 `("relay","RELAY_OUT"): ("RELAY","OUT")`；`test_pin_bindings.py` 刻意表 PA1 2→3；`test_syscfg_prune.py` 增 RELAY 保留/裁剪断言；新增 `tests/test_module_relay.py`：manifest 结构 + 单选生成（syscfg 含 RELAY、文件落盘、main.c 调 relay_init/relay_set 过静态门禁）+ 守卫（`RELAY_ON_LEVEL 0u`、relay_set(1)=吸合→RELAY_ON_LEVEL=0u 分支 clearPins、relay_set(0)→setPins、init 初始断开、页面 Set_Relay_Switch 对照注释、无 printf/IRQHandler/main）
- [x] 编译验证：`run_relay_matrix.py`（.scratch/wiki-modules-batch13/，照 run_joystick_matrix.py 改 slug）单选生成 → SysConfig CLI → gmake 0 error/0 warning；结果回写 manifest verified=true + notes
- [x] 中文提交 → 状态 resolved → code-review（迷你件浅审）


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
