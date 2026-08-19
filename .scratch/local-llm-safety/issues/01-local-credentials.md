# 01 — 本地 LLM 凭据隔离

**What to build:** 本地模型请求默认不携带远程 API key，避免本地端点或兼容网关接收到不属于它的凭据，同时保持旧配置和远程请求兼容。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] 本地路由请求不发送远程 `Authorization` header
- [x] 远程路由继续发送既有认证 header
- [x] 旧配置文件可正常读取，缺省行为兼容
- [x] 测试覆盖本地/远程请求头边界
- [x] 运行相关测试、mypy 和 Node 测试

## Comments

本批次默认不增加 `local_api_key` 配置项；需要兼容网关认证时另立工单。

## Resolution

- `build_llm` 为 local delegate 清空 `api_key`，远程 delegate 保持原配置。
- 已验证：`pytest tests/test_llm.py tests/test_config.py -q`（223 passed）、
  `mypy src`（47 source files clean）、`node --test`（17 passed）。
- 复审后补充端到端路由测试：远程 key 存在时，经 `RoutingLLM` 发送的本地 HTTP
  请求不含 `Authorization`；现有远程请求头断言保留。
