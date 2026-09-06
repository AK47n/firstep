# 05 — sgp30 空气质量传感器（软 I2C + CRC8，手册 sensor--sgp30-gas-sensor.md）

**要做什么：** 模块库 `sgp30` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼气体驱动为纯驱动切片（软 I2C，模块内静态 `_iic_*` 原语族 + CRC8），API 与 mspm0 版完全对齐：`sgp30_init()`（发 0x2003 初始化空气特征值/基准——页面 SGP30_Init 语义）+ `sgp30_read(uint16_t *tvoc_ppb, uint16_t *co2_ppm)`（发 0x2008 测量命令（写命令内嵌延时覆盖器件测量时长）→ 读回 6 字节 + 两组 CRC8）。

**关键事实（已取证，行号见 %TEMP%\batch3-facts.md）：**
- 页面 = F1 标准库；地址 0x58（写 0xB0/读 0xB1 8bit）；命令 0x2003（init）/0x2008（测量）；CO2 ppm + TVOC ppb 双出参（页面打包 uint32_t）；页面默认 SDA=PB8/SCL=PB9（不照抄——共总线 PA6/PA7）。
- **页面缺陷（修正+notes+守卫）**：① **CRC 缺失（主缺陷）**：`crc=crc` 自赋值丢弃 + 只读 5 字节**漏 TVOC CRC 字节**——修正：读满 **6 字节** + **两组 CRC8**（多项式 0x31 初值 0xFF）校验（照 sgp30 器件手册/mspm0 先例；失败=校验失败码）；② 读写路径 NACK 全丢——补检查与失败码；③ 正文「为 0 是读，为 1 是写」语义写反（示例/代码正确——记录不裁决）；④ 15s 预热判定仅正文未实现——归调用方（notes：上电 15s 内 CO2=400ppm/TVOC=0 恒值）；⑤ 页面默认脚互换（记录）。
- mspm0 侧 API：`sgp30_init()/sgp30_read(uint16_t *tvoc_ppb, uint16_t *co2_ppm)`（0-5 失败码 mspm0 口径），CRC8（0x31/0xFF）静态化（`sgp30_crc8`）。

**引脚与默认脚：**
- pins：`SGP30_SCL`（i2c_scl，PA6）/ `SGP30_SDA`（i2c_sda，PA7），macros 4 条（`SGP30_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN`）。
- pin_config.h 宏段同款（注释：共总线 + 重叠 MOTOR_A_DIR/DIR2 + 地址 0x58 与批次 2 全异；同选经绑定换脚）。

**被谁阻塞：** 无——可立即开始（与批次 2 的 sht30 CRC8 先例同构，可参照）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/sgp30/code/sgp30_stm32.c/.h`（独立 stm32 头；.c 静态 `_iic_*` 原语族 + `sgp30_crc8`；零引脚字面量/零标准库）
- [x] init 含 SCL OUT_OD 初始化+置高；read 读满 6 字节 + 两组 CRC8 校验
- [x] manifest.json platforms 增 stm32：files `[code/sgp30_stm32.c, code/sgp30_stm32.h]`、dependencies `["delay"]`、verified false→true、hardware_bound false、pins 4 行、kit/source_url（wiki 原页 `.../sensor/sgp30-gas-sensor.html`）、notes（手册路径+原页+网盘+缺陷清单 5 条+**CRC 修正：读 6 字节+两组 CRC8（0x31/0xFF）——器件正确性修正**+SCL 说明+预热 15s 归调用方+共总线推理+未上板）
- [x] pin_config.h 增 4 宏
- [x] 测试 `tests/test_module_sgp30.py`：形状+宏存在+SCL OUT_OD guard+单选生成全流程+mspm0 零改动守卫+缺陷守卫（CRC8 `0x31`/`0xFF` 多项式、读满 6 字节（buff[5] 读+两组校验）、`0x2003`/`0x2008`、无 `crc = crc` 式自赋值、无 printf/GPIO_Init/RCC_）
- [x] test_pins.py 补 4 宏；test_default_layout.py 白名单 PA6/PA7 组 +2
- [x] UV4 矩阵（init+read(&tvoc,&co2)，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核；中文提交 → resolved → 结论回填

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。

## 结论（2026 批次 3/05 实施回填）

- 实现：`sgp30_stm32.c/.h`（软 I2C 5us 半周期、SDA OUT_OD/IU、SCL OUT_OD+置高；API 全对齐 mspm0：init（引脚配置 + 发 0x2003）+ read（发 0x2008（内嵌 delay_ms(100)）→ 读 6 字节 + 两组 CRC8（0x31/0xFF）→ CO2/TVOC 双出参；返回 0=成功/1-5=失败码；出参判空用 0））。
- 缺陷修正：① **CRC 缺失（主缺陷）**：`crc=crc` 自赋值 + 只读 5 字节漏 TVOC CRC → 读满 6 字节 + 两组 CRC8 校验（失败 5——器件正确性修正）；② NACK 全丢 → 1-5 失败码补齐；③ 正文地址语义写反记录不裁决；④ 15s 预热判定归调用方（不内嵌死等）；⑤ 页面默认脚互换记录。
- 测试：test_module_sgp30.py 7 passed（双平台形状/宏存在/SCL OUT_OD 守卫/单选生成/代码守卫）；test_pins + test_default_layout 26 passed。
- 矩阵：stm32 单选生成 → UV4（C:/Keil5 V5.06u7）0 error、0 module warning（exit 0）→ verified=true。
- 未上板：软 I2C 时序/CRC8 校验真机验证留后续。
