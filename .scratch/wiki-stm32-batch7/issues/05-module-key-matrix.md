# 05 — key_matrix 4×4 矩阵键盘（B 类新 slug · 仅 stm32 条目 · 8 脚宏族，手册 sensor--4x4-keyboard.md）

**要做什么：** 模块库新增 **`key_matrix`**（库内无此模块——B 类，**仅 stm32 平台条目**）：从地阔星页面提炼 4×4 矩阵键盘驱动为纯驱动切片（**4 行输出（gpio_out，低有效拉低）+ 4 列输入（gpio_in，上拉）**——行列扫描），API：`key_matrix_init()`（8 脚配置：行 OUT_PP 初始高、列 IU 上拉输入）+ `key_matrix_scan()`（uint8 返回键值——逐行拉低扫列（页面原式），键值 `i*4+j+1`（**1-16 行主序，0=无键**）；**防抖/连按/释放语义归调用方节拍**——页面无防抖、main 500ms 演示节拍会丢键，不落）。

**关键事实（%TEMP%\batch7-facts.md）：** F1；页面行列全 GPIOA（行输出=PA7-4 低有效、列输入=PA3-0 上拉——**全被既有角色占用不照抄**）；L22「bsp_mh100x.c」vs L39 include「bsp_matrixkey.h」文件名串台（notes）；扫描序与键值 i*4+j+1 页面原式保留。

**引脚与默认脚（同选概率最低推理——8 脚分配是 stm32 硬约束）：**
- pins：`KEY_MATRIX_ROW1..4`（gpio_out，default **PB12/13/14/15**）+ `KEY_MATRIX_COL1..4`（gpio_in，default **PA9/PA10/PB10/PB11**），required true。
- **宏族设计**（跨端口 → 逐脚宏，照批 2 UART 先例）：`KEY_MATRIX_ROW1_GPIO/_ROW1_PIN` … `ROW4_GPIO/_ROW4_PIN` + `COL1_GPIO/_COL1_PIN` … `COL4_GPIO/_COL4_PIN` = **16 宏**，pin_config.h 新段（注释如下）。
- 理由：ROW=PB12-15 叠 DIP0-3+GRAY_D1-4+ttp224——**互替件同脚先例**（open_mv4×digit_uart）：矩阵键盘（机械）与 ttp224（触摸 4 键）互替、同选概率最低、同脚经绑定消解（二选一接入）；COL=PA9/PA10/PB10/PB11 叠 DIGIT/COORD/UWB UART + ZIGBEE UART——键盘与视觉/数传链路不同框；刻意不叠人机面板组合（KEY/OLED/数码管——键盘+屏幕/按键同框）。

