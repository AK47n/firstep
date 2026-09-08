# 批次 4「气压/单总线组」— 立创 wiki 地阔星 STM32F103C8T6 手册模块批量入库（stm32 线）

## 问题陈述

stm32 线进度：批次 1-3 已入库 18 件（min 6 + 软 I2C 总线件 6 + 器件库组 6，均 0/0 矩阵 + 回修闭环）。本批 = **气压/单总线组**：bmp180、ms5611（软 I2C，64 位换算重点件）、dht11、ds18b20（单总线位时序）+ vl53l0x（**B 类新 slug，首个仅 stm32 条目**——但页面驱动不自洽（仅 1 个 60 行 main 演示块，驱动全在页外），**需用户下载网盘资料**，工单 05 待资料（blocked））。

## 方案

照批次 1-3 管线。软 I2C 两件 = 模块内静态 `_iic_*` 原语族 + 逐脚 4 宏 + 共总线 PA6/PA7 + **init 含 SCL OUT_OD 初始化+置高**（批 3 回修口径）；单总线两件 = 单脚双向（`gpio_init` 方向重配 OUT_PP/IU + `delay_us` 忙等 + 时间轴常量单源 .h）；vl53l0x 待网盘资料（工单列下载清单）。每件：提炼 → 纯驱动切片（API 与 mspm0 全对齐）→ 换算 → pin_config.h 宏段 → manifest → 测试 → UV4 矩阵 0/0 → verified → 中文提交。

## 用户故事

1. 做题用户选 stm32 + bmp180/ms5611：`init/read(t,pa)/read_altitude(pa)` 直接出 ℃/Pa/海拔（64 位换算正确、0.01℃ 精度）——不再「需自备」。
2. 做题用户选 stm32 + dht11/ds18b20：`init/read/temperature/humidity` 单总线直接读（超时保护、校验和、位时序常量单源），断线不卡死。
3. 做题用户选 stm32 + vl53l0x（资料到位后）：新模块仅 stm32 条目（mspm0 缺条目标 missing，B 类口径），`vl53l0x_init/read_mm` 直接 ToF 测距。
4. 维护者：每件 stm32 条目可溯源（wiki 原页 source_url + notes 手册路径/网盘/修正记录）。

## 实现决策

### 既定事实（勿重新调研；batch4-facts.md 已取证，全部 F1 无 F4）

① **页面默认脚全不照抄**：bmp180/ms5611 = SDA=PB9/SCL=PB8（=母版 OLED 段）；dht11/ds18b20 = DATA=PB0（=MOTOR_B_DIR）。
② **软 I2C 地址**：bmp180/ms5611 均为 0xEE（8bit 写地址，0x77<<1）——与库内既有 11 件全异；**bmp180×ms5611 同址 0xEE = 互替件不可同挂**（同一总线同址双选 = 必冲突），notes 明示（各自单选默认共总线 PA6/PA7 无妨）。
③ **64 位换算（stm32 线首次落码，mspm0 批 13 修正沿用）**：ms5611 `dT` 必须 **有符号 64 位**（页面 uint32_t：低 20℃ 负值回绕；`C4×dT/128`、`C3×dT/256.0` 的 32 位有符号乘法溢出——积 ~1e11 ≫ 2^31，全温区多数读数偏差数十 hPa）；bmp180 `B7` 可达 ≥2^31 → 双分支保留（非恒真）。
④ **单位口径**：ms5611 温度出参 `TEMP/100.0`（℃保留 0.01 分辨率——页面整数截断修正）；两件气压出 **Pa**（ms5611 P 单位 0.01mbar==1Pa，页面 /100 出 hPa 改为 Pa）；海拔共用 `44330×(1−pow(p/101325.0, 1/5.255))`（math.h/pow，mspm0 侧先例）。
⑤ **单总线**：dht11 响应超时 → 返回 1（mspm0 批 2 修正：0=成功/1=超时，出参化）；ds18b20 0x44 后补 **750ms** 转换等待（mspm0 批 6 修正——页面无等待，首次读回 85℃ 默认值）+ 位槽常量单源 .h（12us/60us/750us 复位）+ 读毕释放总线 + 页外声明剔除。
⑥ **mspm0 API（对齐签名）**：bmp180 `init()/read(float*,float*)/read_altitude(float)`；ms5611 `init()/read(float*,float*)/read_altitude(float)`；dht11 `init()/read(float*,float*)/read_temperature()/read_humidity()`（缓存语义）；ds18b20 `init()/read_temp()→float`（失败语义照 mspm0 .h 注释）。
⑦ **B 类口径**（用户拍板）：vl53l0x 新 slug 仅 stm32 条目（mspm0 缺条目标 missing 警告）；**页面驱动不自洽**（block 1 = 60 行 main 演示；驱动符号全页外——网盘 VL53L0X 文件夹 + sys.h 位带；无引脚表/零寄存器事实）→ 需用户下载后实施（工单 05 待资料）。
⑧ **测试/矩阵**：照批次 1-3（test_module_<slug>.py 模板 + STM32_MACRO_VALUES + test_default_layout 白名单 + UV4 矩阵 0/0）；**64 位镜像单测**（ms5611/bmp180 换算纯函数 Python 镜像 ±0.5m 海拔表——mspm0 批 13 先例）；单总线时间轴常量守卫。

