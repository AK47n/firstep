# 06 — 架构深化 v5：llm.py 拆层——域判决回归域模块，传输只留传输（候选 1）

**What to build:** 第五轮架构深化（2026-08-09 grilling 共识定稿，候选 1，源自 architecture-review-20260809-102431）。llm.py（1777 行）五层杂烩：传输（_chat / 413 / 响应解包）+ 协议（LLM 9 方法）+ 提示词 ×8 + 解析器 + 预算——解析器里内藏 selection 域不变量：需求→模块机械派生（_parse_requirements 顶层 modules 并集）、硬件词表硬约束（_parse_suggestions 的 name 词表校验 / category 降级 / 拒收）、DeepSeek json 数字怪癖（sentence 数字字符串强转，:1193-1197）——域判决执行在传输模块的解析器里；唯一一个定义在 llm.py 的域模型 ValidationResult（:355）迫使 library.py 反向 TYPE_CHECKING 引用（:40），repo 自己"模型归模型层"的规则在这里停步。本轮收口：**"模型输出 → ModuleSelection"整条解释链归 selection.py（build_module_selection，llm 只做 JSON 文本形状提取），ValidationResult 迁 library.py（照 report.py 先例）**。行为零变化（错误文案逐字、派生结果逐字、HTTP 502 映射不变、prompt 文本零改动）。

1. **selection.py 新增公开函数 `build_module_selection(raw, *, known_slugs, known_reference_ids=(), hardware_words=()) -> ModuleSelection`**（域判决单址）：
   - llm.py:1089-1325 的模块选择解释链**整体逐字迁移**：`parse_module_selection` → `build_module_selection`（JSON 已由 llm 解析，入参从 content 改 dict）、`_parse_plain_modules` / `_parse_requirements` / `_parse_suggestions` / `_parse_reference_ids` / `_parse_questions` 全部随迁为 selection 私有助手；
   - 错误类型换 **SelectionError**（selection.py:45 既有，ValueError 子类）——**不 import LLMError**（selection → llm 运行时 import 与 llm → selection 既有边成环；错误文案逐字不变）；
   - 新增 import：`.wordlist`（category_names / model_names / HardwareWordGroup，叶子模块无环）、typing 补 Mapping；
   - 迁出后 llm.py 不再有：sentence 强转、requirements→modules 派生、词表校验/降级、references id 校验、questions 校验——**llm 域判决清零**（grep 坐实："模型推荐了库中不存在的模块" / "库外建议的硬件名不在硬件词表中" / "sentence 必须是正整数" 等文案唯一出处 = selection.py）。
2. **llm.py 解析器只剩机械提取**：
   - `parse_module_selection` 拆为 `extract_module_selection_data(content: str) -> dict`：JSON 解析（非 JSON 抛 LLMError，文案逐字）+ 顶层必须是对象（文案逐字）——**只这两处 LLMError**，返回校验前的原始 dict；语义校验（字段必填 / 类型 / known / 重复 / 派生 / 词表 / 怪癖）全部在 selection 侧；
   - `DeepSeekLLM.select_modules`（:571-576）改调：`data = extract_module_selection_data(content)` → `build_module_selection(data, known_slugs=[...], known_reference_ids=[...], hardware_words=self._hardware_words)`，**捕获 SelectionError → 抛 LLMError(str(exc)) from exc**（传输侧翻译，错误契约 502 / 文案不变）；
   - 其余解析器（parse_distillation_report / parse_summary_report / parse_validation_result / parse_archive_judgment / parse_topic_split / parse_topic_number）**原样不动**（纯机械形状校验构造模型层对象，report/topic 无派生判决——先例：parse_* 留传输层）。
3. **ValidationResult 迁 library.py**（照 report.py 先例：模型归模型层，llm 只消费）：
   - library.py 新增 `ValidationResult` 定义（dataclass，字段 / docstring 逐字，llm.py:355-361 搬移）；library.py:40 TYPE_CHECKING 块删 ValidationResult（留 LLM）；library.py:162 `validate_description` 返回类型直接用模块内定义；
   - llm.py 运行时 `from .library import ValidationResult`（llm → library 边新建；library 对 llm 仅 TYPE_CHECKING，**无环**——与 llm → selection 模型层消费同方向）；parse_validation_result 留 llm.py（照 parse_distillation_report 先例）；
   - 消费方 import 源改：tests/fakes.py:18、tests/test_library.py:25、tests/test_webapp.py:41 从 `contest_generator.library` import。
