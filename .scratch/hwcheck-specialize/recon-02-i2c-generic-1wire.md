# 侦察 02：I2C 通用与单总线六件（at24c02 / ads1115 / pca9685 / dht11 / ds18b20 / hx711）

> 2026-09-25，只读侦察（未新增 / 修改任何文件）。全部结论带 `file:line`。
> 本报告的 12 格配方草案**已喂进真校验器**（`parse_recipes` + `validate_recipes` +
> `render_recipe_section`）逐格 PASS，渲染出的 C 逐句可编——是**跑过的原文**，不是设想。

## 0. 我验证过的方法（可复现）

把 12 格草案喂进真校验器：`parse_recipes` + `validate_recipes(manifests,
interface_names(...), platform_header_names(...))` + `render_recipe_section` 打印产物 C。
**12 格全 PASS**。命令用 `py -3 -B -`（`PYTHONDONTWRITEBYTECODE=1`）不落盘。

## 1. 先把 schema 的四个非显然判据钉死（决定怎么写）

1. **read 表达式里不能有十六进制字面量**。实测报错原文：
   `'at24c02' × mspm0 的读数展示段…表达式 'at24c02_read_byte(0x00)' 里有找不到的名字 'x00'`
   —— `_bare_names` 用 `[A-Za-z_]\w*` 扫整条表达式，`0x00` 切出 `x00`（hwcheck_recipe.py:890-901）。
   **probe/init/expect 不受限**（expect 走 `_is_literal`，`0x5A` 合法）。
   → read 里写 `at24c02_read_byte(0)`、`(int)raw - 8388608`。
2. **probe 带 expect 时，`probe.calls` 每一条都渲染成 `r = <call>;`**，且**只有最后一条参与比较**
   （hwcheck_recipe.py:1274-1302）。→ void 函数不能裸写进去；写读一体的探头要用逗号表达式，
   判据调用放末尾。
3. **探头判 FAIL 直接 `return`**（hwcheck_recipe.py:1298）→ **read 段的读数在 FAIL 时根本不打印**；
   所有「失败先查什么」只能进 note.lines。init 判 FAIL 不 return（1258-1267），此时读数会照打但不可信。
4. `locals` 只收标量（`类型 名字 [= 数字]`）：数组 / 多变量 / 非字面量初值全拒 → 需要缓冲区的接口
   （`at24c02_write_page` 的 `const uint8_t*`）在配方里造不出来。

平台接口面：stm32 = 模块头 ∪ 整棵母版头（实测 6248~6280 个名字，含 `gpio_get`/`delay_ms`/
`AT24C02_SDA_GPIO`）；**mspm0 母版没有 .h，配方只能引用本模块头里的名字**（实测 dht11×mspm0
只有 5 个名字，`delay_ms`/`gpio_get` 不存在）。stm32 main.c 固定 include `headfile.h`，
**`pin_config.h` 只在有通用降级件时才自动 include**（hwcheck.py:824-849）→ 读数用到引脚宏必须自己 include。

## 2. 逐件结论（含 file:line）

### at24c02

| | stm32 | mspm0 |
|---|---|---|
| include | `at24c02_stm32.h`、`pin_config.h` | `at24c02.h` |
| prereq | 无（软 I2C 位操作，不用 ml_i2c；delay 由母版提供） | 无 |
| init | `at24c02_init()` **真配引脚**（OD+两脚置高，at24c02_stm32.c:128-131） | `at24c02_init()` **空函数**（at24c02.c:151-155），引脚靠 syscfg（mspm0.syscfg:478-488） |
| 返回 | void → **不写 init_expect** | void |

**probe（唯一强自证 = 写一字节再读回）**：

```json
{"calls":["(at24c02_write_byte(0, 0x5A), at24c02_wait_write_done(), at24c02_read_byte(0))"],"expect":"0x5A"}
```

渲染：`r = (…, …, at24c02_read_byte(0)); (r == 0x5A)?OK:FAIL`。驱动里 **write_byte 的三次
wait_ack 结果全丢**（at24c02.c:159-166），read_byte 无应答返回 0xFF（头注释 at24c02.h:57-59）
→ 只有「写进去能读回来」才是强证据；`AT24C02_ADDR`(0x50) **是器件地址不是身份寄存器**，不能当期望值。