### 各件决策

| 工单 | slug | 形态 | 默认脚 | API（与 mspm0 对齐） | 页面缺陷（修正+notes+守卫） |
|---|---|---|---|---|---|
| 01 | bmp180 | 软 I2C | SCL=PA6/SDA=PA7（共总线） | `bmp180_init()`（0xAA..0xBE 11 项校准封装）+ `bmp180_read(t,pa)`（**Get_Pressure 内嵌 Get_Temperature 二次转换合并**——单次转换 B5 复用）+ `bmp180_read_altitude(pa)` | ① 二次转换重读合并；② NACK 仅 printf L302-308/330-332 → 状态码（0=成功/1=温度段/2=气压段）；③ char ack 死变量；④ B7 uint32_t 双分支（≥2^31 可达）保留+注释（按页面/标准双分支）；⑤ 掩码 `& 0xFFFC` 不得出现（BMP180 无掩码——反向守卫）；⑥ 页面默认 PB8/9 不照抄 |
| 02 | ms5611 | 软 I2C | SCL=PA6/SDA=PA7（共总线） | `ms5611_init()`（复位 0x1E+delay 300ms+PROM 8 字 0xA0..0xAE+**逐段应答检查**（页面缺——补 3=PROM 应答失败））+ `ms5611_read(t,pa)`（**单次 D1/D2 + 一次全换算**——页面 Get_pressure 重复调 Get_TEMP 二次读合并）+ `ms5611_read_altitude(pa)` | ① **dT 改 long long**（64 位溢出——核心）；② 温度 `TEMP/100.0`（0.01℃）；③ 气压出 Pa；④ PROM 应答检查补；⑤ 页面 Get_TEMP 整数截断修正；⑥ 段间 2×10ms 保留；⑦ 与 bmp180 同址 0xEE 互替——notes |
| 03 | dht11 | 单总线 | DATA=**PB3**（叠 KEY+GRAY_D6——环境件与独立按键/巡线不同框；不叠声光+传感站组合） | `dht11_init()`（单脚 OUT_PP/IU 方向配置）+ `dht11_read(t,h)`（0=成功/1=超时——**页面返回语义混用（0=失败/非0=数据）修正**；40bit 湿整+湿小+温整+温小+校验和）+ `dht11_read_temperature/read_humidity`（缓存，失败保持上次值） | ① 响应/位等待超时无错误汇报 L270-296 → 超时返回 1；② 返回语义归一（0=成功）；③ delay_uus 页外 → delay_us；④ RCU_DHT11 未用宏不落；⑤ extern 全局泄漏收敛；⑥ 19ms 起始 + CHECK_TIME 28us + 位 0/1=54us 低+27/74us 高常量单源 |
| 04 | ds18b20 | 单总线 | DATA=**PB1**（叠 MOTOR_B_DIR2——测温与单电机方向不同框；不叠声光/传感站） | `ds18b20_init()`（单脚配置+总线释放）+ `ds18b20_read_temp()`→float（12bit 0.0625℃、负温补码；失败语义照 mspm0 .h） | ① **0x44 后补 750ms** 转换等待（页面缺失——首次读回 85℃）；② 页外声明 DS18B20_Reset 剔除；③ L51-66 三标题错位+L107「MLX90614」串台+L143 DQ_OUT 注释相反（不落/注释修正）；④ 读槽 2+12+50=64us 落 60-70us；⑤ 复位 750us/释放 15us；⑥ 位槽常量单源 .h（照 mspm0 批 6） |
| 05 | vl53l0x | I2C（**待资料**） | 待定（资料到位后共总线或独立） | 待定（资料到位后按网盘驱动定；预期 `vl53l0x_init()/vl53l0x_read_mm(float*)`） | **页面不自洽**：block 1=60 行 main 演示；驱动符号页外（网盘 VL53L0X 文件夹+sys.h）；无引脚表/零寄存器事实；块内 Status 错误粘滞 L103-111/vl53l0x_data 无声明 L106/L22「温度范围:2m」串台——**需下载：网盘 2 条链接（网盘索引.md vl53l0x 行）的 VL53L0X 驱动源码包 + 寄存器表 + 接线图**；下载后放 `sources/materials/lckfb-地阔星移植手册/网盘下载/vl53l0x/` 并通知 |

