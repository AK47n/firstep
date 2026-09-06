# 02 — ms5611 高精度气压/温度传感器（软 I2C + 64 位换算，手册 sensor--ms5611-pressure-sensor.md）

**要做什么：** 模块库 `ms5611` 新增 **stm32 平台条目**（mspm0 零改动）：从地阔星页面提炼气压驱动为纯驱动切片（软 I2C，模块内静态 `_iic_*` 原语族），API 与 mspm0 版完全对齐：`ms5611_init()`（复位 0x1E + delay_ms(300) + Read_PROM 8 字 0xA0..0xAE + **逐段应答检查**——页面 PROM 读缺应答检查，补 3=PROM 应答失败）+ `ms5611_read(float *temp_c, float *pressure_pa)`（**单次 D1/D2 + 一次 dT/TEMP/OFF/SENS/P 全换算**——页面 Get_pressure 重复调 Get_TEMP 二次读合并，省 ~40ms）+ `ms5611_read_altitude(float pa)`（同 bmp180 44330 公式）。

**⚠️ 64 位换算（stm32 线首次落码——本件核心）：** 页面 dT 为 uint32_t（L375）：低 20℃ 负值回绕；且 `C4×dT/128`、`C3×dT/256.0` 的 32 位有符号乘法溢出（积 ~1e11 ≫ 2^31，全温区多数读数偏差数十 hPa）——**改有符号 64 位 `long long`**（mspm0 批 13 实证+修正，表达式不变），dT = (long long)D2 − C5×256；温度出参 = `TEMP/100.0`（℃ 0.01 分辨率——页面 Get_TEMP 整数截断 `dat=(TEMP/1000)*10+(TEMP/100%10)` 修正）；气压出参 = **P（Pa）**（P 单位 0.01mbar==1Pa；页面 /100 出 hPa 改 Pa）。返回 0=成功/1=D1 段失败/2=D2 段失败/3=数据读失败（页面 NACK printf 改码，段内细分码保留内部）。

**关键事实（已取证，%TEMP%\batch4-facts.md）：** F1；地址 0xEE/0xEF（与 bmp180 同址——**互替不可同挂**）；页面默认 SDA=PB9/SCL=PB8（不照抄——共总线 PA6/PA7）；0x48/0x58 转换命令（OSR=4096）、段间 2×10ms 等待保留；系数：dT=D2−C5×256.0、TEMP=2000+dT×C6/8388608.0、OFF=C2×65536.0+C4×dT/128、SENS=C1×32768.0+C3×dT/256.0、P=(D1×SENS/2097152.0−OFF)/32768.0。

**引脚与默认脚：** pins `MS5611_SCL`（i2c_scl，PA6）/`MS5611_SDA`（i2c_sda，PA7），macros 4 条；pin_config.h 宏段同款（注释：共总线 + 重叠 MOTOR_A_DIR/DIR2 + **0xEE 互替**）。**init 含 SCL OUT_OD 初始化+置高**。

**被谁阻塞：** 无——可立即开始（与 bmp180 同批对仗实施）。

**状态：** resolved

**实施清单：**
- [x] `library/modules/ms5611/code/ms5611_stm32.c/.h`（独立 stm32 头；.c 静态 `_iic_*` 原语族；**dT/C4×dT/C3×dT 全程 long long 评估**——`long long dT = (long long)(d2 - (ms5611_cal[5] * 256.0));` 或等价；零引脚字面量/零标准库）
- [x] init 复位+300ms+PROM 8 字+应答检查；read 单次 D1/D2+全换算（long long）；read_altitude pow
- [x] init 含 SCL OUT_OD 初始化+置高
- [x] manifest.json platforms 增 stm32：files `[code/ms5611_stm32.c, code/ms5611_stm32.h]`、dependencies ["delay"]、verified false、hardware_bound false、pins 4 行、kit/source_url（wiki 原页 `.../sensor/ms5611-pressure-sensor.html`）、notes（手册路径+原页+网盘+**64 位溢出修正（long long，mspm0 批 13 同款）**+温度 0.01℃+出 Pa+二次转换合并+PROM 应答补查+0xEE 互替+SCL 说明+共总线推理+未上板）
- [x] pin_config.h 增 4 宏
- [x] 测试 `tests/test_module_ms5611.py`：形状+宏存在+SCL OUT_OD guard+单选生成全流程+mspm0 零改动守卫+守卫（`0x1E`/`0xA0`/`0x48`/`0x58`、系数 `256.0`/`8388608.0`/`65536.0`/`32768.0`/`2097152.0`、温度 `TEMP/100.0`、出 Pa、**dT 声明含 `long long`**、无 `uint32_t dT` 式、无 `%d`/`printf`）+ **64 位换算镜像单测**：负温向量（dT 负值路径）Python int64 镜像基线 ±0.5m + 海拔表（同 bmp180 公式对仗）
- [x] test_pins.py 补 4 宏；test_default_layout.py 白名单 PA6/PA7 组 +2
- [x] UV4 矩阵（init+read(&t,&pa)+read_altitude(pa)，(void) 化）→ 0/0 → verified=true
- [x] wordlist 零补录复核（ms5611 已在 wordlist lib_modules——mspm0 条目同 slug 已挂接）；中文提交 → resolved → 结论回填

**结论回填（2026-09-06）：** 全部完成。stm32 条目 = 软 I2C 总线件（SDA 方向切换 OUT_OD/IU；SCL OUT_OD 初始化+置高）；共总线 PA6/PA7（地址 0xEE 与既有 11 件全异；**与 bmp180 同址 0xEE 互替不可同挂**——notes 明示）。**64 位换算核心**：dT 全程有符号 long long（页面 uint32_t 负温回绕 + C4×dT/128、C3×dT/256.0 32 位乘法溢出——表达式不变 int64 口径，mspm0 批 13 同款沿用）；温度出参 TEMP/100.0（0.01℃）、气压出参 Pa（0.01mbar==1Pa）；PROM 读逐段应答检查（返 3）；Get_pressure 内嵌 Get_TEMP 二次重读合并（单次 D1/D2 + 段间 2×10ms 保留）；NACK printf→状态码 1-5 中断。int64 镜像单测（负温向量 ±3.6e6 钉死——32 位形态偏差 ~18kPa）。UV4 矩阵 0 error/0 module warning（2026-09-06）→ verified=true；mspm0 条目零改动；提交 c3e23c27（中文）。

**验收标准：** 全部 checkbox；pytest 绿；矩阵 exit 0；64 位镜像单测绿。
