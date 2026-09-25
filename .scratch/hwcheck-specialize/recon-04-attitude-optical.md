# 侦察 04：姿态与光色五件（hmc5883l / qmc5883l / tcs34725 / mlx90614 / sgp30）

> 2026-09-25，只读侦察（未改任何文件）。每条结论带 `file:line`。
> **每一条建议的配方字段都过了 `validate_recipes` 内存实测（10/10 PASS）**，并渲染出 C 逐行核对过。
> 由并行侦察子代理产出，原文照录（落盘时略作排版整理，事实与行号未改）。

## 0. 判据与公共事实（先读，决定字段能写什么）

### 0.1 校验面（与 recon-01 §0 一致，这里只补新的）

- `include` 头名 = 该平台「模块 .h 基名 ∪ 母版 .h 基名」（hwcheck_recipe.py:369-396、847-858）；
  **stm32 写 `xxx_stm32.h`、mspm0 写 `xxx.h`**（实测反证：mspm0 写 `sgp30_stm32.h` → 构建期红）。
- `init`/`probe`/`read` 的名字只认「本模块该平台头 ∪ 母版头 ∪ 本节 locals」；`prereq` 例外，
  按整库 ∪ 母版判（:918-927）。
- **mspm0 母版 .h 数 = 0** ⇒ mspm0 侧 5 件的可用名只有各自头里那几个（实测集合大小：
  mlx90614 7 / sgp30 6 / qmc5883l 24 / hmc5883l 28 / tcs34725 37）；**stm32 侧每件 ~6250 个名**。
- 直接后果（实测）：`delay_ms(...)` **在 mspm0 的 init/probe/read 里一律构建期红**；
  在 stm32 上合法（母版 ml_delay.h）；在**两平台的 `prereq` 里都合法**（PASS 实测）。

### 0.2 渲染面（★ 三条硬约束，决定 probe/init 能写成什么形状）

1. **`r = call;` 前缀**：只要写了 `init_expect`，**init 段每一条调用**都渲染成 `r = call;`
   （hwcheck_recipe.py:1250）；只要写了 `probe.expect`，**probe 段每一条**都如此（:1276）。
   ⇒ **void 函数一行都不能放进"被判定"的那一段**。校验器**不查返回类型**
   （实测：`mlx90614_init()` + `init_expect:"0"` 校验 PASS，但渲染出 `r = mlx90614_init();`
   根本编不过——**构建期守卫在这条上是漏的**）。
2. **expect 只比返回码**：`expect` 允许写宏名，但要跟驱动的**返回码约定**对齐。写给
   `hmc5883l_init()` 的 `expect:"HMC5883L_ID_A_VALUE"`（0x48）会渲染成 `r == 0x48`
   而它返回 0/1/2 ⇒ 永远 FAIL（校验 PASS，板上必红）。
3. **`read` 表达式不能碰结构体成员**：`rgb.c` 被判"找不到的名字 'c'"（提取器不收 struct
   成员名；`_bare_names` 把 `rgb.c` 拆成 `rgb` + `c`，hwcheck_recipe.py:892-901）
   ⇒ TCS34725_RGBC 的四个通道必须**先拷进独立标量 locals**（在 probe/init 段用赋值语句，实测 PASS）。
4. 只有三处能放"裸语句"（无 `r = ` 前缀）：**prereq**（恒裸，:1247-1249）、
   **没写 init_expect 的 init 段**、**没写 probe.expect 的 probe 段**。
   `delay_ms`、`tcs34725_read_reg` 这类 void 调用只能落在这三处。
5. 没写 `probe.expect` 时**一定会**印「本件没有读取型探头…通断无法判定」并记一笔"未判定"
   （:1303-1311，在 `if probe is not None` 之外）——即使 `init_expect` 已经判过
   ⇒ 同一件会同时进"通过"与"未判定"两档。库内先例是 mspm0 `ml_mpu6050`（两级自证、两笔判定）；
   **要凑成"一件一笔"只能二选一**。
6. probe 段多条调用时**只有最后一条**的值参与比较（:1274-1302）⇒ 采集用的调用放前面、
   被判定的放最后。

### 0.3 prereq：五件 × 两平台**全部留空**

