# 01 — 推荐缓存加模块库指纹（库变缓存失效）

**要做什么：** 推荐缓存校验加模块库指纹：指纹 = 装配点 ManifestSummary 摘要行排序 hash（模型看到什么指纹什么）；写缓存存 library_sha256，校验比对——库变（模块增删 / 简介 / 能力 / 多实例标注）→ 缓存失效走真实推荐；旧格式缓存（无指纹字段）保守失效；库没变照常命中。解决"库内明明有 oled 却提示需自备"（旧缓存直出）。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] recommend_cache.library_fingerprint(summaries)：to_line 排序 hash（顺序无关，字段变化自动覆盖，空库稳定）
- [x] cache_recommend 存 library_sha256；validate_recommend 加 library_fingerprint 参数（缺省空 = 跳过）：不符失效 / 旧缓存无字段保守失效（宁可重推）
- [x] webapp recommend 路由：topic.manifest_summaries 算指纹，写缓存与校验同源一次计算两用
- [x] 测试：指纹敏感（简介/删模块/多实例标注）/ 顺序无关 / 空库；validate 匹配/不匹配/旧缓存失效/空参跳过；cache_recommend 落字段；webapp 集成（库变不命中走真实推荐）；既有测试原样绿
- [x] 全量 pytest 绿（2038）；CONTEXT.md「收敛循环」词条补库指纹口径；backlog.md 第 1 项标记已实现
