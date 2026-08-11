# 02 — 骨架母版接口 + stm32 motor/key 补录（工单 01 收尾的可用性闭环）

**What to build:** 工单 01 让母版内嵌模块通过平台检查与生成门禁，但骨架阶段 `build_skeleton_interfaces` 只喂模块头——LLM 生成 main.c 时看不到 ml_* API，母版内嵌模块（oled/delay/led_beep）的调用会被骨架自检改写为注释占位。本工单把母版头并入骨架接口集，并补录 stm32 motor/key（21F code 层胶水未入库，空条目无法覆盖）。

**Status:** resolved（2026-08-10 已合 main，merge commit bc4408f，997 绿 + mypy 干净——01/02 同批合入，CONTEXT.md 合并时两边补句都保留）

## 需求

1. **骨架接口并入母版头**（skeleton.py `build_skeleton_interfaces`）：接口集 = 模块头 + 母版树全部 .h（headfile.h + ml_*.h），LLM 生成 main.c 时知道 ml_oled_show_string 等真实 API。签名需加母版目录参数（webapp 骨架端点传 master_project_dir）。
2. **stm32 motor 补录**（决策已定：中断拆入两模块，引脚宏集中 pin_config.h）：
   - **motor 模块加 stm32 条目**：files = `code/motor.c/h`（21F 提取：驱动 + motor_init/encoder_init，**引脚宏化**——硬编码的 TIM2 CH1/CH2、PA6/PA7/PB0/PB1、EXTI PA2/PA4 + PA3/PA5 全改引用 pin_config.h 宏，值为 21F 原值）；code/motor.c 内加 `EXTI2_IRQHandler` / `EXTI4_IRQHandler`（编码器脉冲计数，照 mspm0 key 模块自带 GROUP1_IRQHandler 先例——中断跟着功能模块走，选 motor 即带计数中断）
   - **pid 模块 stm32 条目 files 补 `code/pid_isr.c`**：`TIM3_IRQHandler`（10ms：关中断读 Encoder_count1/2 → motorA.now/motorB.now → pid_control()，21F isr.c 原样提取）；选 pid 即带 10ms 调度，闭环开箱即用
   - **母版新增 `pin_config.h`**（工程根）：电机相关引脚宏集中声明（值 = 21F 原值）；未来"配置引脚"功能只改此文件（对偶 mspm0 SysConfig 生成宏）；uvprojx IncludePath 补工程根（若缺）
   - 依赖方向 pid → motor（无环）；EXTI2/4 与 TIM3 用 ml_gpio/ml_exti/ml_pwm/ml_tim（功能库母版必有，不声明依赖）
   - 21F isr.c 其余（USART1→digit_uart_rx_handler、EXTI7→MPU6050 姿态融合）本轮不做，后续同模式补
3. **stm32 key 不补录**（决策：不做——21F 无独立按键素材，main.c 仅 PB5 药物检测，属工程级逻辑；key 维持 mspm0 only，stm32 侧平台检查 missing 警告保留）
4. **AI 摘要带平台**（ManifestSummary.to_line）：摘要行加平台标记（如 `（平台: stm32/mspm0）`），AI 推荐从源头不推目标平台没有的模块（可选，低优先）。

## 验收

- [x] 全量测试绿（993）+ mypy 干净
- [x] 选 motor 不选 pid stm32 生成：uvprojx 注册 motor_stm32.c、EXTI2/4 计数编译过（ml_gpio 引用）、无 missing 警告（真实库端到端验证）
- [x] 选 motor+pid stm32 生成：uvprojx 注册 pid_isr.c、TIM3→pid_control 闭环代码在
- [x] pin_config.h 引脚宏值 = 21F 原值（PA2/PA3/PA4/PA5、PA6/PA7/PB0/PB1、TIM2 CH1/CH2）；motor_stm32.c 无硬编码引脚字面量（数据守卫测试）
- [x] key 在 stm32 上仍报 missing（不补录，警告保留回归——manifest + selection 双守卫）
- [x] 骨架接口集含母版头（headfile.h + ml_*.h），LLM 生成 main.c 调 ml_* API 不被打回（skeleton 自检 + 生成门禁都认同一套）
- [x] 母版不选任何模块生成 = 空工程 + pin_config.h，main.c 调母版 ml_* API 过门禁能落盘
- [x] 独立 worktree（firstep-master-02）+ 独立 commit（master-embedded-02），工作区其他未提交修改未混入

## Comments

- 2026-08-10 立项（工单 01 的姊妹工单）：01 是"不误报"，02 是"真可用"。motor/key 补录涉及中断胶水归属，需用户决策后定稿
- 2026-08-10 决策（用户拍板）：① 中断胶水**拆入两模块**——EXTI2/4 编码器计数入 motor.c（选 motor 即带，先例 = mspm0 key 模块自带 GROUP1_IRQHandler，"中断跟着功能走"是模块库原生形态）；TIM3 10ms 调度入 pid 模块新文件 pid_isr.c（选 pid 即带）。否决"isr 独立成模块"：isr 的 TIM3 调 pid_control 使 isr 依赖 pid，而依赖机制是"使用者声明、选被使用者不自动带使用者"——选 pid 不自动带 isr，需手动勾选，可用性坑。否决"单文件归 pid"：只选 motor 时编码器计数中断缺失，motor 测速 API 变死。② **引脚分配集中 pin_config.h**（母版新增，工程根）：motor.c / pid_isr.c 只引用宏，值为 21F 原值——未来"配置引脚"功能只改此文件 + 按配置重写两个 handler（EXTI handler 名绑定引脚：PA2→EXTI2 固定，引脚一换名字就要换，故中断代码必须留在模块内可整体替换的位置）；对偶 mspm0 SysConfig 生成宏（DC_MOTOR_*_PORT/PIN）。③ key 不补录（21F 无独立按键，PB5 药物检测是工程级逻辑）。④ 21F isr.c 其余（USART1/EXTI7）后续同模式补，本轮不做
- 2026-08-10 实施（用户澄清后）：**mspm0 实现保留**——用户"为什么要换成 stm32，我的 stm32 里不应该本来就有驱动电机的文件吗"——21F 驱动只在 sources/contest/2021F/21F/code/motor.c（模块库当年只提取了 pid），本工单把 stm32 版提取为独立文件 code/motor_stm32.c/h，mspm0 的 code/motor.c/h 原样不动。实施要点：① **motor 依赖清空**（dependencies: []）——stm32 侧只用母版 ml_* 功能库不声明依赖（决策原文）；依赖是模块级非平台级，不清空则选 motor 会拖入 mspm0 专属的 huidu/imu_uart/ntb_time/key，违反验收"无 missing 警告"。mspm0 侧选 motor 需手动同选小车栈（huidu/imu_uart/led_beep/ntb_time/key/delay/oled），notes 已注明；② **pid.c 改引 motor_stm32.h**——模块 code/motor.h 是 mspm0 版（含 ti_msp_dl_config.h），stm32 上解析不到；③ **生成门禁 _check_main_calls 并入母版头**（与工单 01 计划同缝的 3 行，合并时冲突为同名改动）——骨架阶段把母版头喂给 LLM 后，门禁必须认同一套，否则"骨架 ml_* 不被打回"在生成端被打回；④ 结构测试 test_skeleton_source_has_no_raw_read_text 从 1 放宽到 2（母版头读盘允许，与 generator 的母版头段同规）；⑤ uvprojx IncludePath 补工程根 `..`（pin_config.h 在工程根，否则模块 include 解析不到）
