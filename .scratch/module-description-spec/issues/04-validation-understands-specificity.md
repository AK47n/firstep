# 04 — 一致性校验认识"专用性"

**What to build:** 简介的 AI 一致性校验能检查"专用性声明"：简介声称"XX 题专用"但代码是通用驱动 → 拒绝；代码明显是赛题专用逻辑但简介未标注 → 提示补充。让库里的简介声明保持可信，AI 推荐时读到的专用性标注是真的。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] 简介声称"XX 题专用"但代码为通用驱动 → 校验拒绝，给出差异说明
- [x] 代码明显赛题专用但简介未标注 → 校验提示补充专用性标注
- [x] 既有校验路径（一致通过 / 不一致拒绝）不受影响
- [x] FakeLLM 覆盖上述两条新路径（沿用注入模式与调用记录断言）

## Comments

- 2026-08-07 工单 04 完成（分支 ticket-module-desc-04，未合并/开 PR）。实现：`llm.py` 新增
  `VALIDATION_SPECIFICITY_RULE` 常量（双端同源唯一出处，ticket 06 教训），嵌入
  `VALIDATION_SYSTEM_PROMPT` 与 `_validation_user_prompt`；契约测试 2 例
  （`test_llm.py`：双端断言 + 实际请求可见）。
  **设计决策**：两条新路径都判为 `consistent=false`（拒绝）——`ValidationResult` 只有
  consistent + issues 两个通道，`consistent=true` 时 issues 被 `add_module` 丢弃，
  "非阻塞提示"在该接缝上机制上无法送达；差异在 issues 文案：路径 1 指出具体差异、
  路径 2 提示补充专用性标注。工单措辞"提示补充"建议随 doc 更新为"拒绝并提示补充"
  （Spec 轴评审标记）。**FakeLLM 两条路径测试**（`test_library.py`）随工单 01 的提交
  （ticket-module-desc-01 @ 2a414b1）一并入库（并发会话代补身份字段参数），
  本分支提交仅含提示词改动与契约测试；工单 01 合 main 后全量 458 passed + mypy 干净。
