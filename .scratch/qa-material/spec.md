# Spec — 赛题答疑 Q&A 注入推荐（qa-material）

## 问题陈述

赛事组常在赛题发布后发布答疑（Q&A）：学生问、赛事组答，澄清题面没写清楚的参数/边界。用户希望把 Q&A 放进一个输入框，AI 推荐时参考这些信息（很多不确定点 Q&A 里有权威答案），减少推荐偏差。

## 方案

「AI 推荐模块」卡片（第 5 步）加一个可折叠的「赛题答疑 Q&A（可选）」输入框；推荐请求带 `qa_text`，后端在 select_modules 的提示词里以「题面后的独立段」注入（Q/A 原文，不并入题面、不影响逐句编号与收敛判定）；Q&A 变化使推荐缓存失效（照 clarify_sha256 先例）。

## 用户故事

1. 作为用户，我把赛事组 Q&A 粘贴进输入框，点「让 AI 推荐」——推荐分析参考 Q&A 的权威澄清，库内命中更准。
2. 作为用户，Q&A 留空时行为与现状逐字节一致（旧请求兼容）。
3. 作为用户，我修改 Q&A 后重推——不会命中旧缓存（缓存含 Q&A 指纹）。
4. 作为用户，Q&A 是静态材料：不参与澄清交互、不并入题面、不干扰"两轮一致"收敛判定。

## 实现决策

- `llm.select_modules`（协议方法）加 `qa_material: str = ""`（缺省空 = 旧行为，无 Q&A 段）；`_selection_user_prompt` 在题面段后、澄清历史前注入「【赛题答疑（赛事组 Q&A）】…」段。协议实现与全部 fakes 同步签名。
- `selection.select_modules_convergent` / `run_recommendation` 加 `qa_material: str = ""` 逐层透传（与 clarifications 同规：空不传关键字，既有假 LLM 零改动）。
- webapp `/api/recommend` 收可选 `qa_text`（字符串，空 = 不带）。
- 推荐缓存：`cache_recommend` 存 `qa_sha256`；`validate_recommend` 加 qa 指纹比较（照 clarify_sha256 先例）——有 topic_id 时 key 不变，靠指纹拦。
- 前端：第 5 步卡片顶部加折叠区（details，照价格参考表样式）：`<summary>赛题答疑 Q&A（可选）</summary>` + textarea + 说明文案；请求体 `qa_text` 有内容才带（空 = 旧载荷逐字节兼容）。

## 测试决策

- test_llm：qa_material 注入 prompt 段（fake transport 断言 user 消息含 Q&A 标题与原文）；空 = 无段。
- test_selection：convergent / run_recommendation 透传（fake LLM 收到 qa_material）。
- test_webapp：recommend 带 qa_text → done 正常；缓存 qa 指纹——同题面不同 Q&A 不命中缓存（重新收敛）。
- 前端结构钉：textarea 与 payload 接线存在（tests/js）。

## 范围外

- 不注入骨架 / 生成 / 赛题简介（用户只要求推荐；机制可扩展）。
- Q&A 不做格式校验（自由文本）；长度上限沿用 wire 预算（超长截断由既有机制兜底）。
