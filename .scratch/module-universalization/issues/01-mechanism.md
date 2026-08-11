# 01 — 判据四要素 + 结构测试机械拦截（机制先行）

**What to build:** 模块形态新规（ADR 0009 + CONTEXT.md 词表已由 grilling 会话落盘，本工单只做代码机制）：① 简介判据三要素改四要素——③ 能力方向（补录必填：声明可用在哪类赛题功能，允许多值点明主能力）、④ 无题绑定（禁题号/年份/具体题名/专用逻辑），落到补录流程的 AI 校验（llm.py 简介校验 + library.py 补录流程）；② 新增结构测试 `tests/test_module_universality.py`：扫描 `library/modules/*/` 全部 .c/.h + manifest.json，机械拦截题号/年份/题名引用。黑名单词表单源（禁题号 2021F/2024H/2026C/2026H + 题名词如"钥匙""锁"），能力词白名单防误伤（"巡线""循迹""PID""灰度"等——巡线是能力词，不能禁）。存量 5 个题专用模块（xunji / pid / ball_detect / lock_control / zone）改造前此测试红（红证），由 02~05 工单逐模块转绿。

**Status:** drafted

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

- [ ] pytest 全绿：新测试红证成立（存量 5 模块命中黑名单 → 红、词表白名单不误伤能力词）；其余测试无回归。
- [ ] mypy src 干净。
- [ ] 补录流程四要素生效（AI 校验 ③④ + 机械拦截，缺能力方向/带题绑定 → 中文提示改写）。
- [ ] 结构测试词表单源：改词表只改一处，测试注释注明维护位置。
- [ ] 工单补实施记录 + 验收勾选，Status resolved。