**read**：`at24c02_read_byte(0)`（255=无应答，与合法 0xFF 不可分）、`AT24C02_SIZE`(256)、
`AT24C02_PAGE_SIZE`(16)；stm32 可加 `gpio_get(AT24C02_SDA_GPIO, AT24C02_SDA_PIN)`
（SDA 是 OUT_OD 空闲高 → 读到 1 = 总线上真有上拉/模块在），但**它只在探头通过后才打印**。

**console**：`e`

**note 要点**：① 写回读 FAIL 的第一嫌疑是 **WP 写保护脚接 VCC**（模块板 WP=VCC 只读 / GND 可写，
驱动不管）——通信好的片也会 MISS；② 空片读回 0xFF，**记号别用 0xFF**；③ 写后必须
`at24c02_wait_write_done()`（=delay_ms(5)，不自动内嵌），否则读回旧值；④ 会覆盖 0 号单元；
⑤ mspm0 的 SDA 输入**没有内部上拉** → 悬空回读值不定；⑥ stm32 默认 PA6/PA7 与 ads1115/pca9685
等 11 件共挂同一软 I2C 总线（地址互异，合法共挂）；mspm0 默认 PB24/PB8 与 STEP_MOTOR、SR04、
HC05 重叠；⑦ **mspm0 头文件说「引脚配置由 init 内 gpio_init 完成」与实现（空函数）不符**。

### ads1115

| | stm32 | mspm0 |
|---|---|---|
| include | `ads1115_stm32.h`、`pin_config.h` | `ads1115.h` |
| prereq | 无 | 无 |
| init | `ads1115_init()`（配引脚 + 写 0xC283，void） | `ads1115_init()`（**只写配置**，引脚靠 syscfg，void） |

**probe**：`{"calls":["ads1115_write_config(ADS1115_DEFAULT_CONFIG)"],"expect":"0"}`
—— 实现证据 ads1115.c:161-178：地址无应答返 **1**、寄存器指针无应答返 **2**、都 ACK 才返 **0**。
**驱动没有任何寄存器读回接口** → 探头只能是这条写事务的返回码（弱于读回，但真的基于 ACK）。

**read**：`ads1115_read(0)`（int16_t 原始值）、电压拆两行
`(v = ads1115_read_voltage(0), (int)v)` + `(int)((v - (int)v) * 10)`（locals `float v = 0`）。
⚠ **`ads1115_read()` 把失败折叠成 0** → **0 既可能是 0V 也可能是通信失败**，绝对不能当判据。

**console**：`v`

**note 要点**：±4.096V 档 1 LSB = 0.125mV；AIN0 悬空读数漂、接 GND ≈0、接 3V3 ≈26400；
**输入不得超 VDD**；ADDR 脚 → 0x48/0x49/0x4A/0x4B；切通道会重写配置；stm32 PA6/PA7 共挂。

### pca9685

| | stm32 | mspm0 |
|---|---|---|
| include | `pca9685_stm32.h`、`pin_config.h` | `pca9685.h` |
| prereq | 无 | 无 |
| init | `pca9685_init(PCA9685_DEFAULT_FREQ_HZ)`（void） | 同 |

**probe：无**（如实写「无」）：两个头文件里**一个读接口都没有**（全是 void）；驱动内部确有
`pca9685_read_reg()`，但它是 **static、寄存器宏只定义在 .c** → 配方引用不到（硬约束：名字必须在头里）
→ 板上无法自证。

**read**：严格说**没有读数**；可放 `PCA9685_DEFAULT_FREQ_HZ`(50) 作能力回显（同 led 的
`LED_CHANNEL_COUNT` 先例），unit 里写明「不是测量值」。

**console**：`c`

