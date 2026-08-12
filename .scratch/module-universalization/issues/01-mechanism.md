# 01 — 判据四要素 + 结构测试机械拦截（机制先行）

**What to build:** 模块形态新规（ADR 0009 + CONTEXT.md 词表已由 grilling 会话落盘，本工单只做代码机制）：① 简介判据三要素改四要素——③ 能力方向（补录必填：声明可用在哪类赛题功能，允许多值点明主能力）、④ 无题绑定（禁题号/年份/具体题名/专用逻辑），落到补录流程的 AI 校验（llm.py 简介校验 + library.py 补录流程）；② 新增结构测试 `tests/test_module_universality.py`：扫描 `library/modules/*/` 全部 .c/.h + manifest.json，机械拦截题号/年份/题名引用。黑名单词表单源（禁题号 2021F/2024H/2026C/2026H + 题名词如"钥匙""锁"），能力词白名单防误伤（"巡线""循迹""PID""灰度"等——巡线是能力词，不能禁）。存量 5 个题专用模块（xunji / pid / ball_detect / lock_control / zone）改造前此测试红（红证），由 02~05 工单逐模块转绿。

**Status:** resolved（2026-08-12 实施闭环，1095 绿 + mypy 干净，见下方实施记录）

## 现状（实施会话核实）

- 简介 AI 校验在 llm.py（validate_module_description 走 _retry_parse，判据①与代码一致、②硬件身份），补录流程在 library.py（add_module）。
- 结构测试先例：tests/test_module_collision.py（跨模块重复路径不变量）、生成门禁分类注册表测试（结构测试防回退文化）。
- CONTEXT.md 简介词条已列判据四要素 + 能力方向词条；ADR 0009 已落盘。

## 实施

1. **llm.py**：简介校验判据加 ③ 能力方向（描述须声明可用功能类别，缺则 AI 判定不通过并提示补写）与 ④ 无题绑定（出现题号/年份/具体题名/专用声明 → 判定不通过并提示改写）。prompt 与解析按现有判据模式扩展，不引新机制。
2. **library.py**（或校验所在处）：补录流程把 ③④ 纳入必填校验链，失败文案中文、含改写指引。
3. **tests/test_module_universality.py**：黑名单词表 + 白名单（能力词）模块内单源；扫描全部模块 .c/.h/manifest 文本，命中黑名单且非白名单即红，报出模块与词。红证：当前库状态（5 个题专用模块命中）→ 测试红；白名单词（"巡线""灰度"等）不误伤（如 huidu / motor 描述含能力词 → 不红）。
4. **CONTEXT.md**：结构测试词表单源位置已在简介词条登记（tests/test_module_universality.py），如有出入同步修正。

## 文件边界

