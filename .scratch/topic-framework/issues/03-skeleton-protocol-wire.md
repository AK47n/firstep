# 03 — 骨架协议贯通（llm 参数 + prompt 注入）

**要做什么：** LLM 协议 `generate_main_skeleton` 加 `topic_framework: str | None = None` 参数（DeepSeek 实现 + RoutingLLM 转发 + fakes 同步，照 plan_tasks / execute_task 先例）；`_skeleton_user_prompt` 加 `topic_framework`——非空时在 reference_fulltexts 段**之前**插「题型框架（必须保留的结构）」段（`### 题型框架：<topic_type>（来源 <entry.id>）` + 原样代码 + 强指令：main.c 必须保留框架结构（枚举 / 调度循环 / 状态机函数名不动），只在 `// TODO:` 处填实现，框架内的调用若接口块不存在写成注释占位）；「学习说明走 LLM 段」——模型消化框架后按接口块填 TODO。None / 空 = 就行为逐字节不变。`skeleton._generate_main_c` / `generate_skeleton` / `run_skeleton` 加参透传（冒烟不传 = 不受影响）。

**被谁阻塞：** 02（build_topic_framework 就绪后由装配层调用，本票只做协议 + prompt）。

**状态：** resolved

**验收：** 全部 ✓（协议签名加参 + DeepSeek/RoutingLLM/fakes 同步；`_skeleton_user_prompt` 框架段在参考段之前 + 强指令；`_generate_main_c` / `generate_skeleton` / `run_skeleton` 透传；测试 test_llm.py 新增 2 条 + 既有 302 全绿）。

- [ ] LLM 抽象 `generate_main_skeleton(..., topic_framework=None)`；DeepSeek 实现 + RoutingLLM 转发（remote 方法加参）+ FakeLLM / RecordingLLM（测试 fakes）同步
- [ ] `_skeleton_user_prompt(problem_text, module_interfaces, reference_fulltexts=None, topic_framework=None)`：framework 段在 reference 段之前；文案含 `### 题型框架：<topic_type>（来源 <entry.id>）`、强指令（保留结构 / 只填 TODO / 不存在的调用注释占位）
- [ ] `_generate_main_c` / `generate_skeleton` / `run_skeleton` 加 `topic_framework` 透传（smoke 路径不受影响；reference_fulltexts 两参 / 三参调用分支保持零回归）
- [ ] 测试：prompt 含 framework 段（顺序断言：framework 在 reference 之前）；None → 逐字节不变（既有断言先例）；fakes 捕获 topic_framework；RoutingLLM remote 转发参数断言
