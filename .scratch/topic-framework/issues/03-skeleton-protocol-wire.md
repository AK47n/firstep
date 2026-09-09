# 03 — 骨架协议贯通（llm 参数 + prompt 注入）

**要做什么：** LLM 协议 `generate_main_skeleton` 加 `topic_framework: str | None = None` 参数（DeepSeek 实现 + RoutingLLM 转发 + fakes 同步，照 plan_tasks / execute_task 先例）；`_skeleton_user_prompt` 加 `topic_framework`——非空时在 reference_fulltexts 段**之前**插「题型框架（必须保留的结构）」段（`### 题型框架：<topic_type>（来源 <entry.id>）` + 原样代码 + 强指令：main.c 必须保留框架结构（枚举 / 调度循环 / 状态机函数名不动），只在 `// TODO:` 处填实现，框架内的调用若接口块不存在写成注释占位）；「学习说明走 LLM 段」——模型消化框架后按接口块填 TODO。None / 空 = 就行为逐字节不变。`skeleton._generate_main_c` / `generate_skeleton` / `run_skeleton` 加参透传（冒烟不传 = 不受影响）。

**被谁阻塞：** 02（build_topic_framework 就绪后由装配层调用，本票只做协议 + prompt）。

**状态：** resolved

**评审记录**（code-review 双轴，HEAD=5b6a08f）：Standards 判定性 6 条已修 4 条——① 平台过滤单源复刻（webapp 内联 `_platform_matches` 判据）→ `selection.platform_matches` 公开 + generator 装配统一收敛；② 域判决落进薄壳（webapp 选框架源）→ 移 `generator.build_topic_framework_info`（随 build_reference_fulltexts 同址）；③ Duplicated Code（平台匹配三处变体）→ 同 ①；④ 文档-实现不一致（manual_references 漏遍历——手动选参考带题型框架被跳过，真 bug）→ 并集 `references` ∪ `manual_references` + 集成测试；⑤ 控制文件语义不自洽（framework/main.c 进 files 清单会双份）→ `_validate_files` 拒绝入素材清单；⑥ prompt 强指令硬编码未单源 → `SKELETON_FRAMEWORK_RULE` 常量。Spec 5 条已修 2 条——① 框架段标题未带 topic_type/source（只收 str 丢元数据）→ `TopicFramework` 结构化（code/topic_type/source=标题）+ 标题还原 spec 模板；④ source 用 id 非标题 → source=entry.title。判定性保留：冒烟返回体 topic_framework:{injected:false}（无害，已注明）；词表走端点（spec 与工单打架，工单内化且端点更单源）；「continue 找下一个 vs None 降级」（工单 04 docstring 裁定）。

**验收：** 全部 ✓（协议签名加参 + DeepSeek/RoutingLLM/fakes 同步；`_skeleton_user_prompt` 框架段在参考段之前 + 强指令；`_generate_main_c` / `generate_skeleton` / `run_skeleton` 透传；测试 test_llm.py 新增 2 条 + 既有 302 全绿）。

- [x] LLM 抽象 `generate_main_skeleton(..., topic_framework=None)`；DeepSeek 实现 + RoutingLLM 转发（remote 方法加参）+ FakeLLM / RecordingLLM（测试 fakes）同步
- [x] `_skeleton_user_prompt(problem_text, module_interfaces, reference_fulltexts=None, topic_framework=None)`：framework 段在 reference 段之前；文案含 `### 题型框架：<topic_type>（来源 <entry.id>）`、强指令（保留结构 / 只填 TODO / 不存在的调用注释占位）
- [x] `_generate_main_c` / `generate_skeleton` / `run_skeleton` 加 `topic_framework` 透传（smoke 路径不受影响；reference_fulltexts 两参 / 三参调用分支保持零回归）
- [x] 测试：prompt 含 framework 段（顺序断言：framework 在 reference 之前）；None → 逐字节不变（既有断言先例）；fakes 捕获 topic_framework；RoutingLLM remote 转发参数断言


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
