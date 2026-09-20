# 07 — 通用降级：未专精模块也能检测

**要做什么：** 清单外的那批模块（绝大多数）也能量产检测程序：做初始化 + **I2C 类模块做总线地址扫描**（"这根总线上有没有东西应答、在哪个地址"），并在页面与产出里**如实标注「未专精：只验总线和初始化」**。

**被谁阻塞：** 03（器件选择与引脚信息）、04（配方机制）。

**状态：** resolved

- [x] 未专精模块也能被选中并生成检测程序，**不报错、不拒绝**
      （`resolve_generic_sections`：168 个未专精格**逐格**都规划得出来，一条都不拒；
      真机编译矩阵里 beep / sht20 / servo / ws2812 / aht10 五件都真生成真编译。
      「一件恰好进一个桶」由 `test_every_device_ends_up_in_exactly_one_bucket` 钉住：
      专精 ∪ 通用 ∪ 缺平台条目 = 选中集，不许有第四种下场）
- [x] 通用路径 = 初始化 + （仅当模块声明了 I2C 类引脚角色时）总线地址扫描；扫描结果打印"应答地址清单 / 无应答"
      （`plan_init` + `scan_for_pins` + `render_generic_section`；**行为证据**
      `probe-07-scan-behaviour.py` 把渲染出的**整份 main.c** 用 gcc 编起来真跑，
      `gpio_*` 由探针仿一条 I2C 总线：从机在 0x3C → 打「应答：0x3C」；谁都不应答
      → 打「无应答」+ 供电 / 上拉 / 线序。两种形态 2/2 符合预期）
- [x] **不猜读函数**：通用路径不产生任何"猜出来的读调用"（结构守卫断言：通用段落里除初始化与扫描外无模块接口调用）
      （`test_render_generic_section_never_calls_anything_but_the_init`：该模块头里的名字
      ∩ 通用小节调用集 == {初始化}；行为面另有一条——探针把 `sht20_read` 桩成
      `abort()`，通用小节一碰就崩，真跑没崩）
- [x] 「未专精」标注在检测页与产出注释里同时出现，措辞一致（单源）
      （`GENERIC_LABEL` 单源三处共用：产物细节行、产物注释块、检测页载荷 `label`；
      前端**一个字不另写**（旧载荷缺 `label` 就不画徽章，不编兜底句）；
      `test_preview_reports_devices_without_a_recipe_as_unspecialized` 同时断言两边）
- [x] 非 I2C、也未专精的模块：只做初始化 + 明说"本件未专精，仅确认初始化不报错"
      （`plan_text` 与产物注释逐字带这句；串口那行也印「（本件未专精，不判返回值）」。
      ⚠ **28 格例外如实记账**：那些格子的初始化要参数（`servo_init(servo_id, channel)`
      / `pca9685_init(freq_hz)`）或本平台没有模块头（`files: []`），通用降级**一个动作
      都做不了**——这时标 `GENERIC_LABEL_IDLE`「未专精：这一趟没有可执行的动作」，**绝不**
      再印「只验总线和初始化」（原实现印了，是"拿没做的事当好结果"，本单评审抓到并整改））
- [x] 单测覆盖三类：I2C 未专精 / 非 I2C 未专精 / 已专精（走配方，不走通用）
      （`tests/test_hwcheck_generic.py` 28 条：sht20（I2C）· ws2812 / beep（非 I2C）·
      led / ml_mpu6050（专精，断言不进通用）；`tests/test_hwcheck.py` 另 12 条钉渲染与端点）
- [x] 检测页对未专精件的措辞与"已专精"可视觉区分，避免用户把走过场当验证过
      （`.hwcheck-generic`（虚框 + 灰描边徽章 + 「不算通过」）对 `.hwcheck-section`
      （实心 `[专精]` + 判定档位）；**真机验收** `verify-07-browser.txt` 10/10，
      用例断言两类各计一件、通用件带 `beep_init()` 与「未专精」原话）

## 边界与决策引用

- 不猜读函数是硬约定：猜出来打印的垃圾值比不测更坏（spec「检测程序怎么来」）。
- 总线类型判据来自模块声明，零新增知识。

## Comments

### 开工前的量（先量后写：四支探针，`.scratch/module-hwcheck/probe-07-*.txt`）

