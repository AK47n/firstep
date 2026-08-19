# 02 — 推荐缓存上 Web（done 载荷复用 + 指纹校验 + 设置开关）

**要做什么：** 把 CLI 已验证的推荐缓存机制搬进后端：`/api/recommend` 默认查缓存（键 = topic_id 或题面 sha256，文件与 CLI 格式兼容），命中直出 done 载荷（SSE 流照常播放 + cache_hit 事件），题面/平台/参考/澄清变化自动失效或警告；设置页提供开关与说明。

**被谁阻塞：** 无——可立即开始（CLI 机制已验收，双客户端对偶）

**状态：** resolved

- [x] `recommend_cache.py`：键（topic_id / 题面 sha256）、路径（`~/.contest_generator/cache/recommend_<key>.json`）、读写载荷与 CLI 格式逐字兼容；`validate_recommend` 题面/平台/键不符 = 失效返回原因，`parameter_warnings` reference_ids / clarify 指纹不符 = 命中带警告；损坏文件 / 写失败静默。
- [x] `/api/recommend` 接线：真实推荐前查缓存（AppConfig `recommend_cache_enabled` 默认开）；命中 → SSE 先发 `cache_hit` 进度事件再发 done（载荷 = 缓存 done 逐字）；未命中 → 真实推荐跑完写缓存（`_CacheWriterEmitter` 拦截 done）；开关关闭不查不写。
- [x] 设置页：推荐缓存开关（「最近 LLM 工作流」卡片标题行）+ 说明文案。
- [x] 前端：进度面板对 cache_hit 显示「复用本地推荐缓存」；带参数警告时显示「⚠ 复用缓存但输入有变：…」。
- [x] 测试：缓存模块单测（键/指纹/损坏/写失败/CLI 形状兼容）；Web 端到端（同题第二次命中且不触达 LLM、题面变失效走真实、开关关闭、坏缓存旁路）。

## Notes

- `recommend_cache.py`：机制照搬 CLI `generate_check.py` 的 `--reuse-recommend`（键 / 指纹 / 载荷形状逐字兼容——`tests/test_recommend_cache.py::test_load_recommend_accepts_cli_shape` 用 CLI 形状喂后端验证）；`load_recommend` 与 CLI 同款形状校验（坏 json / 缺字段 → ValueError）；Web 交互语义 = 坏缓存静默重算（`_load_recommend_safely` → None 走真实推荐，对照 CLI 回归脚本的"缺失即报错"）。
- 路由接线：缓存目录 = 配置目录同级 `cache/`（测试经 fixture config_path 隔离）；命中分支经 `_emit_cached_recommend` 发射（独立于路由函数体——结构防回退 `test_recommend_route_body_free_of_orchestration_calls` 要求路由体内无 `emit.done`/`emit.question`，发射语义归该专用点）；写缓存经 `_CacheWriterEmitter` 拦截 done（写失败旁路不阻塞终态）。
- events.py 登记 `EVENT_CACHE_HIT = "cache_hit"` 进度事件（`warns` 字段 = 参数指纹警告列表），`ProgressEvent` 增 `warns: tuple[str, ...]`。
- config：`AppConfig.recommend_cache_enabled`（缺省 True）；settings GET/PUT 透传（`_optional_bool` helper，非布尔 400）。
- 前端：`cache_hit` 事件显示「复用本地推荐缓存（题面 / 平台未变）…」或带警告差异；开关在「最近 LLM 工作流」卡片标题行。
- 验证：pytest 1882 全绿（+22）、`node --test tests/js/` 全绿、`mypy src` 51 文件干净。
