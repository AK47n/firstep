# 06 — pca9685 16 路舵机驱动（软 I2C，手册 control--16-ch-servo-drive-module.md）

**要做什么：** 模块库 `pca9685` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼 16 路 PWM 驱动为纯驱动切片（软 I2C——芯片内部振荡器生成 PWM，MCU 零位时序；模块内静态 `_iic_*` 原语族），API 与 mspm0 版完全对齐：`pca9685_init(uint16_t freq_hz)`（默认 50Hz——PCA9685_DEFAULT_FREQ_HZ 50u）、`pca9685_set_pwm(uint8_t channel, uint16_t width)`（12bit）、`pca9685_set_angle(uint8_t channel, uint8_t angle)`（0-180° → 0.5-2.5ms 脉宽，**单式映射**）、`pca9685_set_freq(uint16_t freq_hz)`、`pca9685_set_address(uint8_t a5)`（A5 引脚：0x40/0x41 二选）。

**关键事实（已取证，行号见 %TEMP%\batch3-facts.md）：**
- 页面 = F1 标准库（**control 分类**）；地址 0x40（写 0x80/读 0x81 8bit）；12bit PWM；页面默认 SDA=PA5/SCL=PA6（不照抄——共总线 PA6/PA7）。
- **页面缺陷（修正+notes+守卫）**：① **两套角度映射不一致**（setAngle `158+angle*2.2` vs Init `145+angle*2.4`）——统一照 mspm0（0.5-2.5ms→0-180°，单式）；② main 60Hz vs 正文 50Hz → **默认 50Hz**（mspm0 同）；③ `delay_1ms(5)/(100)` 库内无 → delay_ms；④ NACK 全丢——补检查；⑤ 正文频率公式 `(50+1)` 错误（代码正确——按代码，记录）；⑥ Excel FLOOR 注释污染（不落）；⑦ 页面直接控角度（API 保留 set_pwm+set_angle 两级——角度层归一、PWM 层透传，同 mspm0）。
- mspm0 侧 API 签名见 spec 决策表（init(freq_hz)/set_pwm(ch,width)/set_angle(ch,angle)/set_freq/set_address(a5)）。
- **地址冲突（共总线后）**：pca9685 0x40 × 批次 2 sht20 0x40 同址——sht20 不可改；同选时 pca9685 调 `set_address(1)`（0x41，A5 接线）或绑定换独立总线（note 写明，不强制）。

**引脚与默认脚：**
- pins：`PCA9685_SCL`（i2c_scl，PA6）/ `PCA9685_SDA`（i2c_sda，PA7），macros 4 条（`PCA9685_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN`）。
- pin_config.h 宏段同款（注释：共总线 + 重叠 MOTOR_A_DIR/DIR2 + **地址 0x40 与批次 2 sht20 同址——同选时 set_address(1) 或绑定换线**；同选经绑定换脚）。
- init 务必 SCL OUT_OD 初始化+置高。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/pca9685/code/pca9685_stm32.c/.h`（独立 stm32 头——含 PCA9685_DEFAULT_FREQ_HZ 50u 与 API 声明（与 mspm0 同签名）；.c 静态 `_iic_*` 原语族；零引脚字面量/零标准库）
- [x] init 含 SCL OUT_OD 初始化+置高（+PCA9685 上电/频率设置按 mspm0 实现）
- [x] manifest.json platforms 增 stm32：files `[code/pca9685_stm32.c, code/pca9685_stm32.h]`、dependencies `["delay"]`、verified false→true、hardware_bound false、pins 4 行、kit/source_url（wiki 原页 `.../module/control/16-ch-servo-drive-module.html`）、notes（手册路径+原页+网盘+缺陷清单 7 条+**角度映射单式（0.5-2.5ms/50Hz）**+**0x40×sht20 同址提醒（set_address(1) 或换线）**+SCL 说明+共总线推理+未上板）
- [x] pin_config.h 增 4 宏
- [x] 测试 `tests/test_module_pca9685.py`：形状+宏存在+SCL OUT_OD guard+单选生成全流程+mspm0 零改动守卫+缺陷守卫（无 `delay_1ms`、角度映射单式（无 `* 2.2f`/`* 2.4f` 双式、含 0.0005f/0.0025f 换算式）、`0x40`/`set_address` 出现、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 4 宏；test_default_layout.py 白名单 PA6/PA7 组 +2
- [x] UV4 矩阵（init(50)+set_pwm(0,0)+set_angle(1,90)+set_freq(100)+set_address(0)，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。

## 结论（2026 批次 3/06 实施回填）

- 实现：`pca9685_stm32.c/.h`（软 I2C 2us 半周期（页面 5us 按 mspm0 统一）、SDA OUT_OD/IU、SCL OUT_OD+置高；API 全对齐 mspm0：init(freq)/set_pwm/set_angle/set_freq/set_address；s_freq_hz 模块内 static；MODE1 恢复值 oldmode|0xA1 保留页面行为）。
- 缺陷修正：① **角度映射两套不一致（主缺陷）**→ 统一 0.5-2.5ms 单式（50Hz 下 102.4-512 tick，与 servo 模块同口径，无 `* 2.2f`/`* 2.4f`）；② main 60Hz → 默认 50Hz（PCA9685_DEFAULT_FREQ_HZ=50）；③ delay_1ms → delay_ms(5)（init 的 100ms 演示等待不落——demo 节拍）；④ NACK 全丢 → wait_ack 超时内部发停止（void API 无失败码，mspm0 同款记录）；⑤ 正文 (50+1) 公式错误按代码；⑥ Excel FLOOR 注释不落；⑦ 页面直接控角度 → API 保留 set_pwm+set_angle 两级。
- 地址冲突：notes 明示 **0x40 × sht20 同址**——同选 set_address(1)（0x41）或绑定换线（不强制裁决）。
- 测试：test_module_pca9685.py 7 passed（双平台形状/宏存在/SCL OUT_OD 守卫/单选生成/代码守卫）；test_pins + test_default_layout 26 passed。
- 矩阵：stm32 单选生成 → UV4（C:/Keil5 V5.06u7）0 error、0 module warning（exit 0）→ verified=true。
- 未上板：软 I2C 时序/频率/角度真机验证留后续。