| 量的是什么 | 结论（2026-09-20 实测） |
|---|---|
| `probe-07-generic-inventory` | 未专精的「模块 × 平台」格 **168**；其中声明了 I2C 引脚角色的 **16**（全是 stm32） |
| `probe-07-init-callable` | 初始化三级判据的最终分布：**131 精确 + 9 唯一兜底 = 140 格可无参调**，**28 格认不出** |
| `probe-07-missing-init` | 那 28 格为什么认不出：初始化要参数（servo / pca9685 / motor / max7219 / lcd…）或本平台 `files: []`（adc stm32 / k230）；`<slug>_init` 在母版头里也**带参数**（`adc_init(ADCx_enum, ADCINx_enum)` / `uart_init(UARTn_enum,int,uint8_t)`），所以**母版面并进来也没用**——判据就停在"模块自己的头 + 无参声明" |
| `probe-07-i2c-surface` | 16 格的引脚宏形如 `<SLUG>_SCL_GPIO/_PIN`（默认脚 PA6/PA7 一条总线；ml_mpu6050 走母版 `I2C_GPIO`/PA11/PA12）；模块自己的位操作原语是 **static**（`.c` 里），渲染器手里只有宏 |

（另有一支 `probe-07-init-and-i2c` 是中途版：候选面并了母版头，得出 151/13/4 的分布。
它被 `probe-07-init-callable` 取代（母版并进来只会引入同名噪声、且上面那条实测说明
它救不回任何一格），**已删除**——留着两份互相矛盾的证据比没有更坏。本单评审抓到
这一点，记账在此。）

### 三块判据落在哪里

| 判据 | 落点 | 为什么在这 |
|---|---|---|
| 该调哪个初始化 / 认不认得出来 | `hwcheck_generic.plan_init`（纯函数，吃已剥注释的头文本） | 判据三级 + 必须"声明为无参"才敢调；认不出就把**中文理由**当数据带出去 |
| 该不该扫、拿什么扫 | `hwcheck_generic.scan_for_pins`（纯函数） | 零新增知识：manifest 的 `pins[].type` 与 `macros`；扫不了时 `scan_note` 说清为什么 |
| 一节长什么样 | `hwcheck_generic.render_generic_section` / `_runtime` | 渲染是确定性文本，可逐字断言；共用运行时**按需渲染**（0 warning 验收线） |

### 三个设计决策（都写进了代码注释）

1. **扫描是渲染器自己实现的 I2C 主机**（位时序 + 第 9 拍 ACK），不是"读一下"。
   这是本单最大的一处新增面，也是唯一可行的形态：模块自己的
   `xxx_iic_start/stop/send_byte/wait_ack` 全是 **static**（实测：`sht20_stm32.h`
   只暴露 `sht20_init` / `sht20_read`），母版 `ml_i2c` 走的是**另一条总线**
   （PA11/PA12），拿它扫 PA6/PA7 上的器件只会得到一句假的"无应答"。所以：
   引脚由 **manifest 声明的宏**参数化（值在 `pin_config.h`，ADR 0010），
   渲染器不写死任何 `GPIO_A/Pin_6`；扫描**只 ping 地址、一个寄存器都不读**。
   代价如实记：位时序（无延时，与库内 `ml_i2c` 同口径）与 `0x08–0x77` 区间是
   渲染器里的常量，单源在 `SCAN_ADDRESS_FIRST/LAST`。
2. **"有 I2C 角色"不够，还差"能不能驱动"**：mspm0 侧声明了 `i2c_scl/i2c_sda`
   的格子（ml_mpu6050 / oled / aht10…）**没有 pin_config 宏**（引脚由 SysConfig
   实例给），驱动不了 → 不扫。票面只写了角色那半，这条收窄**必须有说法**：
   `scan_note` 同时进检测页与产物（"本平台的引脚由 SysConfig 实例给出……不猜
   实例名，也就不扫"），不让它变成静默少测一项。
3. **进工程仍照旧**（通用件照旧进模块集、进接线表、进 README），只是板上那一节
   只做初始化 + 扫描——与 03 的分工不变。

### 真机判例：`headfile.h` 不带 `pin_config.h`（本单最值得记的一条）

宿主机行为探针（`probe-07-scan-behaviour.py`）**第一次跑就报** `SHT20_SCL_GPIO
undeclared`：扫描要用工程根的引脚宏，而母版的 `headfile.h` 只拉 `ml_*.h`——
模块自己的 `.c` 各自 `#include "pin_config.h"`，`main.c` 没有。于是：

* `_PLATFORM_HEADERS` 加一格 `pin_config`（stm32 = `pin_config.h`，mspm0 = `None`），
  **只在真有扫描件时**印这一行（没有扫描的形态不该平白多一个依赖）；
