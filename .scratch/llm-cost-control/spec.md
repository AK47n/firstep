# spec — LLM 成本控制闭环（费用估算 + 推荐缓存上 Web）

## 问题陈述

最近工作流仪表盘（llm-observability-dashboard/03）已把每次调用的 token 数、provider 拆分、耗时全部展示出来，但**没有换算成钱和时间**：用户仍不知道一次推荐/修复花了多少钱、本地路由到底省了多少。同时 CLI 验收脚本已有 `--reuse-recommend` 推荐缓存（实测单题 8m50s → 2m41s），但用户日常主入口是 Web——同题重跑推荐（改平台/换参考/澄清答案变化后）仍全量重付 LLM 费用，最贵的推荐段（单题 ~10-15 min、~90% 耗时）无处复用。

## 方案

做两件独立但同主题的事，把「省钱」变成可见、可复用的能力：

1. **费用估算**：在现有观测数据（usage 的 prompt_tokens / completion_tokens）上加一层纯函数估算——可配置单价表（DeepSeek 官方价目，本地 = 0 成本），设置页可覆盖单价；仪表盘每行显示估算费用，并汇总「本次工作流 DeepSeek 估算花费」与「若全部走 DeepSeek 的对照花费」（= 本地路由节省额）。明确标注估算性质，不接账单。
2. **推荐缓存上 Web**：把 CLI 已验证的推荐缓存机制（done 载荷落盘 + 题面/平台指纹 + 参考/澄清参数指纹）搬进后端，Web 端推荐请求默认命中缓存直出结果（SSE 流照常播放、进度事件一步到位），缓存不一致时警告并回退真实调用。

## User Stories

1. As 用户，I want 每次推荐/修复结束后看到估算费用，so that 知道这单花了多少钱（DeepSeek vs 本地对照）。
2. As 用户，I want 本地路由的节省额可见，so that 验证本地路由是否真省钱（spec 用户故事 1 的最终闭环）。
3. As 用户，I want 设置页可调整单价，so that 官方调价（2026-08-18 已大幅调价）后不用改代码。
4. As 用户，I want 同题重跑推荐命中缓存秒出，so that 不重复烧最贵的推荐段。
5. As 用户，I want 缓存命中时明确提示「复用缓存」，so that 不会误以为结果是最新算的。
6. As 用户，I want 题面/平台/参考/澄清变化后缓存自动失效或警告，so that 不会拿到过期推荐结果。
7. As 维护者，I want 估算与缓存都是旁路增强，so that 估算表损坏/缓存读写失败不影响生成与修复。
8. As 维护者，I want 缓存文件与 CLI 格式兼容，so that 双客户端对偶（recommend-contract-parity 精神延续）。

## 实现决策

- **费用估算 = 纯函数 + 配置**：`llm_pricing.py` 新模块——`estimate_llm_cost(usage, prices)` 纯函数（prompt_tokens × 输入单价 + completion_tokens × 输出单价）；单价表 `LLMPriceTable`（dataclass：input_per_million / output_per_million，deepseek 与 local 各一张；本地默认 0 成本）；默认单价内置常量（以官方定价页为参考值，注释标明"仅供参考，设置页可改"）；AppConfig 增可选 `llm_prices` 字段（config.json 可存，设置页可编辑，缺省用内置默认）。
- **仪表盘展示**：`llm_recent_workflows.py` 的快照与 `/api/llm-workflows/recent` 载荷增估算字段（每工作流 `est_cost_deepseek` / `est_cost_local` / `est_savings`，本地与 DeepSeek 两套单价各算一次）；前端 summary 行显示「约 ¥x.xx（DeepSeek）/ ¥0.00（本地），省 ¥x.xx」；脚注标注「估算值，仅供参考，以官方账单为准」；费用 0 的调用不显示。
- **推荐缓存 = 后端旁路层**：新模块 `recommend_cache.py`——键 = topic_id 或题面 sha256（与 CLI 一致）；文件 = `~/.contest_generator/cache/recommend_<key>.json`（与 config.json 同目录，格式与 CLI `generate_check.py` 的缓存完全一致：done 载荷逐字 + topic_key/platform/problem_sha256/reference_ids/clarify_sha256）；`load_recommend` 校验题面/平台/键不符 = 失效返回 None + 原因；reference_ids / clarify 指纹不符 = 命中但带警告；写失败静默（旁路）。
- **Web 接线**：`/api/recommend` 路由在跑真实推荐前先查缓存（默认开，AppConfig 增 `recommend_cache_enabled` 开关 + 设置页可关）；命中 → SSE 流照常发事件（先发 `cache_hit` 进度事件，再发 done 终态载荷 = 缓存 done 逐字），不碰 LLM；未命中 → 真实推荐跑完写缓存。设置页新增「推荐缓存」说明与开关、缓存目录显示。
- 前端推荐进度面板对 `cache_hit` 事件显示「复用本地缓存（题面/平台未变）」，缓存带参数警告时在 done 后显示「⚠ 本次输入与缓存时不同，结果沿用旧推荐」。

## Testing Decisions

- 纯函数单测：`estimate_llm_cost`（输入/输出单价、0 usage、缺字段、小数）；`LLMPriceTable` 序列化（config 存取、缺省默认）。
- 缓存模块单测：键（topic_id / 题面指纹）、指纹校验（题面变/平台变/参考变/澄清变 → 失效或警告）、损坏文件 → None 不炸、写失败静默。
- Web 端到端：`/api/recommend` 第二次同题请求命中缓存（SSE 事件序列含 cache_hit + done 载荷与首次一致）；题面变化后失效走真实 LLM（FakeTransport 计数）；设置开关关闭后不查缓存。
- 前端：`tests/js/recent-workflows-format.test.mjs` 扩费用行格式用例；`cache_hit` 事件处理 node 测试。
- 既有 CLI 缓存格式兼容测试：用 generate_check.py 的缓存文件喂后端 `load_recommend` 能读。

## Out of Scope

- 不改 prompt、不改路由策略、不改 LOCAL_LLM_METHODS。
- 不做 LLM 响应缓存（只缓存推荐段 done 载荷；骨架/修复要真实 main_c 不缓存——CLI 决策照搬）。
- 不做 token 级流式、取消按钮、断线恢复（另有 range）。
- 不把 CLI 验收脚本的缓存目录（.scratch/real-run/cache）改掉（Web 用独立目录、格式兼容）。
- 不估算本地电费/机器成本（本地 = 0 成本口径）。
- 不做多模型价目自动同步（单价手动配置）。

## Further Notes

- 依据：llm-observability-dashboard spec 的 Out of Scope 明确把「token 定价表/费用估算」列为下一步切片；check-recommend-cache/01 已验证 CLI 缓存机制（键/指纹/决策 1-6 全在 generate_check.py）。
- 2026-08-18 DeepSeek 大幅调价（最高涨幅 1100%，峰谷定价）——默认单价仅作参考，设置页可覆盖是硬需求。
