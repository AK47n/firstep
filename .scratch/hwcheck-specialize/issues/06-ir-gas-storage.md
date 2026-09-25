# 06 — 专精化批次 D：红外 / 气体 / 存储三件（mlx90614 / sgp30 / at24c02）

**要做什么：** 学生勾这三件中的任何一件（含两平台）时，检测页给它一个 `[专精]` 小节，三件各有
**各自最强的可用探头**（都不是身份寄存器，note 要如实分层）：`sgp30` 的读事务带**两组 CRC8 校验**
（返回码 5 = CRC 对不上），是这一批最硬的；`mlx90614` 只能证"0x5A 上真有东西应答了完整读事务"；
`at24c02` 用 EEPROM 的**「写→等→读回」强自证**（写记号 0x5A 再读回比对）。三件都给读数
（Ta / To 温度、CO2 当量与 TVOC、存储单元回读值）与复测字符。此前它们只有"未专精：只验总线和初始化"。

**被谁阻塞：** 01（命令字符让位——三件都要声明首选 + 候选，不留让位机制就等着撞车）、
02（未专精样本夹具解耦——内容批次的统一前置）。

**状态：** ready-for-agent

- [ ] 六格配方（`mlx90614` / `sgp30` / `at24c02` × `stm32` / `mspm0`）写进
      `library/hwcheck_recipes.json`，事实底稿 = `.scratch/hwcheck-specialize/recon-04-attitude-optical.md`
      §4（mlx90614）、§5（sgp30）+ `.scratch/hwcheck-specialize/recon-02-i2c-generic-1wire.md`
      §2 的 at24c02 小节（并吃它的 §1 四条 schema 判据、§4 缺陷、§5 共同坑）
- [ ] `include` 用**该平台真头名**：`mlx90614.h` / `mlx90614_stm32.h`、`sgp30.h` / `sgp30_stm32.h`、
      `at24c02.h` / `at24c02_stm32.h`（写反构建期红）；`at24c02 × stm32` 的 read 若用到引脚宏
      （`AT24C02_SDA_GPIO`）**必须同时 include `pin_config.h`**——它只在有通用降级件时才自动 include
      （recon-02 §1）
- [ ] `prereq` 六格全空（三件都是软 I2C 位操作，不用母版 ml_i2c；at24c02 的 5ms 写周期由
      `at24c02_wait_write_done()` 自己等）
- [ ] `mlx90614`：`init` = `mlx90614_init()`（**void**：mspm0 空实现 / stm32 只配两脚、不做任何通信）
      ⇒ **不写 `init_expect`**（写了会渲成 `r = mlx90614_init();` 编不过——校验器不查返回类型，
      这是构建期守卫的漏，recon-04 §0.2 / §4 实测）；`probe` =
      `["mlx90614_read_ambient_temp(&ta)", "mlx90614_read_object_temp(&to)"]` + `expect: "0"`
      （0=成功 / 1=通信失败，每处 ACK 都查）；`locals` = `float ta = 0` / `float to = 0`；
      read = 四条：`(int)ta` + `(int)((ta - (int)ta) * 10)`、`(int)to` + `(int)((to - (int)to) * 10)`
- [ ] `mlx90614` **不编身份探头**：RAM 里没有身份寄存器（只有 Ta=0x06 / To=0x07 这类测量字），
      厂商确有 EEPROM 段 ID 字段但库内**一条 EEPROM 通路都没有**；"温度在合理范围"也不算探头
      （不是可编译成 `call == expect` 的比较式 + 合理范围是人为阈值 + 不证身份）——note 按这三条如实写
- [ ] `sgp30`：`init` = `sgp30_init()`（**void**，只发 0x2003；`write_cmd` 的失败码被 `(void)` 丢弃）
      ⇒ 不写 `init_expect`；`probe` = `["sgp30_read(&tv, &co)"]` + `expect: "0"`（签名是
      `sgp30_read(uint16_t *tvoc_ppb, uint16_t *co2_ppm)`：**tv 在前、co 在后**）；返回码分段
      写进 note：1/2/3=写命令应答失败、4=读地址失败、**5=CRC 校验失败**；`locals` =
      `uint16_t tv = 0` / `uint16_t co = 0`；read = `co`（CO2 当量 ppm）+ `tv`（TVOC ppb）
