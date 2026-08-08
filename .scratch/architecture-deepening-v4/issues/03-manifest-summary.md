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

**Status:** pending

## 验收

- [ ] 全量 pytest 绿；`grep -rn "_summary_slugs" src` 无结果
- [ ] `grep -rn "Sequence\[str\]" src/contest_generator/llm.py` 的 select_modules 相关签名消失（改 Sequence[ManifestSummary]）
- [ ] 行渲染逻辑唯一出处 = ManifestSummary.to_line()（webapp / selection / generator 不再拼行）
- [ ] LLM 假对象（tests/fakes.py）与端到端用例全部跟进后绿

## Comments

（2026-08-08 立项，grilling 共识：候选 3。协议签名全链路改对象，字符串只在 prompt 边界；独立于 01/02，串行最后做。测试成本：fakes.py 假 LLM 与各调用方签名跟进，可接受。）