4. **测试随迁**（断言原样）：
   - test_llm.py 的 parse_module_selection 用例拆两类：机械形状（非 JSON / 非对象，:384 区域）留 test_llm 改调 `extract_module_selection_data`；域判决用例（requirements 形状 / known / 重复 / 派生 / 词表 / 怪癖 / references / questions，:334-360 与 :2353-2843 区域）**随迁 test_selection.py** 改调 `build_module_selection`——断言 match 文案逐字原样，`pytest.raises(LLMError, ...)` 改 `pytest.raises(SelectionError, ...)`；
   - 新增结构测试（防回退，先例 errors.py / 04 / 05 工单）：selection 有 `build_module_selection` 属性且 `llm.extract_module_selection_data` 存在（消费 pin，等号引用侧）；`llm.ValidationResult is library.ValidationResult`（定义单址）；llm 无域判决文案（"不在硬件词表中" 字面量唯一出处 = selection.py，grep 式断言）；
   - test_llm / test_library / test_webapp / tests.fakes 的 ValidationResult import 源改 library（定义处断言原样过）。
5. **CONTEXT.md 词表更新**（同批提交）：「模块」词条实现列补"推荐域判决（build_module_selection：模型输出 → ModuleSelection 解释链——需求派生 / 词表约束 / DeepSeek 怪癖）在 selection.py，llm 只做机械提取"；「架构要点」补一句：llm.py 拆层——域判决随域走（照 report.py / selection.py 先例），ValidationResult 归 library.py，llm 缩为 协议 + 提示词 + 机械解析 + 预算 薄传输层。

**明确不动的（边界，勿越）**：行为零变化（错误文案逐字、派生 / 词表判定结果逐字、LLMError → 502 映射不变、recommend 端到端断言原样过）；llm.py 其余解析器（report / archive / topic 族）与全部提示词文本零改动（prompt 字符串一字不动）；DeepSeekLLM 协议签名（LLM Protocol 9 方法）零改动；webapp 路由零改动；selection 其余 API（resolve_selection / associated_references / select_modules_convergent / 模型类）零改动；不引入新模块（判决住 selection，ValidationResult 住 library，都是既有域模块）。

**Status:** resolved（2026-08-09 同批 PR 勾选，823 绿 + mypy 干净）

## 验收

- [x] 全量 pytest 绿（基线 818 → 823，+5：结构测试 3 条 + 随迁净增 2）；recommend 端到端 / summarize / validate 既有断言原样过（行为零变化：错误文案逐字、派生逐字、502 映射不变）
- [x] `grep -rn "不在硬件词表中\|sentence 必须是正整数\|派生\|强转" src/contest_generator/llm.py` 无结果（域判决清零；build_module_selection 唯一出处 selection.py:313）
- [x] `grep -rn "class ValidationResult" src` 唯一出处 = library.py:51
- [x] `grep -rn "build_module_selection" src` = selection.py 定义 + llm.py 消费（DeepSeekLLM.select_modules 一行调用 + import / docstring 引用）
- [x] 结构测试过：selection.build_module_selection 消费 pin + llm.extract_module_selection_data 存在；llm.ValidationResult is library.ValidationResult + "class ValidationResult" 单址断言；"不在硬件词表中" 单址 = selection.py（grep 式）
- [x] CONTEXT.md 两处更新到位（模块词条实现列 + 架构要点新 bullet）

## 实施提示词（新会话用）

