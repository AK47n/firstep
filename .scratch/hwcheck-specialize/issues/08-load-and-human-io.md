# 08 — 专精化批次 F：称重与人机执行四件（hx711 / joystick / servo / relay）

**要做什么：** 学生勾这四件中的任何一件（各两平台、共八格）时，检测页给它一个 `[专精]` 小节，
并且**这件是"能判"还是"只能看现象"一眼可分**：`hx711` 有探头（超时后能读回非 0 = 数据就绪通路活着），
`joystick` 照 `key` 的先例**不写探头**（SW 是"人按才有意义"的输入），`servo` / `relay` 是**纯写执行件**
（探头只能放**不带 expect 的动作**，判定走"没有读取型探头"的如实话术）。四件都给读数
（重量计数 / 摇杆百分比与按键 / 角度与脉宽换算回显 / 引脚电平与极性）与一个复测字符。

**被谁阻塞：** 01（命令字符让位——四件都要声明字符，不留位机制就等着撞车）、
02（未专精样本夹具解耦——本批不是靠它才不会红，而是**有了它才不必再改任何一条既有用例**：
`servo` 现在被若干用例当"未专精样本"用，但那些用例直接调 `plan_generic_section(...)`
**合成**一个通用小节、绕开配方文件（见工单 02 的核查表），所以它们本来就不会红）。

**状态：** resolved

- [x] 八格配方（`hx711` / `joystick` / `servo` / `relay` × `stm32` / `mspm0`）写进
      `library/hwcheck_recipes.json`；事实底稿分两处——
      `hx711` = `.scratch/hwcheck-specialize/recon-02-i2c-generic-1wire.md` §2 的 `hx711` 小节（+ §4-5/6 缺陷、§5 共同坑）；
      `joystick` / `servo` / `relay` = `.scratch/hwcheck-specialize/recon-03-actuators.md` §1–§3（逐件）+ §4 的 D1/D2/D3 + §5 共同坑
- [x] `include` 用**该平台真头名**：`hx711.h` / `joystick.h` / `relay.h`（mspm0）对
      `hx711_stm32.h` / `joystick_stm32.h` / `relay_stm32.h`（stm32）；**`servo` 是唯一两平台共用
      `servo.h`**（stm32 条目根本没有 `servo_stm32.h`）；`hx711`/`joystick` 的 stm32 格若用到
      `HX711_SCK_GPIO` / `JOYSTICK_X_CH` 这类引脚宏，`include` 要**自己带 `pin_config.h`**
      （`headfile.h` 不带它、生成器只在有通用降级件时才自动 include，见 `hwcheck.py:845-849`）；
      `hx711` × stm32 还要带 **`ml_delay.h`**（`delay_ms` 在母版头里，
      **mspm0 侧的配方段引用不到它**——母版没有 .h，具体见下面 `servo` / `relay` 那条）
- [x] **`hx711` 必须写清"一节只能读一次"这一条最硬的实测结论**（recon-02 §2：驱动只等 **20ms**，
      而模块默认 10SPS 的转换周期是 **100ms**；`hx711_init()` 内部先读一次去皮 →
      `init` + 紧接着一次读 = **必 FAIL**）：
      - stm32（`init` 必须调——要配 SCK=PB5/DT=PB0 的脚）：**探头顶一个 `delay_ms(500)`**
        `{"calls":["(delay_ms(500), raw = hx711_read_raw(), (raw != 0) ? 1 : 0)"],"expect":"1"}`，
        locals `uint32_t raw = 0`；500ms 同时覆盖"上电后首个数据 ~400ms"与"10SPS 100ms"
      - mspm0（母版没有 .h，`delay_ms` 在 init/probe/read 里一律构建期红）：**照 `bh1750`
        先例把"等待"放进 `prereq`、`init` 段留空**——
        `prereq = ["hx711_init()", "delay_ms(500)"]`，`probe` 单读作探头
        `{"calls":["(raw = hx711_read_raw(), (raw != 0) ? 1 : 0)"],"expect":"1"}`；
        这一形状**已过真校验器**（`.scratch/hwcheck-specialize/probe-mspm0-delay-shapes.txt`
        的 D 例：PASS 且渲染顺序 = prereq 的 init → 等 500ms → 探头）。
        它比 recon-02 §2 给的"不写 init、单读作探头"多一层：`hx711_init()` 的去皮被保留 ⇒
        `s_tare` 有值（那一条在 recon 里被标成"mspm0 无 delay 可用"，实测 `prereq` 例外——
        见下条与 recon-01 §0）。代价照旧如实写：冷启动那一次 `hx711_init()` 本身可能超时
        （`s_tare` 留 0 ⇒ `get_gram` 不可用），所以**这一格照样不显示克数**、第一遍可能读到 0
        ⇒ **敲 `w` 复读**；两格的取舍与代价都要写进 note