- [ ] `sgp30` 的 feature set（0x202F）/ 序列号（0x3682）是**器件有、库内一个都没实现**
      （`sgp30_write_cmd` 是 static）⇒ 配方层做不出身份探头；**本单不改驱动**，只在 note 如实写
- [ ] `at24c02`：`init` = `at24c02_init()`（stm32 真配两脚 / mspm0 空实现）**void** ⇒ 不写
      `init_expect`；`probe` = **一条逗号表达式**
      `["(at24c02_write_byte(0, 0x5A), at24c02_wait_write_done(), at24c02_read_byte(0))"]` +
      `expect: "0x5A"`（probe / expect **允许**十六进制，read 不允许）；`AT24C02_ADDR`(0x50)
      **是器件地址不是身份寄存器**，不能当期望值
- [ ] `at24c02` 的 read：`at24c02_read_byte(0)`（参数写**十进制**！`0x00` 会被切出 `x00`——recon-02 §1
      的实测报错原文）+ `AT24C02_SIZE`(256) + `AT24C02_PAGE_SIZE`(16)；可选加
      `gpio_get(AT24C02_SDA_GPIO, AT24C02_SDA_PIN)`（SDA 是 OUT_OD 空闲高 ⇒ 读到 1 = 总线上真有
      上拉 / 模块在），但**它只在探头通过后才打印**；读数里那个 0x5A 是刚写进去的记号、不是测量值
- [ ] `console`：`console.command`（首选）+ `console.candidates`（候选，工单 01 落地的字段形状）——
      `mlx90614` 首选 `t`、候选 `f`、`e`；`sgp30` 首选 `v`、候选 `z`、`w`；
      `at24c02` 首选 `e`、候选 `i`、`n`（首选与候选全部取自实测空闲池 `c e f h i n q t v w z` +
      数字 `0-9`；保留字 `r/y/g/o/b` 与帮助 `?` 一个不碰）；两平台同一组，平台内不许重复
- [ ] `note` 至少覆盖：① **每件的探头到底证明了什么**（sgp30 = 通信 + 两组 CRC8 两级自证；
      mlx90614 = 只有 ACK、**无 PEC/CRC**、不证型号更不证测温准；at24c02 = "写进去能读回来"是强自证，
      而 `write_byte` 的三次 `wait_ack` 结果全丢、`read_byte` 无应答返 0xFF 与合法 0xFF 不可分）；
      ② 判 FAIL 时**按返回码排查**（sgp30 的 1/2/3/4/5 分段；mlx90614 的 1 = 0x5A 没人应答；
      at24c02 的第一嫌疑是 **WP 写保护脚接 VCC**——模块板 WP=VCC 只读 / GND 可写，驱动不管，
      通信好的片也会 MISS）；③ 失败模式（mlx90614 两平台时序不对齐：stm32 版在写命令→重起始之间
      加了 `delay_ms(1)`、**mspm0 版没有** ⇒ mspm0 真机若读失败第一嫌疑是这里；测温要 1~2 分钟热平衡，
      开机头几秒的数会漂，属器件特性不是坏；sgp30 **上电 15s 预热期 CO2=400ppm / TVOC=0ppb 恒定、
      此时探头照样判 OK** ⇒ "OK"只证通信 + CRC，不证读数已就绪，一次复测约 0.2~0.3s 不是卡死、
      二次采样间隔不得短于 1s；at24c02 写后不等 `at24c02_wait_write_done()` 会读回旧值，空片读回 0xFF、
      记号别用 0xFF，mspm0 的 SDA 输入**没有内部上拉** ⇒ 悬空回读值不定）；④ 正常范围（Ta 室温
      15~35℃；To = **视场内平均红外温度**：对墙 ≈ 室温、对手掌 / 额头高几度~十几度、正对窗口 / 天空
      可能低于 0℃——负温按 `(int)` 截断，两行要拼起来读；换算 ℃ = RAW×0.02 − 273.15，器件 0.01℃
      分辨率 ⇒ 读数按 0.02 步进、只到小数第一位；CO2 当量室内 400~1000+，400 是预热 / 背景值；
      TVOC 洁净空气 0~几十 ppb）；⑤ 接线与地址坑（三件 7 位地址 0x5A / 0x58 / 0x50 互不相同；
      stm32 三件默认都 PA6/PA7，与 ads1115 / pca9685 等共挂同一软 I2C 总线——地址互异合法共挂，
      同选撞脚由检测页引脚卡消解；mspm0 侧 mlx90614 = PA9/PA8、sgp30 = PA18/PB9（跨口）、
      at24c02 = PB24/PB8 与 STEP_MOTOR / SR04 / HC05 重叠；at24c02 会**覆盖 0 号单元**）；⑥ 平台差异
      （mspm0 无母版 .h ⇒ init / probe / read 里不许写 `delay_ms` / `gpio_get`；mlx90614 的时序差见③；
      at24c02 mspm0 头写"引脚配置由 init 内 gpio_init 完成"与实现（空函数）不符）