```
工单：.scratch/architecture-deepening-v5/issues/06-llm-layer-split.md（架构深化 v5：llm.py 拆层——域判决回归域模块，候选 1）

先读工单全文，按 1-5 节执行。独立 worktree（勿在主检出改，必须 -b 形式）：
git worktree add -b v5-06-llm-layer-split ../firstep-v5-06 main

1. selection 加 build_module_selection（llm.py:1089-1325 模块选择解释链整体逐字迁，错误类型换 SelectionError——不 import LLMError（成环），文案逐字；新增 .wordlist import；llm 域判决清零）
2. llm 解析器拆机械提取：parse_module_selection → extract_module_selection_data（只 JSON 解析 + 顶层对象两处 LLMError）；DeepSeekLLM.select_modules 改调 extract + build_module_selection，捕获 SelectionError → LLMError(str(exc)) from exc；其余解析器原样不动
3. ValidationResult 迁 library（定义逐字搬，TYPE_CHECKING 删名，llm 运行时 from .library import，parse_validation_result 留 llm）；fakes/test_library/test_webapp 改 import 源
4. 测试：test_llm 的 parse_module_selection 用例拆两类（机械留 test_llm 改调 extract；域判决随迁 test_selection 改调 build，断言 match 文案原样、LLMError 改 SelectionError）；结构测试 3 条（build_module_selection 消费 pin / ValidationResult 定义单址恒等 / 域判决文案单址 grep 式）
5. CONTEXT.md 按工单 5 节更新
6. 全量 pytest 绿 + mypy 干净 + 验收全勾后提交（refactor 一条 + docs 一条，风格照仓库）→ PR base 指 main

注意：编辑前先确认 cwd 在 worktree；勿串行做别的工单。
```

## Comments

（2026-08-09 立项，grilling 共识定稿：候选 1 llm.py 拆层。用户委托技术选型（"深度思考然后选择"），逐项复核后定稿。D1 拆层形态：**整条"模型输出 → ModuleSelection"解释链迁 selection**（parse_module_selection 全家含私有助手逐字搬，改名 build_module_selection）——比"只迁三块判决"边界更干净：域不变量单址，deletion test 成立（删 build_module_selection → llm 无法构造 ModuleSelection）；llm 只剩 extract_module_selection_data（JSON 解析 + 顶层对象，纯机械提取）。D2 错误类型：判决错误换 SelectionError，**不 import LLMError**（环事实：selection → llm 运行时 + llm → selection 既有边 = 成环）；传输侧翻译（DeepSeekLLM.select_modules 捕获 SelectionError → LLMError(str(exc))）保住 HTTP 502 契约与文案逐字——错误类型变化是测试随迁的正常调整（断言 match 不变）。D3 ValidationResult 迁 library.py：照 report.py 先例（模型归模型层，llm 消费），parse_validation_result 留 llm（照 parse_distillation_report 先例：解析器留传输层）；llm → library 运行时边新建，library 对 llm 仅 TYPE_CHECKING 无环。D4 边界：report / archive / topic 解析器原样不动（纯机械形状校验，无派生判决；C1 已文档化）；提示词文本零改动；不新建模块。报告：architecture-review-20260809-102431.html。）

（2026-08-09 实施留痕：按 1-5 节执行完毕。refactor 提交：解释链逐字迁 selection.py 改名 build_module_selection（raw dict 入参、错误类型换 SelectionError——selection 不 import LLMError，新增 .wordlist import；docstring 补"非 JSON / 顶层非对象在 llm 侧"一句）；llm.py 只留 extract_module_selection_data（JSON 解析 + 顶层对象两处 LLMError，其余解析器原样不动），DeepSeekLLM.select_modules 改调 extract + build 并捕获 SelectionError → LLMError(str(exc)) from exc（502 契约不变）；ValidationResult 定义逐字迁 library.py（TYPE_CHECKING 删名，llm 运行时 from .library import，parse_validation_result 留 llm）；模块 docstring 补"校验结果模型在 library"，清 category_names/model_names/dataclass 闲置 import，select_modules / parse_archive_judgment docstring 引用同步改名。测试：机械用例（非 JSON / 非对象）留 test_llm 改调 extract；21 个域判决用例随迁 test_selection（json.dumps 改 raw dict、LLMError 改 SelectionError，断言 match 文案逐字原样）；test_reference_library 的 file_label 单址 pin 行号 481→489（ValidationResult 迁入位移）；fakes / test_library / test_webapp 的 ValidationResult import 源改 library；新增 3 个结构测试（build_module_selection 消费 pin + extract 存在 / ValidationResult 定义单址恒等 + class 行 pin / "不在硬件词表中" 单址 grep 式）。docs 提交：CONTEXT.md 两处 + 工单文件闭环。823 绿 + mypy 干净，验收全勾。）
