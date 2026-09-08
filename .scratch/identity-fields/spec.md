## 问题陈述

模块库的「硬件身份字段」（`kit` 套件型号 / `source_url` 购买链接，简介判据②）在
170 个「模块×平台」条目里有 46 条为空，涉及 26 个 slug。用户面对的问题：

1. **库里的条目缺购买信息**——模块详情弹窗只显示「套件：」「来源：」两行空内容，
   用户想照着买件却拿不到型号与链接；买件指引也标不出「库内已有」对应哪件实物。
2. **不知道缺的哪些是真该补的**——26 个 slug 里既有真器件（motor / servo / oled /
   xunji / pid / k230 / ir_beam / led / beep / led_beep / key / step_motor /
   zigbee_link），也有内部件（adc / delay / filter / uart / config / debug_uart /
   digit_uart / imu_uart / ntb_time）与协议切片（coord_detect / huidu /
   zigbee_uart / zigbee_uart_key）。内部件与协议切片**不是用户会单独采购的器件**，
   给它们填购买链接等于伪造数据；真器件不填则是漏。
3. **判据散落三处、已经漂移**——「哪些模块是用户会单独采购的器件」这个判据目前有
   三处各自表述：词表守卫测试里的 `_DEVICE_SLUGS`（8 条）与 `_INTERNAL_SLUGS`
   （12 条）、参考关联豁免表 `MODULE_REFERENCE_EXEMPT`（15 条，含理由）、以及
   manifest 里的 `hardware_bound` 标记。实测三处互相矛盾：`zigbee_link` 被词表当
   器件挂接（`Zigbee 模块（DL-20 串口透传）`），却在参考豁免表里按「协议切片」
   豁免；`beep` 的 mspm0 条目 `hardware_bound=True` 却零引脚零身份，而 stm32 条目
   `hardware_bound=False`——同一个物理器件两个平台标记相反。判据漂移的后果是：
   谁也不知道「这个 slug 该不该有 kit」，补录时只能凭感觉，回潮无人拦。

## 方案

把「模块是器件 / 内部件 / 协议切片」这个判据**收归库内单源**，再由它派生三件事：

1. **身份字段守卫**：器件类 slug 的每个平台条目必须同时有 `kit` 与 `source_url`；
   内部件与协议切片必须两者皆空（显式豁免，不许填）。双向断言，谁回潮谁红。
2. **词表挂接判据**：词表 `lib_modules` 只许挂器件类 slug（买件指引的「库内已有」
   语义 = 用户真会买的那件）；内部件挂了红。
3. **参考关联豁免**：内部件 / 协议切片 / 参考库暂无条目的器件，三种情况各自有
   理由地豁免参考关联（既有 `MODULE_REFERENCE_EXEMPT` 表，理由字段保留）。

三处不再各写名单，统一引用单源；单源里每个 slug 带一句中文理由（为什么它是器件 /
内部件 / 协议切片），判据从「看代码猜」变成「看单源读」。

对用户的可见结果：

- 真器件的模块详情弹窗显示套件型号与购买链接（本次能核实到出处的先补，核不出的
  留在待补清单并另开工单，绝不编链接）。
- 内部件与协议切片明确标注「无需购买链接」，审计不再把它们算成缺口——审计的
  `[身份]` 行只报真器件待补数。
- 判据漂移被测试拦住：三处名单矛盾、器件缺字段、内部件被填字段，任一情况测试红。

## 用户故事

1. 作为**买件的参赛学生**，我想要模块详情里显示这件硬件的套件型号和购买链接，
   以便照着买齐不踩坑。
2. 作为**买件的参赛学生**，我想要内部件（延时、滤波、串口封装、板级配置宏）不被
   标成「要买的东西」，以便买件清单不掺噪音。
3. 作为**补录模块的维护者**，我想要一个地方能查到「这个 slug 算不算器件」，
   以便补录时不再靠猜、也不用同时改三份名单。
