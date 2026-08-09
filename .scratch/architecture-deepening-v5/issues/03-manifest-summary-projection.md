# 03 — 架构深化 v5：模块摘要投影归 manifest.py——生成核心运行时不再拉 LLM 栈（候选 2，Strong）

**What to build:** 第五轮架构深化（2026-08-09，候选 2，源自 architecture-review-20260809-102431）。`build_manifest_summaries` 是纯批量投影（一个 map 过 `ManifestSummary.from_manifest`，llm.py 内零调用），住在 llm.py，迫使生成入口 `generator.py:21 from .llm import LLMError, build_manifest_summaries` 运行时拉进整个 LLM 网络栈——generator.py:49-50 自己引用的规则（"生成流程不该在运行时拉进 LLM 栈"，skeleton.py 用 TYPE_CHECKING 守住了）被自己违反。工单 02 已删掉 webapp 的装配消费（test_webapp.py:1718 已断言 webapp 无该属性）。本轮把投影收进 manifest.py（紧邻 `from_manifest`），generator 对 llm 只剩 LLMError 捕获 + TYPE_CHECKING。纯搬家，行为零变化，行渲染内容逐字不变。

1. **`build_manifest_summaries` 从 llm.py:488-497 逐字迁入 manifest.py**：放 `ManifestSummary.from_manifest` 旁（~line 210 后），docstring 原样保留（"形状归 manifest.ManifestSummary……本函数只是批量投影"）。函数名不变（CONTEXT 词表与既有调用点同名，少 churn）；签名 `Sequence[ModuleManifest] -> list[ManifestSummary]` 不变。
2. **generator.py import 面**：`from .llm import LLMError, build_manifest_summaries`（line 21）→ `from .llm import LLMError`；`from .manifest import ManifestSummary, ModuleManifest`（line 22）→ 追加 `build_manifest_summaries`。两处调用点（181 显式路径 / 202 no-topic 路径）零改动。
3. **test_llm.py**：import 行（line 46）改从 `.manifest` 导入；8 处调用（139/154/169/186/195/196/204/243）原样过（断言内容不动）。
4. **结构测试（防回退，先例 errors.py / test_webapp:1718）**：test_manifest.py 加一条——`build_manifest_summaries` 定义唯一出处 = manifest.py：`import contest_generator.llm as llm; assert not hasattr(llm, "build_manifest_summaries")` + `assert hasattr(manifest, "build_manifest_summaries")`。
5. **CONTEXT.md**：「模块摘要」词条实现列 `manifest.py（ManifestSummary）` → `manifest.py（ManifestSummary / build_manifest_summaries 批量投影）`。

**明确不动的（边界，勿越）**：`ManifestSummary` dataclass / `from_manifest` / `to_line` 零改动（行内容与显示规则逐字不变）；`LLMError` 留在 generator 的运行时 import（resolve_topic_context 可选 LLM 路径的捕获必需——把 LLM 栈从生成核心彻底请出去是候选 1（llm 拆层）的事）；llm.py 只删这个投影定义、其余零改动（不挪 Transport/协议/解析器）；webapp / selection / skeleton 零改动；前端零改动；不新增配置项。

**Status:** resolved（2026-08-09 合入 main 后同批 PR 勾选，804 绿 + mypy 干净）

## 验收

- [x] 全量 pytest 绿（基线 803，+1 结构测试 = 804）+ mypy 干净；test_llm 的 8 处投影用例原样过（只改 import 行）
- [x] `grep -rn "build_manifest_summaries" src`：定义唯一出处 = manifest.py；generator 从 .manifest 导入；llm.py 零残留
- [x] `grep -rn "from \.llm import" src/contest_generator/generator.py` 只剩 `LLMError`（+TYPE_CHECKING 块）
- [x] 结构测试过：`not hasattr(llm, "build_manifest_summaries")` + `hasattr(manifest, "build_manifest_summaries")`
- [x] CONTEXT.md「模块摘要」词条实现列补投影名

## 实施提示词（新会话用）

```
工单：.scratch/architecture-deepening-v5/issues/03-manifest-summary-projection.md（架构深化 v5：模块摘要投影归 manifest.py，候选 2）

先读工单全文，按 1-5 节执行。独立 worktree（勿在主检出改）：
git worktree add ../firstep-v5-03 main

1. build_manifest_summaries 从 llm.py:488-497 逐字迁 manifest.py（from_manifest 旁，docstring 原样）
2. generator.py:21 改 from .llm import LLMError；line 22 的 .manifest import 追加 build_manifest_summaries
3. test_llm.py:46 import 改从 .manifest；8 处调用零改动
4. test_manifest.py 加结构测试（llm 无该属性 / manifest 有）
5. CONTEXT.md「模块摘要」词条实现列补投影名
6. 全量 pytest 绿 + mypy 干净 + 验收全勾后提交（refactor 一条 + docs 一条，风格照仓库）→ PR base 指 main

注意：编辑前先确认 cwd 在 worktree；勿串行做别的工单。
```

## Comments

（2026-08-09 立项，候选 2（用户委托选型后的下一轮首选）。设计决策：D1 投影逐字迁 manifest.py 紧邻 from_manifest（函数名不变少 churn，CONTEXT 词表本就指 manifest.py）；D2 generator 对 llm 只留 LLMError（可选 LLM 路径捕获必需——彻底清栈归候选 1）；D3 测试只改 import 行（8 处用例断言原样，随迁不新增）；D4 结构测试防回退（llm 无该属性，webapp 侧 02 已有断言，两侧合围）。工单 01/02 已闭环（PR #18/#19/#20）。候选 4（蒸馏侧平台适配接缝）为下下轮。）

（2026-08-09 实施闭环，PR #21。逐字搬迁 + import 面按 2/3 节收口；llm.py 顺带清掉唯一引用投影的 `ModuleManifest` import（搬走后即闲置，import 面归零）。基线 803 → 804 绿（+1 结构测试）+ mypy 干净；验收 grep 全过：定义唯一出处 = manifest.py，generator 对 llm 只剩 LLMError + TYPE_CHECKING，llm.py 零残留。）