* 结构守卫 `test_a_bus_scan_brings_in_pin_config_and_resolves_it` 钉住"引了且该平台
  解析得到"；真机口径 UV4 **0 error / 0 warning**（编译矩阵第 3 形态）。

### 测试缝

- 域层纯函数（`plan_init` / `scan_for_pins` / `plan_generic_section` /
  `render_generic_section` / `render_generic_runtime` / `resolve_generic_sections`：
  内存直测 + 真库真件）——`tests/test_hwcheck_generic.py` 28 条。
- 渲染与端点（通用小节接进框架、按需渲染、命令表不含通用件、载荷富化、
  真生成写盘、回读）——`tests/test_hwcheck.py` 新增 12 条（含两条新的全产物级守卫：
  **悬空调用**与**128 字节行缓冲**）。
- 前端 `tests/js/hwcheck.test.mjs` 90 条（含未专精渲染与旧载荷不编造）。
- 真机 `tests/browser/hwcheck.spec.mjs` 10/10（未专精那一段加了 `.hwcheck-generic`
  与三类文案断言）。

## 实施结果与证据（都在 `.scratch/module-hwcheck/`）

| 证据文件 | 内容 | 结论 |
|---|---|---|
| `probe-07-generic-inventory.py` / `.txt` | 量具：未专精格与 I2C 类分布 | 168 格 / 16 格声明 I2C 角色 |
| `probe-07-init-callable.py` / `.txt` | 量具：初始化三级判据的分布（候选面 = 模块自己的头） | **140 可无参调 / 28 认不出** |
| `probe-07-missing-init.py` / `.txt` | 量具：28 格为什么认不出（含"母版面救不回来"的实测） | 要参数 / 无模块头；母版那几个 `*_init` 也带参数 |
| `probe-07-i2c-surface.py` / `.txt` | 量具：I2C 那批的引脚宏与公开函数面 | 宏齐（`<SLUG>_SCL_GPIO/_PIN`）；驱动原语全 static |
| `probe-07-scan-behaviour.py` / `.txt` | **行为证据**：渲染出的**整份 main.c** 用 gcc 真编真跑（探针仿 I2C 从机） | **2/2**：`0x3C` 有器件 → 「应答：0x3C」；无器件 → 「无应答」+ 排查；`sht20_init()` 真被调；`sht20_read` 桩成 `abort()` **没被碰**；汇总「未判定：1 项」 |
| `probe-07-compile-matrix.py` / `.txt` + `probe-07-buildlogs/` | **真编译**（stm32 UV4 / mspm0 gmake + SysConfig）：框架 → beep（只有初始化）→ sht20（初始化 + 扫描 + pin_config.h）→ servo（认不出初始化）→ led + sht20（两套运行时同堂）→ mspm0 的 ws2812 / aht10 | **7/7 全绿（0 error / 0 warning）** |
| `negative-verify-07.py` / `.txt` | 判据强度探针：**21 条注入**（初始化判据放宽 / 编一个初始化出来 / 多候选取第一个 / 扫描不要宏 / 扫描不要角色 / 措辞改第二句 / 塞读调用 / 带 `[专精]` 标记 / 命令台分派通用件 / 无通道也渲染 / 无扫描也渲 ping / 不 include pin_config / 不过滤专精件 / 不去重 / 载荷不带标注 / 漏 probe_none / 前端丢 label / 标注不分档 / 扫不了不说理由 / 超长文案 / 帮助行一条龙） | **21/21 注入后对应用例变红**，文件逐字节复原（每条都先跑基线，基线红的不计结论） |
| `verify-07-suite.txt` | 全量 `python -m pytest -n auto` | **4903 passed / 1 skipped** |
| `verify-07-js-suite.txt` | 完整前端门禁 `node --test "tests/js/*.test.mjs"` | **1660 passed / 0 failed** |
| `verify-07-browser.txt` | `node --test tests/browser/hwcheck.spec.mjs`（真 chromium + 真后端 + 真 UV4） | **10/10** |

**未上板（如实记账，spec「没跑过就写未上板，不假装」）**：本机没有软 I2C 传感器 /
地猛星 / 最小系统板，**扫描在真总线上认不认得出器件没验过**。证据是"两平台编译
绿（7 形态）+ 整份程序在宿主机上真跑（含从机仿真）+ 契约与守卫全覆盖"。
**上板后请按检测页清单做一次**：接一件软 I2C 器件到默认脚，看串口那行是不是
「应答：0xNN」（地址与器件手册对得上）；不接器件时应当是「无应答」+ 三个排查方向。
对不上就按「不对先查哪里」走。

