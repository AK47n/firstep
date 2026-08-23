# 02 — 报告草稿确定性渲染器（report_draft.py + generate 参数）

**要做什么：** 新模块 report_draft.py：render_report_draft 纯函数——确定性章节（工程
概览 / 系统框图文本层次图（模块依赖树 + 引脚连接，不做 Mermaid）/ 模块选型表 / 引脚
分配表（与 README 同源）/ 测试记录模板（与 README 验证顺序清单同源））+ LLM 文本
注入（方案论证 / 软件流程两节，LLM 文本为入参非自调）。generate() 加参数
report_draft_text（缺省空 = 不写报告文件，旧行为逐字节不变；非空 = 写 `设计报告草稿.md`，
README 之后、上下文清单之前）。失败路径走既有 rmtree 兜底（生成原子性不破）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved：2026-08-23 实施完成 + code-review 双轴评审整改闭环；

## Comments

**实施记录（2026-08-23）：**
- 新模块 `report_draft.py`：render_report_draft 纯函数（平台 / 板名 / manifests /
  LLM 文本 / 绑定 / 实例计划 → 完整报告文本），幂等 + 尾部单换行（README 先例）。
- 七章：工程概览（平台 / 开发板可选）→ 系统框图（依赖树文本层次图（缩进 = 依赖
  层级，_dependency_depths 递推）+ 引脚连接表）→ 模块选型表 → 引脚分配表 →
  测试记录模板 → 系统方案论证 / 软件流程设计（LLM 文本注入，空 = 中文占位）。
- LLM 文本契约：`\n\n` 分段、最后一段 = 软件流程、其余 = 方案论证
  （_split_llm_text；llm.py 提示词约束 workflow 段内不用空行，工单 03 兑现）；
  契约外输入（单段）= 整段作论证、流程节占位降级。
- 引脚表单一出处：_append_pin_table 提取到 readme.py（README「引脚接线表」与
  报告「框图·引脚连接 / 引脚分配表」共用表格外壳，行数据源 _pin_rows 同源，
  结构测试钉防漂移）；验证顺序复用 sort_verification_order。
- generate() / generate_project() 加 report_draft_text: str = ""：空 = 不写报告
  文件（旧行为逐字节不变）；非空 = 写盘（演示脚本之后、上下文清单之前）。
- 测试：tests/test_report_draft.py 14 项（章节 / 层次 / LLM 注入 / 占位 / 单段
  降级 / 同源防漂移 / 流程落盘 / 幂等）+ test_generator.py 2 项（spec 测试决策
  逐字规定：缺省不写 + 有文本落盘 + 内容与渲染函数一致（换行归一化比对，写盘
  经平台换行转换））；全量 2154 通过 + mypy 59 文件干净。

**评审整改（code-review 双轴）：**
- Spec：(a) 系统框图兑现「层次图」——依赖树按依赖层级缩进（_dependency_depths，
  多级链深嵌套测试钉住）；(b) LLM 切分契约往返——由工单 03 产侧（webapp 拼接 +
  提示词约束）兑现，webapp 往返测试钉住（论证多段原文 / 流程最后一段）；(c)
  占位语义——契约外输入（单段）→ 该节缺内容走占位降级，docstring 明确 + 单段
  测试钉住。
- Standards（判断项）：(a) _append_pin_table 与 readme 渲染循环重复 → 提取到
  readme.py 共享（消除漂移风险）；(b) 测试输入改契约形状 `\n\n`（弱输入 → 契约
  输入）+ 补单段 → 占位断言；(c) 注释「spec 逐字」措辞修正（章节标题为本实现
  定稿，仅 PLACEHOLDER 为 spec 逐字）；(d) 测试分工（流程测试在 test_report_draft
  与 test_generator 双处）保留——test_readme.py 先例即同文件流程测试，两处覆盖
  角度不同（内容 vs 渲染等价），留痕。

- [x] 新模块 report_draft.py：render_report_draft 纯函数（幂等、尾部单换行）
- [x] 确定性章节全渲染：概览 / 框图（依赖树 + 引脚连接）/ 选型表 / 引脚表（与 README 同源，防漂移测试钉住）/ 测试记录模板（验证顺序同源）
- [x] LLM 文本注入：rationale / workflow 两节；空文本 = 两节中文占位提示（报告仍生成）
- [x] generate() 加 report_draft_text 参数：空 = 不写文件逐字节不变；非空 = 落盘 设计报告草稿.md
- [x] tests/test_report_draft.py（章节 / 占位 / 幂等）+ test_generator.py（缺省不写 / 有文本落盘）
- [x] 全量回归 + mypy 干净