4. 作为**补录模块的维护者**，我想要新录入的器件被机械拦住（缺 kit / 链接直接
   拒绝），以便库不再长大新的缺口。
5. 作为**补录模块的维护者**，我想要内部件被机械拦住（有人顺手给它填 kit 也拒绝），
   以便「器件才有身份字段」这条语义不被稀释。
6. 作为**审计脚本使用者**，我想要 `[身份]` 行只统计真器件缺口，以便一眼看清还剩
   多少真活。
7. 作为**代码评审者**，我想要一条测试断言词表挂接名单 / 参考豁免表 / 身份字段名单
   三者不矛盾，以便判据漂移当场暴露。
8. 作为**维护者**，我想要核不出购买出处的条目明确留档（哪些 slug / 为什么核不出 /
   后续怎么核），以便不编造链接也能推进。
9. 作为**模块库使用者**，我想要内部件条目的空身份字段有明确语义（「不适用」而非
   「待补」），以便 UI 不显示误导性的空行。
   ——**本轮未做**（见「范围外」与工单 05）：详情弹窗对内部件/协议切片仍显示空的
   「套件：」「来源：」行；语义标注（隐藏空行 / 显示「无需购买链接」）另开工单。

## 实现决策

### 单源方案（本 spec 的核心结论）

**判据能抽成单源，本次抽。** 落点 = `library.py`（模块库领域判据的家——同文件已有
「判据④机械词表」`BANNED_TOPIC_WORDS` / `CAPABILITY_WORDS` 的单源先例，结构测试与
补录流程共用同一处）。

形状：

- `ModuleKind` 枚举三值：`DEVICE`（用户会单独采购的器件）/ `INTERNAL`（库内以头文件
  / 工具形态存在的内部件）/ `PROTOCOL`（与上位器件绑定的协议 / 帧解析切片）。
- `MODULE_KIND: dict[str, ModuleKind]`——**只登记非器件类**（内部件 / 协议切片）；
  未登记 = 器件。理由：库里 93 个模块绝大多数是器件，器件为默认值可以让新增器件
  自动进入守卫，而内部件/协议切片是少数且需要逐条写明理由。
- `MODULE_KIND_REASONS: dict[str, str]`——每个被登记的 slug 一句中文理由（与
  `MODULE_REFERENCE_EXEMPT` 的理由同源，两表由测试断言一致）。
- 判据函数 `module_kind(slug)` / `requires_identity(slug)`：`requires_identity(slug)`
  为真当且仅当 `module_kind(slug) is DEVICE`。
- 派生函数 `device_slugs()` / `internal_slugs()` / `protocol_slugs()`：供词表守卫与
  测试取名单，不再各自手写。

**为什么不是别处**：`manifest.py` 是数据模型（PlatformEntry 字段形状），判据是库的
领域知识，放模型层会让「什么算器件」变成数据形状问题；`reference_library.py` 是参考
库域，词表与身份字段不依赖参考库（依赖方向反了）。`library.py` 是模块库域判据的
既有家。

**参考豁免的派生关系**：`MODULE_REFERENCE_EXEMPT` 的判据是「该模块在参考库里没有
可关联的条目」——**这是另一个判据，比器件判据多一层**：内部件 / 协议切片可能因同名
例程（`uart` / `adc` / `key`）有映射而合法不豁免（实测 `adc` / `debug_uart` /
`digit_uart` / `imu_uart` / `uart` / `zigbee_uart` / `zigbee_uart_key` 就是这种），
也可能因参考库无条目而豁免；器件则可能因「参考库暂无条目」临时豁免。故单源是
`MODULE_KIND`（器件判据），豁免表保留（参考关联域判据），测试断言两者不矛盾：

- 同一 slug 不得既豁免又有映射（既有断言，两域打架 = 库错误）；
- 凡进豁免表的内部件 / 协议切片，理由的类别前缀必须与 `MODULE_KIND` 一致
  （`内部件` / `协议切片`），防两处措辞各自漂移；
