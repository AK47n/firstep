# 02 — LLM 调用结构化观测

**What to build:** 每次 LLM 调用都产生不含敏感素材的结构化观测记录，使本地/远程路由、耗时、尝试、错误和解析结果可诊断、可统计。

**Blocked by:** 01 — 本地 LLM 凭据隔离

**Status:** resolved

**Notes:** `llm.py` 通过标准库 logger 输出不含素材的 `llm_observation` 结构化字段；覆盖远程/本地 route、模型、耗时、HTTP/响应解析错误、请求字节数和可用 usage。发送前体积拒绝、HTTP/网络和响应形状失败均产生记录；重试中的每次实际请求各有独立调用记录。

- [ ] 记录 operation、provider、model、耗时、尝试次数和最终状态
- [ ] 记录 HTTP 状态、错误类别、解析状态、请求大小及 provider 提供的 usage
- [ ] 记录不包含题面、源码、完整请求体、Authorization 或敏感 URL
- [ ] 本地和远程调用可明确区分
- [ ] 失败和重试也有可关联的调用记录
- [ ] 相关日志/观测测试通过
- [ ] 运行全量 pytest、mypy 和 Node 测试
