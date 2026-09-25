# 05 — 专精化批次 C：姿态与光色三件（hmc5883l / qmc5883l / tcs34725）

**要做什么：** 学生勾这三件中的任何一件（含两平台）时，检测页给它一个 `[专精]` 小节，并且
**"真做了身份判定"与"只证通信"一眼可分**：`hmc5883l` / `qmc5883l` 的初始化返回值里就装着
**器件 ID 比对**（返回码 2 = ID 不符，是硬身份判据）；`tcs34725` 的初始化返回
**1 = 检出（ID 0x44 / 0x4D）、0 = 未检出**，极性与常规相反。三件都给读数（三轴磁场 LSB +
航向角 / RGBC 四通道计数）与复测字符。此前它们只有"未专精：只验总线和初始化"。

**被谁阻塞：** 01（命令字符让位——三件都要声明首选 + 候选，不留让位机制就等着撞车）、
02（未专精样本夹具解耦——内容批次的统一前置；本批 6 格不在它点名的耦合点上，见 Comments）。

**状态：** ready-for-agent

- [ ] 六格配方（`hmc5883l` / `qmc5883l` / `tcs34725` × `stm32` / `mspm0`）写进
      `library/hwcheck_recipes.json`，事实底稿 = `.scratch/hwcheck-specialize/recon-04-attitude-optical.md`
      §1（hmc5883l）、§2（qmc5883l）、§3（tcs34725）；形状约束见该报告 §0.2、共同坑 §7
- [ ] `include` 用**该平台真头名**（六格互不相同）：`hmc5883l.h` / `hmc5883l_stm32.h`、
      `qmc5883l.h` / `qmc5883l_stm32.h`、`tcs34725.h` / `tcs34725_stm32.h`——mspm0 写成
      `xxx_stm32.h` 构建期红（recon-04 §0.1 的实测反证）；delay 头不用写（框架已 include）
- [ ] `prereq`：五格留空（三件都是软 I2C 位操作，不用母版 ml_i2c），**只有 `tcs34725 × mspm0` 一格有**
      （见下面 `tcs34725` 那条）；别照抄 `ml_mpu6050` 的 `prereq: ["I2C_Init()"]`——那是母版软 I2C 的
      PA11/PA12，与本批无关
- [ ] `hmc5883l` / `qmc5883l`：`init` = `xxx_init()` + `init_expect: "0"`（0=成功 / 1=总线无应答 /
      **2=ID 不符**）；`probe` = `["xxx_read(&mx, &my, &mz)", "xxx_read_heading(&deg, 0, 0)"]` +
      `expect: "0"`（probe 段多条时**只有最后一条**参与比较：采集调用放前面、判据调用放末尾）；
      `locals` = `int16_t mx = 0` / `my` / `mz` + `float deg = 0`
- [ ] `hmc5883l` / `qmc5883l` 的**身份判据只能落在 init 的返回码上**：两件的寄存器读原语都是
      `static` ⇒ 配方写不出 ID 字节给学生看（recon-04 §6③）；`expect` **不许写**
      `HMC5883L_ID_A_VALUE` / `QMC5883L_CHIP_ID`（会渲成永远 FAIL 的比较式，recon-04 §0.2 实测）
- [ ] `hmc5883l` / `qmc5883l` 判定计数**知情**：`init_expect` 与 `probe.expect` 都写 = 同一件记两笔
      （ID 一笔 + 读事务一笔；spec 硬约束⑥ 允许但要写明），note 里说清两笔各证明什么
- [ ] `tcs34725`：`init` 段**裸写、不写 `init_expect`**（init 段里有 void 的 `tcs34725_read_reg`，
      一写 expect 就会渲成 `r = tcs34725_read_reg(...)` 编不过）；身份判据落在
      `probe: {"calls": ["tcs34725_init()"], "expect": "1"}`——**极性 1 = 检出**（recon-04 §3）
- [ ] `tcs34725` 的时序形状按 recon §3 的三条出路挑定：**stm32 走 (a)**（`init.calls` =
      `tcs34725_init()` → `delay_ms(100)` → 读 `TCS34725_ID` → `rgb.* = 0` 兜底 →
      `tcs34725_read_rgb(&rgb)` → 四通道拷进标量）；**mspm0 走 (c)**（同一串去掉 `delay_ms` 放进
      `prereq`：上电第一遍读 0、敲 `c` 复测才拿真值，代价是读到"上一轮"的采样）；**(b) 不选**——
      它把这一格降成"读数恒 0"，与"给读数"这条深度目标冲突。(a) / (c) 都是 recon 实测 PASS 的形状
