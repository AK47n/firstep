# 07 — 就绪总览接入输出目录预警

**要做什么：** 06-A 的「输出目录已存在」非阻塞 ⚠ 预警目前只在「检查能否生成」面板（#readiness-check 的 warn 槽）出现；常驻的「就绪总览」（#gen-overview .ov-summary）看不到。本工单把同一预警并入总览摘要（追加 ⚠ 段），并让第 9 步 chip / 左侧导航 dot / 卡片徽章同源标 warn——新手不点开「检查能否生成」也能在总览上提前看到「目录已存在/非空」提示。

**被谁阻塞：** 06（preview-dir 端点与 outputDirWarnRow 已就绪）——本工单纯前端接入，可立即开始。

**状态：** claimed（开始实现；测试先红后绿）

- [ ] genOverviewSummaryHTML 支持附加 dirWarn 段（可选参，⚠ {title}：{reason}，class ov-missing ov-dir-warn；不传/传 null 时不渲染）
- [ ] 总览摘要显示预警：ui/generate-steps.js refreshGenOverview 把共享的 outputDirWarnRow 结果传给摘要；genOverviewWarn(9) 在有预警时视为有警告（step9 chip / 左侧导航 dot / 卡徽章同源）
- [ ] 请求复用不冲突：ui/generate-readiness.js 抽出共享请求（按载荷 key 缓存 + 同 key 在途复用 + 失败静默），面板（refreshOutputDirWarn）改薄封装行为不变；总览侧仅在缓存未命中时挂一次刷新，防 fetch 后重刷循环
- [ ] 相关测试更新并全绿（gen-overview.test.mjs 新增用例 + 守卫新文件钉住 glue 接线；全量 node --test tests/js/*.test.mjs + pytest 不回归）