## 双轴评审与整改（Standards + Spec，基线 `4f30806c` 未提交工作区）

两轴并行子代理评审，**结论已逐条处置**：

**Standards 轴：3 条硬违规 + 6 组判断题**

| # | 意见 | 处置 |
|---|---|---|
| S1 | **硬违规**：`hwcheck_recipe.py` 的产物注释仍写「未专精件本版不出小节」——本单让它出小节，这句成假话 | **已修**：改成「未专精件走通用降级，出的是另一套小节（工单 07，不带 [专精] 标记）」 |
| S2 | **硬违规**：`hwcheck_generic.py` 模块头写判据来自 `discover_init`，**该符号不存在**（真名 `plan_init`）；六个用例名也叫 `test_discover_init_*` | **已修**：文档改 `plan_init`，用例改名 `test_plan_init_*`（判据强度探针里三处引用同步） |
| S3 | **硬违规**：`index.html` 注释把「未专精点名」指为 `.hwcheck-warn`（07 已换成 `.hwcheck-generic`） | **已修** |
| S4 | Duplicated Code：`_generic_includes` 是 `_section_includes` 的逐字复制 | **已修**：合成 `_ordered_includes(groups, skip)`，两批各给一组 |
| S5 | Speculative Generality：`BusScan.first_address/last_address` 全库无人读（扫描区间有第二份死判据源） | **已修**：删字段，区间单源 = `SCAN_ADDRESS_FIRST/LAST`（渲染器直接取） |
| S6 | Data Clumps：`GenericSection.init` + `init_reason` 正是 `InitPlan` 的两半 | **已修**：直接持 `InitPlan`（`.init.name` / `.init.reason`）；顺带发现并修掉一处**静默失效**——地板断言写成 `if section.init:`（对象恒真）会永远为真 |
| S7 | 单源/措辞双写：前端 `|| "未专精"` 兜底 + 自写「只验总线和初始化、不读数据」，却自称"不另写一句" | **已修**：前端只渲染服务端给的 `label` / `plan` / `message`；缺 `label` 就不画徽章（不编兜底句），块首说明也不再复述标注 |
| S8 | 领域词汇缺口：「通用降级 / 未专精」未进 `CONTEXT.md` | **记账转 09**（该单的验收框就是"领域词表新增「硬件检测」词条"）；本单在下面的备忘里把要写进去的词交给它 |
| S9 | 轻微：`hwcheck.py` 被改写的那行仍留「零器件最小**自检**」 | **已修**（只改本单 touch 的这行；05 记账的其余「自检」用词债仍在，仍归后续小单） |

**Spec 轴：4 条缺失/部分 + 2 条超范围 + 4 条实现与证据对不上**

| # | 意见 | 处置 |
|---|---|---|
| ① | **判据被静默收窄**：票面只写"声明了 I2C 角色"，实现还要求"两个引脚宏齐全"，mspm0 那几格因此不扫而页面不说 | **已修**：新增 `GenericSection.scan_note`（"本平台的引脚由 SysConfig 实例给出……不猜实例名，也就不扫"），进检测页 `plan` 与产物细节行；用例 `test_plan_generic_section_says_why_it_did_not_scan_an_i2c_device` + 注入 S 双向钉住 |
| ② | **票面第 5 条的原话 grep 不到**，更重的是 28 格**一次 init 都不调**却照印「只验总线和初始化」 | **已修**（本单最值钱的一条整改）：① 那句原话进 `plan_text` 与产物注释（串口行也印「本件未专精，不判返回值」）；② 标注按**这一趟真做了什么**三选一（`GENERIC_LABEL` / `_SCAN_ONLY` / `_IDLE`），什么都没做的格子打 `_IDLE` |
| ③ | 单源只对 `label` 成立（前端硬写同一句） | 同 S7（已修） |
| ④ | 七个验收框仍全空、状态只到 claimed | **已办**：本节 + 验收全勾 + `Status: resolved` |
| ⑤ | 超范围：渲染器里新长出一个 I2C 主机（位时序是渲染器新知识） | **保留并说明**（见「三个设计决策」1）：模块原语全 static、母版总线不是这一条——这是唯一可行形态；引脚与是否扫描仍是 manifest 的事实，位时序与地址区间单源常量，且**有行为证据**（真跑认得出 0x3C、认不出没器件） |
| ⑥ | 超范围：`_PLATFORM_HEADERS` 新增 `pin_config` 键 | **保留并说明**：编译证据支持（不加就 `undeclared`），且只在有扫描件时印；已有结构守卫钉住"引了且解析得到" |
| ⑦ | 文档指向不存在的名字 | 同 S2（已修） |
| ⑧ | **两份探针互相矛盾**（151/13/4 vs 131/28/9），工单未说哪份算判据；docstring 的"多候选"举例与实测不符 | **已修**：删掉中途版探针（理由记在「开工前的量」）；docstring 改成实测口径——真实库**没有**"多候选且无精确命中"那一格（`pid`/`motor` 都有精确命中），判据留着是为库演进 |
| ⑨ | 证据文件编码不齐（两份 GBK / 一处替换字符 `�`） | **已修**：四支探针改成自己写 UTF-8（不再靠 PowerShell `*>` 重定向）；`�` 的根因另有价值——见下一条 |
| ⑩ | 扫描标签取 `pin.default`，改绑引脚后会与页面接线表打架 | **保留并记账**：总线**驱动走宏**（值在 pin_config.h），所以改绑后扫的仍是那条总线的真脚，只有**印出来的脚名**是声明默认脚；检测页目前不支持改绑（03 的账），支持了标签要跟着绑定走——模块头已写明这条 |