- [ ] `tcs34725` 的 `locals`：`TCS34725_RGBC rgb`（**不带初值**——结构体 locals 不能带初值）+
      `uint8_t id = 0` + `uint16_t cc = 0` / `rc` / `gc` / `bc`；结构体出参**必须先拷进标量**
      （`rgb.c` 在 read 里会被拆成裸名 `c` 报错）；read 项 = `id` + `cc` `rc` `gc` `bc`
- [ ] `read` 照 recon 写：hmc / qmc = `mx` `my` `mz`（LSB，有符号）+ `(int)deg` + 小数行
      `(int)((deg - (int)deg) * 10)`；tcs34725 = `id` + 四个通道计数。**read 表达式里不许出现
      十六进制字面量**（`0x00` 会被切出 `x00`）——0x44 / 0x4D 这类期望值只写在 `unit` 文字里
- [ ] `console`：`console.command`（首选）+ `console.candidates`（候选，工单 01 落地的字段形状）——
      `hmc5883l` 首选 `h`、候选 `i`、`n`；`qmc5883l` 首选 `q`、候选 `w`、`z`；
      `tcs34725` 首选 `c`、候选 `e`、`f`；**两平台同一组**（命令表按平台各一张，平台内不许重复）。
      候选全部取自实测空闲池 `c e f h i n q t v w z` + 数字 `0-9`（池 31 / 现状已占 10）；
      保留字 `r/y/g/o/b` 与帮助 `?` 一个不碰
- [ ] `note` 至少覆盖：① **探头到底证明了什么**（hmc / qmc 的 `init == 0` 含 ID 比对 = 身份判据，
      probe 的 `== 0` 只证读事务通；tcs34725 的 `tcs34725_init() == 1` 才是身份判据，而
      `tcs34725_read_rgb()` **在 mspm0 侧器件没接时也返回 1**，绝不能当通信判据）；② 判 FAIL 时
      **按返回码排查**（hmc：1=总线无应答（供电 / 上拉 / 线序 / 地址）、2=ID 不符=手上这颗不是
      HMC5883L（市售"HMC5883L 模块"绝大多数其实是 QMC5883L）；qmc：1=总线无应答 / 2=Chip ID≠0xFF；
      框架只印 OK / FAIL 不印 r，这两个码只能由 note 写给学生）；③ 失败模式（hmc 上电第一遍可能
      0,0,0——连续测量 15Hz 第一轮数据 ~67ms 才出、配方里插不进等待，敲 `h` 复测；qmc 的 DRDY 等待
      上限只有 20ms，短于自身 ODR 10Hz 的 ~100ms ⇒ 刚 init 完读**必然**走"超时后按现状读一次"、
      敲 `q` 复测即真值；tcs34725 读数为 0 是驱动时序不是接线；init 判 FAIL **不 return**
      （hwcheck_recipe.py:1258-1267）⇒ 读数照打但不可信）；④ 正常范围（hmc：1090 LSB/Gauss、地磁 0.25~0.65 G ⇒ 单轴大致 ±(0~700) LSB、
      三轴模长 ~300~700，转动模块数字必须跟着变；qmc：±8G ≈ 3000 LSB/G ⇒ 单轴几百~两千；
      tcs34725：16bit 0~65535、65535=饱和/过曝、室内光照 Clear 约几百~几千）；⑤ 接线与地址坑
      （7 位地址 0x1E / 0x0D / 0x29 三者互不相同可共挂，但 0x29 与 vl53l0x 同址、互替不可同挂；
      **三件地址都是驱动里写死的常量**（库内没有 `set_address` 之类的改址接口）⇒ 要换地址只能换器件
      或换总线；stm32 三件默认都 PA6/PA7、同选撞脚由检测页引脚卡消解；mspm0 侧 tcs34725 与 qmc5883l
      **都是 PA23/PA24**、hmc5883l 是 PB6/PB7；两脚必须**外部上拉**——mspm0 的 syscfg 两脚没配内部上拉）；
      ⑥ 平台差异（mspm0 无母版 .h ⇒ init / probe / read 里不许写 `delay_ms` / `gpio_get`，跨模块调用
      只能进 `prereq`；mspm0 的 SCL 只写电平、输出方向完全依赖 SysConfig + `SYSCFG_DL_init()`，
      那行不生效 = 总线死）；⑦ hmc5883l 的数据区顺序是 **X-Z-Y** 不是 X-Y-Z，别看寄存器表名猜轴
