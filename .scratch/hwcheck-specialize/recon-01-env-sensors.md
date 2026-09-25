# 侦察 01：I2C 环境传感六件（aht10 / sht20 / sht30 / bh1750 / bmp180 / ms5611）

> 2026-09-25，只读侦察（未改任何文件）。全部结论带 `file:line`。
> 用途：`library/hwcheck_recipes.json` 写配方时的事实底稿。
> 由并行侦察子代理产出，原文照录。

## 0. 判据与公共事实（先读，决定每个字段能写什么）

**校验面（`src/contest_generator/hwcheck_recipe.py`）**

- `include.headers`：头名必须落在"该平台库内模块 .h 基名 ∪ 母版 .h 基名"里
  （`platform_header_names` hwcheck_recipe.py:369-396；`validate_recipes` 847-858）。
- `locals` 类型词、`init`/`probe` 的调用名、`read` 的调用名**与裸常量名**：只能来自
  **本模块该平台的头文件** ∪ 母版头（hwcheck_recipe.py:859-901 + `interface_names` 1040-1117）。
- **`prereq` 是唯一例外**：按"库内任何模块 ∪ 母版"判（hwcheck_recipe.py:918-927）。
- ⚠ **mspm0 母版没有 .h**（`library/masters/mspm0/` 只有 main.c / mspm0.syscfg / .project 等，实测无 .h；
  `library/masters/stm32/` 有 ml_*.h、pin_config.h、headfile.h…）。所以 **mspm0 侧 init/probe/read
  只有本模块头里的名字可用**，而 stm32 侧还白送全部母版名（`delay_ms`、`gpio_get`、`I2C_Init`…）。
  同一句配方两边判据面不同 → 见「共同坑①」。

**渲染与判定**

- `read` 表达式走 `hwcheck_report_int(int value)`（hwcheck.py:1239，带负号处理）→ 必须整型。
- `probe` 渲染成 `r = <call>;` … `(r == expect)`；**probe.calls 有多条时只有最后一条的值被比较**
  （hwcheck_recipe.py:1274-1302）。`probe.calls` 允许写赋值语句（xunji 先例：`gray = xunji_read_gray()`）。
- 渲染顺序固定：`locals` → `prereq` → `init` → `probe` → `read`（hwcheck_recipe.py:1245-1327）。
  probe 判 FAIL 会 **return**，后面的 read 不执行。
- `init_expect` 有值但 `init` 为空 → 构建期红（hwcheck_recipe.py:479-483）。

**控制台字符（实测）**

- 保留字 `r y g o b` + 帮助 `?`（hwcheck_console.py:90、99-110）；配方已占
  `l d m u k p s j x a`（library/hwcheck_recipes.json 实测去重）。
- **可用字母只剩 `c e f h i n q t v w z`**（数字 0-9 也全空，`_require_command_shape` 收数字，
  hwcheck_console.py:499-523；渲染时非字母不生成大写 case，395-400）。

**总线 / 前置（两平台都相同，结论 = prereq 全空，bh1750 除外）**

- 这 6 件在 stm32 侧**不用母版 ml_i2c**（manifest 各条目原话"不用母版 ml_i2c"）——它们直接走
  `ml_gpio`：`gpio_init/gpio_set/gpio_get`（ml_gpio.h:44-46），而 **`gpio_init` 内部自己开 RCC 时钟**
  （ml_gpio.c:17 `RCC->APB2ENR |= 4<<GPIOn;`），stm32 各模块 `init` 里自己
  `gpio_init(SCL, OUT_OD)` + 置高。
- mspm0 侧引脚由 SysConfig 实例 + `SYSCFG_DL_init()` 配好（框架已调，hwcheck.py:229-235），
  驱动自己 `DL_GPIO_initDigitalOutput/Input` 切 SDA 方向。
- **所以 6 件 × 2 平台的 `prereq` 都不需要 `I2C_Init()`**（`I2C_Init` 确实存在于 ml_i2c.h:13，但与本批无关）。
- `delay_us/delay_ms`：mspm0 在 `delay.h`（delay 模块头，library/modules/delay/code/delay.h:5-6，
  框架已为你 include，hwcheck.py:841-842）；stm32 在母版 `ml_delay.h:4-5`（经 `headfile.h`，
  ml_delay.c:10 直接用 SysTick，无需 init）。