- [x] **`hx711` 的 `read` 只许复用探头那次采样**：形状 = 两条 `read.items`——
      `raw`（24bit 偏移值，≈8388608 = 零点）与 `(int)raw - 8388608`（有符号计数）；
      **必须十进制**（`8388608`，不是 `0x800000`——`read` 表达式禁用十六进制字面量，
      recon-02 §1-1 的报错原文就出在这一处）；
      **`read` 段不许再调 `read_raw()` / `get_gram()`**（会再次超时返 0）；加分项：
      `HX711_GAP_VALUE`(207.00f) 是 **float 宏，不能进整数读数**，只作"标定参考"放在 unit 里说明
- [x] **`joystick` 没有探头**（照 `key` 先例，`library/hwcheck_recipes.json:344` 的口径）：
      **不写 `probe` 段**；可选但不推荐的 `joystick_read_sw()` 静态电平探头**不要写**
      （学生一上手就按着、或接线把 SW 拉低就假 FAIL）；
      `init` = `joystick_init()`（两平台都 **void** → **不写 `init_expect`**）；`prereq` 空
      （`joystick_init()` 自己 `adc_init(...)`，SysConfig 那侧更是框架已经调过 `SYSCFG_DL_init()`）
- [x] `joystick` 的 `read` = 三条：`joystick_read_x_percent()` / `joystick_read_y_percent()` /
      `joystick_read_sw()`（unit 里写清"不推杆≈50、推到两端≈0/100、允许偏差"与
      "1=按下 / 0=松开"）；**不要用 `JOYSTICK_ADC_MAX` / `JOYSTICK_ADC_SAMPLES` 在 mspm0 格**
      （那两个宏 mspm0 侧定义在 `joystick.c:16-18`，**不在头文件里** → 引用会构建期红；
      stm32 侧在 `joystick_stm32.h:31,35`）
- [x] **`servo` / `relay` 是纯写执行件**：`probe` 只能放**不带 `expect` 的动作**
      （硬约束②：一旦写了 `expect`，该段每条调用都会被渲染成 `r = …;`，void 调用直接编译错）。
      ⚠ **"动作 + 等待"的序列在两平台上的形状不同**——`delay_ms` 只在 **stm32** 的
      init/probe/read 里合法（母版 `ml_delay.h` 是母版头）；**mspm0 母版没有 .h**，
      `delay_ms` 出现在 init/probe/read 一律构建期红，唯一放行它的是 `prereq`
      （按"库内任何模块 ∪ 母版"判；recon-01 §0、recon-04 §0.1 都实测 PASS）。
      所以 **mspm0 侧照 `bh1750` 先例把整条动作序列放进 `prereq`、`init` 段留空**
      （`prereq` 渲染在 init **之前**，序列里自己先调 init；这是形状被 schema 逼出来的，
      不是随手选择——配方注记里要写明理由，下一个人照抄才不会再踩）：
      - `servo`：`servo_init(0, 0)`（**双参**，`servo.h:37`；manifest 写单参是文档漂移，
        照头文件写）
        · stm32：`init` = `servo_init(0, 0)`；probe（无 expect）= `servo_set_angle(0, 0)`
          → `delay_ms(600)` → `servo_set_angle(0, 90)` → `delay_ms(600)` →
          `servo_set_angle(0, 180)` → `delay_ms(600)` → `servo_set_angle(0, 90)`
        · mspm0（**不写 `init` 段**）：`prereq` = `["servo_init(0, 0)", "delay_ms(600)",
          "servo_set_angle(0, 90)", "delay_ms(600)", "servo_set_angle(0, 0)"]`
          ——**不要扫到 180°**（D1：周期 640000 超 16 位量程，≈96° 以上输出恒高，
          扫到 180 可能完全不动，学生会读成"舵机坏了"）
      - `relay`：
        · stm32：`init` = `relay_init()`；probe（无 expect）= `relay_set(1)` →
          `delay_ms(500)` → `relay_set(0)`（**收尾回到断开**，别让负载一直吸着）
        · mspm0（同款 `prereq` 形状，**不写 `init` 段**）：`["relay_init()", "relay_set(1)",
          "delay_ms(500)", "relay_set(0)"]`
      - 两件的接口都只有 init / set 两三个：**没有 `relay_on/off/toggle`、没有通道宏**（D7），
        `servo_id` / `channel` 形参被实现丢弃（D5，多舵机是假接口）——凭常识写的名字
        一律构建期红
