# 03 — 修库内驱动缺陷：`hx711` 的 20ms 超时窗口短于 10SPS 的 100ms 转换周期（`init` 之后紧接着读必超时）

**要做什么：** `hx711` 接好传感器时，**第一次读就能拿到数据**：今天驱动等 DRDY 的上限是
`2000 × delay_us(10)` = **20ms**，而模块默认 **10SPS** 的转换周期是 **100ms**
（只有把 RATE 拉高到 80SPS = 12.5ms 才够）⇒ `hx711_init()`（内部先读一次去皮）之后紧接着的
任何读**必然超时返 0**；而 `0` 又是**歧义词**：`count ^ 0x800000` 在 `count == 0x800000`
（空秤零点）时也返 0，与"没等到数据"完全无法区分。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] **先把"0 的歧义"处理方案写下来再动代码**（本单唯一需要设计决策的一步）：
      候选 ①超时返回哨兵值（如 `HX711_TIMEOUT_SENTINEL`）；②改成"状态码 + 出参"
      双平台同名同型；③保留返回值语义、另加一个"上一次读是否超时"的查询接口。
      评估三点：**双平台 API 对偶**（库内 `tests/test_module_hx711.py` 若有对偶守卫不能破）、
      对配方的影响（`hwcheck-specialize/08` 还没落地 ⇒ 现在改最省事）、以及"0 是合法读数"
      这条不能靠调用方自觉。选定方案与理由写进工单结论
- [x] 等 DRDY 的**时间窗 ≥ 一个转换周期**：默认 10SPS ⇒ ≥100ms（要覆盖 `hx711_init()` 的去皮
      与紧随其后的读）；若 RATE 可配，窗口按配置算；阈值用**常量**表达并配注释说明出处
- [x] `init` / `tare` 是"**消费一次采样**"的读，却没有任何节流或重试（recon-02 §4-5）：
      要么在读之间落实节流（等一个转换周期）、要么让 `init` 不再消费采样
      （把去皮改成显式 `hx711_tare()` 或允许重试）——选法写结论
- [x] 测试（驱动级，照既有 `tests/test_module_*.py` 体例，不照抄实现表达式）：
      ① 超时窗口 ≥ 100ms（用转换周期常量独立复算）；② `init` 之后**紧接着**一次读不会必然超时
      （或：读失败时能明确区分"超时"与"零值"）；③ 双平台行为一致
- [x] **反证**：把窗口改回 20ms / 把歧义处理撤掉 → 新用例必须红（各测一次）
- [x] **真编译矩阵**：`py -3 .scratch/hwcheck-specialize/probe-compile-matrix.py --slugs hx711`
      → 两格全 `[PASS]`（编译器 0 error / 0 warning，链接器告警另记）
- [x] **回来改配方口径**：`hwcheck-specialize/08` 的 stm32 那格现在靠"探头顶一个
      `delay_ms(500)` + 三元判据"绕开这一条、mspm0 那格把 `hx711_init() + delay_ms(500)`
      塞进 `prereq`（读数 `raw` 只复用那一次采样）；本单修好后那两处"绕"可以简化
      ——谁先落地谁改，两边结论互相点名
- [x] 上板状态如实写：**未上板**（本单证据 = 只读侦察 + 数据手册转换周期；真机上"接好就能读"
      要实际称重验证）

---

## Comments

### 2026-09-25 立案依据（recon 只读实测）

- 侦察原文 = `.scratch/hwcheck-specialize/recon-02-i2c-generic-1wire.md` §2 的 `hx711` 小节
  与 §4 的 **5 / 6** 两条。
- 事实链（本单复核过的源码）：
  - `library/modules/hx711/code/hx711.c:26-56`（mspm0 版，stm32 版同型）：`hx711_read_raw()`
    先 `while (DT 高) { delay_us(10); if (++timeout > 2000) return 0; }` ⇒ **20ms 超时**，
    注释自己写着"20ms 超时近似手册转换周期"——而模块默认 10SPS 是 **100ms**；
  - `:16-19` `hx711_init()` 就是 `s_tare = hx711_read_raw();`（立创版 `Get_Maopi` 语义）
    ⇒ 上电这一遍：去皮消费掉一次采样，紧接着的读要再等一个转换周期 ⇒ **必超时**；
  - `:55` `return count ^ 0x800000u;` ⇒ `count == 0x800000`（无负载零点）时返回 **0**，
    与"超时返 0"撞车 ⇒ **0 是歧义词**（§4-6）；
  - 模块默认 10SPS；RATE 拉高才 80SPS（12.5ms）——所以"改窗口"必须按转换周期算，别只改个数字。
