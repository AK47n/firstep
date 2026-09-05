# 01 — max7219 模块（8 位数码管 + 4合1 点阵，合并 screen--8-bit-led-tube.md 与 screen--max7219-matrix-display.md）

**要做什么：** 模块库新增 `max7219` 条目（仅 mspm0）：**单模块双形态**——同一 MAX7219 芯片、同一软 SPI 驱动内核（DIN/CLK/CS 3 脚位操作 + 16 位包寄存器 API），数码管 8 位形态（BCD 译码：`max7219_write_digit` 位 1-8 / 值 0-9 或 0x0F 熄灭）与 4合1 点阵形态（无译码：`max7219_write_matrix` 8 行字模 × 级联片数 1-4）；`max7219_init(form, brightness)` 按形态配译码方式/扫描界限/亮度；选中后生成工程打开即可编译。**digit_led（8 位数码管）并入本模块**——见工单 04 决策档。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**结论：** 2026-09-05 完成并提交。两页面合并为单模块双形态：驱动内核同源（16 位包 = 寄存器地址字节 + 数据字节，MSB 先，CS 低选通/上升沿锁存）；数码管 = decode mode 0xFF + 位 1-8 + BCD 值（0x0F = 灭），点阵 = decode 0x00 + 行 1-8 + 行字模（位 7（MSB）= 最左、1 = 点亮）；级联按标准链序（首包落最远片——上游 4 合1 页面「Max7219_display 首包=第一片」命名与链序矛盾、且 Max7219_Lock 为 CS(1)带后 CS(0) 的脉冲锁存，本实现按标准锁存修正，notes 记录）；母版 syscfg 新 GPIO 实例 MAX7219（3 输出，CS 初始 SET = 空闲高），默认 DIN=PB9/CLK=PA18/CS=PB18（与 DC_MOTOR AIN1/AIN2/BIN1 重叠——大数字显示/计分计时与双电机小车同选概率最低，同选经引脚绑定消解；PA18 兼 BSL 脚作输出无碍）；无 TIMER/无 GPIO 中断/无硬件 SPI 外设占用，依赖空。单选生成 → gmake 0 error / 0 warning（PASS）；未上板。

- [ ] 双页面合并决策：同芯片 MAX7219、驱动内核（Write_Max7219 位序 + 0x09/0x0A/0x0B/0x0C/0x0F 寄存器族）完全同源 → **单模块双形态**（不拆 8-bit-led-tube + max7219-matrix 两模块——重复内核、同选链接重复定义风险）；形态差异 = 译码方式（0xFF = 数码管 BCD / 0x00 = 点阵行直通）；API = `max7219_init(form, brightness)` + `max7219_write_digit` / `max7219_write_matrix` 两族 + `max7219_write_reg`（底层/级联片寻址）+ `max7219_clear`（按形态全灭：BCD 0x0F / 点阵 0x00）+ `max7219_set_chip_count`（级联片数 1-4，默认 1）
- [ ] 代码提炼：从两页面「代码块」章节抽完整 bsp → 改造为 `code/max7219.c` + `code/max7219.h`：去 main/printf、函数名规范化、引脚宏参数化（`MAX7219_PORT`/`MAX7219_DIN_PIN` 等 syscfg 生成宏）、去演示字模表（disp1 不随库入库）；级联链序 = 首包落最远片（先发最远片数据），与上游演示命名的不一致在 notes 记录
- [ ] 母版 `mspm0.syscfg`：新 GPIO 实例 `MAX7219`（3 associatedPins：DIN/CLK/CS 全 OUTPUT，CS initialValue SET = 空闲高）；默认脚 = DIN PB9 / CLK PA18 / CS PB18（与 DC_MOTOR AIN1/AIN2/BIN1 重叠——大数字显示与双电机小车同选概率最低；PA18 兼 BSL 脚，作输出无碍），注释写明依据；重叠对登记 `test_pin_bindings` 刻意表（PB9/PA18/PB18 1→2 新条目）
- [ ] `syscfg_instances.py` INSTANCE_CONSUMERS 登记 `"MAX7219": ("max7219",)`
- [ ] `manifest.json`：`dependencies: []`（软 SPI 位操作无需延时——GPIO 翻转本身慢于 MAX7219 10MHz 上限）；mspm0 平台条目（files/verified 初 false/hardware_bound false/kit+source_url 手册原页/notes 含两手册路径+原页+网盘链接+改造要点+编译记录）；pins：DIN/CLK/CS = gpio_out（default 按分配）；简介判据：能力方向（数字显示/计分计时/点阵文字图形）+ 无题绑定
- [ ] wordlist.json 补录：「显示模块」加「MAX7219 数码管/点阵显示」方案挂 `lib_modules: ["max7219"]`；models 加 "MAX7219"（digit_led 并入后不另立词条）
- [ ] 测试：`test_pins.py::MSPM0_DEFAULT_MAP` 增 3 对角；`test_syscfg_prune.py` 增 MAX7219 断言；`test_pin_bindings.py` 刻意表；新增 `tests/test_module_max7219.py`（manifest 结构 + 母版 syscfg 断言 + 单选生成 → syscfg 含 MAX7219 + 文件落盘 + main.c 调 init/write_digit/write_matrix 过静态门禁）
- [ ] 编译验证：复制 `run_joystick_matrix.py` 改 slug 为 max7219（main.c 调 init+write_digit+write_matrix）→ gmake 真编译 0 error、模块自身 warning 0（`C:/ti/ccs2050`）；结果回写 manifest verified=true + notes 记录；code-review 后中文提交