**note 要点**：纯写件 → 板上打不了 OK/FAIL，现象只能用示波器/逻辑分析仪看通道脚；
**照 xunji 先例，检测程序不该主动驱动执行机构**，建议这一节不放任何 set_angle/set_pwm；
`pca9685_init` 会复位 MODE1=0x00 + 设 prescale + **16 路归零共 65 次 I2C 事务 + delay_ms(5)**；
V+ 舵机供电要独立于 VCC 并**共地**；OE 低有效；**默认地址 0x40 与 sht20 同址**（同选要
`pca9685_set_address(1)`=0x41 或换独立总线）；mspm0 PB6/PB7 与 AHT10/STEP_MOTOR/HUIDU 重叠、
**SDA=PB7 与 dht11 DATA=PB7 撞**。

### dht11

| | stm32 | mspm0 |
|---|---|---|
| include | `dht11_stm32.h`、`pin_config.h` | `dht11.h` |
| prereq | 无 | 无 |
| init | `dht11_init()` void（单脚输出+空闲高） | 同 |

**probe**：`{"calls":["dht11_read(&temp, &humi)"],"expect":"0"}`，locals `float temp = 0` /
`float humi = 0`。**0 = 模块应答 + 40bit 校验和通过** → 单总线件能做到的强自证，不需要身份寄存器。

**read**：`(int)temp` / `(int)((temp - (int)temp) * 10)` / `(int)humi` / `(int)((humi - (int)humi) * 10)`
（DHT11 分辨率 1℃/1%RH，**小数位通常恒 0，正常**）。

**console**：`h`

**note 要点**：① **stm32 默认脚 PB3 = JTDO**，作 GPIO 需 `SWJ_CFG` 释放 JTAG，**库内一行都没做**
→ 默认脚很可能收不到应答，最省事的出路是改引脚绑定；② **DHT11 上电 1s 内不该发指令**，
而检测程序上电就跑 → **上电第一遍可能 FAIL，敲 h 复测**；③ 采样间隔 ≥2s；④ 失败时出参保持原值
不动 → 读数恒 0 不是「0℃」；⑤ 位循环超时只靠校验和兜底（1/256 可漏）；⑥ mspm0 PB7 与 pca9685
SDA 同脚；⑦ **mspm0 头里没有任何时序宏**（stm32 头有 7 个）→ mspm0 配方不能引用那些名字。

### ds18b20

| | stm32 | mspm0 |
|---|---|---|
| include | `ds18b20_stm32.h`、`pin_config.h` | `ds18b20.h` |
| prereq | 无 | 无 |
| init / probe | `ds18b20_init()` **返回 0 = 检测到器件**（复位+应答脉冲）；**init 与 probe 可以写同一句**（与 mpu6050 mspm0 的「init 判一次 + 探头判一次」同先例），note 里说明「这是同一次物理检查，不是测了两件事」 | 同 |

**关于 0x28 家族码 / 64 位 ROM ID：库内没有**。全模块 grep 只有 `0xCC`（跳过 ROM）/`0x44`/`0xBE`，
头文件里**没有 0x28、没有搜索 ROM、没有 CRC 接口** → 单总线唯一的自证就是 `ds18b20_init()`
的应答脉冲。要 ROM ID 得自己写驱动。

**read**：`(t = ds18b20_read_temp(), (int)t)` + `(int)((t - (int)t) * 10)`（locals `float t = 0`；
逗号表达式避免调两次，**每次调用阻塞 750ms**）；stm32 可加 `DS18B20_CONVERT_MS`(750)。
小数第一位按 0.0625 步进只会出现在 0/1/2/3/5/6/7/8/9，**末两位看不到**。

**console**：`t`

**note 要点**：① **失败签名很具体**：stm32 侧悬空 → 寄存器 0xFFFF → 读回 **-0.0625℃**；
恒 **85.0℃** = 上电默认未转换；恒 0.0℃ = 读位全 0；② stm32 的 `read_temp` **器件缺席也不报错**
→ 判在场只能靠 init；③ 量程 -55~+125℃、±0.5℃、0.0625℃/LSB、每次 750ms、建议间隔 ≥1s；
④ stm32 PB1 与 MOTOR_B_DIR2 重叠；mspm0 DATA=PA7 与 SERVO_PWM/DC_MOTOR BIN2/RC522 CS 重叠。

### hx711

