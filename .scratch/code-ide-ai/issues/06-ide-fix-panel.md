# 06 — IDE 修复面板（B 全配双出口）

**要做什么：** IDE 底部第三面板 `#code-fix-panel`（与编译/变更/AI 对话面板
同型并列）+ 双入口：
- 面板：head「修复」+ 状态行 + 收起钮；内容 = 编译/修复事件流（状态/错误
  列表/轮次条/应用结果/回滚入口/继续修复——渲染复用 fx/generate.js
  compileStatusText 等先例 + 面板域容器）；绑定工单 05 的共享回调。
- 入口：编译失败面板（代码 tab）「在此修复」按钮（现有 goto 按钮旁/替代为
  二选：IDE 内修复 | 去生成页修复——双按钮）；点击 → 守卫（与生成页同
  guardCodeTabWrite(WG.fix)）→ startFixCenterCore(IDE 回调)。
- 单实例：isFixRunning() 时按钮 disabled/提示（防重入双出口一致）；生成页
  修复中心与 IDE 面板同时打开 → 状态广播双面板一致。
- 修完后 IDE 侧感知：循环写盘 → checkCodeDiskChanges（一期机制，面板自动
  出现变更）——闭环。

**被谁阻塞：** 05（共享状态机）。

**状态：** resolved

- [x] 验收 1：编译失败（目录=生成上下文）→「在此修复」→ IDE 面板状态流转
  （状态行/错误列表/轮次）；生成页入口同时可用（单实例锁生效）。
- [x] 验收 2：脏标签 → 守卫弹窗确认/取消（与生成页同文案同行为）。
- [x] 验收 3：面板与编译/变更/AI 对话三面板同型并列不互扰；折叠收起独立。
- [x] 验收 4：修完写盘 → 变更面板自动出现（感知联动）；smoke 全绿。

**结论：** 实现完成（共享状态机订阅制广播改造成长驻——双面板同步见 spec.md
「评审确认」段 s6）。要点与偏离：
- 核心 fix-center-core.js 升级为**订阅制广播**：subscribeFixCenter(cb) 注册
  长驻回调组（生成页壳层与 IDE 面板各 subscribe 一次——单实例循环事件天然
  广播双 DOM；与触发方 input.callbacks 同组时 Set 去重只收一次）；
  发射点全部 emitAll(name,...args)（单监听器异常不阻断）；退订函数返回。
- 新 ui/code-fix-panel.js：#code-fix-panel（与编译/变更/AI 对话同型并列，
  放在 #code-ai-chat-panel 后、.code-statusbar 前）；head = 修复 + 状态行 +
  继续修复/回滚/收起；内容 = 轮次条 + 错误提示 + 结果列表。长驻回调绑面板
  DOM（index.html 全 DOM 常驻，hidden 无害）；onCompiled → checkCodeDiskChanges
  （感知闭环）；「在此修复」/「继续修复」经 guardCodeTabWrite(WG.fix/
  WG.continueFix, **{anyDir:true}**——IDE 内发起任意目录都防脏标签覆盖，
  与工单 04 AI apply 同语义）；回滚复用 confirmModal + /api/fix-errors/rollback。
- 编译失败面板双按钮：「去生成页一键编译修复」（B 低配保留）+「在此修复」
  （同条件显隐——setGotoVisible 一处控制，含 isMainCDiskDir 语义）。
- 新 fx/fix-rows.js：fixRowHTML(item) 修复结果行共享（生成页 onApply 与
  IDE onApply 复用行结构——Standards 判断项「onApply 与 fixRenderResults
  重复建行」部分整改）。
- fixRenderResults(parsed,fixes,round,listEl?,onRowClick?) 参数化：生成页
  缺省（fixToggleSource 行点击）；IDE 面板传 listEl + ideRowClick（打开
  编辑器跳行）。
- **偏移**：IDE 面板 onLog/onBanner/onTelemetry 为空实现（编译输出日志、
  横幅、LLM 用量展示属生成页上下文——IDE 有独立编译面板；不重复渲染）。
- **核心改动**：runCompileOnce/runFixOnce/fixRounds/fixHandleEvent 去掉 cb
  参数改广播；start/continue/runFixOnceCore/runCompileOnceCore/fixRoundsCore
  触发方临时订阅（finally 退订）；FIX_MAX_ROUNDS/导出面不变（check_contract
  钉仍绿）；新增测试「订阅制广播：长驻订阅收到事件（双面板同步）+ 同组去重」。
- **双轴评审整改（H1 阻断级）**：触发方订阅改 subscribeTrigger（原始
  callbacks 对象直接进 fixSubs，has 去重、仅新增才退订）——原 withCbs
  包装新对象导致「长驻 + 触发方」双引用并存 → 事件双发（onApply 重复行 /
  recordLLMUsage 双计 / 生成页双 toast）；单测补触发组单发断言+onBanner
  不双发回归钉。
- **评审语义修正（J5）**：「在此修复」任意目录可见（编译失败非超时即可；
  startFixHere 空 problemText 降级 + anyDir 守卫配套）；「去生成页」需
  isMainCDiskDir。smoke-07 S1/S1.5 双场景验证。
- 测试：node 1076 全绿；smoke-07 17 项全 PASS（S1 非上下文 fix-here 现/
  goto 藏/S1.5 上下文 goto 现/S2 状态流转/轮次条/结果行/回滚+确认+toast/
  双面板同步/感知联动/收起展开/S5 生成页入口拦截）；smoke-03/04/05/06
  回归全 PASS；pytest 53（contract+repo_language）。
- 踩坑：getCodeDir 从 ui/codeeditor.js 导出（不是 codeview.js——签名表
  讹传）；顶层模块错误（import 不存在导出）→ 全页按钮失效——诊断用 CDP
  Runtime.exceptionThrown 捕获 + Network.setCacheDisabled 后 reload 复查。