- [x] `servo` / `relay` 的 `read` 都是**换算表回显，不是测量值**（note 必须说清）：
      `servo` = `SERVO_ANGLE_MAX`(180) / `SERVO_FREQ_HZ`(50) / `SERVO_PULSE_US(90)`（中位脉宽 µs）；
      `relay` × stm32 = `gpio_get(RELAY_GPIO, RELAY_PIN)`（**这是真回读**：1 = 引脚高 = 断开 =
      正常收尾，0 = 还在吸合）+ `RELAY_ON_LEVEL`(0)；`relay` × mspm0 = **只有 `RELAY_ON_LEVEL` 一条是诚实的**
      （mspm0 侧连引脚都读不了，**不许**硬凑 `DL_GPIO_readPins(...)`——SysConfig/driverlib 名字
      在 mspm0 配方任何段都会校验期红）
- [x] `console`：`hx711` 首选 `w`、候选 `n`/`z`；`joystick` 首选 `i`、候选 `n`/`t`；
      `servo` 首选 `d`、候选 `v`/`i`；`relay` 首选 `e`、候选 `n`/`z`（每格一句说明，
      说明 ≤ 约 40 字节——板上是 `hwcheck_line[128]` 行缓冲，中文一字 3 字节）；
      候选按 recon-03 §0 的可用池挑（保留字 `r/y/g/o/b/?` 一个不碰；
      mspm0 已占 `a d j k l m p s u x`、stm32 已占 `a d k l m p u`）；
      本批内部八格首选零冲突；跨批次两处争用——`servo` 与批次 E 的 `ads1115` 都想要 `v`、
      `relay` 与批次 E 的 `pca9685` 都想要 `e`——候选就是为这种撞车准备的
      （工单 01 的让位机制：谁先分配谁拿首选，另一件落到候选，**别把候选偷偷写死成默认字符表**）
