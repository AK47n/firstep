# 01 — 赛题答疑 Q&A 注入推荐

**要做什么：** AI 推荐模块卡片加可折叠「赛题答疑 Q&A」输入框：用户粘贴赛事组问答，推荐时作为题面后的独立段注入提示词（权威澄清参考），Q&A 变化使缓存失效；留空 = 现状逐字节一致。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] llm.select_modules 加 qa_material 参数 + _selection_user_prompt 注入【赛题答疑（赛事组 Q&A）】段（题面/参考后、澄清前，_fit_fulltext_wire 预算兜底）；Protocol / DeepSeekLLM / RoutingLLM / fakes 同步签名（缺省空 = 旧行为逐字节）
- [x] select_modules_convergent / run_recommendation 透传 qa_material（空不传关键字）
- [x] webapp recommend 收可选 qa_text；推荐缓存加 qa_sha256（qa_fingerprint：cache_recommend 存 / validate_recommend 比，旧缓存无字段兼容 = 空 Q&A 匹配、带 Q&A 失效）
- [x] 前端：第 5 步折叠「赛题答疑 Q&A（可选）」输入框（details 样式 + 说明文案）+ 请求体 qa_text（空 = 旧载荷兼容）
- [x] 测试：prompt 注入（位置断言）/ convergent+run_recommendation 透传 / 缓存指纹（同 Q&A 命中、变失效、旧缓存兼容）/ webapp 端到端透传 / 前端结构钉；全量 pytest 2032 + JS 49 绿；CONTEXT.md「收敛循环」词条补 Q&A 口径
