# 07 — 就绪总览接入输出目录预警

**要做什么：** 06-A 的「输出目录已存在」非阻塞 ⚠ 预警目前只在「检查能否生成」面板（#readiness-check 的 warn 槽）出现；常驻的「就绪总览」（#gen-overview .ov-summary）看不到。本工单把同一预警并入总览摘要（追加 ⚠ 段），并让第 9 步 chip / 左侧导航 dot / 卡片徽章同源标 warn——新手不点开「检查能否生成」也能在总览上提前看到「目录已存在/非空」提示。

**被谁阻塞：** 06（preview-dir 端点与 outputDirWarnRow 已就绪）——本工单纯前端接入，可立即开始。

**状态：** resolved（主提交 73fd592 + CHANGELOG bd1c412；评审整改 7634ada + CHANGELOG bfdda43）

**结论：** 双轴评审——Standards「无硬违规」：缓存/在途复用/seq 序号竞态守卫正确，且修复了旧代码慢请求覆盖新缓存 key 的竞态；防重刷循环验证无循环（fetch 后重刷一次即终止、失败静默不重试风暴）。判断项未整改：单槽 _dirWarnInflight（K1→K2→K1 快速跳变时多一次冗余请求，seq 守卫仍保正确）、_dirWarnCache* 四变量同步改可收拢为对象（胶水层可容忍）、getOutputDirWarnRow 薄转发（拥有模块状态属合理门面）、ov-dir-warn 类无 CSS（工单验收要求，复用 .ov-missing 警告色）；建议的行为级并发测试未做——需为模块级 apiPost 造 mock 接缝，超出小活范围（seq/在途逻辑由源级守卫+推演保护，与仓库 ui 层惯例一致）。Spec「忠实实现、符合」：4 条验收全落地；1 测试小缺口（「传 null 不渲染」无独立用例——已补）；观察项「门槛不一致」（摘要 reason 门槛 vs 警示行存在门槛，依赖 outputDirWarnRow 恒填 reason 不可达——已整改统一为行对象存在门槛）；done 语义不对称（step9 已 done 时指示器不标 warn、摘要仍显 ⚠）与工单测试刻意一致；流程时序（实现提交未勾验收框、评审通过后置 resolved）属正常。全量 824 JS 全绿（816 旧 + 8 新）。

- [x] genOverviewSummaryHTML 支持附加 dirWarn 段（可选参，⚠ {title}：{reason}，class ov-missing ov-dir-warn；不传/传 null 时不渲染）
- [x] 总览摘要显示预警：ui/generate-steps.js refreshGenOverview 把共享的 outputDirWarnRow 结果传给摘要；genOverviewWarn(9) 在有预警时视为有警告（step9 chip / 左侧导航 dot / 卡徽章同源）
- [x] 请求复用不冲突：ui/generate-readiness.js 抽出共享请求（按载荷 key 缓存 + 同 key 在途复用 + 失败静默 + 仅最新请求落缓存），面板（refreshOutputDirWarn）改薄封装行为不变；总览侧仅在缓存未命中时挂一次刷新，防 fetch 后重刷循环
- [x] 相关测试更新并全绿（gen-overview.test.mjs 新增 2 用例 + null/undefined 变体；overview-dir-warn-guard.test.mjs 6 用例；全量 node --test tests/js/*.test.mjs 824 全绿）
