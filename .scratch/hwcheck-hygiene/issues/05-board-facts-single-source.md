# 05 — 板级事实单源：LED 引脚与排障引脚白名单都以选型数据为源

**要做什么：** 页面上凡说"这块板子的 LED 在哪几个引脚"，都从**选型数据**取；
排障侧的引脚白名单也以**同一数据**为源——不再"文案里写过 PC13，所以 PC13 是白名单"这种
文案与判据互为因果的写法。

**被谁阻塞：** 无——可立即开始。（与 04 都动 `hwcheck_board` / `hwcheck_triage` 一带，
按编号顺序落地即可。）

**状态：** ready-for-agent

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

- [ ] `hwcheck.py` 那句不再写死引脚：从选型数据取（平台 → LED 通道映射 / 首引脚），
      渲染出来的话术与今天**逐字可不同但语义不变**（红灯通道用于 stm32 / 用户 LED 用于 mspm0 的
      区分必须保留——那是学生照着找灯的依据）。
- [ ] `hwcheck_triage.py` 的引脚白名单改以**同一数据**为源（平台默认引脚 + 计划/绑定的真实引脚），
      **不再**以"清单文案里出现过"为源；`:362-366` 那段自述与实现同步改写。
- [ ] 用例：改选型数据里的一个值（monkeypatch 或临时改数据）→ 渲染出的清单文案跟着变
      （这是"单源"的判据，不是"文案里含 PC13"）；白名单用例：给一个**只在文案里出现过**、
      但不在数据里的脚 → 不再被当作上下文事实。
- [ ] **反证**：把硬编码那句放回去 → 相应用例红；复原后逐字节相同
      （`.scratch/hwcheck-hygiene/probe-05-red.py` / `probe-05-red.txt`）。
- [ ] 读数：全套 pytest + `-k "hwcheck or triage or checklist or selection"` 落盘。
- [ ] 若要动 `hwcheck.py` 的渲染产物，**两平台真编译矩阵**复跑一次（生成链与清单同源，别只跑单测）：
      读数按 `hwcheck-hardening` 的先例写进本目录（`probe-05-compile-matrix.txt`）。