- 五件都是**软 I2C 位操作**、不用母版 ml_i2c（manifest 各条目原话）；stm32 侧各驱动自己在 `init`
  里 `gpio_init(SCL/SDA, OUT_OD)` + 置高（hmc5883l_stm32.c:173-176；qmc5883l_stm32.c:208-211；
  mlx90614_stm32.c:169-172；sgp30_stm32.c:173-176；tcs34725_stm32.c:245-248）；mspm0 侧引脚由
  SysConfig 实例 + 检测程序开头那行**活调用** `SYSCFG_DL_init()`（hwcheck.py:229-235）配好。
- **不要照抄 `ml_mpu6050` stm32 的 `prereq: ["I2C_Init()"]`**：`I2C_Init` 存在于母版 ml_i2c.h:13，
  但它初始化的是**母版软 I2C 的 PA11/PA12**（pin_config.h:799-801），与本批无关。
- 延时头框架已经 include（mspm0 `delay.h` hwcheck.py:214/841；stm32 经 `headfile.h` 拉
  `ml_delay.h`）⇒ `include` 里**不用**写 delay 头。

### 0.4 总线 / 引脚 / 上拉

- **stm32 侧五件默认脚全都是 PA6(SCL)/PA7(SDA)**（pin_config.h:289-296 HMC、297-306 QMC、
  348-351 TCS、352-355 MLX、356-359 SGP）⇒ 同一物理总线只能挂一个"脚位组"，同选必然撞脚；
  检测页会标「⚠ 引脚冲突」并有一键绑定。五件 7 位地址互不相同（0x1E / 0x0D / 0x29 / 0x5A / 0x58）
  ⇒ **协议上可共挂**，卡的是脚。
- **mspm0 侧**：hmc5883l = PB6/PB7、mlx90614 = PA9/PA8、sgp30 = PA18/PB9（跨口）、
  **tcs34725 = PA23/PA24 与 qmc5883l = PA23/PA24 同脚**——这两件在 mspm0 上同选也撞。
  syscfg 两脚都是 `OUTPUT / initialValue=CLEARED`、**没配内部上拉** ⇒ 总线**必须靠模块板自带 /
  外接上拉**。
- mspm0 驱动的 SCL **只写电平**（`DL_GPIO_setPins/clearPins`），从不
  `DL_GPIO_initDigitalOutput(SCL_IOMUX)`（hmc5883l.c:42-49 同型）⇒ SCL 输出方向完全依赖
  SysConfig + `SYSCFG_DL_init()`；那行不生效 = 总线必死。

### 0.5 复测字符（实测占用表）

- 保留 `r y g o b` + 帮助 `?`；配方已占 `l d m u k p s j x a`。空闲字母 =
  `c e f h i n q t v w z`（+数字 0-9 全空）。
- **建议（首选 → 候选）**：`hmc5883l: h → i,n`；`qmc5883l: q → w,z`；`tcs34725: c → e,f`；
  `mlx90614: t → f,e`；`sgp30: v → z,w`。
- ⚠ **与票 03（aht10 h / sht20 t / sht30 e）首选重叠**：aht10 也首选 `h`、sht20 也首选 `t`。
  按票 01 的让位机制不报错，但**页面显示的是分配后的字符**，别在两处写死"敲 h 测罗盘"。
- 另一处 spec↔代码细节：分配顺序实际是 `resolve_sections` 的**验证顺序**
  （`sort_verification_order`，hwcheck_recipe.py:1141-1155），不是配方文件里的书写顺序。

## 1. hmc5883l（三轴磁力计，7 位地址 0x1E → 写 0x3C/读 0x3D）

| | mspm0 | stm32 |
|---|---|---|
| 头 / include | `hmc5883l.h` | `hmc5883l_stm32.h` |
| prereq | 无 | 无 |
| init | `hmc5883l_init()` → `uint8_t`（hmc5883l.h:72；hmc5883l.c:206） | 同（hmc5883l_stm32.h:70；.c:167，含两脚 gpio_init :173-176） |
| **init 能当判据吗** | **能**：0=成功 / 1=总线无应答 / 2=**ID 不符**（hmc5883l.c:213-219、230） | **能**，同上（:178-184、195） |
| 身份怎么读 | **只在 init 内部读**：`hmc5883l_read_regs(0x0A, id, 3)` → 比 `HMC5883L_ID_A/B/C_VALUE`（=0x48/0x34/0x33） | 同左 |
| **有对外寄存器读函数吗** | **没有**（`read_regs`/`write_reg` 都 static）⇒ 身份判据只能用 `hmc5883l_init() == 0` | 同左 |
| probe | `hmc5883l_read(&mx,&my,&mz)` 与 `hmc5883l_read_heading(&deg,0,0)`，**最后一条**判 `== 0` | 同左 |
| locals | `int16_t mx = 0` / `my` / `mz` / `float deg = 0` | 同 |
| read | `mx` `my` `mz`（LSB，有符号）+ `(int)deg` + 小数行 | 同 |
| console | 首选 `h`（候选 `i`、`n`） | 同 |
| 上板状态 | `verified:true / hardware_bound:false`，**未上板** | 同 |