- 对配方的影响（**本单不修配方**，但两边要互相点名）：`hwcheck-specialize/08` 的取舍就是被这条
  逼出来的——stm32 侧 `init` 必须调（要配 SCK=PB5/DT=PB0），所以探头顶 `delay_ms(500)`
  （同时覆盖"上电首个数据"与"10SPS 100ms"）；mspm0 侧 `delay_ms` 只能进 `prereq`，
  于是写成 `prereq = ["hx711_init()", "delay_ms(500)"]` + 单读探头，`read` 只复用那一次采样。
  修好之后这些"绕"都能撤掉。
- 相邻但**不在本单**：`HX711_GAP_VALUE`（207.00f）是 float 宏、克换算需要每只秤实测标定
  （属用法问题，不是缺陷）；mspm0 侧默认脚 PA28/PA31 与 JY61P / IMU601 / SHT30 / FINGERPRINT
  重叠（引脚布局问题，归引脚绑定那条路）。

### 2026-09-25 落地结论

**第一步：设计决策——「0 的歧义」怎么处理**（工单要求先写下来再动代码）

| 候选 | 双平台 API 对偶 | 对配方的影响 | 「不能靠调用方自觉」 |
|---|---|---|---|
| ① 超时返回**哨兵值** | 不动（签名一字不改） | 无（`read_raw()` 照调） | ✓ **值本身就在返回值里**，想忽略也忽略不掉 |
| ② 状态码 + 出参 | **要改签名**（四函数全动） | 配方与骨架调用点全要改 | ✓ |
| ③ 另加「上次是否超时」查询 | 加函数（不改签名） | 加一行调用 | ✗ **调用方不查就还是分不开**——正是工单否掉的那条 |

**选定 ①**，理由：合法读数是 `count ^ 0x800000`（24 位，`count` 24 位 ⇒ 结果 ∈ [0, 0xFFFFFF]），
所以 **`0xFFFFFFFF` 必然在合法域之外**，当哨兵天然无歧义；且签名零改动 ⇒ 配方、骨架、克换算
全都不用跟着改。③ 被否掉的直接原因就是工单那句「不能靠调用方自觉」。

**第二步：窗口按转换周期算**（工单要求"阈值用常量表达并配注释说明出处"）

| 常量 | 值 | 出处 |
|---|---|---|
| `HX711_SPS_DEFAULT` | 10 | 模块默认输出速率（RATE 脚接低，数据手册） |
| `HX711_CONV_PERIOD_MS` | 100 | `1000 / SPS` |
| `HX711_READY_TIMEOUT_MS` | 200 | `2 × 转换周期`（旧实现是写死的 20ms） |
| `HX711_POLL_US` | 10 | 轮询步长（原样） |
| `HX711_READY_TIMEOUT_LOOPS` | 20000 | `窗口 × 1000 / 步长`——**由窗口推出来**，不再手写 2000 |

`init` / `tare` 那个「消费一次采样却没有节流」的问题：**由驱动自己承担**——窗口 ≥ 一个完整
转换周期，正常路径就变成「等下一个样本」而不是失败（这就是工单说的"读之间落实节流"的等价物），
调用方不必再自己补 `delay_ms`。

**改了什么**

1. `library/modules/hx711/code/hx711.c` / `hx711_stm32.c`：时间窗常量 + 超时返回
   `HX711_TIMEOUT_SENTINEL`（两平台同款同值）；`hx711_get_gram()` 把「没读到」与「空秤」
   分开（超时 → **-1.0f**，空秤/负重量 → 0.0f）。
2. `library/modules/hx711/code/hx711.h` / `hx711_stm32.h`：新增 `HX711_TIMEOUT_SENTINEL`
   并写清「为什么非要有这个值」；四个接口的注释按新语义改（含 `hx711_init()` 会等满一个周期）。
3. `library/modules/hx711/manifest.json`：两平台 notes 里「20ms 超时返回 0」「0 是歧义词」
   那几处改成修后口径（`**未上板**` 保留）。
4. `library/hwcheck_recipes.json`：**两格**的探头判据从「读到一个非 0 的数」改成
   「读到的值 ≠ `HX711_TIMEOUT_SENTINEL`」；stm32 格的 `delay_ms(500)` 拐杖与随之无用的
   `ml_delay.h` 摘掉，mspm0 格的 `prereq` 只留 `hx711_init()`；两格 note 四处按修后口径重写。
   顺手删掉 mspm0 格里那条**从 stm32 抄错的**「接线坑：默认 SCK = PB5 / DT = PB0」
   （本平台是 PA28/PA31，上一行已经写对——同一格两套引脚会直接误导接线）。
5. `tests/test_module_hx711.py`：三条新判据 + 把原来那条「20ms / return 0」守卫改写成新口径。

**判据与读数**