**两平台头名对照（写配方最容易踩的一处）**

| slug | mspm0 头 | stm32 头 |
|---|---|---|
| aht10 | `aht10.h` | `aht10_stm32.h` |
| sht20 | `sht20.h` | `sht20_stm32.h` |
| sht30 | `sht30.h` | `sht30_stm32.h` |
| bh1750 | `bh1750.h` | `bh1750_stm32.h` |
| bmp180 | `bmp180.h` | `bmp180_stm32.h` |
| ms5611 | `ms5611.h` | `ms5611_stm32.h` |

**函数名两平台完全同名同签名**——配方只需换 include 头名，调用一字不改。

**12 个格全部 `verified: true`（编译矩阵绿）且全部 notes 写着"未上板"**（软 I2C 时序真机验证留后续）
——note 里要写实。

---

## 1. aht10（温湿度，地址 0x38）

| | mspm0 | stm32 |
|---|---|---|
| 头 | `code/aht10.h` | `code/aht10_stm32.h` |
| include | `["aht10.h"]` | `["aht10_stm32.h"]` |
| prereq | 无 | 无 |
| init | `aht10_init()` — **void**（aht10.h:28 / aht10.c:149） | `aht10_init()` — **void**（aht10_stm32.h:43 / aht10_stm32.c:124；内含 SCL `gpio_init(OUT_OD)`+置高，:129-130） |
| init 能否当判据 | **不能**（void） | **不能**（void） |
| probe | `aht10_read(&t, &h)` == `0`（aht10.h:32 / aht10.c:165；0=成功、1=读地址重试 ≤5 次全无应答，aht10.c:187-197） | 同左（aht10_stm32.h:48 / aht10_stm32.c:145；超时判失败在 :179-181） |
| 身份寄存器 | **无**（AHT10 无 WHO_AM_I；状态字节 buff[0] 被读进来但**丢弃**，aht10.c:199-207 只用了 buff[1..5]） | 同左 |
| read | `(int)t`、`(int)((t - (int)t) * 10)`、`(int)h`、`(int)((h - (int)h) * 10)` | 同左 |
| 单位/范围 | t：℃，-40~85℃，精度 ±0.3℃；h：%RH，0~100，±2%RH | 同 |
| console 建议 | `h` | `h` |
| 默认脚 | **PB6=SCL / PB7=SDA**（mspm0.syscfg:349,353） | **PA6=SCL / PA7=SDA**（pin_config.h:281-284） |
| 地址 | 0x38（写 0x70 / 读 0x71；aht10.c:153,174,190） | 0x38（aht10_stm32.c:133,154,173） |

**headers 里没有任何 `#define`** → probe 的 `expect` 只能写数字字面量 `"0"`。

**note 要点（写实）**

- 本件**没有身份寄存器**：探头是"整条读事务的返回码"（写地址 0x70 → 0xAC 0x33 0x00 → 轮询读地址 0x71，
  任一步 NACK 就返回 1）——它证明 0x38 上有器件应答，**不证明数据物理上准**。
- ⚠ **已知规格偏差（库内自记）**：读前的等待窗口 ≈20ms+5×1ms ≈25ms ≪ AHT10 手册要求 ≥80ms
  （aht10.c:184-186 与 aht10_stm32.c:164-169 的注释明写"真机如失败调大读前延时"）。**真机上 probe
  判 FAIL 时，第一嫌疑不是接线而是这个窗口**——先在 aht10.c:186 / aht10_stm32.c:169 的 `delay_ms(20)`
  上加大再复测。
- init 里有两次 `delay_ms(50)`（aht10.c:151,162）→ 上电这一遍在这一件上会停 ~100ms，正常。
- 读数怎么算合理：室温 20~30℃、湿度 30~70%RH 是常见室内值；湿球/呼吸吹气能看到明显跳变。
- 接线：模块 3.3V 供电、SCL/SDA 需上拉（模块板多自带）；SDA 方向运行时切换，**两平台都不要外接强上拉电阻到 5V**。

---

## 2. sht20（温湿度，地址 0x40，SHT2x 旧系列）