**建议字段（两平台只差 include 头名）**

```json
{"include":{"headers":["hmc5883l_stm32.h"]},
 "locals":{"declarations":["int16_t mx = 0","int16_t my = 0","int16_t mz = 0","float deg = 0"]},
 "init":{"calls":["hmc5883l_init()"]},"init_expect":"0",
 "probe":{"calls":["hmc5883l_read(&mx, &my, &mz)","hmc5883l_read_heading(&deg, 0, 0)"],"expect":"0"},
 "read":{"items":[{"expression":"mx","unit":"X 轴原始磁场（LSB，有符号）"}]},
 "console":{"command":"h","description":"…"}}
```

渲染实测：`r = hmc5883l_init();` → `r = hmc5883l_read(&mx,&my,&mz); r = hmc5883l_read_heading(&deg,0,0); if (r != 0) return;`

**read 项与正常范围**（5 条；小数行是库内惯例）
- `mx`/`my`/`mz`：LSB（有符号）。增益 ±1.3 Ga、**1090 LSB/Gauss**（hmc5883l.h:54-55 原话）；
  地磁 0.25~0.65 G ⇒ **单轴大致 ±(0~700) LSB、三轴模长 ~300~700 LSB**；转动模块时数值必须跟着变，
  某个朝向某轴接近 0 是正常的。
- `(int)deg` + 小数行：度，0~360 顺时针；负角已被驱动归一（所以小数行不会是负的）。

**note 要点**
1. **数据区顺序是 X-Z-Y 不是 X-Y-Z**（hmc5883l.c:240-241 原话）——别看寄存器表名猜轴。
2. 判 FAIL 时**返回码 1 与 2 含义不同**：1=总线无应答（供电/上拉/线序/地址），
   2=**ID 不符 = 手上这颗不是 HMC5883L**（市售「HMC5883L 模块」绝大多数其实是 QMC5883L）
   ——框架只印 OK/FAIL 不印 r，note 必须把这两个码写给学生。
3. **上电第一遍读数可能是 0,0,0**：连续测量模式 15Hz，第一轮数据要 ~67ms 才出，而配方里没法插等待
   ⇒ 敲 `h` 复测就是真值。
4. **转动模块数字不跟着变 = 数据没刷新**；恒 0 且判 OK 先按第 3 条复测再看。
5. 接线坑：两脚都要**外部上拉**；stm32 默认 PA6/PA7，与库内其余软 I2C 件同一组脚，同选撞脚。

## 2. qmc5883l（QST，7 位地址 0x0D）

与 hmc5883l **API 同名同语义**（可互替），差异全在寄存器与判据：

| | mspm0 | stm32 |
|---|---|---|
| include | `qmc5883l.h` | `qmc5883l_stm32.h` |
| init | `qmc5883l_init()` → `uint8_t` | 同 |
| init 判据 | **能**：0=成功 / **1=总线无应答** / **2=Chip ID≠0xFF** | 能，同 |
| Chip ID 0xFF 怎么读 | **只在 init 内部**：软复位 → 等 10ms → 读寄存器 **0x0D** → 比 `QMC5883L_CHIP_ID`（0xFFu） | 同左 |
| 有对外读寄存器接口吗 | **没有**（static） | 同 |
| probe | `qmc5883l_read(&mx,&my,&mz)` + `qmc5883l_read_heading(&deg,0,0)`，最后一条 `== 0` | 同 |
| read/console | 同 hmc5883l，字符首选 `q` | 同 |