- `test_hx711_ready_window_covers_a_conversion_period`（两平台各一格）：独立复算
  `1000 / 10SPS = 100ms`，断言窗口 ≥ 一个转换周期、且**轮询圈数由窗口推出来**、
  源码里不再出现写死的 `2000`。
- `test_hx711_timeout_is_never_disguised_as_a_zero_reading`（两平台各一格）：断言哨兵
  **> 0xFFFFFF**（24 位合法域之外）、超时分支 `return HX711_TIMEOUT_SENTINEL`、
  **不许出现 `return 0;`**、克数接口把「没读到」与「空秤」分开。
- `test_hx711_window_and_sentinel_are_identical_on_both_platforms`：跨文件对拍六个常量
  逐项相等 + 公共 API 签名一字不动。
- **反证**：`.scratch/driver-defect-fixes/probe-guard-strength-03.py` →
  `probe-guard-strength-03.txt`——四条注入逐条让对应用例变红、逐字节复原（sha256 一致）：
  ① 窗口缩回 1/10 个转换周期；② 超时又 `return 0`；③ 哨兵值落回 24 位合法域内（`0x800000`）；
  ④ 只改 stm32 的轮询步长（两平台悄悄分叉）。
- **真编译矩阵**：`probe-compile-matrix.py --slugs hx711` → `probe-compile-matrix-03.txt`：
  **两格全 `[PASS]`**，编译器 0 error / 0 warning、链接器 0 warning（新配方里的
  `HX711_TIMEOUT_SENTINEL` 真编进去了）。
- `tests/test_module_hx711.py` + `tests/test_hwcheck_recipe.py` + `tests/test_hwcheck*.py`
  **358 passed / 10 skipped**（另：`test_module_hx711.py` 单跑 11 条全绿）。

**上板状态：未上板。** 本单证据 = 只读侦察 + 数据手册转换周期 + 驱动级判据 + 真编译矩阵 +
反证；「接好传感器第一次读就能拿到数据」要真机上秤，归 `docs/agents/local-environment.md`
那条安排（工单 `hwcheck-acceptance/05`）。

**双轴评审的整改**（`code-review`，Standards + Spec 各一轮）——本轮抓到一处**真缺陷**：

1. **【真缺陷，已修】去皮会把哨兵值存成零点**：`s_tare = hx711_read_raw();` 在超时时让
   `s_tare = 0xFFFFFFFF`，于是 `克 = (raw - s_tare)` 变成 `raw + 1` 的**天文数字**
   （旧代码存 0 反而没这么坏）。改成 `hx711_tare()` 里过哨兵判断（**没读到就零点原样不动**），
   `hx711_init()` 走同一处；两平台同改，并补判据
   `test_hx711_tare_never_stores_a_timeout_as_the_zero_point` + 注入 E（撤掉守卫必须红）。
   ——工单第 18 行那句「不能靠调用方自觉」，对**驱动自己**同样成立。
2. **【文案与实现不符，已修】印出来的不是 4294967295 而是 `-1`**：渲染出口是
   `hwcheck_report_int(int value)`，而两格 `locals` 是 `uint32_t raw` ⇒ 哨兵过 int 形参印成 -1。
   量具 `probe-03-printed-values.py` 打印了真产物里的调用点与函数签名；两格 `read` 的 `unit`、
   `note`（判 FAIL / 0 的歧义两条）与命令台说明都按**实际印出来的**改写。
3. **【如实口径，已修】冷启动那条提示被删过头**：窗口 200ms，而 HX711 上电后第一个样本要
   ~400ms ⇒ 冷启动那一次 `hx711_init()` **仍可能超时**（那时零点不存）。这条写回两格 note
   （旧版写「第一遍可能读到 0」，现象是真的、理由写错了）。
4. **【判据漏绑定，已修】**：mspm0 侧原来只钉 `#define` 与「源码里没有 2000」，循环本身没有断言
   → 补「循环退出界 == `HX711_READY_TIMEOUT_LOOPS`」与「步长 == `HX711_POLL_US`」两条。
5. **【Duplicated Code，已按仓库先例处理】**：两份测试文件里逐字相同的 C 解析助手抽到
   `tests/_c_macros.py`（照 `tests/_c_escape.py` 先例：那份也是三处重复之后抽出来的），
   两个测试文件 thin 引用。
6. **【越界追认】**：删 `ml_delay.h` / 双侧 `delay_ms(500)` / servo 补 180° 三处，工单点名过但
   spec 射程没写 → 已在 `spec.md`「范围外」补追认（见那一节的第二次修订）。
7. 评审**核过站得住**的：哨兵 0xFFFFFFFF 确在 24 位合法域之外；双平台 6 个常量逐项一致；
   「两平台对拍」用例确实抓得住单侧分叉。