| | mspm0 | stm32 |
|---|---|---|
| 头 | `code/sht20.h` | `code/sht20_stm32.h` |
| include | `["sht20.h"]` | `["sht20_stm32.h"]` |
| prereq | 无 | 无 |
| init | `sht20_init()` — **void，空实现**（sht20.h:43 / sht20.c:194-198，函数体一行不做，注释明说"引脚配置由 SYSCFG_DL_init() 完成"） | `sht20_init()` — **void**，仅配脚：`gpio_init(SCL,OUT_OD)`+`gpio_init(SDA,OUT_OD)`（sht20_stm32.h:55 / sht20_stm32.c:169-176） |
| init 能否当判据 | **不能**（void，且 mspm0 侧是空函数） | **不能**（void；只配脚不做通信） |
| probe | `sht20_read(&t, &h)` == `0`（sht20.h:50 / sht20.c:200；1=温度段失败、2=湿度段失败；段内 1/2/3 = 写地址/命令/读地址超时，sht20.c:153-192） | 同左（sht20_stm32.h:63 / sht20_stm32.c:180） |
| 身份寄存器 | **无**（SHT2x 无 ID 读命令；驱动也未实现 SHT3x 那种序列号读法） | 同左 |
| read | `(int)t`、`(int)((t - (int)t) * 10)`、`(int)h`、`(int)((h - (int)h) * 10)` | 同左 |
| 单位/范围 | t：℃，-40~125℃，±0.3℃；h：%RH，0~100，±3%RH | 同 |
| console 建议 | `t` | `t` |
| 默认脚 | **PA16=SCL / PA17=SDA**（mspm0.syscfg:523,527） | **PA6/PA7**（pin_config.h:317-320） |
| 地址 | 0x40（写 0x80 / 读 0x81） | 同 |

**头里的真宏（可当 `expect` 的常量，若要用）**：`SHT20_ADDR 0x40u`（sht20.h:34 / sht20_stm32.h:46）、
`SHT20_CMD_TEMP 0xF3u`（:35 / :47）、`SHT20_CMD_HUMI 0xF5u`（:36 / :48）、
`SHT20_READ_RETRY_MAX 50u`（:37 / :49）、`SHT20_READ_RETRY_MS 2u`（:39 / :51）。
但**没有可读的身份/状态接口**，expect 只能对返回码写 `"0"`。

**note 要点**

- 驱动**不做身份校验**：`sht20_read` 的 0 只代表"0x40 应答了写地址、测量命令、以及轮询到读地址 ACK"
  ——这是三件温湿度里**判据最弱**的一件（无 CRC）。
- no-hold 单次模式：每次读要发测量命令并轮询读地址，温度段最长 85ms → 驱动给 ≤50×2ms=100ms 窗口
  （sht20.h:37-39）。**读超时（返回 1）时先怀疑窗口/线长，不是器件坏**。
- **走线坑**：stm32 侧地址 0x40 与库内 **pca9685 同址**（manifest sht20 的 notes 原话）——同一条软
  I2C 总线上同时挂 pca9685 + sht20 = 寻址冲突，必须错开总线或改 pca9685 的 A0-A5 跳线。
- 读数范围同 aht10；14bit 原始值低 2 位状态位已在驱动里 `& 0xFFFC`（sht20.c:190）。

---

## 3. sht30（温湿度，地址 0x44，周期模式 + CRC8）

| | mspm0 | stm32 |
|---|---|---|
| 头 | `code/sht30.h` | `code/sht30_stm32.h` |
| include | `["sht30.h"]` | `["sht30_stm32.h"]` |
| prereq | 无 | 无 |
| init | `sht30_init()` — **void**（sht30.h:38 / sht30.c:187-190）。⚠ **内部把 `sht30_write_mode()` 的返回值 `(void)` 丢掉了**（sht30.c:189）→ 通信失败也照样返回 void | 同左（sht30_stm32.h:52 / sht30_stm32.c:164-174；先 `gpio_init(SCL,OUT_OD)`+置高、`gpio_init(SDA,OUT_PP)`） |
| init 能否当判据 | **不能**（void，且结果被吞） | **不能**（void） |
| probe | `sht30_read(&t, &h)` == `0`（sht30.h:45 / sht30.c:192；**0=成功且两组 CRC8 都过**，1/2/3=写地址/命令字节应答失败，4=读地址超时 >20×2ms，5=CRC 校验失败，sht30.c:204-255） | 同左（sht30_stm32.h:60 / sht30_stm32.c:176） |
| 身份寄存器 | **无**（未实现 0x3682 序列号读命令） | 同左 |
| read | `(int)t`、`(int)((t - (int)t) * 10)`、`(int)h`、`(int)((h - (int)h) * 10)` | 同左 |
| 单位/范围 | t：℃，-40~125℃（±0.2℃ 典型 / ±0.3℃ 页面标称）；h：%RH，0~100，±2%RH | 同 |
| console 建议 | `e` | `e` |
| 默认脚 | **PA28=SCL / PA31=SDA**（mspm0.syscfg:502,506）——⚠ **与 ms5611 的 PA28/PA31 同脚** | **PA6/PA7**（pin_config.h:321-324） |
| 地址 | 0x44（写 0x88 / 读 0x89） | 同 |