| | stm32 | mspm0 |
|---|---|---|
| include | `hx711_stm32.h`、`pin_config.h`、`ml_delay.h` | `hx711.h` |
| prereq | 无 | 无 |
| init | `hx711_init()`（配引脚 PB5/PB0 + 空秤去皮；void） | **建议不调**——理由见下 |

**「悬空读回什么」**：`hx711_read_raw()` 先 `while(DT 高){delay_us(10); if(++timeout>2000) return 0;}`
（**20ms 超时**）。没接传感器时 DT 被内部上拉**一直高 → 超时 → 返回 0**。接上时返回
`count ^ 0x800000` → 无负载 ≈ **0x800000 = 8388608 = 零点**。

⚠ **本次侦察最硬的一条**：**同一节里 `hx711_read_raw()` 只能调一次**。读完 24 位 + 第 25 个脉冲后
DOUT 立刻回高，下一次数据要等一个转换周期（模块默认 10SPS = **100ms**），而驱动只等 **20ms**
→ **第二次读必然返 0**（只有 RATE 拉高到 80SPS = 12.5ms 才够）。`hx711_init()` 内部**先读一次**
（去皮）→ **init + 紧接着一次读 = 必 FAIL**。所以：

- **stm32**（init 必须调，因为要配引脚）：探头顶一个延时再读
  `{"calls":["(delay_ms(500), raw = hx711_read_raw(), (raw != 0) ? 1 : 0)"],"expect":"1"}`，
  locals `uint32_t raw = 0`，include 加 `ml_delay.h`（`delay_ms` 在母版 ml_delay.h:7-8，
  **mspm0 清单里没有，写不了**）。500ms 同时覆盖「上电后 HX711 首个数据 ~400ms」和「10SPS 100ms」。
- **mspm0**（无 delay 可用）：**不写 init**（syscfg 已把 SCK 配输出、DT 配上拉输入），
  单读作探头：`{"calls":["(raw = hx711_read_raw(), (raw != 0) ? 1 : 0)"],"expect":"1"}`。
  代价：`s_tare` 保持 0 → **gram 不可用**（`get_gram` 会给出 ≈40kg 的假数）→ 这一格不显示克数；
  冷启动第一遍可能读到 0 → **敲 w 复读**。

**read**：`raw`（24bit 偏移值，≈8388608 = 零点）、`(int)raw - 8388608`（有符号计数；
**必须十进制**）。**read 段不要再调 read_raw/get_gram**（会再次超时返 0）。

**console**：`w`

**note 要点**：① 0 = 20ms 内没等到 DRDY（没接 / 线断 / 刚上电 400ms 内 / 上一次读不到 100ms）；
② 连上时的正常范围：空秤 ≈8388608，加重物单调变化，噪声 ±几百~几千计数；③ 克换算需要去皮 +
每只秤实测标定 `HX711_GAP_VALUE`（默认 207.00f，**float 宏，不能进整数读数**）；
④ SCK 空闲低、DT 空闲高；⑤ stm32 SCK=PB5/DT=PB0；mspm0 SCK=PA28/DT=PA31
（**与 JY61P/IMU601/SHT30/FINGERPRINT 重叠**）；⑥ `^0x800000` 的 0 与超时的 0 撞车 → 0 是歧义词。

## 3. console 字符（已对真占用表核过）

保留字 `r/y/g/o/b/?`。真库已占：**stm32 = a,d,k,l,m,p,u；mspm0 = a,d,j,k,l,m,p,s,u,x**。
建议：at24c02=`e`、ads1115=`v`、pca9685=`c`、dht11=`h`、ds18b20=`t`、hx711=`w`
—— 零冲突，且帮助行 64~98 字节 < 128 行缓冲（中文 3 字节/字，说明句别超 ~30 字）。

## 4. 库内驱动缺陷 / 缺口（本次发现，均未改动）

1. **at24c02 mspm0 头/实现不符**：头写「引脚配置由 init 内 gpio_init 完成」，而 init **一行都不做**。
2. **at24c02 读写路径 ACK 全丢**：write_byte 三次 wait_ack 结果不检查，read_byte 无应答返 0xFF
   与合法 0xFF 不可分 → 只有 write_page/read_block 才有 `2 = 无应答`。
