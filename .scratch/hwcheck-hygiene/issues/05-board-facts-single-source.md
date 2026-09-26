# 05 — 板级事实单源：LED 引脚与排障引脚白名单都以选型数据为源

**要做什么：** 页面上凡说"这块板子的 LED 在哪几个引脚"，都从**选型数据**取；
排障侧的引脚白名单也以**同一数据**为源——不再"文案里写过 PC13，所以 PC13 是白名单"这种
文案与判据互为因果的写法。

**被谁阻塞：** 无——可立即开始。（与 04 都动 `hwcheck_board` / `hwcheck_triage` 一带，
按编号顺序落地即可。）

**状态：** resolved

**来源**：评审 P2-11 的 Y9。**实测更正（两处）**：① 硬编码在 `hwcheck.py:497-498`（评审说 486-487，
那是烧录条）；② 评审说真源是 `library/boards/*.json`——**该目录不存在**，板库在
`src/contest_generator/boards/`（2 个 JSON），而且 **JSON 里没有 LED 的结构化事实**
（只有自由文本 `notes` 与 `fixed[].occupies`，`PC14`/`PC15` 与"地猛星用户 LED = PA15"在 JSON 里**没有**）。

**已拍板的口径（spec 实现决策）**：单源落在**选型数据的平台默认**，**不动板库 JSON**。

## 现状（实测）

- 硬编码：`src/contest_generator/hwcheck.py:497-498`
  ——「stm32 板载三色 LED 在 PC13/PC14/PC15（本程序用红灯通道 LED_RED），地猛星用户 LED 是 PA15」。
- 真源：`src/contest_generator/selection.py:2342-2345`
  ——`builtin_pins = {PLATFORM_STM32: {"red": "PC13", "yellow": "PC14", "green": "PC15"}}`、
  `first_pin = {PLATFORM_MSPM0: "PA15"}`。
- 文案当判据来源：`src/contest_generator/hwcheck_triage.py:362-366`——「材料里出现过的脚就是上下文事实，
  允许引用」，其中"材料"= `hwcheck.render_checklist` 渲染出来的那段文字。

## 验收标准

- [x] `hwcheck.py` 那句不再写死引脚：从选型数据取（平台 → LED 通道映射 / 首引脚），
      渲染出来的话术与今天**逐字可不同但语义不变**（红灯通道用于 stm32 / 用户 LED 用于 mspm0 的
      区分必须保留——那是学生照着找灯的依据）。
- [x] `hwcheck_triage.py` 的引脚白名单改以**同一数据**为源（平台默认引脚 + 计划/绑定的真实引脚），
      **不再**以"清单文案里出现过"为源；`:362-366` 那段自述与实现同步改写。
- [x] 用例：改选型数据里的一个值（monkeypatch 或临时改数据）→ 渲染出的清单文案跟着变
      （这是"单源"的判据，不是"文案里含 PC13"）；白名单用例：给一个**只在文案里出现过**、
      但不在数据里的脚 → 不再被当作上下文事实。
- [x] **反证**：把硬编码那句放回去 → 相应用例红；复原后逐字节相同
      （`.scratch/hwcheck-hygiene/probe-05-red.py` / `probe-05-red.txt`）。
- [x] 读数：全套 pytest + `-k "hwcheck or triage or checklist or selection"` 落盘。
- [x] 若要动 `hwcheck.py` 的渲染产物，**两平台真编译矩阵**复跑一次（生成链与清单同源，别只跑单测）：
      读数按 `hwcheck-hardening` 的先例写进本目录（`probe-05-compile-matrix.txt`）。

## 结论（读数与账）

**数据单源落在哪。** `selection.INSTANCE_POLICIES["led"]`（**本来就有**的那张策略表，多实例展开读的
同一张）新增两个小投影函数，供两处消费：

| 新投影 | 回答什么 | 消费方 |
|---|---|---|
| `selection.led_builtin_pins(platform)` | led 在本平台的**板载通道脚**（stm32 = PC13/PC14/PC15 配 LED_RED/YELLOW/GREEN） | ① 上板清单那句"灯在哪几个脚"；② 排障引脚白名单 |
| `selection.led_first_pin(platform)` | led 在本平台的**首实例脚**（mspm0 = PA15 的用户 LED） | 同上 |

**两处消费方各改了什么。**

* `hwcheck.py`：上板清单 heartbeat 那条的「不对先查」不再写死脚，改由新的
  `_heartbeat_led_hint(config.platform)` 从数据渲染——给三色通道的板子说
  「板载三色 LED 在 PC13/PC14/PC15（本程序用红灯通道 LED_RED）」，只给一个用户 LED 的板子说
  「板载用户 LED 是 PA15」（宏名沿用本文件既有的 `_LED_CHANNEL` 单源）。**语义不变**：
  "红灯通道 vs 用户 LED"这层区分仍在，那是学生照着找灯的依据。
* `hwcheck_triage.py`：`build_triage_facts` 的引脚来源**改成四处**——本次接线行、板上共享脚、
  选型数据的平台默认脚、**检测计划那几段**（`_plan_texts`：小节 plan / 通用件 plan+message /
  顺序说明 / 自建件 plan+notes）——外加**学生自己写的现象**（他说"我把线插到 PB7 了"，那是事实）。
  **移出**的是**上板清单那段手写散文**（旧 `_material_texts` 把清单的 `expect`/`check` 也扫进来：
  文案与判据互为因果，改一句话就悄悄改了判据 = 评审 P2-11 的原缺陷）。原来那条真缺陷
  （模型复述材料里的 PC14 被判非法）**仍然挡着**，依据换成了数据：PC14 在数据里，所以它是事实
  ——不管文案写没写。