**注意（写给 note）**：`0x0D` 在本器件**既是写入阶段的从机地址字、又是 Chip ID 寄存器地址**
（两者同值不冲突：位置不同）。
**量程/范围**：CTRL1=0x1D ⇒ OSR=512 / **±8G** / ODR=10Hz / 连续。±8G 档灵敏度约 **3000 LSB/G**
⇒ 地磁对应**单轴大致几百~两千 LSB**。
**时序坑**：`read()` 先等 DRDY 位，**超时上限只有 20ms**，而 ODR=10Hz 刷新周期 ~100ms
⇒ **刚 init 完读必然超时，随后"按现状读一次"**（宁给旧值也不返回失败）⇒ 上电第一遍读数可能是
0/旧值，**敲 `q` 复测即真值**。
**型号互替坑**：HMC 的初始化序列发给 QMC 会**静默**写坏控制字（0x09 在 HMC 是只读状态寄存器、
在 QMC 是控制1；0x0B 在 HMC 是 ID 尾字节、在 QMC 是 SET/RESET 周期）。

## 3. tcs34725（颜色识别，7 位地址 0x29）

| | mspm0 | stm32 |
|---|---|---|
| include | `tcs34725.h` | `tcs34725_stm32.h` |
| prereq | 无 | 无 |
| init | `tcs34725_init()` → `uint8_t`，**1=检出（ID 0x44/0x4D）/ 0=未检出** | 同 |
| **init 能否当判据** | **能，但极性与常规相反：`init_expect` 要写 `"1"`** | 同 |
| 身份怎么读 | init 内部 `tcs34725_read_reg(TCS34725_ID, &id, 1)` 再比 0x44/0x4D（`TCS34725_ID` = 0x12） | 同 |
| **`tcs34725_read_reg` 签名** | **`void tcs34725_read_reg(uint8_t sub_addr, uint8_t *data, uint8_t n)`**——有出参、返回 void | 同签名 |
| **能不能进配方表达式** | **不能进"被判定"的段**（会渲染 `r = tcs34725_read_reg(...)` 编不过）；**只能当裸语句** | 同 |
| probe 建议 | **`tcs34725_init()` 作最后一条**判 `== 1`（唯一真身份判据） | 同 |
| read | `id`（0x44/0x4D 才对）+ 四个通道标量 | 同 |
| 上板状态 | `verified:true`、**未上板** | 同 |

**★ 时序硬坑（本件独有，note 必须写）**：`tcs34725_init()` 里 `enable()` 先写 `ENABLE=PON`
（AEN=0）再写 `PON|AEN` ⇒ **每次 init 都重启积分**；默认积分 24ms，而 init 之后到读 STATUS 只隔
~1ms ⇒ **AVALID 没置位，`tcs34725_read_rgb()` 返回 0，通道数据一个字都没写**。加上 mspm0 的
init/probe/read 里**没有 `delay_ms` 可用**：**mspm0 侧任何"init 之后立刻读"的形状都拿不到真实颜色值**。

> ⚠ **2026-09-25 落地时的实测修正（工单 05，正文原文保留不改）**：出路 (c) 的**确切形状**是
> 「把**读 + 拷贝**那一串放进 `prereq`」，**`tcs34725_init()` 不能放在 `prereq` 开头**——
> `enable()` 会重启积分并清掉 AVALID，而 `prereq` 渲染在 init **之前**且紧接着就读 STATUS
> ⇒ 读回 0（`tcs34725.c:266-268` 直接 return、不动出参），**上电第一遍与每次复测都恒 0**，
> 拿不到下面那句"复测拿到真值"。init 留在 `init` 段与 `probe` 里，形状才成立。
> 读数与反证：`.scratch/hwcheck-specialize/probe-compile-matrix-05.txt`
> 与工单 05 的「双轴评审整改」第 4 条。

三条出路，挑一条并在 note 说清：

- **(a) stm32（推荐）**：把"等待+读+拷贝"放进**没写 init_expect 的 init 段**（裸语句），
  probe 用 `tcs34725_init()` 判身份：
  `init.calls = ["tcs34725_init()", "delay_ms(100)", "tcs34725_read_reg(TCS34725_ID, &id, 1)",
  "rgb.c = 0", "rgb.r = 0", "rgb.g = 0", "rgb.b = 0", "tcs34725_read_rgb(&rgb)",
  "cc = rgb.c", "rc = rgb.r", "gc = rgb.g", "bc = rgb.b"]`；
  `probe = {"calls":["tcs34725_init()"],"expect":"1"}`。**实测 PASS + 渲染正确**。
