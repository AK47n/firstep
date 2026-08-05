# 02 — 判定模型改造：内容判据 + 动作词表收敛

**What to build:** 判定唯一判据 = 读内容后判断通用性 / 基础建设必需性（ADR 0001）。公共文件进判定（keep 默认倾向 / exclude，禁 merge）；冲突文件开放 exclude（merge / exclude 二选一，禁 keep）；merge 语义从"选定来源工程"升级为"读多份 → 分析 → 整合出通用版本"（选一份是特例），FileDecision 扩展带整合产物内容与整合说明。

**Blocked by:** 01 — 判定素材（两阶段摘要）

**Status:** resolved

## Answer

- [x] 分类（公共 / 冲突 / 独有）不再决定动作：公共文件可判 exclude；冲突文件可判 exclude
- [x] merge 产物 = AI 写出的新文件内容：FileDecision（或等价结构）新增整合产物字段（content + 整合说明）
- [x] 公共文件 AI 判 merge/exclude → 拒绝（与现状一致）；判 keep 冗余忽略
- [x] DISTILL prompt 更新：判据（通用 / 必需）、动作词表、整合要求（选一份是特例）
- [x] 假 LLM 测试全绿：公共剔除、冲突剔除、整合产物携带、词表收敛

实施要点：FileDecision 新增 content / explanation（merge 必填，其余动作禁带）；source 从"merge 必填"降为"选一份特例时可选"；冲突文件开放 exclude（keep 仍禁）；merge 只用于冲突文件、落盘写 content 而非复制源工程；公共文件 AI 判 merge/exclude 仍拒绝（keep 冗余忽略），但确认时用户可改剔除。prompt 以"读内容判断通用 / 基础建设必需"为唯一判据。01（两阶段摘要）未在本工单实施。