**单源判据（不是"文案里含 PC13"）**：`test_heartbeat_checklist_pins_come_from_the_selection_data`
用 `monkeypatch.setitem` 改选型数据里的一格 → 文案跟着变（旧值消失）；白名单侧
`test_pin_that_only_appears_in_the_copy_is_not_a_fact` 把 `PX9` 写进清单文案 → 白名单**不涨**；
另一侧 `test_pin_from_the_detection_plan_is_still_a_fact` 钉住"计划里的脚照旧算事实"（评审
当场证伪过第一版把计划一起踢掉）。

**两处既有用例按新口径改写**（都是"口径变了、判据跟着走"，不是放松）：
`test_context_facts_whitelist_is_built_from_board_and_selection_data`（期望集多了 PC14/PC15，
它们现在是数据来的）、`test_pin_from_the_selection_data_is_a_fact_even_if_the_copy_omits_it`
（原 `test_pins_quoted_from_the_material_are_allowed`：保护的行为不变、依据换成数据），
外加 `test_context_without_devices_still_renders_the_lamp_only_path` 的
"一件器件不选 → 白名单为空"改成"只剩板子自己的 LED 脚"（板载 LED 是**板子的事实**，
与选没选器件无关）。

**读数（本机实跑，落盘在本目录）。**

| 闸门 | 命令 | 读数 | 读数文件 |
|---|---|---|---|
| 全套 pytest | `python -m pytest -n auto -q` | **5600 passed + 11 skipped**（≈124s；上一单 5596 + 11，+4 = 本单新用例） | `probe-05-pytest-full.txt` |
| 定向 pytest | `python -m pytest -n auto -q -k "hwcheck or triage or checklist or selection"` | **876 passed + 10 skipped** | `probe-05-pytest-hwcheck.txt` |
| 前端门禁 | `node --test "tests/js/*.test.mjs"` | **1818 passed / 0 fail**（本单没动前端，作回归读数） | `probe-05-js.txt` |
| 真编译矩阵 | `python .scratch/hwcheck-specialize/probe-compile-matrix.py --slugs "led,delay,debug_uart" --out …` | **6 格全 `[PASS]`**（编译器 0 error / 0 warning、链接器 0 告警、无拦下） | `probe-05-compile-matrix.txt` |
| 反证 | `python .scratch/hwcheck-hygiene/probe-05-red.py` | A/B 两处注入各自点名变红，两次复原 sha256 逐字节相同、回绿 | `probe-05-red.txt` |

**编译矩阵为什么不必跑全量**：本单改的 `render_checklist`
是**页面载荷**，`render_main_c` 不消费它（`hwcheck.py` 里 `render_checklist` 只有定义与 `__all__`
两处引用，没有任何调用方在产物渲染链上），所以 main.c 的字节不该变。为免"我说不变"就当证据，
仍按 `hwcheck-hardening` 的先例跑了一次真编译（`--slugs led,delay,debug_uart`，每平台 3 格）。

**双轴评审（Standards / Spec，2026-09-26）与处置。** 两条硬违规 + 三处判断题，**全部已整改**：

| 评审发现 | 处置 |
|---|---|
| 硬：**自述没跟着口径改**（`hwcheck_triage.py` 文件头 / 段标题 / `build_triage_context` docstring + `CONTEXT.md` 四处仍在讲"材料与白名单同一处装配"） | 四处都改了：文件头与 docstring 写明**"材料"的射程有边界**（计划类数据算、上板清单那段手写散文不算）；`CONTEXT.md` 同步 |
| 硬（Spec）：**第一版把"检测计划"里的脚一起踢出了白名单** —— 模型复述它自己看过的计划（`PA2`/`PA3`）被判非法，正是 `hwcheck-unknown-device/09` 修过的"材料说得的、判据说不得" | **恢复**：新增 `_plan_texts`（小节 plan / 通用件 plan+message / 顺序说明 / 自建件 plan+notes）作事实来源，**只**把上板清单的 `expect`/`check` 移出；补用例 `test_pin_from_the_detection_plan_is_still_a_fact`；反证 B 的注入也改成"把清单文案并回 `plan_texts`" |
| 硬：取不到板载 LED 数据时那句渲染成空位 → 「② ③」悬空序号 | 新增 `_heartbeat_check_text`：取不到就**整条不出现**、序号接着排；补用例钉住 |
| 判：`led_builtin_pins` 返回 `(宏, 脚)` 但两个消费方都丢掉宏（零消费者的半边 + `token.upper()` 可能吐假宏） | 改成只返回脚（`tuple[str, ...]`）；宏名统一走 `hwcheck._LED_CHANNEL`（检测程序真的初始化的那一路） |
| 判：两个投影各抄一遍 `INSTANCE_POLICIES.get("led")` 守卫 | 抽出内部件 `_led_policy()`，两个投影共用 |
| 判：`build_triage_facts` 挂在 `__all__` 却只有 `build_triage_context` 一个调用点（Middle Man） | **不改**：它是本单之前就有的形状（工单 09 立的），本单只加了 `platform` / `plan_texts` 两个入参；要收进内部件属另一件事，记在这里 |
| 判：工单里"两平台各一格"与实际 6 格不符 | 已按实测改写（上表） |
