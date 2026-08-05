# 01 — AI 判定素材升级：两阶段（读全文 → 摘要 → 判定）

**What to build:** 提炼判定前，AI 先逐文件读全文产出摘要，再基于摘要判定。判定素材从"路径 + 配置摘要"升级为含文件内容摘要——兑现 ADR 0001 的"读内容判断"，此前 AI 一个字的内容都看不到。

**Blocked by:** 无（独立，可先行）

**Status:** resolved

## Answer

- [x] llm 协议/实现：distill_master 内部两阶段——第一阶段逐文件读全文出摘要，第二阶段基于摘要判定（DeepSeek json_mode 两轮调用）
- [x] master 层把待判文件全文与路径传给 LLM；多份不一致文件传所有份
- [x] 摘要不进报告；判定条目 reason 带摘要要点即可
- [x] 假 LLM 测试：断言第二阶段的输入包含第一阶段产物（摘要）；畸形/缺摘要走既有"宁可大声失败"路径

实施要点：llm.distill_master 两轮 json_mode 调用——第一阶段以 JUDGMENT_SUMMARY_SYSTEM_PROMPT + _summarize_user_prompt 逐文件读全文出摘要（parse_summary_report 严格校验：版本不重不漏、未知文件 / 工程拒绝），第二阶段基于摘要 + 结构与配置对比判定。master 层 build_judgment_files 把冲突与独有文件的所有内容版本传给 LLM。摘要不进报告，判定 reason 引用摘要要点。已与 02 判定模型整合（merge 带整合产物全文，见 02）；假 LLM 测试全绿。