**头里的真宏**：`SHT30_ADDR 0x44u`（sht30.h:30 / sht30_stm32.h:44）、
`SHT30_CMD_PERIODIC 0x2130u`（:31 / :45）、`SHT30_CMD_READ 0xE000u`（:32 / :46）、
`SHT30_READ_RETRY_MAX 20u`（:33 / :47）、`SHT30_READ_RETRY_MS 2u`（:34 / :48）。
另有 `sht30_read_temperature(float*)` / `sht30_read_humidity(float*)` 返回 `uint8_t`（0=成功）
——**也可以当 probe**（sht30.h:50-51 / sht30.c:258,269），但要用 locals 接出参。

**note 要点**

- 三件温湿度里**判据最强**的一件：返回 0 = 应答 + 6 字节回包 + **两组 CRC8（0x31/0xFF）都通过**
  （sht30.c:243）。判 FAIL 时按返回码细分排查：1/2/3 = 器件没应答（查供电/上拉/线序/ADDR 脚），
  4 = 测量没在 40ms 内就绪（周期模式每秒 1 次，等一拍再敲复测），5 = **通信通了但数据被干扰**
  （线太长/上拉太弱）。
- **init 返回值不可用**：外层 void、内层 write_mode 的结果被丢（sht30.c:189）。别写 `init_expect`。
- 平台差异：**stm32 侧 SDA 走推挽 OUT_PP + 浮空输入 IF**（sht30_stm32.c:18-19，全库唯一一派），
  **上电依赖模块板自带 1k-10k 上拉**；其余 5 件是 OD+IU。
- 地址跳线：模块 ADDR 脚接地 = 0x44（驱动写死 0x44，sht30.c:172）；ADDR 接 VDD 会变成 0x45，
  **驱动改不了，必须接地**。

---

## 4. bh1750（光照，地址 0x23 —— 唯一一个"连身份读法都没有"的件）

| | mspm0 | stm32 |
|---|---|---|
| 头 | `code/bh1750.h` | `code/bh1750_stm32.h` |
| include | `["bh1750.h"]` | `["bh1750_stm32.h"]` |
| prereq | **必填**：`["bh1750_init()", "bh1750_start_measure()", "delay_ms(BH1750_MEASURE_DELAY_MS)"]`（理由见下 ⚠） | 同左 |
| init | `bh1750_init()` — **void**（bh1750.h:22 / bh1750.c:171-174；内部 `bh1750_write_cmd(0x01)` 的返回值被丢，**无应答静默**） | `bh1750_init()` — **void**（bh1750_stm32.h:46 / bh1750_stm32.c:148-158；先 `gpio_init(SCL,OUT_OD)`+`gpio_init(SDA,OUT_OD)`+两脚置高，再发 0x01） |
| init 能否当判据 | **不能**（void + 结果被吞） | **不能** |
| probe | `bh1750_read_lux(&lux)` == `0`（bh1750.h:27 / bh1750.c:181-203；0=成功、1=读地址无应答） | 同左（bh1750_stm32.h:54 / bh1750_stm32.c:165-187） |
| 次级探针（可选） | `bh1750_start_measure()` == `0`（bh1750.h:24 / bh1750.c:176-179：写 0x10 且地址/命令都收到 ACK） | 同左 |
| 身份寄存器 | **无**。BH1750FVI **没有 ID 寄存器**（命令集只有 0x01/0x10/0x11/0x20…）——**这是真"没有"，不是没找** | 同左 |
| read | `(int)lux`、`(int)((lux - (int)lux) * 10)` | 同左 |
| 单位/范围 | lx，0~65535 lx、1 lx 分辨率（原始值 ÷1.2，bh1750.c:200）；室内 100~500 lx，桌面台灯下 500~2000 lx，手电直照能上万 | 同 |
| console 建议 | `f`（Flux/光照） | `f` |
| 默认脚 | **PA12=SCL / PA13=SDA**（mspm0.syscfg:409,413） | **PA6/PA7**（pin_config.h:285-288） |
| 地址 | 0x23（写 0x46 / 读 0x47；bh1750.c:18） | 同（bh1750_stm32.c:23） |