- **(b) mspm0 同形去掉 `delay_ms(100)`**（实测 PASS）：读数会**恒为 0**（先用 `rgb.* = 0` 兜底）；
  note 如实写"本平台读数为 0 是驱动时序决定，不是接线问题；要看数值请用 stm32 侧"。
- **(c) mspm0 变体（实测 PASS）**：把 `tcs34725_read_rgb(&rgb)` + 四个拷贝放进 **`prereq`**
  （渲染在 init **之前**）⇒ 上电第一遍 0、**敲 `c` 复测拿到真值**。代价：读到的是"上一轮"的采样。
- 另：**mspm0 的 `tcs34725_read_rgb()` 在器件没接时也会返回 1**（见 §6 缺陷①）⇒ **绝不能**
  拿它当通信判据；身份判据只能用 init。

**建议字段（stm32 版）**

```json
{"include":{"headers":["tcs34725_stm32.h"]},
 "locals":{"declarations":["TCS34725_RGBC rgb","uint8_t id = 0","uint16_t cc = 0","uint16_t rc = 0","uint16_t gc = 0","uint16_t bc = 0"]},
 "init":{"calls":["tcs34725_init()","delay_ms(100)","tcs34725_read_reg(TCS34725_ID, &id, 1)","rgb.c = 0","rgb.r = 0","rgb.g = 0","rgb.b = 0","tcs34725_read_rgb(&rgb)","cc = rgb.c","rc = rgb.r","gc = rgb.g","bc = rgb.b"]},
 "probe":{"calls":["tcs34725_init()"],"expect":"1"}}
```

（`TCS34725_RGBC rgb;` **不要写初值**——`= 0` 在 C 里是非法初始化，`locals` 的初值只收数字字面量。）
**正常范围**：16bit 计数 0~65535，**65535 = 饱和/过曝**；ATIME=24ms + 增益 1X 下室内光照 Clear
约**几百~几千**；鲜艳色块对应通道占比明显更高（`tcs34725_rgb_to_hsl` 出参是结构体，**进不了
read 表达式**）。
**地址坑**：0x29 与 **vl53l0x 同址、互替不可同挂**。

## 4. mlx90614（非接触红外测温，SMBus，7 位地址 0x5A）

| | mspm0 | stm32 |
|---|---|---|
| include | `mlx90614.h` | `mlx90614_stm32.h` |
| prereq | 无 | 无 |
| init | `mlx90614_init()` — **void**；**空实现** | void；**非空**：只配两脚 OUT_OD + 置高，**不做任何通信** |
| init 能当判据吗 | **不能**（void，且空实现）。写 `init_expect` ⇒ 渲染 `r = mlx90614_init();` **编不过**（校验器不查返回类型，实测 PASS——这是构建期守卫的漏，别踩） | 同 |
| **能不能做身份探头** | **不能。** RAM 里没有身份寄存器（只有 Ta=0x06 / To=0x07 这类测量字）；厂商确有 EEPROM 段 ID 字段，但库内驱动**一条 EEPROM 通路都没有** | 同 |
| **可用的通信自证** | `mlx90614_read_ambient_temp(&ta)` / `read_object_temp(&to)` 的返回码：**0=成功 / 1=通信失败**（每处 ACK 都查）⇒ 探头 = "0x5A 上真有东西应答了完整读事务"（证通信、**不证型号**） | 同（stm32 多一处写-读间 `delay_ms(1)`） |
| **"温度在合理范围"为什么不算探头** | ① 不是可编译成 `call == expect` 的比较式（渲染器只支持返回码比对，检测页也**不做阈值判决**）；② 合理范围是人为阈值；③ **不证身份** | 同 |

**建议字段**

```json
{"include":{"headers":["mlx90614_stm32.h"]},
 "locals":{"declarations":["float ta = 0","float to = 0"]},
 "init":{"calls":["mlx90614_init()"]},
 "probe":{"calls":["mlx90614_read_ambient_temp(&ta)","mlx90614_read_object_temp(&to)"],"expect":"0"},
 "read":{"items":[{"expression":"(int)ta","unit":"环境温度整数部分（℃）"}]}}
```

