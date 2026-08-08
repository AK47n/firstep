# 01 — 架构深化 v3：推荐工作流归位（C1，模块推荐收敛循环移出 llm.py）

**What to build:** 第三轮架构深化（improve-codebase-architecture 驱动，2026-08-08 报告，Top recommendation C1）。llm.py（2057 行）装了 9 个职责，其中"推荐工作流"（收敛循环驱动 + 逐句对照 + 功能需求层）与 4 个推荐模型类属于模块选择域而非 LLM 客户端；selection.py 反向 `from .llm import ReferenceSuggestion` 违反 report.py 确立的依赖方向（"llm 层依赖模型层而非反向"）。本工单：模型 + 工作流整体移入 selection.py，依赖方向翻转，死代码 `select_modules_two_level` 删除。

1. **模型类移入 selection.py**：`OutOfLibrarySuggestion`、`FunctionRequirement`、`ModuleSelection`、`ReferenceSuggestion`（llm.py 约 356-430 行）整体搬迁（含各自的 to_dict），llm.py 改为 `from .selection import ...` 运行时导入（与 llm 从 report.py 导入判定模型的先例一致）。
2. **工作流移入 selection.py**：`select_modules_convergent`（llm.py:1714-1786）、`_number_topic_sentences`（1654）+ `_SENTENCE_BOUNDARY`（1651）、`_revision_prompt`（1668-1692）、`_functional_layer_key`（1695-1711）、常量 `SELECT_CONVERGENCE_MAX_ROUNDS`（212）。签名不变（`llm: LLM` 参数），LLM 协议类型仅 TYPE_CHECKING 导入（与 library.py:33 先例一致，避免 llm ↔ selection 环）。
3. **死代码删除**：`select_modules_two_level`（llm.py:1619-1641）无生产调用（grep 证实），收敛驱动第 1 轮已内联两级注入协议（llm.py:1753-1771）——删函数 + 其专属测试（tests/test_llm.py:2402-2449），两级注入协议覆盖由收敛测试保留。
4. **导入面更新**（文件边界，逐处 grep 定位，禁止扩面）：
   - llm.py：模型导入改指 selection；删除已搬走的定义。
   - selection.py：新增 `TYPE_CHECKING` 下 `from .llm import LLM`；运行时新增 `from .events import EVENT_CONVERGED, EVENT_ROUND, ProgressEvent, ProgressEmitter, _emit`（events.py 是叶子，契约不动）。
   - generator.py:20：`ReferenceSuggestion` 改从 `.selection` 导入。
   - webapp.py:63：`select_modules_convergent` 改从 `.selection` 导入。
   - tests/fakes.py:18、tests/test_webapp.py:34-38、tests/test_llm.py:59-60、tests/generate_wiring_fakes.py（如引用）：模型 / 收敛函数导入改指 selection。
   - 收敛循环测试（tests/test_llm.py:3029 起整段）移入 tests/test_selection.py（模块归属随实现走），其余不动。
5. **CONTEXT.md 同步**：收敛循环 / 功能需求层 / 逐句对照 / 实现覆盖检查 / 库外建议 / 硬件词表 六行的"主要实现"从 `llm.py（未实现）` 改为 `selection.py`（顺带修正工单 10 落地后残留的"未实现"过期标注）；模块（模块推荐）相关行补一句依赖方向。

**明确不动的（边界，勿越）**：
- `parse_module_selection` + `_parse_suggestions`（llm.py:1186/1338，硬件词表校验策略）留在 llm.py——它是模型输出解析期的适配器实现，与解析器同 file 才是 locality；词表策略另立工单再议。
- `build_manifest_summaries` + `_summary_slugs`（llm.py:566/1933）留在 llm.py——摘要行格式被解析器反解析（格式即 adapter 输入契约），两侧同 file 保持既有"改动格式须同步两处"约束。
- `_selection_user_prompt` / `_build_user_prompt` / `_truncate_content`（prompt 拼装）留在 llm.py。
- LLM 协议 / DeepSeekLLM / transport / retry / batch / 提炼 / 赛题库 / 参考库协议全部留在 llm.py。events.py 一字不动。

**Status:** done

## 验收

- [x] 全量 pytest 绿（723 passed）+ mypy 干净（22 文件零问题）
- [x] `grep -rn "select_modules_two_level" src tests` 零命中（死代码除净）
- [x] `grep -rn "select_modules_convergent" src` 生产调用只有 webapp.py 一处（导入源是 selection）
- [x] llm.py 不再运行时导入 selection 之外被搬走的模型定义；selection.py 对 llm 仅 TYPE_CHECKING
- [x] CONTEXT.md 六行词表"未实现"标注已修 + 依赖方向描述
- [x] 收敛行为回归：收敛测试（两轮一致即停 / 轮数上限 / 补问暂停 / 两级注入第 1 轮）全绿，真机不涉及（纯后端重构，无界面变化）

## Comments

（2026-08-08 立项，架构评审 C1。评审报告：C:\Users\luoji\AppData\Local\Temp\architecture-review-20260808-145320.html）

（2026-08-08 完成：worktree 分支 63b3d3f 合 main 4ec4ac8。723 绿 = 728 − 5 死代码测试，mypy 零问题；LLM 协议签名与 HTTP 契约一字未动，收敛测试整体移入 tests/test_selection.py 逐条通过。C2–C6 未立项，待指定。

一处必要的边界偏离（依赖方向翻转的必然前置，已实测复现）：reference_library.py:35 的 `from .llm import LLM` 由运行时导入转 TYPE_CHECKING——LLM 在该文件仅用于 draft_description 类型注解。若不动它，llm.py 改为运行时 `from .selection import ...` 后 llm → selection → reference_library → llm 成加载环（llm 部分初始化时 LLM 未定义，启动即 ImportError）。转换与 library.py:33 先例同款，运行行为零变化。其余文件严格在边界内。）