### 默认脚与重叠全景（定稿）

| slug | 默认脚 | 重叠主体（同选概率最低） |
|---|---|---|
| bmp180 | SCL=PA6/SDA=PA7 | MOTOR_A_DIR/DIR2（共总线；与批 2/3 同总线地址全异；**与 ms5611 同址 0xEE 互替**） |
| ms5611 | SCL=PA6/SDA=PA7 | 同上（互替件错开语义=不可同挂，notes） |
| dht11 | DATA=PB3 | KEY+GRAY_D6（环境件与独立按键/巡线不同框；不叠声光/传感站组合——温湿度+声光/显示为常见搭配） |
| ds18b20 | DATA=PB1 | MOTOR_B_DIR2（测温与单电机方向不同框；不叠声光/传感站/总线环境件） |
| vl53l0x | 待定 | 资料到位后定（建议同款低同框分配） |

- 四件默认互不相撞（PA6/PA7 + PB3 + PB1——PB3 现 2 角色三叠、PB1 现 1 角色二叠，白名单登记）；vl53l0x 待资料后补。
- 白名单登记：PA6/PA7 组 +2×2（bmp180/ms5611 各 2 角色——与批 2/3 总线共享组同组）、PB3 +1（dht11）、PB1 +1（ds18b20）。

## 测试决策

- `tests/test_module_bmp180.py` / `test_module_ms5611.py` / `test_module_dht11.py` / `test_module_ds18b20.py`（照批次 2/3 模板）：形状+宏存在+**I2C 件 SCL OUT_OD guard**+单选生成全流程+mspm0 零改动守卫+缺陷守卫：
  - bmp180：`0xAA`/`0xBE` 校准基址、`32768.0`/`2048.0`/`0.1f`、`44330`/`101325.0`/`5.255`、无 `& 0xFFFC`；
  - ms5611：`0x1E`/`0xA0`/`0x48`/`0x58`、系数 `256.0`/`8388608.0`/`65536.0`/`32768.0`/`2097152.0`、温度 `TEMP/100.0`、出 Pa、`long long`/`int64_t` dT、无 `uint32_t dT` 式；
  - dht11：`19`ms/`28`us/`54`us/`27`us/`74`us 常量、`0=`成功返回语义、无 `delay_uus`、校验和；
  - ds18b20：`750`ms 等待、`0xCC`/`0x44`/`0xBE`、`12`us/`60`us/`750`us 位槽、无 `MLX90614` 串台（注释内允许记录? 守卫=源码无串台字面量,notes 记录页面串台）、负温补码注释（`* 0.0625f`）。
- **64 位换算镜像单测（最高既有接缝）**：ms5611/bmp180 气压→海拔纯函数 Python 镜像（mspm0 批 13 先例：math.pow 基线表 ±0.5m）；ms5611 dT 低负温测试向量（int64 基线断言——防 uint32_t 回潮）。
- `tests/test_pins.py` STM32_MACRO_VALUES 补 8 宏；test_default_layout.py 白名单（PA6/PA7 组 +4、PB3 +1、PB1 +1）。
- UV4 矩阵（照 run_<slug>_matrix.py 配方；bmp180/ms5611 MAIN_C 带 (void)read_altitude 等）→ 0/0 → verified=true。
- vl53l0x：资料到位后补 test/矩阵（工单 05 实施清单预列）。

## 范围外

- vl53l0x 实施（待用户下载资料——工单 05 阻塞）；mspm0 条目改动（全部零改动——vl53l0x 非 mspm0 无）；C 类核对（批次 11）；母版 ml_i2c 改造；上板真机验证（notes）。
- ms5611 OSR/SPI 模式（固定 4096/I2C）；bmp180 oss 参数化（固定 0）+ BMP280 换代；ds18b20 12bit 以外分辨率/寄生供电；dht11 采样节拍（归调用方）；vl53l0x 多目标/连续测量模式（资料后按驱动定）。

## 补充说明

- 排序：01 bmp180 → 02 ms5611（互替件同批对比实施、64 位换算镜像单测对仗）→ 03 dht11 → 04 ds18b20（单总线打样对仗）→ 05 vl53l0x（待资料，不阻塞 01-04）。
- 页内事实 = %TEMP%\batch4-facts.md（b51a0eaa 报告，2026-09 回填本表）；地猛星/地阔星页程序体 diff 全同（mspm0 批 13/6/2 修正记录 stm32 版原样沿用——报告中已逐条核对）。
- 收尾清单：全量测试→sweep 更新→code-review 两轴→CONTEXT 补录→中文提交。