渲染实测：`mlx90614_init();`（裸）→ `r = mlx90614_read_ambient_temp(&ta); r = mlx90614_read_object_temp(&to); if (r != 0) return;`
**单位/范围**：℃；换算 `℃ = RAW×0.02 − 273.15`（页面系数，器件本身 0.01℃ 分辨率 ⇒ 读数按 0.02
步进、只到小数第一位）。Ta 正常 = 室温 15~35℃；To = **视场内平均红外温度**：对着墙 ≈ 室温，
对着手掌/额头高几度~十几度，正对窗口/天空可能低于 0℃。
**note 要点**：判 FAIL = 0x5A 没人应答；判 OK ≠ 型号对、更 ≠ 测温准（**无 PEC/CRC 校验**）；
测温要**1~2 分钟热平衡**，开机头几秒的数会漂，属器件特性不是坏。

## 5. sgp30（空气质量，7 位地址 0x58）

| | mspm0 | stm32 |
|---|---|---|
| include | `sgp30.h` | `sgp30_stm32.h` |
| init | `sgp30_init()` — **void**（只发 0x2003） | void（先配两脚再发 0x2003） |
| init 能当判据吗 | **不能**（void；且 `write_cmd` 的失败码被 `(void)` 丢弃） | 同 |
| **feature set / 序列号** | **器件有、驱动没有**：参考实现里有 `get_feature_set = 0x202F` 与 `get_serial_id = 0x3682`——**库内一个都没实现**，`sgp30_write_cmd` 是 static ⇒ **配方层做不出身份探头**（要它得改驱动，本单不许改） | 同 |
| **最强可用探头** | `sgp30_read(&tv, &co) == 0`：写 0x2008 → 读满 6 字节 → **两组 CRC8 校验**；0=成功、1/2/3=写命令应答失败、4=读地址失败、**5=CRC 校验失败**——比纯 ACK 探头**强一档** | 同 |
| read | `co`（CO2 当量 ppm）+ `tv`（TVOC ppb） | 同 |
| console | 首选 `v`（候选 `z`、`w`） | 同 |

**建议字段**

```json
{"include":{"headers":["sgp30_stm32.h"]},
 "locals":{"declarations":["uint16_t tv = 0","uint16_t co = 0"]},
 "init":{"calls":["sgp30_init()"]},
 "probe":{"calls":["sgp30_read(&tv, &co)"],"expect":"0"},
 "read":{"items":[{"expression":"co","unit":"CO2 当量（ppm，室内 400~1000+；400 是预热/背景值）"},
                  {"expression":"tv","unit":"TVOC（ppb，洁净空气 0~几十）"}]}}
```

**note 要点**：① **上电 15s 预热期 CO2=400ppm、TVOC=0ppb 恒定**，此时**探头照样判 OK**
⇒"OK"证的是通信 + CRC，**不证读数已就绪**；② 返回码分段要给全（1/2/3 写命令、4 读地址、
5=**CRC 对不上**先查线长/上拉/干扰）；③ 驱动内部 `delay_ms(100)` 已等过测量时长 ⇒
**一次复测约 0.2~0.3s**，不是卡死；④ 供电 3.3V、约 40mA；⑤ 二次采样间隔不得短于 1s。

## 6. 库内驱动缺陷（**只记录，本单不修**）

① **tcs34725 × mspm0：`tcs34725_read_rgb()` 在器件没接时返回 1（假通过）**。证据：mspm0 侧
   `tcs34725_i2c_write`/`i2c_read` 都是 **void 且丢弃 `wait_ack()` 返回值**，`read_rgb` 里
   `uint8_t status = TCS34725_STATUS_AVALID;` **预置了 AVALID**，器件不在时读回 0xFF
   ⇒ `status & AVALID` 为真 ⇒ 返回 1，四通道读成 0xFFFF。对照 stm32 侧有
   `tcs34725_read_reg_checked` 检查应答 ⇒ 没接时返回 0。**同一 API 两平台语义不一致**。
   对配方的实际影响：**mspm0 侧只能用 `tcs34725_init()` 判身份**。
② **tcs34725 × mspm0：`tcs34725_read_reg()` 无应答检查** ⇒ `id` 读回值无法区分"没接"与
   "接错型号"。