- 词表挂接名单（买件指引）只许含器件——这是器件判据的**强**一致性面
  （身份字段守卫与词表守卫共用同一名单）。

**本次发现并修正的第四处漂移**：词表把 `coord_detect`（K230 帧解析切片）挂进了
`K230（CanMV）` 方案——按判据它不该挂（用户不采购解析切片，实物是 K230 板）。
修正为只挂 `k230`（方案注仍显示「库内已有：k230」，K230 的解析代码随依赖自动进
工程，功能无损失）。判据不放宽来迁就数据。

### 26 个 slug 的类别判定表（逐条给理由）

| slug | 类别 | 理由（写进单源） |
|---|---|---|
| `adc` | INTERNAL | 内部件：板载 ADC 读取封装（无独立实物，通道随引脚绑定） |
| `config` | INTERNAL | 内部件：板级配置宏（引脚/时钟宏集合，不是实物） |
| `debug_uart` | INTERNAL | 内部件：调试串口封装（printf 流，随母版） |
| `delay` | INTERNAL | 内部件：软件延时工具 |
| `digit_uart` | INTERNAL | 内部件：数码管识别串口封装（K230/上位件通道） |
| `filter` | INTERNAL | 内部件：滤波工具（可选配套，无实物） |
| `imu_uart` | INTERNAL | 内部件：IMU601 串口封装（器件在 ml_mpu6050/上位件侧） |
| `ntb_time` | INTERNAL | 内部件：板载时间基准（滴答计时，无实物） |
| `uart` | INTERNAL | 内部件：通用串口封装 |
| `huidu` | INTERNAL | 内部件（同传感器切片）：灰度读取切片，实物归 xunji / pid 条目 |
| `coord_detect` | PROTOCOL | 协议切片：K230 视觉帧解析（CSV 坐标帧），实物归 k230 条目 |
| `zigbee_uart` | PROTOCOL | 协议切片：Zigbee DL-20 接收帧解析（ID 身份帧），实物归 zigbee_link |
| `zigbee_uart_key` | PROTOCOL | 协议切片：Zigbee DL-20 发射组帧，实物归 zigbee_link |
| `beep` | DEVICE | 器件：有源蜂鸣器模块（用户单独采购） |
| `ir_beam` | DEVICE | 器件：红外对射传感器（三线制，用户单独采购） |
| `k230` | DEVICE | 器件：立创·庐山派 K230-CanMV 视觉开发板（副控，用户单独采购） |
| `key` | DEVICE | 器件：独立轻触按键模块（用户单独采购） |
| `led` | DEVICE | 器件：LED 指示灯（板载/外接，用户会买灯珠或模块） |
| `led_beep` | DEVICE | 器件：LED + 蜂鸣器声光组合套件（用户单独采购） |
| `motor` | DEVICE | 器件：直流减速电机 + TB6612 驱动板（用户单独采购） |
| `oled` | DEVICE | 器件：0.96 寸 OLED（SSD1306，用户单独采购） |
| `pid` | DEVICE | 器件：红外对管循迹数组 + PID 闭环（实物 = 灰度/循迹数组，词表已挂接） |
| `servo` | DEVICE | 器件：SG90/MG90S 9g 舵机（用户单独采购） |
| `step_motor` | DEVICE | 器件：脉冲式步进电机 + 驱动板（用户单独采购） |
| `xunji` | DEVICE | 器件：8 路灰度循迹数组（实物 = 灰度传感器，词表已挂接） |
| `zigbee_link` | DEVICE | 器件：Zigbee DL-20 串口透传模块（用户单独采购，词表已挂接） |

**三处矛盾的三条修正**（单源落地后同步）：

1. `zigbee_link`：词表当器件挂接（对）→ 单源判 DEVICE，从「协议切片」豁免理由里
   移出（它自己不是切片，切片是 zigbee_uart / zigbee_uart_key）→ 需要身份字段。
