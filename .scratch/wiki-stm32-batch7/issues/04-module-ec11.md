# 04 — ec11 旋转编码器（B 类新 slug · 仅 stm32 条目，手册 sensor--ec11.md）

**要做什么：** 模块库新增 **`ec11`**（库内无此模块——B 类，**仅 stm32 平台条目**，mspm0 缺条目标 missing 警告）：从地阔星页面提炼 EC11 旋转编码器驱动为纯驱动切片（A/B 相 2 GPIO 输入 + SW 按键 1 GPIO——**默认轮询 A/B 相**（A 相跳变采样 B 相判向——页面算法；**非 EXTI**——避开 `_check_exti_line_conflicts` 异口同线门禁、不占 TIMER（页面 TIM3 定时器中断扫描消抖改为轮询；页面真值表 L60-61 与正文 L44-46、代码判向 L157-189 矛盾——**按代码（A 相跳变采样 B）为准**+notes）），API：`ec11_init()`（3 脚上拉输入配置）+ `ec11_get_delta()`（返回自上次调用以来的方向+步数增量——正=顺时针/负=逆时针（归一化页面 0/1/2 计数语义））+ `ec11_read_sw()`（1=按下/0=松开——SW 低有效；防抖**归调用方节拍**——页面 100ms 阻塞消抖不落）。

**关键事实（%TEMP%\batch7-facts.md）：** F1；页面默认 A=PA6/B=PA4/SW=PA7（**全占不照抄**）；页面 printf 在驱动文件内（L235/255——剔除）；真值表/判向矛盾按代码。