⚠ **为什么整条测量序列必须塞进 `prereq`（这是本批唯一一处 schema 逼出来的形状）**

- BH1750 的一次测量 = 上电(0x01) → 连续高分辨率(0x10) → **等 ≥140ms** → 读 2 字节。
- 那个"等"只能用 `delay_ms(...)`，而 `delay_ms` 只在 delay 模块头 / 母版 ml_delay.h 里。
- 段内引用判据面：**mspm0 侧 init/probe/read 只认 bh1750.h 里的名字** → `delay_ms` 出现在
  init/probe/read 会**构建期红**；stm32 侧因 ml_delay.h 是母版头反而能过 → **同一句配方一边过一边红**。
- `prereq` 按"库内任何模块 ∪ 母版"判（hwcheck_recipe.py:918-927），是**唯一**放行 `delay_ms` 的段。
  所以：prereq = 三句（init → start → wait），**不写 init 段**（缺段合法，`usable` 由 prereq/probe/read 撑住），
  probe = `bh1750_read_lux(&lux)`。

**头里的真宏**：只有 `BH1750_MEASURE_DELAY_MS 140`（bh1750.h:20 / bh1750_stm32.h:42）。
⚠ `BH1750_ADDR_WRITE 0x46`、`BH1750_CMD_POWER_ON 0x01`、`BH1750_CMD_CONT_H_RES 0x10`
**定义在 .c 里**（bh1750.c:18-21 / bh1750_stm32.c:23-26），**不在头里**→ 配方引用它们会构建期红。

**note 要点**

- **本件没有身份寄存器、init 也没有返回值**：板上唯一能判的是"读地址 0x47 有没有 ACK"（probe）。
  读回 0 lx 有两种含义：① 探头已判 OK 但环境真的全黑（手捂住就是 0~5 lx）；② 没做上面的 140ms 等待。
  **先看探头那一行的 OK/FAIL 再解释读数**。
- ALT ADDRESS 脚接地 = 0x23（驱动写死 0x46，bh1750.c:159）；接 VDD = 0x5C/0xB8，**驱动改不了，必须接地**。
- 卫星坑：mspm0 侧 PA12/PA13 与 PWMAB C0/C1（motor 双路 PWM）默认重叠，同选时以检测页接线表为准。
- 环境参考：室内日光灯 100~300 lx、窗边白天 1000~20000 lx、直接太阳 30000+；拿手遮住/移开应看到
  数量级变化，**这才是"真的在测"的证据**。

---

## 5. bmp180（气压/温度/海拔，地址 0xEE）

| | mspm0 | stm32 |
|---|---|---|
| 头 | `code/bmp180.h` | `code/bmp180_stm32.h` |
| include | `["bmp180.h"]` | `["bmp180_stm32.h"]` |
| prereq | 无 | 无 |
| init | `uint8_t bmp180_init(void)`（bmp180.h:46 / bmp180.c:253-302）：**逐项读 0xAA..0xBE 共 11 个校准字，任一 NACK 返回 1**，全成功返回 0；校准缓存进模块静态 | 同左（bmp180_stm32.h:60 / bmp180_stm32.c:228-285；内含 `gpio_init(SCL,OUT_OD)`+`gpio_init(SDA,OUT_OD)`，:235-237） |
| init 能否当判据 | **能当"通信通"的判据**（0 = 11 次寄存器读全部 ACK）；**但没做身份校验**——不读芯片 ID 寄存器（0xD0，BMP180 应为 0x55） | 同左 |
| probe | `bmp180_read(&t, &p)` == `0`（bmp180.h:55 / bmp180.c:331；0=成功、1=温度段失败、2=气压段失败） | 同左（bmp180_stm32.h:70 / bmp180_stm32.c:314 起） |
| 身份寄存器 | **有（0xD0=0x55）但驱动没暴露**：`bmp180_write_cmd`（bmp180.c:179）与 `bmp180_read16`（bmp180.c:203）都是 **static** → **配方写不了 ID 比对** | 同左 |
| read | `(int)t`、`(int)((t - (int)t) * 10)`、`(int)p`、`(int)bmp180_read_altitude(p)` | 同左 |
| 单位/范围 | t：℃（每数值 0.1℃，bmp180.c:326）；p：**Pa**（≈101325）；海拔：m（44330 公式，bmp180.c:398-402） | 同左 |
| console 建议 | `c` | `c` |
| 默认脚 | **PA23=SCL / PA24=SDA**（mspm0.syscfg:605,609） | **PA6/PA7**（pin_config.h:378-381） |
| 地址 | 0xEE 写 / 0xEF 读 | 同；⚠ **与 ms5611 同址 0xEE → stm32 侧同总线两件互替不可同挂** |