- [ ] 上板状态照旧如实写**「未上板」**（三件两平台 `verified: true / hardware_bound: false`）——
      编译绿不是板上证据
- [ ] 检测页实测：三件两平台显示 `[专精]`（不是 `未专精`），命令表里是**分配后**的字符
- [ ] **扩张地板**追加这 6 格到 `EXPANSION`（工单 03 立的那一处：`EXPANSION` 只装**扩张**格；
      `EXPANSION_CELL_COUNT` 是**手写字面量**——**别写成 `len(EXPANSION)`**，那是恒真断言）：
      落地后 `EXPANSION_CELL_COUNT` 改成 **18**（+ `PILOT` 那 17 格 = 配方文件应有的总覆盖 **35**）；
      **只追加、不改写**已有行；`PILOT` 常量**不动**——它钉的是 v1 清单，有 `len(PILOT) == 17` 的精确断言
- [ ] `tests/test_hwcheck_generic.py` 的未专精基线（写单时是 `planned >= 157` / `with_init >= 132`；
      **批次 A 落地后已降到 153 / 128**——以你落地当时的实数为准）**按实数
      如实下调并写原因**：本批 6 格每格各 -1（实测这 6 格的通用规划都拿得到无参初始化）；写单时实测
      （批次 A/B 尚未落地）`planned = 159` / `with_init = 134` ⇒ 本批落地后 **153 / 128**（若 A/B
      先落地，就在它们之后的数上再 -6）。跟着实数改数，**不许删断言**
- [ ] **真编译矩阵**：`py -3 .scratch/hwcheck-specialize/probe-compile-matrix.py --slugs hmc5883l,qmc5883l,tcs34725`
      → 六格全 `[PASS]`（exit=0、编译器 0 error / 0 warning；**链接器形态告警另记**），读数落盘
- [ ] **反证**：把 `tcs34725 × mspm0` 那一格配方撤掉 → 扩张地板断言必须红（35 → 34）

---

## Comments

### 2026-09-25 立项依据与关键事实

- 这 6 格现在全部是"未专精"，学生看不到判定与读数。三件两平台 manifest 是
  `verified: true / hardware_bound: false`（recon-04 §7.9）——**都未上板**；recon-04 的配方草案
  过了真校验器 + 渲染逐行核对（报告抬头原话），本单取其中 6 格。
- **身份判据只在 `init()` 内部，`expect` 只能写返回码**：两件的寄存器读原语都是 `static`
  （`hmc5883l_read_regs` hmc5883l.c:172、`qmc5883l_read_regs` qmc5883l.c:177；recon-04 §1 / §2 / §6③）
  ⇒ 配方没法把 ID 字节显示给学生，只能 `expect: "0"` 让 init 内部判；而写给 `hmc5883l_init()` 的
  `expect: "HMC5883L_ID_A_VALUE"`（0x48）会渲成 `r == 0x48`，驱动返 0/1/2 ⇒ **永远 FAIL**
  （校验 PASS、板上必红，recon-04 §0.2 实测）。
- **tcs34725 的时序硬坑与三条出路**（recon-04 §3 原文口径）：`enable()` 先写 `ENABLE=PON`（AEN=0）
  再写 `PON|AEN` ⇒ **每次 init 都重启积分**；默认积分 24ms，而 init 之后到读 STATUS 只隔 ~1ms
  ⇒ AVALID 没置位、`tcs34725_read_rgb()` 返回 0、**通道数据一个字都没写**（`tcs34725.c:261-268`：
  未置位直接 `return 0`、不动出参——所以 (b) / (c) 形状要先用 `rgb.* = 0` 兜底）；再加上 mspm0 的
  init / probe / read 里**没有 `delay_ms` 可用** ⇒ mspm0 侧任何"init 之后立刻读"的形状都拿不到真实
  颜色值。三条出路：(a) stm32 把"等待+读+拷贝"放进没写 `init_expect` 的 init 段（裸语句）、probe 用
  `tcs34725_init()` 判身份；(b) mspm0 同形去掉 `delay_ms(100)`（读数恒 0）；(c) mspm0 把那一串放进
  `prereq`（渲染在 init 之前）⇒ 上电第一遍 0、敲 `c` 复测拿真值，代价是读到"上一轮"的采样。
  本单选 (a) + (c)：唯一同时给出"身份判据"与"真读数"的形状。
