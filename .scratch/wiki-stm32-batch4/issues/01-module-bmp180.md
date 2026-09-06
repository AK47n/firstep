# 01 — bmp180 气压/温度传感器（软 I2C，手册 sensor--bmp180-pressure-sensor.md）

**要做什么：** 模块库 `bmp180` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼气压驱动为纯驱动切片（软 I2C，模块内静态 `_iic_*` 原语族——批次 2 模式），API 与 mspm0 版完全对齐：`bmp180_init()`（0xAA..0xBE 逐项 Read16 读 11 项校准系数 AC1..MD 入模块静态）+ `bmp180_read(float *temp_c, float *pa)`（**单次温度转换 + B5 复用气压段**——页面 Get_Pressure 内嵌 Get_Temperature 二次转换重读合并）+ `bmp180_read_altitude(float pa)`（44330 公式，math.h/pow）。返回 0=成功/1=温度段失败/2=气压段失败（页面 NACK printf 改状态码）。

**关键事实（已取证，行号 %TEMP%\batch4-facts.md）：** F1 标准库；地址 0xEE/0xEF（0x77<<1，写/读 8bit）；**与 ms5611 同址 0xEE = 互替件不可同挂**（notes）；页面默认 SDA=PB9/SCL=PB8（不照抄——共总线 PA6/PA7）。页面缺陷：① 二次转换重读合并；② NACK 仅 printf L302-308/330-332 → 状态码；③ char ack 死变量 L207；④ **B7 uint32_t 双分支保留**（≥2^31 可达，mspm0 批 13 判定非恒真——else 分支不可删）；⑤ 掩码 `& 0xFFFC` 不得出现（BMP180 无——反向守卫）；⑥ 正文/代码系数「3072 vs 3096」类不一致（按 0.25 精度的 X1=.. 口径照 mspm0）。换算原式照 mspm0（T=((B5+8)/16)×0.1、B6..B4/B7/p 全套 32 位原式、p 出 Pa）。

**引脚与默认脚：** pins `BMP180_SCL`（i2c_scl，PA6）/`BMP180_SDA`（i2c_sda，PA7），macros 4 条（`BMP180_SCL_GPIO/_SCL_PIN/_SDA_GPIO/_SDA_PIN`）；pin_config.h 宏段（GPIO_A/Pin_6、GPIO_A/Pin_7；注释：共总线 PA6/PA7 与批 2/3 同总线地址全异；重叠 MOTOR_A_DIR/DIR2；**与 ms5611 同址 0xEE 互替不可同挂**；同选经绑定换脚）。**init 必含 SCL OUT_OD 初始化+置高**（批 3 回修口径）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实施清单：**
- [x] `library/modules/bmp180/code/bmp180_stm32.c/.h`（独立 stm32 头——照 key_stm32.h 先例；.c 静态 `_iic_*` 原语族；零引脚字面量/零标准库）
- [x] 校准结构体 + init 读 11 项；`bmp180_read` 单次转换 + B5 复用；`read_altitude` pow
- [x] init 含 SCL OUT_OD 初始化+置高
- [x] manifest.json platforms 增 stm32：files、dependencies ["delay"]（pow 走 math 库——**检查 uvprojx 无 math 显式链接项**：ARMCC 标准库自动含 math（ir_distance/pid 先例），链接不报错则无需动工程；若 L6218E 则 notes 记录并查 keil.py 是否需加——**预期不需要**）、verified false、hardware_bound false、pins 4 行、kit/source_url（wiki 原页 `.../sensor/bmp180-pressure-sensor.html`）、notes（手册路径+原页+网盘+缺陷清单 5 条+B7 双分支说明+0xEE 互替+SCL 说明+共总线推理+海拔公式分工+未上板）
- [x] pin_config.h 增 4 宏
- [x] 测试 `tests/test_module_bmp180.py`：形状+宏存在+SCL OUT_OD guard+单选生成全流程+mspm0 零改动守卫+守卫（`0xAA`/`0xBE`、`32768.0`/`2048.0`/`0.1f`、`44330`/`101325.0`/`5.255`、无 `& 0xFFFC`、无 printf/GPIO_Init/RCC_）+ **海拔换算纯函数镜像单测**（44330 公式 Python 镜像：101325→0.0m/100000→~110.9m/95000→~540.4m，±0.5m）
- [x] test_pins.py 补 4 宏；test_default_layout.py 白名单 PA6/PA7 组 +2
- [x] UV4 矩阵（init+read(&t,&pa)+read_altitude(pa)，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核（bmp180 已在 wordlist lib_modules——mspm0 条目同 slug 已挂接）；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = 软 I2C 总线件（SDA 方向切换 OUT_OD/IU 页面原式开漏+上拉主流一派；SCL OUT_OD 初始化+置高批次 3/01 回修口径）；共总线 PA6/PA7（地址 0xEE 与既有 11 件全异；**与 ms5611 同址 0xEE 互替不可同挂**——notes 明示）；B7 uint32_t 双分支按页面/标准保留（非恒真 else 分支不可删）+ 注释；Get_Pressure 内嵌 Get_Temperature 二次转换合并（B5 复用）；NACK printf→状态码 0/1/2；char ack 死变量剔除；无 & 0xFFFC 反向守卫；海拔 44330 公式（math.h/pow，ARMCC 自动含 math 无需显式链接项——矩阵实证）。UV4 矩阵 0 error/0 module warning（2026-09-06）→ verified=true；mspm0 条目零改动；提交 b93cb1df（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0。