**被谁阻塞：** 无——可立即开始（本批最重件）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/key_matrix/` 新目录：`code/key_matrix_stm32.c/.h`（8 脚 gpio_init/gpio_set/gpio_get；`key_matrix_scan` 逐行拉低→扫 4 列→恢复行高（页面原式）；零引脚字面量/零标准库/无防抖代码）
- [x] `manifest.json`（**仅 platforms.stm32**：files、dependencies []、verified true、hardware_bound false、pins 8 行、kit（4×4 矩阵键盘——页面「模块来源」）、source_url `https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/4x4-keyboard.html`、notes（**B 类：无 mspm0 条目**+手册路径+原页+网盘+文件名串台+防抖归调用方+8 脚默认分配推理+未上板）+ description（能力方向：矩阵键盘输入/16 键扫描；无题绑定）
- [x] pin_config.h 增 16 宏（注释如上）
- [x] 测试 `tests/test_module_key_matrix.py`：形状（仅 stm32/8 pins/16 macros）+宏存在（抽 4 条断言：ROW1/PB12、COL1/PA9、COL4/PB11——16 宏全量在场）+**stm32 单选生成全流程**+**mspm0 missing 警告断言**+守卫（`i * 4 + j + 1`、0-16 语义注释、无防抖/delay_ms/while 等待、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 16 宏；test_default_layout.py 白名单：PB12-15 +4（key_matrix ROW——ttp224 同脚组）、PA9/PA10/PB10/PB11 +4（COL——注 PA10 与 joystick SW 并列登记；conflict_groups_resolved PB10/PB11 断言更新）
- [x] UV4 矩阵（init+scan，(void) scan 化——scan 无参返 uint8）→ 0/0 → verified=true
- [x] wordlist 补录（models +「4×4 矩阵键盘」+ solution lib_modules=key_matrix——B 类；**默认词表完整 wire 7886 > 8050 fit 上限 7884（差 2B）截断 → WORDLIST_PROMPT_BYTES 8050→8120（同刀记录）**）
- [x] 中文提交 → resolved → 结论回填

**结论回填（2026-09-07）：全部完成。B 类新 slug——库内无矩阵键盘模块，从零设计（相近件：key 独立按键（上拉低有效 + 通道表）/ttp224 触摸按键（4 路 OUT））；**仅 stm32 平台条目**（mspm0 选本件 resolve_selection 报 missing 警告——测试断言 WARNING_MISSING 子串「缺少平台 mspm0 的版本」）。**8 脚宏族逐脚宏**（pin_config.h 单源 16 宏——行列跨端口、无共享端口宏无同口约束，照批 2 UART 先例；页面 port_row/port_col 数组全 GPIOA 组织不照抄）：ROW1-4=PB12/13/14/15（叠 DIP0-3+GRAY_D1-4+ttp224——**互替件同脚先例**：机械键盘×触摸 4 键互替、二选一接入无需另消解；与 DIP/GRAY 不同框、同选概率最低）+ COL1-4=PA9/PA10/PB10/PB11（叠 DIGIT/COORD/UWB UART + ZIGBEE UART——键盘与视觉/数传链路不同框；PA10 与 joystick SW 并列登记——白名单）；页面默认 PA7-4/PA3-0 全 GPIOA 全被既有角色占用不照抄；**行列扫描页面原式**：逐行拉低（低有效）→ 扫 4 列（列被拉低 = 键按下）→ 键值 **i×4+j+1**（行主序 1-16、0=无键）→ 恢复行高 → 命中即整扫退出（多键同时按只返回首个——页面 behavior；键值 1-16 顺序映射、无物理键位映射表——键面字符图由调用方/接线决定）；**无防抖/连按/释放语义——防抖归调用方节拍**（页面无防抖代码（key_scan 无延时无两次确认）、main 500ms 演示节拍会丢键——不落；调用方 10-20ms 采样 + 两次确认 + 沿检测——驱动零阻塞纯 GPIO 快扫）；API = key_matrix_init（4 行 OUT_PP 50MHz + 4 列 IU——页面 MatrixKey_GPIO_Init 等效；**行初始置高**：页面未显式置位行脚（复位 ODR=0 → 初始化后行低 = 首扫「第 0 行被迫选中」）——补初始色高行为等价无回归、扫描原式不变）+ key_matrix_scan（uint8_t 0-16）；页面缺陷：L22「bsp_mh100x.c/.h」vs L39 include「bsp_matrixkey.h」文件名串台（mh100x=他件名残留）——notes 记录不落码、main 演示（delay_ms(500)+printf）不落；verified=true（UV4 0 error/0 module warning，2026-09-07）+ kit/source_url（4x4-keyboard.html 原页）+ notes；**wordlist 补录**（感知传感器 models +「4×4 矩阵键盘」+ solution lib_modules=key_matrix——默认词表完整 wire 7812→7886 超 8050 fit 上限 7884（差 2B）截断——**WORDLIST_PROMPT_BYTES 8050→8120 上调**（fit 上限 7954 ≥ 7886 + 68B 余量——llm.py 注释链同刀记录（ec11/key_matrix 分两刀）；推荐真实库预算回归 test_recommend_real_library_budget 实证 ≥2KB 余量不受影响）；test_pins 宏表 +16、test_default_layout 白名单 PB12-15 +4（ttp224 同脚组）+ PA9/PA10/PB10/PB11 +4（conflict_groups_resolved PB10/PB11 断言 +COL3/COL4 更新）。**

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
