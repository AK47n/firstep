# 07 — hx711 称重传感器（GPIO 双线 24bit，手册 sensor--hx711-weighing-sensor.md）

**要做什么：** 模块库 `hx711` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼 24 位称重驱动为纯驱动切片（SCK 输出 + DT 输入双线，非 I2C——本批唯一 GPIO 时序件），API 与 mspm0 版完全对齐：`hx711_init()`（SCK 配输出、DT 配上拉输入 + 上位机协议空闲电平）、`hx711_tare()`（去皮——当前读数存为零点）、`hx711_read_raw()`（读一次原始 24 位数据，通道 A 增益 128；0=转换失败超时）、`hx711_get_gram()`（读一次并换算克数，float，含去皮；raw 越界负值返回 0）。

**关键事实（已取证，行号见 %TEMP%\batch3-facts.md）：**
- 页面 = F1 标准库；SCK=PB8/DT=PB9 页面默认（不照抄——PB8/9=OLED 段；本件独立默认脚）；24bit 有符号补码；页面「查看资料」节空（不提炼）。
- **页面缺陷（修正+notes+守卫）**：① **`while(DT_GET());` 无界轮询（主缺陷）**——拆机/未接传感器时死等；修正 = **20ms 超时**（mspm0 先例，超时返回 0=失败）；② 全局泄漏（HX711_Buffer/Weight_Maopi/Weight_Shiwu 非 static）+ Flag_Error 死变量——收敛模块内 static；③ **GapValue 207.00 演示校准常数**——参数化（照 mspm0：宏或模块级可调，换算 = (raw - zero)/scale 口径按 mspm0 实现）；④ 24bit 补码 `^0x800000` 转无符号偏移量（mspm0 同款——负重钳 0）；⑤ 页面默认脚 PB8/9（不照抄）。
- mspm0 侧 API：`hx711_init()/tare()/read_raw()/get_gram()`（见 spec 决策表）。

**引脚与默认脚（同选概率最低推理）：**
- pins：`HX711_SCK`（type `gpio_out`，default **PB5**，macros `[HX711_SCK_GPIO, HX711_SCK_PIN]`）/ `HX711_DT`（type `gpio_in`，default **PB0**，macros `[HX711_DT_GPIO, HX711_DT_PIN]`），required true。
- pin_config.h 宏段：`#define HX711_SCK_GPIO GPIO_B` / `_SCK_PIN Pin_5` / `_DT_GPIO GPIO_B` / `_DT_PIN Pin_0`（注释：默认 SCK=PB5 / DT=PB0——PB5 叠 MOTOR_A_ENC（光电编码器闭环小车——与静态称重/电子秤不同框）；PB0 叠 MOTOR_B_DIR（TB6612 B 相方向——不同框）；**刻意不叠**本批 I2C 件与采集类（flame/ir_beam/human_ir——称重+传感站常见组合）与声光件（秤+报警灯/蜂鸣常见）；同选经绑定消解）。
- 页面默认 SCK=PB8/DT=PB9 **不采用**（OLED 段常备件）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/hx711/code/hx711_stm32.c/.h`（独立 stm32 头；.c 用 gpio_init/gpio_set/gpio_get；SCK 输出 PP、DT 上拉输入 IU——页面「先 PP 输出、读时重配 IPU」按 mspm0 先例收敛为 init 配 IU + SCK PP；零引脚字面量/零标准库）
- [x] 超时保护：DT 等待 20ms（`delay_us` 计数 2000×10us，照 mspm0 实现）；补码按 mspm0 表达式（`^ 0x800000u`）；去皮/克换算按 mspm0 口径（GAP 参数化宏 HX711_GAP_VALUE）
- [x] manifest.json platforms 增 stm32：files `[code/hx711_stm32.c, code/hx711_stm32.h]`、dependencies `["delay"]`、verified false→true、hardware_bound false、pins 2 行、kit/source_url（wiki 原页 `.../sensor/hx711-weighing-sensor.html`）、notes（手册路径+原页+网盘+缺陷清单 5 条+20ms 超时修正+补码/去皮口径+GapValue 参数化+默认脚推理+未上板）
- [x] pin_config.h 增 4 宏
- [x] 测试 `tests/test_module_hx711.py`：形状+宏存在+单选生成全流程+mspm0 零改动守卫+缺陷守卫（超时 20ms（`timeout > 2000` + 超时返回 0 语义）、无 `while (DT_GET` 无界式、无 `GapValue 207` 硬编码（参数化宏）、补码表达式与 mspm0 一致注释、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 4 宏；test_default_layout.py 白名单 PB5/PB0 组（+1/+1——叠 MOTOR_A_ENC/MOTOR_B_DIR）
- [x] UV4 矩阵（init+tare+read_raw(返 uint32 (void) 化)+get_gram(返 float (void) 化)）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。

## 结论（2026 批次 3/07 实施回填）

- 实现：`hx711_stm32.c/.h`（GPIO 双线 SCK/DT——非 I2C；SCK OUT_PP + DT IU（页面先 PP 输出再重配 IPU 按 mspm0 收敛——DT_OUT 置高 1us 为非必需动作）；API 全对齐 mspm0：init（引脚配置 + 空秤去皮）/tare/read_raw（24 位 + 第 25 脉冲，等 DT 就绪 **20ms 超时** 返 0，`^ 0x800000u`）/get_gram（(raw−tare)/HX711_GAP_VALUE，差 ≤0 钳 0.0））。
- 缺陷修正：① `while(DT_GET());` 无界轮询（主缺陷）→ 20ms 超时返 0；② 全局泄漏（HX711_Buffer/Weight_Maopi/Weight_Shiwu/Flag_Error 死变量）→ static s_tare 收敛；③ GapValue 207.00 演示常数 → HX711_GAP_VALUE 宏参数化（头文件默认 207.00f）；④ 24bit 补码 `^0x800000` 保留（mspm0 同款）；⑤ 页面「查看资料」节空不提炼。
- 测试：test_module_hx711.py 7 passed（双平台形状/宏存在/单选生成/代码守卫：超时+P 补码+GAP 参数化+static 收敛+零标准库）；test_pins + test_default_layout 26 passed（PB5/PB0 白名单）。
- 矩阵：stm32 单选生成 → UV4（C:/Keil5 V5.06u7）0 error、0 module warning（exit 0）→ verified=true。
- 未上板：GPIO 时序/20ms 超时窗口/GapValue 校准真机验证留后续。