- [x] `note` 至少覆盖：① **探头到底证明了什么**——`hx711` 只证"DRDY 通路 + 一次采样出来了"
      （**不证重量准**：克换算要去皮 + 每只秤实测标定）；`joystick` / `servo` / `relay`
      **证不了通信**（要么没身份寄存器，要么是纯写件）；② 判 FAIL 时按**返回码**怎么排查
      （`hx711`：`raw == 0` = 20ms 内没等到 DRDY——没接 / 线断 / 刚上电 400ms 内 / 上一次读不到 100ms）；
      ③ 失败模式四条——恒 0 / 恒定值 / 超时 / **上电第一遍失败**（`joystick` × mspm0 读数**可能恒 0**（D2），
      而 0% 恰好又是"杆推到端点"的合法读数 → 学生分不清"坏了"与"推到端点"）；
      ④ 正常范围参考（空秤 ≈8388608、加重物单调变化、噪声 ±几百~几千计数；摇杆中点"应≈50、允许偏差、
      **库内明确写着没实测**"；舵机 0/90/180° = 0.5/1.5/2.5ms；继电器 = 听咔哒 + 看模块指示灯）；
      ⑤ 接线与引脚坑（`hx711` SCK 空闲低 / DT 空闲高、stm32 SCK=PB5/DT=PB0、
      mspm0 SCK=PA28/DT=PA31 **与 JY61P/IMU601/SHT30/FINGERPRINT 重叠**；
      `servo` stm32 **PB6** 与 pid GRAY_D7/rc522 SCK/lcd-oled SPI DC 重叠、mspm0 **PA7** 与
      motor BIN2/ds18b20 DATA/rc522 CS 重叠；`relay` stm32 **PB4**、mspm0 **PA1** 与
      ml_mpu6050 SCL / i2c_probe SCL / gp2y1014au LED 重叠；`joystick` 见下条）；
      ⑥ 平台差异（`joystick`：mspm0 = **PA26/PA25**（ADC12_0 MEM1/MEM2）+ **PA9**，
      stm32 = **PA1/PA0**（ADC_Channel_1/0）+ **PA10**——**引脚与通道号完全不同**；
      `relay` mspm0 侧**连引脚都读不了**；mspm0 配方**不能**写 `delay_ms` / `gpio_get` / `DL_*`）
- [x] `note` **另须如实提示、本单不修的驱动缺陷**（recon-02 §4、recon-03 §4，只提示不改库）：
      **hx711 的 20ms 超时短于 10SPS 的 100ms 转换周期**，且 init/tare 是"消费一次采样"的读却
      没有任何节流/重试（§4-5）；**hx711 的 0 是歧义词**（`count ^ 0x800000` 在 count=0x800000 时
      也返 0，与超时不可分，§4-6）；**joystick × mspm0 的超时判据用"自旋次数"而不是时间 → X/Y 读数
      很可能恒 0**（D2，推断，需上板）；**servo × mspm0 周期 640000 超过 16 位定时器量程 →
      50Hz 出不来、≈96° 以上输出恒高**（D1，推断，需上板 → 所以这一格不扫 180°）；
      **servo 的 `servo_id` / `channel` 形参被实现丢弃**（D5，多舵机是假接口）；
      **relay × stm32 上电/复位瞬间可能吸合一下**（D3：`gpio_init` 只写 CRL/CRH 不写 ODR +
      复位 ODR=0 + 低电平吸合）——学生最容易被吓到的现象，note 要明说"不是坏了"；
      `relay` stm32 默认脚 **PB4 是 NJTRST / JTAG 复用脚**、库内没动 `SWJ_CFG`
      （万一完全不动、读数也不跟着变，先把 OUT 换到普通 GPIO 脚再试）
- [x] `note` 还要**翻译渲染器那句通用话术**（`hwcheck_recipe.py:1350-1366` 会给没探头的件打
      "本件没有可读的身份 / 状态寄存器…（灯闪 / 屏亮）"）——这四件既没灯也没屏，note 要像 `sr04`
      那样说清各看什么：**`joystick` 看推杆时百分比变不变 / `servo` 盯舵机臂动不动 /
      `relay` 听咔哒声与模块指示灯**
- [x] 检测页实测：四件两平台都显示 `[专精]`（不是「未专精」），命令表里是各自声明的字符
- [x] **扩张地板**追加这 8 格到 `EXPANSION`（工单 03 立的那一处：`EXPANSION` 只装**扩张**格；
      `EXPANSION_CELL_COUNT` 是**手写字面量**——别写成 `len(EXPANSION)`，那是恒真断言）：
      落地后 `EXPANSION_CELL_COUNT` 改成 **40**（+ `PILOT` 那 17 格 = 总覆盖 **57**）；
      **只追加、不改写**已有行；`PILOT` 常量**不动**（有 `len(PILOT) == 17` 的精确断言，
      见 spec「覆盖记录与地板」）
