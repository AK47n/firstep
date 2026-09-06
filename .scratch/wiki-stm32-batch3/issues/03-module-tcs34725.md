# 03 — tcs34725 颜色识别传感器（软 I2C，手册 sensor--tcs34725-color-recognition-sensor.md）

**要做什么：** 模块库 `tcs34725` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼颜色识别驱动为纯驱动切片（软 I2C，模块内静态 `_iic_*` 原语族），API 与 mspm0 版完全对齐：`tcs34725_init()`（读 ID 判器件 0x44=TCS34725/0x4D=TCS34727）、`tcs34725_read_rgb(TCS34725_RGBC *out)`（STATUS AVALID 判新数据，C/R/G/B 低字节在前）、`tcs34725_rgb_to_hsl(const RGBC*, HSL*)`、`tcs34725_set_integration_time/set_gain/enable/disable`。

**关键事实（已取证，行号见 %TEMP%\batch3-facts.md）：**
- 页面 = F1 标准库；地址 0x29（写 0x52/读 0x53，COMMAND_BIT 0x80）；RGBC 低字节在前；页面默认 SDA=PB8/SCL=PB9（不照抄——共总线 PA6/PA7）。
- **页面缺陷（修正+notes+守卫）**：① 读写路径 NACK 全丢——补 wait_ack 检查与失败码；② **RGBtoHSL c==0 除零**——防护（c==0 时输出 0/0/0）；③ extern 全局 rgb/hsl 泄漏——收敛模块内 static + 出参；④ `if(id==0x4D | id==0x44)` 按位或 → `||`；⑤ 函数名拼错 TC34725_GPIO_Init（不落）；⑥ 页面默认脚与 ADS1115 页互换（记录不裁决）。
- mspm0 侧 API 签名见 spec 决策表（结构体 TCS34725_RGBC/HSL 与 mspm0 .h 同款——stm32 .c 复用 mspm0 .h 的类型定义？**注意**：mspm0 的 tcs34725.h 已有 RGBC/HSL 结构与函数声明——stm32 侧只需新增 code/tcs34725_stm32.c（实现）+ 复用 mspm0 的 .h？**拆解**：跨平台共享协议类型（RGBC/HSL）与 mspm0 版 .h 一致，stm32 实现文件 include 同目录 tcs34725.h（mspm0 头文件含 DL_ 调用?——mspm0 .c 才是 DL 实现；.h 只是类型+API 声明。**推荐**：stm32 实现放 code/tcs34725_stm32.c，include "tcs34725.h"（复用类型与声明，若 .h 有 mspm0 专属注释/宏不影响编译），原型与 mspm0 一致——实施时若 .h 含 mspm0 专属代码（如 DL 宏）则拆成 stm32 独立 .h（照 key_stm32.h 先例：key 是独立 .h）。**裁决：照 key 先例做独立 `tcs34725_stm32.h`**（类型 RGBC/HSL 复制声明到 stm32 头？或 include 共享类型头——按实施最简单路径，避免 mspm0 .h 被 stm32 污染；notes 记录分工）。

**引脚与默认脚：**
- pins：`TCS34725_SCL`（i2c_scl，PA6）/ `TCS34725_SDA`（i2c_sda，PA7），macros 4 条（`TCS34725_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN`）。
- pin_config.h 宏段同款（GPIO_A/Pin_6、GPIO_A/Pin_7；注释：共总线 + 重叠 MOTOR_A_DIR/DIR2 + 地址 0x29 与批次 2 全异；同选经绑定换脚）。
- init 务必 SCL OUT_OD 初始化+置高。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/tcs34725/code/tcs34725_stm32.c/.h`（独立 stm32 头——照 key_stm32.h 先例，RGBC/HSL 类型与 API 声明与 mspm0 同签名；.c 静态 `_iic_*` 原语族；零引脚字面量/零标准库）
- [x] init 含 SCL OUT_OD 初始化+置高
- [x] manifest.json platforms 增 stm32：files `[code/tcs34725_stm32.c, code/tcs34725_stm32.h]`、dependencies `["delay"]`、verified false→true、hardware_bound false、pins 4 行、kit/source_url（wiki 原页 `.../sensor/tcs34725-color-recognition-sensor.html`）、notes（手册路径+原页+网盘+缺陷清单 6 条+SCL 说明+共总线推理+与 mspm0 头文件分工+未上板）
- [x] pin_config.h 增 4 宏
- [x] 测试 `tests/test_module_tcs34725.py`：形状+宏存在+SCL OUT_OD guard+单选生成全流程+mspm0 零改动守卫+缺陷守卫（`c == 0` 防护、`||`、无 `|` 按位或判 ID、rgba 低字节前注释、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 4 宏；test_default_layout.py 白名单 PA6/PA7 组 +2
- [x] UV4 矩阵（init+read_rgb(结构体)+rgb_to_hsl+set_integration_time+set_gain+enable+disable，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。

## 结论（2026 批次 3/03 实施回填）

- 实现：`tcs34725_stm32.c/.h`（独立 stm32 头——RGBC/HSL 类型与 API 声明与 mspm0 同签名同字段；软 I2C 2us 半周期、SDA OUT_OD/IU、SCL OUT_OD+置高；API 全对齐 init/read_rgb/rgb_to_hsl/set_integration_time/set_gain/enable/disable/write_reg/read_reg）。
- 缺陷修正：① 读写路径 NACK 全丢 → 低层 helper 返回状态（0/1/2）+ `read_reg_checked` 失败传播到 init/read_rgb（公开 API 签名同 mspm0）；② RGBtoHSL `c==0` 除零防护（出参不动）；③ extern 全局 rgb/hsl 收敛为出参；④ ID 判定 `||`；⑤ TC34725 拼写不落；⑥ 页面默认脚互换记录 + delay_s 笔误不落。
- 测试：test_module_tcs34725.py 7 passed（双平台形状/宏存在/SCL OUT_OD 守卫/单选生成/代码守卫）；test_pins + test_default_layout 26 passed。
- 矩阵：stm32 单选生成 → UV4（C:/Keil5 V5.06u7）0 error、0 module warning（exit 0；首版 NULL 未定义修正——出参判空用 0）→ verified=true。
- 未上板：软 I2C 时序/积分时间真机验证留后续。