**头里的真宏**：`BMP180_ADDR_W 0xEEu`、`BMP180_ADDR_R 0xEFu`、`BMP180_REG_CTRL_MEAS 0xF4u`、
`BMP180_CMD_TEMP 0x2Eu`、`BMP180_CMD_PRES 0x34u`、`BMP180_OSS 0u`（bmp180.h:36-41 /
bmp180_stm32.h:48-53）。**注意：这些不是身份值**，别拿它们当 probe.expect 假装做了 ID 校验。

**note 要点**

- 两级自证：① `bmp180_init()` 返回 0 = 11 个校准字全部读回（**本批最强的"总线通"证据之一，
  但仍不是身份校验**）；② probe `bmp180_read()` 返回 0 = 温度段 + 气压段各一次完整写命令/读数据成功。
- **读数怎么算合理**：海平面标准气压 101325 Pa；同一房间里不同高度差 1 米 ≈ 12 Pa——**手拿上下一米
  就能看到 p 变化，这是"真的在测"的最好证据**；温度 ±1℃ 精度（比 ms5611 差一档）。海拔读数在你
  所在城市一般不是 0（海平面参考值固定 101325）。
- 本件 oss 固定 0 = ultra low power（`BMP180_OSS`）——分辨率最低档，读数抖动比 ms5611 大是设计如此。
- 与 ms5611 是**互替件（exclusive_group: barometer）且 stm32 侧同址 0xEE**：同选必冲突，二选一。

---

## 6. ms5611（高精度气压/温度/海拔，地址 0xEE）

| | mspm0 | stm32 |
|---|---|---|
| 头 | `code/ms5611.h` | `code/ms5611_stm32.h` |
| include | `["ms5611.h"]` | `["ms5611_stm32.h"]` |
| prereq | 无 | 无 |
| init | `uint8_t ms5611_init(void)`（ms5611.h:52 / ms5611.c:213-265）：复位 0x1E → 等 300ms → 读 PROM 8 字。**返回码：0=成功、1=器件地址无应答、2=复位命令无应答、3=PROM 读应答失败** | 同左（ms5611_stm32.h:69 / ms5611_stm32.c:186-244） |
| init 能否当判据 | **能当"通信通"的判据**（0 = 复位 + 8 字 PROM 全应答）；**没做身份校验**（也没校验 PROM CRC，见缺陷⑥） | 同左 |
| probe | `ms5611_read(&t, &p)` == `0`（ms5611.h:62 / ms5611.c:267；0=成功、1=D1 段失败、2=D2 段失败、3=数据读失败） | 同左（ms5611_stm32.h:80 / ms5611_stm32.c:248 起） |
| 身份寄存器 | **无**（MS5611 无 ID 寄存器；PROM word0 是厂家/传感器信息，但 `ms5611_cal[]` 是模块 static） | 同左 |
| read | `(int)t`、`(int)((t - (int)t) * 10)`、`(int)p`、`(int)ms5611_read_altitude(p)` | 同左 |
| 单位/范围 | t：℃（**0.01℃ 分辨率**）；p：**Pa**（0.01mbar≡1Pa）；海拔：m（44330 公式） | 同左 |
| console 建议 | `q`（气压 qì；与 bmp180 的 `c` 必须错开） | `q` |
| 默认脚 | **PA28=SCL / PA31=SDA**（mspm0.syscfg:644,648）——⚠ **与 sht30 同脚** | **PA6/PA7**（pin_config.h:382-385）；⚠ 与 bmp180 同址 0xEE |
| 地址 | 0xEE 写 / 0xEF 读 | 同 |