- [x] `tests/test_hwcheck_generic.py` 的未专精基线（写单时是 `planned >= 157` / `with_init >= 132`；
      **批次 A 落地后已降到 153 / 128**——以你落地当时的实数为准），
      `test_hwcheck_generic.py:423-424`）**按实数如实下调并写原因**：本批 8 格转专精，
      其中 **6 格**现在拿得到无参初始化（`servo` × 2 格拿不到——`servo_init(servo_id,
      channel)` 是两个参数，通用降级给不出参数 ⇒ 如实说"不调"）⇒ 两个数**各降 8 / 6**
      （读数 = `.scratch/hwcheck-specialize/probe-batch-cells.txt`；落地时仍以当场实测为准）
- [x] **真编译矩阵**：`py -3 .scratch/hwcheck-specialize/probe-compile-matrix.py --slugs hx711,joystick,servo,relay`
      → 八格全部 `[PASS]`（exit=0、编译器 0 error / 0 warning；链接器形态告警（`warning #10210-D:`）
      另记进读数，见 spec「补充说明」的口径漏洞）
- [x] **反证**：把 `hx711` × `stm32` 那一格撤掉 → 扩张地板断言必须红
      （它是本批事实链最全的一格：`init` + 三元判据探头 + `delay_ms` 跨模块 include + `locals` 复用，
      撤掉后地板若还是绿的，就说明地板没真的钉住"配方内容"）

---

## Comments

### 2026-09-25 立项依据与关键事实

- 这 8 格现在全部是"未专精"（`library/hwcheck_recipes.json` 顶层只有 10 件 / 17 格专精）；
  四件 manifest 与 recon 的实测结论都是 **未上板**（recon-02 §5-11、recon-03 §1–§3 各自末句）。
- **本批是"如实降级"的第二个展示面**：同样是"未专精 → 专精"，`hx711` 能给一笔真判定，
  `joystick` 只能给读数（**不写探头**），`servo` / `relay` 只能给"不带 expect 的动作"——
  页面会把差别写清楚，正是原目标①"看看能不能正常用"要的那种诚实（spec 用户故事 5 / 6）。
- **`hx711` 那一格是整批的"写法试金石"**：它同时踩了三条硬约束——① 跨模块 `delay_ms` 只能进
  `prereq`（但这里用的是 "探头顶延时" 的逗号表达式，所以 `ml_delay.h` 要进 `include`）；
  ② 带 `expect` 的 `probe` 每条调用都是 `r = …;` → 延时必须包进逗号表达式、判据调用放**最后**；
  ④ `read` 只能复用探头那次采样（`locals` 的 `uint32_t raw`）——一写错就是"编译过、判定永远 FAIL"。
- `hx711` 的 0 是**歧义词**这条必须让学生看见：`raw == 0` 既可能是"没接传感器"，
  也可能是"秤正好在零点"（`^ 0x800000` 的副作用）——recon-02 §4-6 的原话口径。
- `relay` × stm32 的"上电咔哒"（D3）是**现象类缺陷里最该写进 note 的一条**：
  学生第一次上电就会被吓到，而库内代码在这个顺序上没做保护（`ml_gpio.c:13-59` 的 `gpio_init`
  不写 ODR + 复位 ODR=0 + 低电平吸合 + `relay_stm32.c:34-36` 的顺序）。
- `servo` × mspm0 的 D1 决定了一格形状：**不扫 180°**——`servo_set_angle(0, 180)` 在
  16 位 LOAD 截断下可能完全不动，学生会把它读成"舵机坏了"。
- 两处字符争用（`servo` 想要 `v`，而 `ads1115` 的首选就是 `v`；`relay` 想要 `e`，
  而 `pca9685` 的首选就是 `c`/`e` 一族）正是工单 01 的存在理由：**候选不是装饰，
  是让"专精面变宽"不兑换成"组合变少"的那一步**。
- 事实层面的一个**口径提醒**：`joystick` / `servo` / `relay` 三件 manifest 的 `dependencies`
  是 `[]`（recon-03 §0 末条），而 `hx711` 那件是 `["delay"]`（manifest 实测）——
  也就是说 `hx711` 的 mspm0 侧延迟能力由 **SysConfig/框架**提供，而**配方段里引用不到**
  `delay_ms`（母版无 .h），这正是 mspm0 那格要把等待放进 `prereq` 的原因。
