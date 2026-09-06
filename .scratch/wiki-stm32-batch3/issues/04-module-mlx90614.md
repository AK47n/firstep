# 04 — mlx90614 非接触红外测温（软 I2C，手册 sensor--mlx90614-non-contact-temp-sensor.md）

**要做什么：** 模块库 `mlx90614` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼 SMBus 测温驱动为纯驱动切片（软 I2C，模块内静态 `_iic_*` 原语族），API 与 mspm0 版完全对齐：`mlx90614_init()`（空实现占位——无上电初始化序列；但**含 SCL OUT_OD 初始化+置高**，这是本批责任非空）+ `mlx90614_read_object_temp(float *temp_c)`（寄存器 0x07）/`mlx90614_read_ambient_temp(float *temp_c)`（寄存器 0x06），返回 0=成功/1=通信失败（出参带回——**不返回温度值**，0=成功/失败码，与 mspm0 一致；0℃ 合法值不与失败混用）。

**关键事实（已取证，行号见 %TEMP%\batch3-facts.md）：**
- 页面 = F1 标准库；地址 0x5A（写 0xB4/读 0xB5 8bit）；换算 0.01℃/LSB（0.02K/LSB 源码 → `* 0.02f - 273.15f`）；页面默认 SCL=PA0/SDA=PA1（不照抄——PA0/1 = ADC/电机 PWM 常备件；共总线 PA6/PA7）。
- **页面缺陷（修正+notes+守卫）**：① **PEC/CRC 整体禁用**——PEC_Calculation 定义未调用且读时序无 PEC 字节（与正文 L52 矛盾）；按 mspm0 先例剔除 PEC、notes 记录（「页面演示无 PEC 也通」）；② 失败 `return 0.0` 与合法 0℃ 混用 → **出参 + 状态码**（mspm0 API 已如此，照抄）；③ 注释 MLX90615 笔误（不落）；④ 「必须开漏」注释 vs 代码 Out_PP——**按总线协议与批次 2 先例统一 OUT_OD**（SCL/SDA 均开漏 + 外上拉；页面代码 PP 差异记 notes）；⑤ **写-读间 delay_ms(1) 被页面注释掉 → 加回**（SMBus 最小空闲时序点）；⑥ 无温补/发射率修正（mspm0 同款，notes——出厂校验器件）。
- mspm0 侧 API：`mlx90614_init()/read_object_temp(float*)/read_ambient_temp(float*)`（见 spec 决策表）。

**引脚与默认脚：**
- pins：`MLX90614_SCL`（i2c_scl，PA6）/ `MLX90614_SDA`（i2c_sda，PA7），macros 4 条（`MLX90614_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN`）。
- pin_config.h 宏段同款（注释：共总线 + 重叠 MOTOR_A_DIR/DIR2 + 地址 0x5A 与批次 2 全异；同选经绑定换脚）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/mlx90614/code/mlx90614_stm32.c/.h`（独立 stm32 头——照 key_stm32.h 先例；.c 静态 `_iic_*` 原语族；零引脚字面量/零标准库/零 PEC 名称）
- [x] init 含 SCL OUT_OD 初始化+置高（**本件 init 非空实现**——因引脚配置必须由 init 完成，mspm0 版为空（syscfg 代配），stm32 版承担引脚初始化，notes 说明差异）
- [x] manifest.json platforms 增 stm32：files `[code/mlx90614_stm32.c, code/mlx90614_stm32.h]`、dependencies `["delay"]`、verified false→true、hardware_bound false、pins 4 行、kit/source_url（wiki 原页 `.../sensor/mlx90614-non-contact-temp-sensor.html`）、notes（手册路径+原页+网盘+缺陷清单 6 条+SCL 说明+**PEC 禁用记录**+引脚模式 OUT_OD（页面注释✓代码 PP 差异）+共总线推理+未上板）
- [x] pin_config.h 增 4 宏
- [x] 测试 `tests/test_module_mlx90614.py`：形状+宏存在+SCL OUT_OD guard+单选生成全流程+mspm0 零改动守卫+缺陷守卫（`* 0.02f - 273.15f`、无 `PEC`、无 `return 0.0` 式失败（状态码+出参）、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 4 宏；test_default_layout.py 白名单 PA6/PA7 组 +2
- [x] UV4 矩阵（init+read_object_temp(&t)+read_ambient_temp(&t)，(void)t 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。

## 结论（2026 批次 3/04 实施回填）

- 实现：`mlx90614_stm32.c/.h`（软 I2C 2us 半周期、SDA OUT_OD/IU、SCL OUT_OD+置高；API 全对齐 mspm0：init（非空——引脚配置）+ read_object_temp/read_ambient_temp（0=成功/1=失败，出参 ℃=raw×0.02−273.15，出参判空用 0））。
- 缺陷修正：① PEC/CRC 禁用剔除（零 PEC 名称）；② 失败 return 0.0 混用 → 出参+状态码；③ MLX90615 笔误不落；④ 页面注释「必须开漏」vs 代码 Out_PP → 统一 OUT_OD（SDA_IN=IU；页面代码 PP 差异记录）；⑤ **写-读间 delay_ms(1) 页面注释掉 → 加回**（mspm0 版保留页面省略，差异记录）；⑥ 无温补/发射率（出厂校验器件，notes）。
- 测试：test_module_mlx90614.py 7 passed（双平台形状/宏存在/SCL OUT_OD 守卫/单选生成/代码守卫）；test_pins + test_default_layout 26 passed。
- 矩阵：stm32 单选生成 → UV4（C:/Keil5 V5.06u7）0 error、0 module warning（exit 0；首版 NULL 未定义修正）→ verified=true。
- 未上板：软 I2C 时序/0.02 系数真机验证留后续。