2. `huidu`：参考豁免理由「同传感器切片」保留，单源判 INTERNAL（实物归 xunji/pid）。
3. `ir_beam`：单源判 DEVICE（要身份字段），参考关联仍豁免（参考库无该器件条目）——
   两种豁免不同域，允许并存并各自有理由。

`hardware_bound` 保持原语义（生成前警告「硬件绑定」），**不改它、不拿它当身份判据**：
实测它与器件判据矛盾（beep/mspm0=True 而 beep/stm32=False），继续用它会让判据更漂。

### 豁免的表达形式

**空值 + 单源理由**，不给 manifest 加显式字段。理由：

- 身份字段的语义已经是「由人补填的硬件事实」，空 = 无该事实；内部件/协议切片的
  「无该事实」是**结构性**的，判据在单源里能查到，不需要在 26 个 manifest 里重复
  26 份「不适用」标记（重复即漂移源）。
- 加显式字段（如 `identity_exempt: true`）会让同一事实有两个出处（manifest 字段 vs
  单源判据），两者不一致时又要一条守卫——净增复杂度。
- 生成链路不消费身份字段做逻辑分支（`collect_kits` 只是空值跳过），空值零副作用。

### 守卫的两向断言

新增 `tests/test_library_invariants.py` 用例（照既有风格：失败信息点名「哪个模块 /
哪条不变量 / 具体差异」）：

- `test_device_modules_declare_identity_fields`：器件类 slug（含未登记进单源的库内
  模块）每个平台条目 `kit` 与 `source_url` 均非空，且 `source_url` 以 `http` 开头。
- `test_backlogged_device_modules_declare_identity_fields`：待补清单里的器件同判据，
  标记 `xfail(strict=True)`——数据补齐即 XPASS 判失败，逼摘标记（`tests/conftest.py`
  对本仓 xfail 一律 strict，本工单引入：不加全局 `xfail_strict`，只对显式标记生效）。
- `test_internal_and_protocol_modules_have_no_identity_fields`：`INTERNAL` /
  `PROTOCOL` 的 slug，所有平台条目 `kit` 与 `source_url` 均为空。
- `test_module_kind_map_only_lists_real_modules_with_reasons`：单源里每个 slug 都在
  库内、都有理由；理由表不登记单源外的 slug。
- `test_internal_and_protocol_slugs_reference_declarations_do_not_contradict`：内部件 /
  协议切片不得既豁免又有参考映射（两域打架）。
- `test_wordlist_hooks_are_devices_only`：词表挂接的 slug 必须是器件类。
- `tests/test_wordlist.py` 既有两条用例改为引用单源名单（`device_slugs` /
  `slugs_of_kind`），不再手写 `_DEVICE_SLUGS` / `_INTERNAL_SLUGS`；原「这 8 个 slug
  曾被漏挂」的回归语义由「全部器件必须挂接」覆盖（更强）。
- `tests/test_skeleton_mapping_coverage.py` 的
  `test_reference_exempt_reason_kind_matches_module_kind`：`INTERNAL`/`PROTOCOL` 的
  参考豁免理由类别前缀与单源一致。

红证方式（不污染真实库）：用例内部用 `tmp_path` 合成 manifest 语料或直接对
`PlatformEntry` 构造断言函数输入——但**守卫本身要跑真实库**，红证用「临时副本注入」
（既有先例：工单 library-hookup-and-invariants/02 用临时副本破坏四类全红）。落地时
用脚本对真实 `library/modules/` 做一次临时破坏（给 `delay` 填 kit / 清空 `motor` 的
kit）跑守卫，记红证后还原。

### 审计脚本同步

`.scratch/library-audit/audit.py` 的 `check_identity_fields` 改为：内部件/协议切片
跳过计数（引用 `library.MODULE_KIND`），`[身份]` 行报「真器件缺口」。审计脚本是人工
复跑工具，与测试同源取判据，不再各算各的。