- src/contest_generator/llm.py —— 简介校验判据 ③④
- src/contest_generator/library.py —— 补录流程必填校验 ③④
- tests/test_module_universality.py —— 机械拦截 + 黑/白名单词表单源 + 红证
- **不动**：library/modules/* 内容（02~05 工单）、manifest.py 模型（判据用描述句表达，不引结构化 capability 字段——grilling 定案 Q6）

## 验收

- [x] pytest 全绿：新测试红证成立（存量 5 模块命中黑名单 → 红、词表白名单不误伤能力词）；其余测试无回归。
- [x] mypy src 干净。
- [x] 补录流程四要素生效（AI 校验 ③④ + 机械拦截，缺能力方向/带题绑定 → 中文提示改写）。
- [x] 结构测试词表单源：改词表只改一处，测试注释注明维护位置。
- [x] 工单补实施记录 + 验收勾选，Status resolved。

## 实施记录（2026-08-12）

**红证（注册表置空全库扫描，find_topic_word_hits 命中 11 个模块）**：

```
  ball_detect: 2026H            config: 2026C 钥匙 锁     debug_uart: 2026C 锁
  filter: 2026C                 lock_control: 2026C 钥匙 锁  pid: 2021F 2026H 锁
  uwb_uart: 钥匙                xunji: 2024H             zigbee_uart: 2026C 钥匙 锁
  zigbee_uart_key: 2026C 钥匙 锁  zone: 2026C 钥匙 锁
```

其中 02~05 工单的五模块（xunji / pid / ball_detect / lock_control / zone）全部命中，红证成立。

**实施中发现（超出工单字面的数据事实，设计为此调整）**：

1. **题词污染面大于 5 模块**：2026C 数字钥匙词（2026C/钥匙/锁）还落在 config（"2026C 数字钥匙题专用：集中配置头"）、debug_uart（"2026C 门锁端调试串口"）、zigbee_uart / zigbee_uart_key（"2026C 门锁端/钥匙端 Zigbee"）、filter（"出身 2026C 题"）的简介与 uwb_uart 代码注释（"旧钥匙数据"）——共 11 个模块。工单 05 文件边界明确"不动 config / zigbee_uart / uwb_uart"，02~05 清理后这些模块仍带题词 → 纯黑名单扫描永远无法转绿。
2. **设计定案**：沿用 errors.py 白名单先例，在结构测试内设**模块级例外注册表** `EXCEPTION_REGISTRY`（slug → 理由，唯一出处）：11 个模块全部登记（5 个 = 02~05 清理范围，6 个 = 无工单覆盖遗留），测试提交态全绿；**02~05 清理各自模块后必须删除注册表条目**——清理后不删条目 = 存量校验红（`test_exception_registry_entries_are_real_contamination`），防漏同步；新增模块带题词不登记 = 红（`test_no_topic_bindings_outside_exception_registry`）。
3. **扫描范围定案**：简介（manifest.description）+ 全部 .c/.h；manifest 的 notes 不扫——notes 是补录/验证历史（delay/led_beep/oled/motor 的"2026C/21F 真机编译过"），非简介，扫了 02~05 也无法转绿（工单只重写 description）。
4. **词表单源定案**：黑名单 + 能力词白名单入 **library.py**（`BANNED_TOPIC_WORDS` / `CAPABILITY_WORDS` / `find_topic_word_hits`）——补录流程（validate_description 机械预检）与结构测试共用，改词表只改一处；CONTEXT.md 简介词条按工单 item 4 同步修正（原登记 tests/test_module_universality.py，出入已同步）。
5. **能力词白名单机制**：黑名单命中区间落在能力词出现区间内 = 不计（"锁"加黑名单时"锁定"不误伤）；反方向能力词不遮蔽题名引用（黑名单"巡线题"含"巡线"但不在其区间内 → 仍红）。合成词表测试两条覆盖。

**改动清单**：

- `src/contest_generator/library.py`：判据④机械词表单源（BANNED_TOPIC_WORDS / CAPABILITY_WORDS / find_topic_word_hits）+ `validate_description` 机械预检（add_module / update_module_description 共用；命中 → LibraryError 中文改写指引，不调 AI）。
- `src/contest_generator/llm.py`：`VALIDATION_SPECIFICITY_RULE` → `VALIDATION_UNIVERSALITY_RULE`（③ 能力方向必填 / ④ 无题绑定含代码侧剥离指引，ADR 0009；旧"专用性声明一致性"检查被④取代），系统/用户提示词双端同源。
- `tests/test_module_universality.py`（新）：全库扫描 + 例外注册表 + 存量校验 + 白名单合成用例，词表单源 import library.py。
- `tests/test_library.py`：旧专用性两测试改写（机械④拦截不调 AI / AI ④代码侧剥离）；补 update_module_description 机械拦截 + 能力词通过机械检查两测试。
- `tests/test_llm.py`：specificity 两契约测试改 universality（双端断言）。
- `tests/test_topic_library.py`：discover_related_modules 两测试改直写 manifest 构造素材（补录已拒题绑定，机制本身照测）。
- `tests/test_autocommit.py`：写函数分类注册表补 `find_topic_word_hits: ("read", "")`。
- `CONTEXT.md`：简介词条词表单源位置同步（library.py）；赛题库词条注明发现机制对直写 manifest 条目生效；架构要点补词表单源位置。

**验证**：全量 pytest 1095 绿（+8 新测试；红证在实施时以空注册表演示，提交态全绿）；mypy src 32 文件干净。

**遗留提示**：discover_related_modules 的简介词发现机制（topic_library）已与判据④ 冲突——补录/编辑拒题绑定后该机制只对直写 manifest 的存量条目生效，是否移除/换机制建议另立工单；6 个无工单覆盖模块（config/debug_uart/zigbee_uart/zigbee_uart_key/filter/uwb_uart）的题词清理同样建议另立工单（本工单机制 + 注册表已机械兜底不扩散）。