③ **身份校验只藏在返回码里，没有对外读法**：hmc5883l / qmc5883l 的寄存器读原语是 static
   ⇒ 配方无法把 ID 字节显示给学生，只能写 `expect:"0"` 让 init 内部判。
④ **mlx90614 无 PEC/CRC 通路** ⇒ 通信层只有一个 ACK 判据，**数据完整性无校验**。
⑤ **mlx90614 两平台时序不对齐**：stm32 版在写命令→重起始之间加了 `delay_ms(1)`，
   **mspm0 版没有** ⇒ mspm0 真机若读失败，第一嫌疑是这里。
⑥ **qmc5883l 的 DRDY 等待上限（20ms）短于自身 ODR（10Hz ≈ 100ms）** ⇒ 上电首次读**必然走
   "超时后按现状读"**分支（设计上刻意，但配方 note 必须讲清）。
⑦ **mspm0 侧 SCL 的输出方向完全依赖 SysConfig**（驱动只写电平、从不配 IOMUX）⇒ 若哪天
   `SYSCFG_DL_init()` 那行不生效，表现是"总线死、全 FAIL"，与器件坏不可区分。
⑧ （非缺陷，但影响配方）**框架层**：`init_expect` + 无 expect 的 probe 会让同一件**同时**进
   "通过"和"未判定"两档；校验器**不查返回类型**，void 函数 + expect 能过构建期却在编译期炸。

## 7. 写配方时的共同坑（含必须同步改的测试地板实测数）

1. **mspm0 没有母版头** ⇒ `delay_ms` / `gpio_get` / 母版宏**只能出现在 stm32 段**；
   mspm0 段的 init/probe/read 只认本模块头（prereq 例外）。**两侧不能照抄同一串调用**。
2. **`r = call;` 前缀**：`init_expect` / `probe.expect` 一写，该段**每条**调用都被加前缀
   ⇒ 该段不许出现 void 调用；需要 void 调用时把它放进**没写 expect 的那一段**。
3. **expect 不能写身份常量**：必须是**返回码**（`"0"` / `"1"`）。写 `HMC5883L_ID_A_VALUE`、
   `QMC5883L_CHIP_ID`、`TCS34725_ID` 这类都会变成永远 FAIL 的比较式。
4. **read 表达式不能碰结构体成员** ⇒ 结构体出参必须先拷进标量 locals；**结构体 locals
   不能带初值**。
5. **判定计数**：想让一件只记一笔判定，只能"init_expect 或 probe.expect 二选一"；
   两个都写 = 两笔；probe 不写 expect = 多一笔"未判定"。
6. **测试地板/基线（实测数字，必须同步改）**：
   - `tests/test_hwcheck_generic.py`：现测 **planned=159 / with_init=134**（地板写的是 ≥157 / ≥132）。
     本批 5 件 × 2 平台 = 10 格**每格各 -1** ⇒ 加完后 **149 / 124** ⇒ **两条地板都会红**，
     必须如实下调并写原因。
   - `tests/test_hwcheck_recipe.py` 的 `PILOT`（等号断言 17 格 / 10 件）**按 spec 不动**；
     扩张部分另立新常量。`test_recipe_file_itself_keeps_the_floor_cell_count`（≥17 / ≥10）
     加格子不会红，不用改。
   - `tests/test_hwcheck_console.py` 的"真实库配方字符互不相同"会跟着新字符一起跑，
     `h/q/t/v/c` 与既有无冲突（但与票 03 的首选 h/t/e 有重叠，见 §0.5）。
7. **引脚**：stm32 五件默认全 PA6/PA7；mspm0 上 tcs34725 与 qmc5883l 都 PA23/PA24
   ⇒ note 里要提醒"同选撞脚由检测页引脚卡消解/一键绑定"。
8. **别写 `I2C_Init()` 前置**（母版 ml_i2c 的 PA11/PA12，与本批无关）；这五件 prereq 全空。
9. 上板状态：五件两平台都是 `verified:true / hardware_bound:false`，**未上板** ⇒ note 与验收
   记录照旧写"未上板"。

**证据可复现**：本报告的所有 PASS/FAIL 与渲染结论，都是用 `parse_recipes` + `validate_recipes`
+ `render_recipe_section` 在内存里跑的（未落盘、未改库）。