### 30 余条真器件链接的分批处理

原则：**核不出出处的一律不落库**。取源优先级（本次实测结论）：

1. **库内同硬件已有条目**（首选，零编造风险）：motor/mspm0 取 motor/stm32 的
   TB6612 条目；xunji/mspm0 与 pid 双平台取灰度传感器条目。
2. **立创 wiki 模块手册原页**（抓索引页核实存在）：oled 双平台、servo/mspm0、
   motor/mspm0、xunji/mspm0、pid 双平台、k230 双平台（庐山派板页）。
3. **核不出**：led、beep、led_beep、key、step_motor、zigbee_link、ir_beam
   ——立创 wiki 模块手册索引（dmx 70 页 / dkx-stm32f103c8t6 77 页，本次抓取核实）
   里没有这些器件的手册页；这些 slug 进工单 04 的待补清单，**不落库**。

## 测试决策

- **好测试只测外部行为**：断言「库里哪些 slug 必须有身份字段、哪些必须没有」+
  「三处判据不矛盾」，不测单源字典的内部结构、不钉具体条目的字段顺序。
- **测试的模块**：`tests/test_library_invariants.py`（新守卫，主落点）、
  `tests/test_wordlist.py`（既有两条用例改引用单源）、
  `tests/test_skeleton_mapping_coverage.py`（既有豁免断言，补一条与单源一致）。
- **既有先例**：`tests/test_library_invariants.py` 的「全库不变量 + 失败信息点名」
  风格；`tests/test_wordlist.py` 的器件/内部件两向守卫；工单
  library-hookup-and-invariants/02 的「临时副本注入红证」手法。
- **红先绿后**：守卫用例先跑一次证明红（当前库 46 条缺口里器件类必红），再落豁免与
  回填让它转绿。**不许为让测试绿而放宽判据**。

## 范围外

- **UI 语义标注（用户故事 9）**：内部件/协议切片的详情弹窗仍显示空的「套件：」
  「来源：」行——本轮交付判据、守卫、回填、待补清单，UI 展示形态另开工单 05
  （隐藏空行 / 显示「无需购买链接」的措辞口径需要先定）。
- 5.5 四条已知遗留（mq4-9 措辞 / 77 条目未上板 / oled 词表方案级缺口 / A 类 3 页
  mspm0-only 例外）——本次不动。
- 其它工单的状态字段清理（tracker 里 30 多张已落地未翻状态的工单）——独立工作。
- `hardware_bound` 语义与取值的统一（它与器件判据的矛盾本次只记录，不改数据）。
- 库内既有 69 个已带身份的 slug 的类别普查（本次只判 26 个缺口 slug；守卫对未登记
  slug 默认按器件要求，若某既有 slug 实为内部件会红——按需在单源补登记，不改字段）。
- 参考库条目补充（为待补器件补参考条目是另一条路，本次只落待补清单）。

## 补充说明

- 本次交付分批：01 单源 + 三处引用改造 + 不矛盾断言；02 豁免落地 + 双向守卫（红证
  在此记录）；03 可核实真器件回填 + 审计复跑；04 核不出出处的条目清单 + 后续路径
  （可不做完，至少落清单）。
- 预算影响：`kit` 只在 `ManifestSummary.to_line()` 的完整行里出现，瘦身行
  `lean_copy` 不含套件段（工单 preselect-visibility/01）——本次回填的条目若被瘦身行
  消费则零影响；完整行消费点（详情弹窗、参考库套件锚定词表）只增显示。复跑
  `tests/test_manifest.py::test_lean_summary_lines_fit_preselect_budget_for_real_library`
  与全量预算回归确认余量不被吃穿（词表预算余量已吃紧：mspm0 最坏形态 378B）。
- 本次改动是纯库数据 + 测试 + 审计脚本，不碰 manifest 渲染与 UI 代码，无需重启
  4003 应用验证。
