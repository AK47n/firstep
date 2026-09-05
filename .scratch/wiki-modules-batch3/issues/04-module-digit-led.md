# 04 — digit_led 决策档（8 位数码管：并入 max7219，不独立入库）

**要做什么：** 决定 digit_led（8 位数码管形态）的落库形态——独立模块，还是并入工单 01 的 max7219 模块。本工单只在工单 01 决策后落档，无独立实施。

**被谁阻塞：** 工单 01（max7219）——本工单是 01 的决策子项。

**状态：** resolved

**结论：** **并入 max7219（不独立入库）**。决策依据（写于 spec 与工单 01）：① 同芯片——8 位数码管与 4合1 点阵都用 MAX7219 控制，驱动内核（16 位包位序 Write_Max7219 + 寄存器族 0x09/0x0A/0x0B/0x0C/0x0F）完全同源；② 拆两模块 = 两份内核 + 两套 GPIO 实例 + 两处 wordlist 挂接，且同选时链接期 `Write_Max7219` 强符号重复定义（L6200E）；③ 单模块双形态费用 = 一个 form 参数 + 两族服务函数（`max7219_write_digit` 数码管 / `max7219_write_matrix` 点阵），8 位数码管形态即 `max7219_init(MAX7219_FORM_DIGIT, ...)` + `max7219_write_digit` 可直接使用——**用户选 max7219 即同时覆盖 digit_led 的 8 位显示需求**；④ wordlist「显示模块」只挂 max7219 一条（models 加 "数码管"、"MAX7219" 已有语义——数码管词条 lib_modules 指向 max7219）。digit_led 不再另建目录/另开工单。

- [x] 与工单 01 对齐：MAX7219 模块覆盖 8 位 BCD 数码管形态（write_digit）——digit_led 需求闭环
- [x] 重复驱动取舍记录：不推荐拆 8-bit-led-tube + max7219-matrix 两模块 / 不推荐再启 digit_led 第三模块——全部写进 spec「digit_led 决策」节
- [x] 收尾：wordlist 显示模块 = max7219 单挂接（"数码管" models 词条保留）；无独立测试/编译矩阵（随工单 01 一并验收）
