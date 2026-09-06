# 02 — ads1115 四通道 16bit 外扩 ADC（软 I2C，手册 sensor--ads1115-multichannel-a-to-d-sensor.md）

**要做什么：** 模块库 `ads1115` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼四通道 16bit ADC 驱动为纯驱动切片（软 I2C，模块内静态 `_iic_*` 原语族——批次 2 模式），API 与 mspm0 版完全对齐：`ads1115_init()`（写默认配置 0xC283）、`ads1115_write_register(reg, hi, lo)`、`ads1115_write_config(config)`、`ads1115_read(ch)`→int16_t（MUX 切通道 + 读转换寄存器）、`ads1115_read_voltage(ch)`→float（raw/32768×FSR）、`ads1115_set_gain/set_data_rate`。

**关键事实（已取证，行号见 %TEMP%\batch3-facts.md）：**
- 页面 = F1 标准库；地址 0x48（写 0x90/读 0x91 8bit）；16bit 补码，配置默认 0xC283；页面默认 SCL=PB8/SDA=PB9（不照抄——共总线 PA6/PA7）。
- **页面缺陷（修正+notes+守卫）**：① **负值换算错误**（`(65535-num)*0.000125` 近似 + `>32768` 未含 32768——按 mspm0 版 int16_t 直乘 0.000125f 修正）；② 失败返 -1.0 与合法 -1.0V 混用（mspm0 API 出参+状态码化，照抄）；③ 注释 3/4 返回码未实现（按实际实现）；④ printf 残留（剔除）；⑤ `delay_1ms(1)` 库内无 → 换算 delay_us/ms。
- mspm0 侧 API 签名见 spec 决策表；stm32 版同函数名/同失败码/同出参单位（V）。

**引脚与默认脚（同选概率最低推理）：**
- pins：`ADS1115_SCL`（i2c_scl，default **PA6**）/ `ADS1115_SDA`（i2c_sda，default **PA7**），required true，macros 4 条（`ADS1115_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN`）。
- pin_config.h 宏段：`#define ADS1115_SCL_GPIO GPIO_A` / `_SCL_PIN Pin_6` / `_SDA_GPIO GPIO_A` / `_SDA_PIN Pin_7`（注释：共总线 PA6/PA7——与批次 2 六件同总线（地址全异 0x48）合法共享；重叠 MOTOR_A_DIR/DIR2（电机方向——外扩 ADC 与带方向的小车运动不同框）；同选经绑定换脚）。
- **init 务必 SCL OUT_OD 初始化+置高**（回修口径）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/ads1115/code/ads1115_stm32.c/.h`（UTF-8；.c include 本模块 .h + pin_config.h + headfile.h；静态 `_iic_*` 原语族；零引脚字面量/零 ml_i2c/零标准库/零 printf）
- [x] init 含 `gpio_init(ADS1115_SCL_GPIO, ADS1115_SCL_PIN, OUT_OD);` + 置高；SDA 按原语族 SDA_OUT/IN 结构
- [x] manifest.json platforms 增 stm32：files `[code/ads1115_stm32.c, code/ads1115_stm32.h]`、dependencies `["delay"]`、verified false→true、hardware_bound false、pins 4 行、kit/source_url（wiki 原页 `.../sensor/ads1115-multichannel-a-to-d-sensor.html`）、notes（手册路径+原页+网盘+采购+页面缺陷清单①②③④⑤+SCL 初始化说明+共总线推理+未上板）
- [x] pin_config.h 增 4 宏（注释如上）
- [x] 测试 `tests/test_module_ads1115.py`（照 test_module_aht10.py）：形状+宏存在+**SCL OUT_OD guard**+stm32 单选生成全流程+mspm0 零改动守卫+缺陷守卫（负值换算 `raw/32768*fsr` 且无 `65535`/无 `* 0.000125` 错误系数（与 mspm0 版守卫同款——issue 的 `* 0.000125f` 口径按库内既有守卫钉死为正确式）、无 `printf`/`delay_1ms`/`GPIO_Init`/`RCC_`）
- [x] test_pins.py STM32_MACRO_VALUES 补 4 宏；test_default_layout.py 白名单 PA6/PA7 组 +2（ADS1115）
- [x] UV4 矩阵（MAIN_C 调 init+read(0)+read_voltage(1)+set_gain+set_data_rate+set_address，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核（slug 已挂接）；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。

## 结论（2026 批次 3/02 实施回填）

- 实现：`ads1115_stm32.c/.h`（软 I2C 2us 半周期、SDA OUT_OD/IU 切换、SCL OUT_OD+置高；API 与 mspm0 全对齐——init/write_register(0/1/2)/write_config/read(int16_t 失败 0)/read_voltage(raw/32768×FSR)/set_gain/set_data_rate/set_address）。
- 缺陷修正：① 负值换算 int16_t 补码正确式（无 65535-num 近似、无 `>32768` 未含 32768）；② 失败返 -1.0 → int16_t 失败返 0；③ 注释 3/4 → 按实际实现 0/1/2（高/低字节无应答页面忽略，mspm0 同款）；④ printf 剔除；⑤ delay_1ms → delay_ms(1)。
- 测试：test_module_ads1115.py（双平台形状/宏存在/SCL OUT_OD 守卫/stm32+mspm0 单选生成/代码守卫）7 passed；test_pins + test_default_layout 26 passed（组合跑）。
- 矩阵：stm32 单选生成 → UV4（C:/Keil5 V5.06u7）0 error、0 module warning（exit 0）→ verified=true。
- pin_config.h 批次 3 宏段（24 宏一次落位——含本件 4 宏；后续 03-07 复用）。
- 未上板：软 I2C 时序/MUX 切换真机验证留后续。