**⑨ 的根因顺带挖出一个 06 的既有缺陷（已修）**：`probe-07-scan-behaviour.txt` 里那句
「无应答…（有没有接反）」末尾是 `�`——不是编码问题，是**撞上了框架的行缓冲**：
`hwcheck_line[128]` 会把超长行截断，中文一字 3 字节，截在字中间就是半个乱码。
我为此加了一条**全产物级**结构守卫（`test_every_reported_line_fits_the_line_buffer`：
每个 `hwcheck_report("…")` 的字节数必须 < 128），它当场又抓到**06 留下的另一行**：
帮助里一条龙列五条既有命令的那行 **136 字节**（06 的两个探针都没发现——它们的
`hwcheck_report` 是 printf 桩，不模拟缓冲）。两处都修了：无应答文案缩短、既有命令
**每行两条**排（措辞一字不改，那几句是镜像库内 `debug_uart.c` 的说明）。

**未修但记账**：`plan_text` 里的函数签名可能很长（如 `servo_init(uint8_t servo_id,
uint8_t channel)`）——**页面上**不截断（那里没有缓冲限制），产物里改走
`hwcheck_detail` 细节行且理由本身已压短；将来若出现超长签名，行缓冲守卫会当场红。

## 给后续工单的接口备忘

- **09（pilot 补齐 + 收尾留档）**：
  - 新配方的写法与命令字符规则照 04/05/06 的备忘不变；**通用降级与专精是互斥的**
    ——某格一旦有配方，它就从通用路径消失（`resolve_generic_sections` 按
    `specialized` 过滤），不需要在别处删任何东西；
  - 覆盖清单**地板守卫**若要连"通用面的基线"一起钉：本单已在
    `tests/test_hwcheck_generic.py` 钉了三条地板（未专精格 ≥ 168、可无参初始化
    ≥ 140、stm32 I2C 可扫格 ≥ 18），09 加 pilot 地板时别与它们重复；
  - **领域词条**（09 的验收框）要写进去的新词：**通用降级**（没有配方时的确定性
    兜底路径 = 初始化 + I2C 类件的总线地址扫描，**不猜读函数**）、**未专精标注**
    （`GENERIC_LABEL` 三档，按这一趟真做了什么选）；判据单源指向
    `hwcheck_generic.plan_init` / `scan_for_pins` / `GenericSection.label`。
    ADR 也归 09（"检测程序 = 确定性渲染 + 库内配方数据"），本单可补的一条实测：
    **扫描器是渲染器自带的最小 I2C 主机**（模块原语全 static，见上）。
- **任何以后改 `hwcheck_line` 行缓冲的人**：`test_every_reported_line_fits_the_line_buffer`
  按 128 字节判；改大/改小请同步那条常量与它的说明（两处都写死了 128）。
- **任何以后改库内 `debug_uart.c` 那五条既有命令的人**：`LEGACY_COMMANDS` 是镜像，
  parity 守卫逐字符核对（06 的备忘）；本单只动了帮助的**排版**（每行两条），
  命令字符与措辞没动。
- **改绑引脚（引脚配置）以后**：通用降级的扫描**已经在走宏**（值在 pin_config.h），
  唯一要跟上的是 `scan_label` 印出来的脚名（现在印 manifest 声明默认脚，见 Spec ⑩）。