**头里的真宏**：`MS5611_ADDR_W 0xEEu`、`MS5611_ADDR_R 0xEFu`、`MS5611_CMD_RESET 0x1Eu`、
`MS5611_CMD_D1 0x48u`、`MS5611_CMD_D2 0x58u`、`MS5611_PROM_BASE 0xA0u`、`MS5611_PROM_WORDS 8u`、
`MS5611_CONV_WAIT_MS 10u`、`MS5611_INIT_WAIT_MS 300u`（ms5611.h:37-45 / ms5611_stm32.h:53-61）。
同样：**都不是身份值**。

**note 要点**

- 两级自证（同 bmp180）：init 0 = 复位+PROM 全应答；probe 0 = D1/D2 两次转换与数据读全通。
  **一次 init 里有 `delay_ms(300)`，一次 read 里有两段各 10ms——上电这一遍在这一件上要停约 0.4 秒**，不是卡死。
- 读数怎么算合理：p ≈ 101325 Pa（1 米高度差 ≈ 12 Pa，**上下举一米就能看到变化**）；t 精度 ±0.8℃，
  分辨率 0.01℃；海拔用固定海平面 101325 Pa 换算，内地城市不会读到 0——**别把"海拔不是 0"当故障**。
- 与 bmp180 的差别（选型口诀）：本件 ±1.5 mbar / 0.1 m 级、PROM 二次补偿、适合定高闭环；
  bmp180 是老件、±1 hPa / ±1℃、精度低一档。**两件互替，二选一**。
- ⚠ stm32 侧与 bmp180 **同址 0xEE**，同一条软 I2C 总线上同时选两件必然寻址冲突（生成侧不会拦，
  只有 UI 的互斥组卡片提示）→ 接线表里两件同时出现就是错。
- mspm0 侧默认脚 PA28/PA31 与 sht30 **完全同脚**；同选时以检测页接线表为准。

---

## 7. 库内驱动缺陷 / 不一致（侦察发现，未改）

① **`aht10.h:15-17` 的引脚注释是错的（文档缺陷）**：头注释写"SCL（输出，默认 PA26）/ SDA（双向，默认 PA25）"，
   而 `mspm0.syscfg:349,353` 与 `aht10/manifest.json:22-23` 都是 **PB6/PB7**。

② **`sht30_init()` 吞掉返回值**：`sht30.c:189` `(void)sht30_write_mode(SHT30_CMD_PERIODIC);`
   —— 外层 void + 内层结果丢弃，**这一件的 init 在板上完全无判据**。

③ **`bh1750_init()` 同样吞返回值**：`bh1750.c:173`（stm32 侧 `bh1750_stm32.c:157` 有 `(void)`）。

④ **`bh1750` 的地址/命令宏藏在 .c 里**：头文件里只有 `BH1750_MEASURE_DELAY_MS`。

⑤ **`bmp180` 有 ID 寄存器但驱动不暴露**：`bmp180_write_cmd`（bmp180.c:179）/`bmp180_read16`（bmp180.c:203）
   是 static → 想做"读 0xD0 比对 0x55"这种真身份探头，必须先在库里加一个公开读法。

⑥ **`ms5611` 读了 PROM CRC 却不校验**：`ms5611.c:236-263` 把 8 个字（含 idx7 = CRC）全读进
   `ms5611_cal[]`，但整个驱动没有一处用 `ms5611_cal[7]` 做 CRC4 校验（stm32 侧同）。

⑦ **AHT10 测量窗口小于手册要求**：`aht10.c:184-186` 与 `aht10_stm32.c:164-169` 注释明写
   "窗口 ~25ms ≪ AHT10 手册测量 ≥80ms，按页面原式保留"。

⑧ **`sht20` 是唯一没有便捷封装的温湿度件**：sht30 有 `sht30_read_temperature/read_humidity`，
   aht10 有 `aht10_read_temperature/read_humidity`，**sht20 只有 `sht20_read`**。