- [ ] 上板状态照旧如实写**「未上板」**（三件两平台 `verified: true / hardware_bound: false`）——
      编译绿不是板上证据
- [ ] 检测页实测：三件两平台显示 `[专精]`（不是 `未专精`），命令表里是**分配后**的字符
- [ ] **扩张地板**追加这 6 格到 `EXPANSION`（工单 03 立的那一处：`EXPANSION` 只装**扩张**格；
      `EXPANSION_CELL_COUNT` 是**手写字面量**——**别写成 `len(EXPANSION)`**，那是恒真断言）：
      落地后 `EXPANSION_CELL_COUNT` 改成 **24**（+ `PILOT` 那 17 格 = 总覆盖 **41**）；
      **只追加、不改写**已有行；`PILOT` 常量**不动**（有 `len == 17` 的精确断言）
- [ ] `tests/test_hwcheck_generic.py` 的未专精基线（写单时是 `planned >= 157` / `with_init >= 132`；
      **批次 A 落地后已降到 153 / 128**——以你落地当时的实数为准）**按实数
      如实下调并写原因**：本批 6 格每格各 -1（实测这 6 格的通用规划都拿得到无参初始化）；
      写单时实测 `planned = 159` / `with_init = 134` ⇒ 若前面三批（A/B/C，共 18 格）都已落地
      则为 **141 / 116**（否则按落地当日实数 -6）。跟着实数改数，**不许删断言**
- [ ] **真编译矩阵**：`py -3 .scratch/hwcheck-specialize/probe-compile-matrix.py --slugs mlx90614,sgp30,at24c02`
      → 六格全 `[PASS]`（exit=0、编译器 0 error / 0 warning；**链接器形态告警另记**），读数落盘
- [ ] **反证**：把 `at24c02 × mspm0` 那一格配方撤掉 → 扩张地板断言必须红（41 → 40）

---

## Comments

### 2026-09-25 立项依据与关键事实

- 三件的共同点是**都没有身份寄存器可读**，但"最强可用探头"分三档，配方形状不能互相照抄
  （recon-04 §4 / §5、recon-02 §2）：`sgp30_read()` 写 0x2008 → 读满 6 字节 → **两组 CRC8 校验**
  （0=成功 / 1-3=写命令应答失败 / 4=读地址失败 / 5=CRC 对不上）> at24c02 的"写→等→读回"强自证 >
  mlx90614 的纯 ACK（0=成功 / 1=通信失败）。note 必须把这三档的差别写给学生看。
- `mlx90614` 为什么做不出身份探头（原文口径）：RAM 里没有身份寄存器（只有 Ta=0x06 / To=0x07 这类
  测量字），厂商确有 EEPROM 段 ID 字段但**库内驱动一条 EEPROM 通路都没有**；`mlx90614_init()` 两平台
  都判不了（mspm0 **空实现**、stm32 只配两脚，且都是 void ⇒ 写 `init_expect` 会渲成
  `r = mlx90614_init();` **编不过**，而 `validate_recipes` 实测 PASS——构建期守卫在这条上是漏的，
  recon-04 §0.2 / §4）；驱动也没有 PEC/CRC 通路 ⇒ **数据完整性无校验**（§6④）。
