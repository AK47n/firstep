# 03 — 架构深化 v4：manifest 摘要协议结构化（候选 3，Strong）

**What to build:** 第四轮架构深化（2026-08-08 grilling 共识，候选 3）。模块 slug 语汇从盘上到 LLM 再回来以散文行传输：`build_manifest_summaries`（llm.py:488）拼行 → 进 prompt → 模型回答 → `_summary_slugs`（llm.py:1682）反解析行取 slug，两端 docstring 自认"改动格式须同步两处"。四个调用方（webapp.py:421/426、generator.py:168 TopicContext、selection.py:398-454、llm.py 自身）都得知道行文法。深化：结构化 ManifestSummary 对象成为接缝，字符串只在 prompt 边界渲染一次。

1. **manifest.py 加 `ManifestSummary`**（ModuleManifest 的所有者，collect_kits 同模块）：
   - dataclass：slug / description / kits（tuple，collect_kits 单源）/ dependencies（tuple）；
   - `from_manifest(manifest)` 类方法；
   - `to_line()`——行渲染唯一实现（原 build_manifest_summaries 的行文法逐字搬入，套件段 / 依赖段显示规则不变）。
2. **`build_manifest_summaries` 改签名**：返回 `list[ManifestSummary]`（llm.py 内保留，或迁 manifest.py——按 grilling 共识放 manifest.py 作纯形状，llm.py 只消费）；`_summary_slugs` **删除**，known_slugs = `[s.slug for s in summaries]`。
3. **LLM 协议签名变更**：`select_modules` 的 `manifest_summaries: Sequence[str]` → `Sequence[ManifestSummary]`（llm.py:453/572/594/605 + prompt 构建处 1494-1501 改 `[s.to_line() for s in ...]`）；selection.py:398-454、TopicContext.manifest_summaries 字段类型（generator.py:121/168）、webapp.py:421-426 全跟进。
4. **测试**：test_llm.py 摘要行格式用例改断言 to_line()；fakes.py 假 LLM 签名跟进；防漂移（行格式 ↔ 反解析）测试删除（不再有反解析）。

**明确不动的（边界）**：行显示内容与顺序（套件 / 依赖段规则逐字不变，只换载体）；collect_kits 单源实现零改动；keil.py / ccs.py / events.py / errors.py 零改动。

**Status:** resolved

## 验收

- [x] 全量 pytest 绿（772，main 基线 773 − 删除的反解析用例；本分支基于 main，不含 01/02）；`grep -rn "_summary_slugs" src tests` 无结果
- [x] `grep -rn "Sequence\[str\]" src/contest_generator/llm.py` 的 select_modules 相关签名消失（改 Sequence[ManifestSummary]）
- [x] 行渲染逻辑唯一出处 = ManifestSummary.to_line()（webapp / selection / generator 不再拼行）
- [x] LLM 假对象（tests/fakes.py）与端到端用例全部跟进后绿
- [x] mypy 干净（25 文件，main 预存 1 错误除外——工单 01 已修，合入 main 后消失）

## Comments

（2026-08-08 立项，grilling 共识：候选 3。协议签名全链路改对象，字符串只在 prompt 边界；独立于 01/02，串行最后做。测试成本：fakes.py 假 LLM 与各调用方签名跟进，可接受。）

（2026-08-08 实施完成，refactor 提交 + merge PR。要点：

- **ManifestSummary 归 manifest.py**：dataclass（slug / description / kits / dependencies，后两者默认空元组）+ from_manifest（collect_kits 单源）+ to_line()（原行文法逐字搬入——套件段 / 依赖段显示规则不变）。
- **build_manifest_summaries 变批量投影**：返回 list[ManifestSummary]，llm.py 内保留函数体但只剩一行列表推导；`_summary_slugs` 反向解析**删除**，known_slugs = `[s.slug for s in summaries]`。
- **协议签名全链路**：LLM Protocol.select_modules / DeepSeekLLM.select_modules / select_modules_convergent 都改 Sequence[ManifestSummary]；`_selection_user_prompt` 在 prompt 边界 `[s.to_line() for s in ...]`；TopicContext.manifest_summaries 变 tuple[ManifestSummary, ...]；webapp 路由零改动（summaries 变量自动跟上）。selection.py / llm.py 的 collect_kits 直接 import 移除（改 ManifestSummary 路径）。
- **测试**：test_llm 的摘要用例改断言对象（[s.to_line() ...] 列表）；批量替换内联字符串 summaries 为 ManifestSummary("slug", "描述")；RecordingLLM 假对象签名跟进；删除反解析 round-trip 用例（不再有反解析）。tests/fakes.py 与 test_selection.py 假 LLM 签名跟进。
- **过程教训（第三次）**：03 的编辑最初又落在 01 分支（reset 后没切回 02 分支，cherry-pick 时顺带发现）——已用"临时提交 → 基于 main 建分支 → cherry-pick --no-commit"把 03 独立出来，PR base 直指 main，diff 干净。）
