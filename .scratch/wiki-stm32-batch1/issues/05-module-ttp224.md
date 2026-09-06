# 05 — ttp224 四路电容触摸（4 × GPIO 输入，手册 sensor--ttp224-touch-sensor.md）

**要做什么：** 模块库 `ttp224` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼 4 路触摸驱动为纯驱动切片（4 × GPIO 输入，页面 OUT1-4），API 与 mspm0 版对齐——`ttp224_init()`（4 脚 GPIO 输入配置）+ `ttp224_read(uint8_t channel)`（channel 1-4，越界返回 0，1=触摸/0=未触摸）+ `ttp224_read_all()`（低 4 位掩码 bit0=通道1…bit3=通道4，支持多点触摸）+ 极性单宏 `TTP224_TOUCH_LEVEL 1u`。

**关键事实（已取证）：**
- 页面 = **F1 标准库**：`RCC_APB2PeriphClockCmd(RCC_TTP)`、**`GPIO_Mode_IPD`（下拉输入）**、每通道 GPIO_ReadInputDataBit 扫描、`stm32f10x.h`。
- 页面结构：bsp_ttp.c/bsp_ttp.h/main（3 代码块；页面正文「主要就是使用 4 个 GPIO 监控模块的 OUT1-4 输出，那个 OUT 输出则说明对应区域被触摸」——**触摸=高电平**，与 IPD 匹配）。
- **与 mspm0 版差异记录**：mspm0 版为 4 × 上拉输入（IU）——上下拉差异对推挽输出模块无影响；stm32 版按**页面原式 IPD（下拉输入）**实现（ml_gpio 的 `ID` 模式），notes 记录平台差异与理由。
- 页面 4 个扫描函数（Key_IN1_Scanf 类）收敛为 `ttp224_read/read_all`（mspm0 批次先例）。

**换算实现**：`gpio_init(TTP224_GPIO, TTP224_OUTn_PIN, ID)`（下拉输入）逐脚；`ttp224_read` = `gpio_get` 按 LEVEL 宏归一（ID 模式 + LEVEL 1u = 高=触摸自洽）；无延时依赖（dependencies []）。

**引脚与默认脚（同选概率最低推理）：**
- pins：`TTP224_OUT1..OUT4`（type `gpio_in`，default **PB12/PB13/PB14/PB15**，required true，macros `[TTP224_GPIO, TTP224_OUT1_PIN]` … `[TTP224_GPIO, TTP224_OUT4_PIN]`——四脚共享 `TTP224_GPIO` 宏（同口约束，pinwriter 共享端口宏校验同值放行，I2C_GPIO 先例））。
- pin_config.h 新宏段：`#define TTP224_GPIO GPIO_B` + `#define TTP224_OUT1_PIN Pin_12` … `OUT4_PIN Pin_15`（注释：默认 PB12-15 = 叠 `DIP0-3`（config 拨码 ID）+ `GRAY_D1-4`（pid 灰度输入）——触摸按键与「拨码系统配置/巡线灰度」不同框、同选概率最低；触摸+无线链路（互替）/手动输入同框低；同选经引脚绑定消解——注：同口绑定约束=四脚须同 GPIO 口，换口需整组迁移）。
- mspm0 侧先例：默认 PA22/PA25/PA26/PA27（叠 HUIDU 巡线/ZIGBEE/NRF/joystick/IR_REMOTE/ADC MEM3）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/ttp224/code/ttp224_stm32.c/.h`（UTF-8；.c include 本模块 .h + pin_config.h + headfile.h；零引脚字面量；TTP224_TOUCH_LEVEL 1u + TTP224_CHANNELS 4u 宏）
- [x] manifest.json platforms 增 stm32：files `[code/ttp224_stm32.c, code/ttp224_stm32.h]`、verified false、hardware_bound false、pins 4 角色如上、kit（TTP224 套件名）、source_url `https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/ttp224-touch-sensor.html`、notes（手册路径+原页+网盘+采购 + 页面原式 IPD 下拉输入（与 mspm0 上拉差异）+ 触摸=高电平自洽 + 共享宏同口约束 + 默认脚推理 + 未上板）
- [x] pin_config.h 增 `TTP224_GPIO/TTP224_OUT1..4_PIN`（5 宏）
- [x] 测试 `tests/test_module_ttp224.py`：形状（4 pins 元组）+ 母版宏存在（5 条断言）+ stm32 单选生成全流程 + 守卫（TTP224_TOUCH_LEVEL 1u、ID 模式 `, ID)` 出现、无 printf/main/GPIO_Init/RCC_、read_all 掩码语义注释）
- [x] test_pins.py STM32_MACRO_VALUES 补 5 宏；test_default_layout.py 白名单 ttp224×config+pid（PB12-15 重叠，含 DIP/GRAY 四对）
- [x] 编译矩阵 UV4 0/0（MAIN_C 调 ttp224_init+read(1..4)+read_all，(void) 化）→ verified=true
- [x] wordlist 感知传感器/触控输入分类；词表预算链（slug 已挂接，零改动）
- [x] 中文提交 → resolved → 结论回填

**验收记录：**
- 矩阵 PASS：UV4 V5.06u7 `-j0 -r -b` exit 0，`0 Error(s), 0 Warning(s)`；编译日志 `.scratch/wiki-stm32-batch1/matrix/ttp224/build.log`。
- 页面原式 IPD 下拉（ml_gpio `ID`）——与 mspm0 上拉差异记录（模块推挽输出，上下拉不影响判定）；页面 GPIO_ResetBits 对输入脚冗余不保留；页面 4 个 Key_INx_Scanf 收敛 read(ch)/read_all（低 4 位掩码）。
- 页面杂项记录不修正：正文 TTP223B 文案串台（标题/采购/代码均 TTP224 4 路）、规格「100Ms」「GOIO」拼写误。
- 测试：test_module_ttp224 7 passed（双平台形状 + 5 宏存在 + stm32/mspm0 单选生成 + 守卫）；test_pins/test_default_layout 全绿（27 passed 组合跑）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