- `sgp30` 的身份面同理：参考实现里的 `get_feature_set = 0x202F` 与 `get_serial_id = 0x3682`
  器件有、**库内一个都没实现**，`sgp30_write_cmd` 是 static ⇒ 配方层做不出身份探头（要它得改驱动，
  本单不许改，recon-04 §5 / §6）；它最容易误读的一条是**上电 15s 预热期读数恒定 400 / 0、探头照样
  判 OK** ⇒ note 必须写"OK 只证通信 + CRC，不证读数已就绪"。
- `at24c02` 的强自证与它的边界（recon-02 §2 原文）：驱动里 **`write_byte` 的三次 `wait_ack` 结果全丢**
  （at24c02.c:159-166）、`read_byte` 无应答返回 0xFF（头注释 at24c02.h:57-59）⇒ 只有"写进去能读回来"
  才是强证据；`AT24C02_ADDR`(0x50) **是器件地址不是身份寄存器**，不能当期望值；**WP 写保护脚**
  （模块板 WP=VCC 只读 / GND 可写，驱动不管）是写回读 FAIL 的第一嫌疑——通信好的片也会 MISS；
  写后必须 `at24c02_wait_write_done()`（= `delay_ms(5)`，不自动内嵌），否则读回旧值。
- schema 四条判据（recon-02 §1 原文口径，六格都吃）：① read 表达式**禁十六进制字面量**（实测报错
  `'at24c02' × mspm0 的读数展示段…表达式 'at24c02_read_byte(0x00)' 里有找不到的名字 'x00'`）；
  ② probe 带 expect 时**每条 call 都渲成 `r = <call>;`**、且**只有最后一条参与比较**
  （hwcheck_recipe.py:1274-1302）⇒ 读写一体要用逗号表达式、判据调用放末尾（void 调用不能裸写进去）；
  ③ 探头判 FAIL **直接 `return`**（hwcheck_recipe.py:1298）⇒ read 段的读数在 FAIL 时根本不打印，
  "失败先查什么"只能进 note；④ `locals` 只收标量（`类型 名字 [= 数字]`）⇒ 带指针 / 长度的接口
  （`at24c02_write_page` 的 `const uint8_t*`）在配方里造不出缓冲区。
- include 面（recon-02 §1）：stm32 = 模块头 ∪ 整棵母版头（实测 6248~6280 个名字，含 `gpio_get` /
  `delay_ms` / `AT24C02_SDA_GPIO`）；**mspm0 母版没有 .h** ⇒ 只能引用本模块头里的名字
  （`delay_ms` / `gpio_get` 不存在）；stm32 main.c 固定 include `headfile.h`，而 `pin_config.h`
  **只在有通用降级件时才自动 include**（hwcheck.py:824-849）⇒ 读数要用引脚宏就得自己 include。
- 引脚（recon-02 §2 末、recon-04 §0.4）：stm32 三件默认 PA6/PA7，与 ads1115 / pca9685 等 11 件共挂
  同一软 I2C 总线（地址互异，合法共挂）；mspm0 侧 at24c02 默认 PB24/PB8 与 STEP_MOTOR / SR04 / HC05
  重叠、sgp30 = PA18/PB9 跨口、mlx90614 = PA9/PA8。
- 库内驱动缺陷（**本单不修**，note 如实提示）：at24c02 mspm0 头写"引脚配置由 init 内 gpio_init
  完成"而 init **一行都不做**（recon-02 §4.1 / §2 note⑦）；at24c02 读写路径 ACK 全丢（§4.2）；
  mlx90614 无 PEC/CRC 且两平台时序不对齐（recon-04 §6④⑤）。
- 基线 / 地板：写单时按 `test_hwcheck_generic.py` 的同一条算法实测 `planned = 159` /
  `with_init = 134`，本批 6 格每格各 -1（三件的通用规划都拿得到无参 init：`mlx90614_init` /
  `sgp30_init` / `at24c02_init`）⇒ 按落地当日实数 -6；`PILOT`（`len == 17`）不动，扩张部分另立新常量。
- 三件两平台都是 `verified: true / hardware_bound: false`（recon-02 §5.11「这 6 件全部未上板」、
  recon-04 §7.9）⇒ 验收记录照旧写「未上板」。