**引脚与默认脚（同选概率最低推理）：**
- pins：`EC11_A`（gpio_in，default **PA4**，macros `[EC11_A_GPIO, EC11_A_PIN]`）/ `EC11_B`（gpio_in，default **PB5**）/ `EC11_SW`（gpio_in，default **PB0**）。
- pin_config.h 宏段：`EC11_A_GPIO GPIO_A`/`EC11_A_PIN Pin_4`、`EC11_B_GPIO GPIO_B`/`EC11_B_PIN Pin_5`、`EC11_SW_GPIO GPIO_B`/`EC11_SW_PIN Pin_0`（注释：A=PA4 叠 microwave/MOTOR_B_ENC、B=PB5 叠 hx711 SCK/MOTOR_A_ENC、SW=PB0 叠 hx711 DT——EC11 人机旋钮与微波/称重/光电编码器闭环不同框；**刻意不叠人机面板组合件**（KEY/OLED/数码管——旋钮+屏幕/按键面板标配）与声光件；同选经绑定消解）。
- **EXTI 门禁注意**：默认脚与既有 ENC 角色（MOTOR_A_ENC 线 5/PB5、MOTOR_B_ENC 线 4/PA4）同脚同线——门禁只查「用户绑定改动」默认组合不拦（现状口径）；EC11 与 motor 同选时经绑定换脚；本件轮询无 ISR，无强符号冲突。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/ec11/` 新目录：`code/ec11_stm32.c/.h`（3 脚 gpio_init IU 上拉 + 轮询判向后沿/边沿采样（A 相跳变采样 B——页面算法归一增量语义）；零引脚字面量/零标准库/无 EXTI/NVIC/TIM）
- [x] `manifest.json`（**仅 platforms.stm32**：files `[code/ec11_stm32.c, code/ec11_stm32.h]`、dependencies []（无延时依赖——轮询无阻塞）、verified true、hardware_bound false、pins 3 行、kit（EC11 旋转编码器——页面「模块来源」）、source_url `https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ec11.html`、notes（**B 类：无 mspm0 条目（仅 stm32）**+手册路径+原页+网盘+页面三条事实（TIM 中断改轮询/真值表矛盾按代码/printf 剔除/SW 防抖归调用方）+默认脚推理+未上板；description 含能力方向（旋钮输入/步进计数）+无题绑定）
- [x] pin_config.h 增 6 宏
- [x] 测试 `tests/test_module_ec11.py`：形状（**仅 stm32**/files/pins 3 行/macros/source_url wiki 原页/notes 子串「B 类」「无 mspm0」）+宏存在（`EC11_A_GPIO\s+GPIO_A` 等 6 条）+**stm32 单选生成全流程**+**mspm0 missing 警告断言**+守卫（无 `EXTI`/`NVIC`/`TIM`/`printf`/`GPIO_Init`/`RCC_`/`delay_ms`/`IRQHandler` 字面量；`ec11_get_delta` 增量语义注释；「A 相跳变采样 B」判向注释）
- [x] test_pins.py 补 6 宏；test_default_layout.py 白名单 PA4/PB5/PB0 +1×3（含 conflict_groups_resolved PB0 断言更新）
- [x] UV4 矩阵（init+get_delta×2+read_sw，(void) 化）→ 0/0 → verified=true
- [x] wordlist 补录（感知传感器 models +「EC11 旋转编码器」+ solution lib_modules=ec11——B 类首次；**默认词表完整 wire 7812 > 7900 fit 上限 7734 截断 → WORDLIST_PROMPT_BYTES 7900→8050（注释链第 14 次上调）**）
- [x] 中文提交 → resolved → 结论回填

**结论回填（2026-09-07）：全部完成。B 类新 slug——库内无旋转编码器模块，从零设计（相近件：motor 光电编码器 EXTI 计数/key 独立按键/ntb_time 节拍）；**仅 stm32 平台条目**（mspm0 选本件 resolve_selection 报 missing 警告——测试断言 WARNING_MISSING 子串「缺少平台 mspm0 的版本」）。**轮询判向设计**：默认轮询 A/B 相（A 相跳变采样 B 相判向——页面 Encoder_Scanf 算法：A↑+B 低=正转/B 高=反转、A↓ 镜像；页面 L60-61 真值表/正文 L44-46/代码判向矛盾——**按代码为准**+notes；哪边正转由 A/B 接线决定——页面 L146「你说的算」）；**不注册 EXTI**（避开异口同线门禁——微波雷达轮询先例）、**不占 TIMER**（TIM2/3/4 被 PWM/骨架调度占用——页面 TIM3 中断扫描（注释 10ms/实际 5ms——PSC 3600-1/ARR 100 矛盾记录）改调用方 10ms 级调度防抖；快速旋转两次调用间 A 多跳变会漏计——页面定时器扫描同款限制）；API = ec11_init + **ec11_get_delta（int16_t——自上次调用以来净增量，正=顺时针/负=逆时针，清零式；页面 0/1/2 计数语义归一 +1/-1/0；增量单位 = A 相边沿事件——转一格半个脉冲/转两格一个完整脉冲（页面 L50-52）：每格 2 次 A 相边沿，真机标定留后续）+ ec11_read_sw（1=按下/0=松开——SW 低有效，防抖归调用方节拍——页面 delay_ms(100)×2 阻塞消抖不落，驱动零阻塞）；默认脚 A=PA4/B=PB5/SW=PB0（页面默认 A=PA6/B=PA4/SW=PA7 全占不照抄）——叠 microwave/MOTOR_B_ENC（A）+ hx711 SCK/MOTOR_A_ENC（B）+ hx711 DT（SW）：EC11 人机旋钮与微波雷达/称重/光电编码器闭环不同框、同选概率最低；刻意不叠人机面板组合件（KEY/OLED/数码管——旋钮+屏幕/按键面板标配）与声光件；**EXTI 门禁**：默认脚与既有 ENC 角色同脚同线（PA4 线 4/PB5 线 5）——门禁只查用户绑定改动、默认组合不拦（轮询无 ISR 无强符号冲突）；同选经引脚绑定消解；页面缺陷：printf 在驱动文件内（ec11.c L235/255——Encoder_Rotation_left/right 演示计数函数）剔除、SW 100ms 阻塞消抖不落、页内 img1/img2 未内嵌（波形语义从文字+代码还原）；verified=true（UV4 0 error/0 module warning，2026-09-07）+ kit/source_url（ec11.html 原页 + 网盘 8889）+ notes；**wordlist 首次 B 类补录**（感知传感器 models +「EC11 旋转编码器」+ solution lib_modules=ec11——默认词表完整 wire 7692→7812 超 7900 fit 上限 7734 截断——**WORDLIST_PROMPT_BYTES 7900→8050 上调**（fit 上限 7884 ≥ 7812 + 72B 余量——llm.py 注释链第 14 次上调记录；推荐真实库预算回归 test_recommend_real_library_budget 实证 ≥2KB 余量不受影响）；test_pins 宏表 +6、test_default_layout 白名单 PA4/PB5/PB0 +1×3（conflict_groups_resolved PB0 断言 +ec11.EC11_SW 更新）。**

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