- **一处 recon 自相矛盾的定案（本单落地前实测过）**：recon-03 §2 给 `servo` 的推荐探针动作里
  夹着 `delay_ms(600)`，而同一份 recon 的 §0 又写着"mspm0 侧配方只能引用模块自己 .h 里的名字"
  ——两句不能同时成立。实测（`.scratch/hwcheck-specialize/probe-mspm0-delay-shapes.txt`，
  跑的是真 `parse_recipes` + `validate_recipes` + `render_recipe_section`）：
  `delay_ms` 出现在 mspm0 的 **probe（A 例）或 init（E 例）一律构建期红**，
  整条序列放进 **`prereq`（B / C 例）PASS 且渲染顺序正确**。所以 mspm0 侧的
  `servo` / `relay` / `hx711` 三格都用 `prereq` 形状（`bh1750` 的同一条先例）。

### 2026-09-25 落地结论（含双轴评审整改）

**验收读数**（全部先落盘再打印）：

| 验收项 | 命令 | 结果 |
|---|---|---|
| 两平台真编译矩阵 | `probe-compile-matrix.py --slugs hx711,joystick,servo,relay --out …-08.txt` | **八格全 `[PASS]`**（exit=0、编译器与链接器各 0 error / 0 warning、页面标记 `[专精]`） |
| 反证 A（撤一格） | `probe-expansion-floor.py --victim hx711 --platform stm32 --out …-08.txt` | 撤掉 → 地板 rc=1 且点名该格；拿回来 rc=0；sha256 逐字节还原 |
| 反证 C（撤回写错的探头） | `probe-locals-guard.py` | 把采样改回存进 `r` → 新守卫红且点名；改回绿、逐字节还原 |
| 反证 B（撤共享候选池） | `probe-console-pool.py` | 57 格上重跑，仍成立 |
| 每批纪律④（字符组合穷举） | `probe-console-combos.py` | `|S| <= 6` 全子集（stm32 **397566** 组 / mspm0 **768181** 组）**零撞车** |
| 地板与基线 | `tests/test_hwcheck_recipe.py` / `test_hwcheck_generic.py` | `EXPANSION_CELL_COUNT` 32 → **40**（手写字面量）；基线 127/104 → **119/98** |
| 全套回归 | `pytest tests/` | 全绿（一次 `test_js_gate` 抖动，单独复跑绿、整套复跑绿） |

**双轴评审整改 4 条**（定点 `5cb7528a`；完整清单见 `08-落地记录.md` §4）：

1. **`hx711 × stm32` 的探头把采样存进了 `r` 而不是 `raw`**——编译过、校验过、探头判 OK，
   而两行读数恒 `0` / `-8388608`，是最像"测过了"的假绿。已改，**并立判据**
   （`test_expansion_cells_that_declare_locals_actually_write_them` + 它自己的自检用例
   + 反证 C）：新格子声明的每个 `locals` 都必须在渲染产物里真被赋值。
2. **`hx711 × mspm0` 的 note 里写着 stm32 的引脚**（PB5/PB0，与同格 PA28/PA31 自相矛盾）——
   已按平台写实，并补回"等待只能进 prereq"的理由与代价。
3. `servo` 的控制台说明写死了"0°→90°→0°"，而 stm32 侧实际扫到 180°（敲一次字符跑整节）——
   说明改成不绑定角度，note 里按平台分别写清扫描段数。
4. `servo` 的「未上板…与 manifest 口径一致」不成立（servo 的 manifest 没有这句）——换成
   servo 专属的如实口径。

另：**一条前提纠正**——本批 JSON 在盘上是 **LF**（不是 CRLF），本批按 LF 写、不做行尾转换；
批次 E 落地时按 CRLF 处理的那一版是错的。

顺手记账（不在本单修）：库里三处**模块头注释的引脚与 syscfg 不一致**（`hx711.h` 的 PB24/PB8、
`joystick.h` 的"四通道"、`servo` manifest 的单参）——见 `.scratch/backlog.md` §23。
