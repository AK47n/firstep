# 03 — webapp 错误映射集中化（评审候选 3，最急需）

**What to build:** 2026-08-06 架构评审报告急需待办第 ① 项：webapp 错误映射集中化。现状问题：
1. `/api/masters/scan` 与 `/api/masters/distill` 的 catch 元组漏 `OSError` → 扫描读文件遇权限 / 占用 / 磁盘满时裸 HTTP 500 无中文 message——568cf51 修过的同类 bug（confirm 端点）还活着，且每个路由的 catch 元组是散布的拷贝，新路由随时可能再漏。
2. `_error_response` 兜底分支把**未知异常当业务 400 吞掉**：真 bug 以 400 静默通过，配合测试 `raise_server_exceptions=False` 时无声无息，回归永远测不出来。

**改法（评审建议）：** 一张 error_to_http 表（已知异常 → 400/502，未登记 → 500）+ 路由包装兜底（路由不写 catch 元组）+ 未知异常默认 500。

**Status:** resolved

## Answer

- [x] `_error_response` 单点化：LLMError → 502；KeilProjectError/CcsProjectError → 400；OSError → 400（"文件操作失败：…"）；业务组（ExtractionError/LibraryError/MasterError/SelectionError/GeneratorError/ConfigError）→ 400；**兜底改 500**（"服务器内部错误（类型名）：…"）
- [x] `_map_errors` 路由包装：同步 / 异步（extract 路由）双形态；HTTPException 原样穿透（参数校验的 400 不受影响）；其余异常统一经 error_to_http 表映射
- [x] 全部 19 个路由挂 `@_map_errors`，17 处 per-route catch 元组删除——路由只写业务逻辑
- [x] 回归测试 3 条（均 raise_server_exceptions=False 捕获真实语义）：
  - `test_master_scan_oserror_returns_400_not_500`：monkeypatch scan_project 抛 OSError → 400 带中文（评审点名的 scan 漏捕场景，旧代码下是 500）
  - `test_master_distill_oserror_returns_400_not_500`：AI 阶段抛 OSError → 400（distill 漏捕的同类漏洞）
  - `test_unknown_exception_returns_500_not_400`：未登记 RuntimeError → 500 带类型名（旧代码下 detail 为空）
- [x] 全量 406 pytest 绿（403 基线 + 3 新测试）+ mypy 17 文件干净；`inspect.iscoroutinefunction`（Python 3.14 下 asyncio 版本已弃用）
- [x] CONTEXT.md 词表补"错误映射"、架构要点补"错误映射单源化"
