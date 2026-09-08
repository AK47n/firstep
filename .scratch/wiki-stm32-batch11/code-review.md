# 批次 11 code-review 两轴（收官全量对仗）

- 固定点：批次 10 收官 a05f9e05 之后的全部变更（批 11/01 + 批 11/02 + 终局收尾）。
- 独立审查员双轴（并行子代理，互不污染）——结论按轴汇总，不跨轴排序。

## Standards（标准轴）

**(a) 文档化标准违反（硬违规）**

1. **提交态与「resolved/全绿」不符（workflow.md Step 4）**：批 11 成果未全提交——CONTEXT.md、budget.py、llm.py（词表预算 8300→8500 记账链）、motor/servo manifest（kit/source_url 补缺口）曾滞留工作树；sweep/收尾报告/matrix 未跟踪 → **已整改**：终局提交补齐全部文件，HEAD 全量 pytest 复验绿（见收尾报告）。
2. **工单缺 01 文件（workflow.md Step 3「one file per ticket」）**：提交信息自称批 11/01 但 issues/ 仅 02 → **已整改**：补 `.scratch/wiki-stm32-batch11/issues/01-c-class-check.md`（resolved + 结论回填）。
3. **spec 不同步（Step 2）**：spec.md「范围外」仍列 st7789_para 待资料 → **已整改**：spec.md 顶部加「状态（2026-09-12）：全部完成」注记（保留历史原始表述）。

**(b) 基线气味（判断项；仓库标准/先例压过处注明）**

- **Duplicated Code**：st7789_para_stm32.c 绘制/文本层与 ili9341/ili9488/lcd 近乎逐行同构——「每模块自带 code/ 副本」既定取舍（先例 + 模块自足性）压过，记录不整改。
- **封装/命名**：`st7789_para_wr_reg/wr_data8/wr_data/address_set` 注释「内部」却非 static 且 .h 无原型（ili9341 同款）→ **已整改**：4 函数 static 化（本件新码，越于先例；ili 先例记录留待统一）。
- **Primitive Obsession / Data Clumps / Repeated Switches**：dir 裸 uint8_t、（x,y,fc,bc,sizey,mode）参数簇、sizey==12/16 与 d==0/1 级联——「API 照 mspm0 lcd.h 风格」文档化风格压过，记录。
- **注释准确性**：ml_mpu6050.h L18-20「0x65 与 ACCEL_YOUT_L 撞值」实为无撞（ACCEL_YOUT_L=0x3E）→ **已整改**：措辞订正为「非定义寄存器（错误常量）」；st7789_para_font.h 残留《0.96寸彩屏》来源头——双重来源注释（font 真源 = 0.96 页——ili 两件同款先例），记录。
- RD 脚全链声明但只写不读：物理 8080 接线需要且 notes 已记——非 Speculative Generality，记录。

**结论**：模块代码结构层面无硬违规（ADR 0009/0005/0010 判据、引脚单源、简介四要素、中文提交均符合）；硬违规集中于提交完整性（已整改）与工单文件管理（已整改）。

## Spec（规格轴）

**(a) 规格要求但缺失/部分实现**

1. **终局收尾未提交、提交态不自洽**（HEAD 曾缺词表预算上调——329ebb34 已含 wordlist 新条目而 llm.py 预算仍 8300 → test_wordlist_segment 红证）→ **已整改**：终局提交含 budget/llm/CONTEXT/kit+source_url/sweep/报告/code-review.md，HEAD 复验全绿。
2. **code-review 产物缺失（指令③）**：收尾报告引用 code-review.md 但文件不存在（悬空引用）→ **已整改**：本文件落地。
3. **Sweep 未达「77 页对应」**：实为 74/77（A 58/61：huidu/xunji/sr04 mspm0-only 例外）→ 如实记录（指令「如有遗留如实记录」口径）；stm32 能力由 pid（巡线）/us016（超声）承接——非同 slug、范围外。
4. **ml_mpu6050.h 前置说明未做**（核对报告建议②「.h 加一行 + notes 同步」——仅 notes 落地）→ **已整改**：.h 前置注释行补齐（使用前先调 I2C_Init()）。

**(b) 未被要求的额外行为**

- servo/motor **kit+source_url 补录**：核对报告仅建议 notes 映射/订正，未要求补键值——合规配套（C 类溯源缺口补全，接受）。
- 词表预算 8300→8500（llm.py/budget.py 注释链）：工单未列——红证驱动必要配套，可接受。
- d705cf7e（批 10 changelog 尾随）混入 diff 范围，非批 11 内容（自动提交机制，接受）。

**(c) 看似实现但实现方式有偏差**

- **「清屏——全部直提包内」不实**：包内 lcd_init.c LCD_Init 无清屏（清屏在演示 main.c，白色）；实现于 init 末尾 `st7789_para_clear(BLACK)`——序列字节逐项核对无误，与 ili 两件同款先例（统一库内 BLACK 口径），功能无碍但表述失实 → **已整改**：manifest notes 措辞订正（清屏 = init 尾部动作——包内演示白、统一库内 BLACK 口径，ili 先例）。
- 其余核对通过：8080 位操作/方向表/偏移表/14 脚重拍/28 宏/API 签名与 lcd·ili 同构；0-96-iic 两项记录性建议内容在固定点已存在，无缺失。

## 汇总

- **Standards 轴**：3 硬违规（提交完整性/01 工单/spec 同步——全部已整改）+ 4 判断项（2 已整改、2 记录）；最重 = 提交完整性（整改后 HEAD 全绿）。
- **Spec 轴**：4 缺失/部分（全部已整改或如实记录）+ 2 范围外/自动提交（接受）+ 1 表述失实（已整改）；最重 = 提交自洽（整改后 HEAD 全绿）。
