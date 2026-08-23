# 01 — 澄清阶段按需视觉问答编排（核心闭环，mock 视觉）

**要做什么：** 用户在推荐流程中被 AI 反问图上信息时，系统不再直接打扰——澄清阶段产出的待问问题先逐条机械判定「是否图内信息问题」，命中的经注入的视觉问答回调消化，答案并入澄清历史随收敛喂给模型；答不上的维持现状问用户。不注入回调（未配置视觉 / 无图 / 调用方不接入）时，行为与现状逐字节一致。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] `selection.py` 新增纯函数 `vision_answerable(question: str, problem_text: str) -> bool`：问题提到题面引用过的图号（问题含「图N」且题面含「图N」或题面含 `[图N 标注`）**且**问题含尺寸/位置类关键词（尺寸、宽度、长度、走廊、门口、位置、走向、标注、距离、坐标、多大、多少、面积、高度）→ True；关键词表为模块常量（单源，结构测试防回退）
- [x] `run_recommendation` 新增参数 `vision_qa: Callable[[str], str | None] | None = None`；澄清门内 `llm.clarify` 返回 pending 后、`emit.question` 前：逐条判定 → 命中且回调存在 → 调用取答案；答案非 None → 从 pending 移除、以 `(question, answer)` 并入 clarifications；答案 None → 保留待问
- [x] 收敛循环补问（`selection.questions`）走同一回调与同一喂回逻辑
- [x] 被视觉消化后 pending 为空 → 不发出 question 事件，带 clarifications 直接进收敛（复用「有澄清历史跳过澄清门」既有路径）
- [x] `tests/test_selection_vision_qa.py`：假回调注入覆盖四路径（全答掉 / 部分答掉 / 全答不上 / 未注入）——question 事件内容、clarifications 内容、收敛输入正确；未注入时与改动前行为一致（现有推荐测试全绿）
- [x] 判定函数单测：命中/漏判边界（图号引用、关键词、大小写、题面无图时含关键词不命中）

## Comments

实施记录（2026-08）：

- 实现：`vision_answerable`（图号按「图N」正则提取编号求交，非子串匹配——防「图1」误命中「图10」；`VISION_ANSWERABLE_KEYWORDS` 常量单源）；`_answer_vision_questions`（逐条消化，答案 `(问题, 答案)` 并入澄清历史，空/空白答案视为答不上）；`run_recommendation` 澄清门与收敛补问均接线，收敛补问全消化后带答案重跑一轮收敛（最多一次，重跑后仍有疑问直接问用户，防问问题链死循环）；收敛装配提取局部函数 `_converge` 消除十参数重复调用。
- 测试：`tests/test_selection_vision_qa.py` 16 个用例——判定命中/漏判边界（含「图10」不误命中「图1」、题面无图号、空输入）+ 编排四路径（全答掉→无 question 事件直接收敛、部分答掉→question 只含剩余、答不上/空答案→原样问用户、未注入→行为不变）+ 收敛补问消化后重跑（含重跑后仍有疑问直接问用户）。
- Review：双轴自审（standards + spec）。Standards：中文注释/命名/常量单源合规；修复 Duplicated Code（收敛调用提取 `_converge`）。Spec：验收条目全满足；修复判定子串误匹配边界。
- 回归：全量 2221 passed（含既有 158 推荐/选择测试零回归）。
