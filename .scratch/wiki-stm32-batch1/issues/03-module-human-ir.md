# 03 — human_ir 人体红外传感器（GPIO 输入，手册 sensor--human-body-infrared-sensor.md）

**要做什么：** 模块库 `human_ir` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼 HC-SR501 人体红外驱动为纯驱动切片（1 × GPIO 输入），API 与 mspm0 版对齐——`human_ir_init()`（空实现占位，gpio_init 配内部上拉输入）+ `human_ir_read()`（返回 1=感应到人体/0=未感应，按 `HUMAN_IR_TRIGGER_LEVEL` 极性）。

**关键事实（已取证）：**
- 页面 = **F1 标准库**：`RCC_APB2PeriphClockCmd(RCC_HUMANIR)`、`GPIO_Mode_IPU`、`Get_HumanIR()` = `GPIO_ReadInputDataBit(PORT_HUMANIR, GPIO_HUMANIR)?Bit_SET:Bit_RESET`、`stm32f10x.h`。
- 页面结构：bsp_humanir.c（约 45 行）/bsp_humanir.h（约 24 行）/main（`printf("%d\r\n", Get_HumanIR())` 演示——剔除）。
- **极性缺陷（确认，修正口径与 mspm0 同款）**：页面 L102 函数注释「0=感应到人体」与正文（L44）/器件规格「感应到输出**高**电平」矛盾，页面代码 L108 实际返回 `Bit_SET`（高=1）——按器件规格「高=感应到」修正，`HUMAN_IR_TRIGGER_LEVEL 1u`，manifest notes 记录「页面注释与正文/规格矛盾，按规格修正」（mspm0 版同为修正口径，先例 batch8）。

**换算实现**：`gpio_init(HUMAN_IR_GPIO, HUMAN_IR_PIN, IU)`（内部上拉输入）+ `human_ir_read` = `gpio_get(...)` 按 TRIGGER_LEVEL 宏归一。

**引脚与默认脚（同选概率最低推理）：**
- pins：`HUMAN_IR_OUT`（type `gpio_in`，default **PB7**，required true，macros `[HUMAN_IR_GPIO, HUMAN_IR_PIN]`）。
- pin_config.h 新宏段：`#define HUMAN_IR_GPIO GPIO_B` / `#define HUMAN_IR_PIN Pin_7`（注释：默认 PB7 = 叠 `GRAY_D8`（pid 灰度第 8 路输入）——人体红外与巡线车不同框、同选概率最低；刻意不叠声光/按键/门禁组合件（LED/BUZZER/KEY/SERVO）；同选经引脚绑定消解）。
- 本件 GPIO 输入——**不注册 EXTI**（轮询，mspm0 线「共享实例 ISR 唯一」先例；HC-SR501 输出脉冲慢速无中断需求）。

**被谁阻塞：** 无——可立即开始。

**状态：** claimed

**实施清单：**
- [ ] `library/modules/human_ir/code/human_ir_stm32.c/.h`（UTF-8；.c include 本模块 .h + pin_config.h + headfile.h；零引脚字面量；HUMAN_IR_TRIGGER_LEVEL 1u 宏放 .h）
- [ ] manifest.json platforms 增 stm32：files `[code/human_ir_stm32.c, code/human_ir_stm32.h]`、verified false、hardware_bound false、pins 如上、kit（HC-SR501 套件名——按页面「模块来源」）、source_url `https://wiki.lckfb.com/zh-hans/dkx-stm32f103c8t6/module/sensor/human-body-infrared-sensor.html`、notes（手册路径+原页+网盘+采购 + 极性依据/修正记录 + 默认脚推理 + 轮询不注册中断 + 未上板）
- [ ] pin_config.h 增 `HUMAN_IR_GPIO/HUMAN_IR_PIN`
- [ ] 测试 `tests/test_module_human_ir.py`：形状 + 母版宏存在 + stm32 单选生成全流程 + 守卫（无 printf/main/GPIO_Init/RCC_；HUMAN_IR_TRIGGER_LEVEL 1u；`gpio_get` 出现）
- [ ] test_pins.py STM32_MACRO_VALUES 补两宏；test_default_layout.py 白名单 human_ir×pid（PB7 重叠）
- [ ] 编译矩阵 UV4 0/0 → verified=true
- [ ] wordlist 感知传感器；词表预算链
- [ ] 中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