3. **ads1115 无法读回任何寄存器**；且 `ads1115_read()` 把 4 种失败都折叠成 0，与合法 0V 撞车。
4. **pca9685 板上不可自证**：内部 read_reg 与寄存器宏全在 .c 私有；void API 吞掉 NACK。
5. **hx711 时间窗与 10SPS 不匹配（最影响配方）**：20ms 超时短于 100ms 转换周期 →
   init 去皮后紧接的读必超时；init/tare 都是「消费一次采样」的读，却没有任何节流/重试。
6. **hx711 的 0 是歧义词**：`count ^ 0x800000` 在 count=0x800000 时也返 0，与超时无法区分。
7. **dht11**：位循环超时不报错（靠 1/256 的校验和兜底）；上电 1s 稳定期无等待；
   mspm0 头无时序宏而 stm32 头有（平台不对称）。
8. **ds18b20**：无 ROM/家族码/CRC 接口；stm32 的 `read_temp` 器件缺席不报错（→ -0.0625℃ 假值）。
9. **stm32 全库没有释放 JTAG 的代码**（无 SWJ_CFG/AFIO 操作），而 dht11 默认脚 PB3=JTDO
   → 默认脚可能根本收不到应答。
10. **母版源码编码**：`library/masters/stm32` 下多个 ml_*.h/.c 与 `sys/stm32f10x.h` **不是 UTF-8（GBK）**。
    配方校验读母版头用 `errors="replace"`，ASCII 名字仍能提取 → 不影响配方，但新解析器要当心。

## 5. 写配方时的共同坑（12 条）

1. read 表达式**禁用十六进制字面量**；probe/expect 可以用。
2. probe 带 expect → 每条 call 都是 `r = …`：void 用逗号表达式包起来，判据调用放**最后**。
3. 探头 FAIL 会 return → 读数不打印；**失败指引只能写 note**。
4. 慢器件的「消费型」读接口一节只调一次：hx711 ≥100ms、dht11 ≥2s、ds18b20 每次 750ms、
   at24c02 写后 5ms。用 `locals` + 逗号表达式把采样值存下来给 read 段复用。
5. locals 只能标量：带指针/长度的接口在配方里造不出缓冲区 → 用单字节接口。
6. 浮点量拆两行、负数按 `(int)` 截断 → note 必须写「两行拼起来读」。
7. include 自带：stm32 用到引脚宏要写 `pin_config.h`，跨模块调用写 `ml_delay.h` 等；
   mspm0 只写模块自己的头。
8. mspm0 配方**不能**写 `delay_ms`/`gpio_get`/`DL_GPIO_*`（母版无 .h）——平台不对称用 note 讲清。
9. **两处测试地板会因此变红**：`tests/test_hwcheck_generic.py:423-424` 的 `planned >= 157` /
   `with_init >= 132`（实测现值 **159 / 134**；这 12 格转专精后变 **147 / 124**）→ 必须**如实下调
   这两个数并写清理由**。`tests/test_hwcheck_recipe.py` 的 PILOT 常量（17 格 / 10 件）
   **不要动**。
10. 引脚：stm32 上 at24c02/ads1115/pca9685 **默认都是 PA6/PA7**（同一条软 I2C 总线，地址
    0x50/0x48/0x40 互异 → 合法共挂；只有 pca9685 0x40 与 sht20 0x40 同址要留意）；
    单总线件刻意不在 PA6/PA7。mspm0 各件脚都不同，但 dht11 DATA=PB7 与 pca9685 SDA=PB7 撞、
    hx711 PA28/PA31 与 jy61p/IMU601 撞 → 生成器按引脚绑定消解，note 里说明。
11. 这 6 件**全部未上板**（manifest 原话），note 里给的是「按数据手册/驱动实现推断的正常范围」。
12. **通用可复用写法（12 格全部通过校验且渲染成合法 C）**：「写→等→读回」逗号表达式探头
    （at24c02）、ACK 返回码探头（ads1115）、函数返回码探头（dht11/ds18b20）、三元判据探头
    （hx711 `(raw != 0) ? 1 : 0`）、`(v = 采样(), (int)v)` + 小数位两行（ads1115/ds18b20）。