- (c) 的前提本单核对过（不是推测）：复测会重跑**整节**——`render_console_runtime` 的分派是
  `case '<字符>': … hwcheck_check_<slug>();`（hwcheck_console.py 的 `render_console_runtime`），
  而 `prereq` 是小节体里的裸语句、渲染顺序固定为 `locals → prereq → init → probe → read`
  （hwcheck_recipe.py 的 `render_recipe_section`）⇒ "敲 `c` 复测拿到上一轮积分值"成立。
- mspm0 侧 `tcs34725_read_rgb()` 是**假通过**：mspm0 的 i2c 读写都是 void 且丢弃 `wait_ack()` 返回值，
  `read_rgb` 里 `uint8_t status = TCS34725_STATUS_AVALID;` 预置了 AVALID（`tcs34725.c:263`）⇒ 器件不在时
  读回 0xFF、`status & AVALID` 为真、返回 1、四通道读成 0xFFFF；对照 stm32 侧有
  `tcs34725_read_reg_checked` 检查应答 ⇒ 没接时返回 0。**同一 API 两平台语义不一致**（recon-04 §6①）
  ⇒ mspm0 的身份判据只能用 `tcs34725_init()`。
- 引脚与地址（recon-04 §0.4）：stm32 三件默认全 PA6/PA7（pin_config.h:289-296 HMC、297-306 QMC、
  348-351 TCS）⇒ 同一物理总线只能挂一个"脚位组"、同选必然撞脚（检测页标 ⚠ 并有一键绑定）；
  三件 7 位地址 0x1E / 0x0D / 0x29 互不相同 ⇒ 协议上可共挂、卡的是脚；mspm0 侧 tcs34725 与
  qmc5883l 都是 PA23/PA24（同选也撞），总线上必须靠模块板自带 / 外接上拉。
- 字符重叠是**预期**而不是错：批次 A 的 aht10 也首选 `h`、sht20 也首选 `t`（recon-04 §0.5 ⚠）；
  按 01 的让位机制不报错，但页面显示的是**分配后**的字符、分配顺序 = `sort_verification_order`
  的验证顺序（hwcheck_recipe.py:1141-1155）而不是配方文件书写顺序 ⇒ 文案里别写死"敲 h 测罗盘"。
- 基线 / 地板：写单时按 `test_hwcheck_generic.py` 的同一条算法实测 `planned = 159` /
  `with_init = 134`（与 recon-04 §7.6 一致），本批 6 格每格各 -1（三件的通用规划都拿得到无参 init：
  `hmc5883l_init` / `qmc5883l_init` / `tcs34725_init`）⇒ 落地后 153 / 128。
- 库内驱动缺陷（**本单不修**，note 如实提示）：③ 身份校验只藏在返回码里（§6③）；⑥ qmc 的 DRDY
  20ms 上限短于自身 ODR（§6⑥）；⑦ mspm0 侧 SCL 输出方向完全依赖 SysConfig——驱动只写电平、
  从不 `DL_GPIO_initDigitalOutput(SCL_IOMUX)`（hmc5883l.c:42-49 同型，§6⑦）；⑧ 校验器**不查返回类型**
  且"`init_expect` + 无 expect 的 probe"会让同一件同时进"通过"与"未判定"两档（§6⑧）——本单三件都写了
  `probe.expect`，不吃后半条。
- 既有用例里唯一用到本批件的是 `tests/test_hwcheck_board.py:209`（hmc5883l + qmc5883l 的 PA6/PA7
  合法共享视图），它不吃配方 ⇒ 本批**不需要改任何既有用例**（正是 02 立的那条判据）；02 的耦合表
  只点名 `sht20`（`tests/test_hwcheck.py:2166` / `:2245`），本批 6 格不在表上——仍把 02 列为前置，
  是为了内容批次统一按同一条流水线走（配方多 6 格后地板与基线一次改到位）。