⑨ **`sht30` 的 stm32 电平配置全库唯一**：`sht30_stm32.c:18-19` 用 `OUT_PP` + `IF`，其余 5 件是
   `OUT_OD` + `IU`。**不接模块时这条推挽 SDA 会被驱动成低电平**。

⑩ **mspm0 侧 SysConfig 里 SCL/SDA 的 `initialValue` 全是 `CLEARED`**：上电瞬间两根线被驱到**低**，
   直到驱动第一次 start 序列才拉高——可作"刚上电第一遍偶发失败，复测就好"的解释。

⑪ **`aht10_read` 读进来的状态字节 `buff[0]` 被丢弃**（aht10.c:199-207 只用 buff[1..5]）：
   AHT10 的状态寄存器（bit7 忙、bit6 校准使能）其实拿到了却没暴露。

---

## 8. 写配方时的共同坑

① **段内引用判据面两平台不对称（最要命的一条）**。mspm0 母版没有 .h → mspm0 的 `init/probe/read`
   只能用**本模块头里的名字**；stm32 侧白送全部母版名字。**同一句配方可能 stm32 过、mspm0 构建期红**。
   想跨模块调用（`delay_ms` / 别的模块的初始化）**只能写进 `prereq`**。

② **两个平台头名不同**（§0 对照表）：6 件全部如此。写错 = 构建期红。

③ **本批 6 件没有一个能做"身份探头"**：probe 只能写成"驱动的 ACK/CRC 返回码 == 0"（jy61p 先例）；
   `expect` 一律是字面量 `"0"`，别去引用 `SHT20_ADDR` / `BMP180_CMD_TEMP` 这类宏假装在读身份。

④ **init 返回值能不能当判据（本批结论表）**

| slug | mspm0 init | stm32 init | 0 能否当"通信通" | 理由 |
|---|---|---|---|---|
| aht10 | `void` | `void` | ❌ | 只有延时+校准序列，应答结果全丢 |
| sht20 | `void`（**空函数**） | `void`（只配脚） | ❌ | 无器件初始化序列 |
| sht30 | `void` | `void` | ❌ | 外层 void + 内层结果被丢 |
| bh1750 | `void` | `void` | ❌ | 外层 void + 内层结果被丢 |
| bmp180 | `uint8_t` | `uint8_t` | ✅（**非身份校验**） | 0 = 11 个校准字全部 ACK |
| ms5611 | `uint8_t` | `uint8_t` | ✅（**非身份校验**） | 0 = 复位 + 8 字 PROM 全部 ACK |

⑤ **`init_expect` 只在 bmp180 / ms5611 上写 `"0"`**，其余四件**必须留空**（照渲"已调用（本件不判返回值）"）。

⑥ **probe.calls 多条时只有最后一条进比较式**。要"先 start 再 wait 再 read"这种多步序列，
   把**要比较的那一条放最后**；前面几条可以带赋值（xunji 先例）。

⑦ **float 必须拆两行 + 进 `locals.declarations`**：`float t = 0` / `float h = 0` / `float p = 0` /
   `float lux = 0`（初值只收数字字面量，写 `0.0` 连 `parse_locals` 的 `_is_literal` 都过不去）。

⑧ **控制台字符**：可用池实测只剩 **`c e f h i n q t v w z`**（+ 数字 0-9）。**bmp180 与 ms5611
   不能共用同一个字符**——`exclusive_group: barometer` 只是 UI 软单选，生成侧硬互斥表只有
   zigbee 一对（generator.py:2035-2041），绕过 UI 同选即 400。

⑨ **`prereq` 段只查调用名，不查裸宏名**——`delay_ms(BH1750_MEASURE_DELAY_MS)` 里的宏不会被校验；
   但**它仍然必须真存在**（否则编译期红）。

⑩ **可选加强（stm32 侧独有）**：加一条"总线空闲电平"证据行，例如
   `gpio_get(AHT10_SCL_GPIO, AHT10_SCL_PIN)`（正常空闲应为 1）。代价：必须把 `pin_config.h` 写进
   `include.headers`，且 mspm0 侧没有对应写法（无母版头、也没有 pin_config.h）。

⑪ **上板前提**：12 个格全部是"编译矩阵绿 / 未上板"。note 里写正常范围时请带上
   "实测差异优先于本页参考值"的口径。
