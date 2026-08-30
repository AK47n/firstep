# 走查发现：反馈机制与横向一致性（子代理 39a06193 报告，只读）

范围：错误提示体系（errors.py + toast/错误渲染）、长任务进度（SSE + progress.js/step-state.js）、确认与撤销、全局一致性、键盘与可达性、视觉层残留。共 23 条。未改文件。

## 一、错误提示体系
1. 【P1】文件系统失败直透 Windows 英文原文，无修复步骤：errors.py:167 `_ErrorEntry((OSError,), 400, lambda exc: f"文件操作失败：{exc}")`；generation_output.py:203-204 Keil 占用抛 OSError，str(exc) 原样上界面。修法：按 errno/winerror 分派（WinError 32 → 关闭 Keil μVision；Errno 28 → 磁盘空间不足；PermissionError → 只读/无权限）。
2. 【P1】内部长错误只走 toast 2.5s 即消失不可复制：ui/delivery.js:51-52 catch 仅 toast；app.js:116 `setTimeout(()=>el.remove(),2500)`；长文案 events.py:20-23 INTERNAL_ERROR_HINT。同类 toast-only：reference.js:212、pdf.js:147/162、library.js:402、recent.js:26/48/65。修法：500/长错误改常驻内联块（可复制），或 toast 加复制按钮+延长。
3. 【P2】烧录失败被误判「烧录未就绪」：ui/flash.js:31-34 任意错误（含 500）都进 fx/flash.js:51-58 flashGuideHTML，title 固定「烧录未就绪」（fx/flash.js:54）。修法：仅预期/400 渲染未就绪卡，其它走通用错误卡。
4. 【P2】500 兜底暴露 Python 异常类型名：errors.py:232 `return 500, f"服务器内部错误（{type(exc).__name__}）：{exc}"`。修法：去掉类型名，保留提示+复制反馈。
5. 【P2】SSE 错误终态裸串「请求失败」与 handle() 不一致：generate-revise.js:186、generate-fix.js:308、generate-tasks.js:903、params.js:281 `data.message || "请求失败"`；根因 6 个 SSE 助手各自内联 `err.detail || ("请求失败（HTTP "+resp.status+"）")`（generate-revise.js:180、generate-fix.js:297/340、generate-tasks.js:897、params.js:275、generate-recommend.js:649、master.js:282）。修法：抽 parseError(e) 共享助手。
6. 【P2】backup_id 术语未人话化：fix_errors.py:660（非法的备份编号）/:663（备份不存在）、revision.py:96/99。修法：补人话+下一步（自动回滚备份已失效…）。

## 二、长任务进度
7. 【P1】「让 AI 推荐」进度面板只有跳动秒数：ui/generate-recommend.js:611-620 startRecProgress 清空 rec-prog-text、隐藏 rec-bar 至首条 round 事件；ui/progress.js:19-23 tick() 只写两个时钟；后端首个事件即 round（sse.py:20-23、events.py:29-39 无 start），首次选模 LLM 调用（分钟级）期间无中间事件。修法：发 start 事件带中文阶段标签；立即显示「AI 正在选模块…（可能要几分钟）」。
8. 【P1】修订/参数/编译修复长跑只有一行状态文字无计时：ui/generate-revise.js:290,325-326,403,404-406、ui/params.js:158,200-203、ui/generate-fix.js:235-236,286-287 全一行 textContent；对照 ui/master.js:165-178（批次百分比条）、ui/progress.js:19-23（fmtClock 双计时器）。修法：加「已等待 X 分 Y 秒」秒表（复用 fmtClock）。
9. 【P1】生成端点单次 POST 用「每 2s 轮播 5 个子阶段名」假装进度：ui/generate-core.js:593-598 setInterval 每 1s genStatus(genStageTexts(floor(waitSecs/2))+"（已等待…）")；:599 await apiPost("/api/generate") 非 SSE；fx/generate.js:25-30 genStageTexts(i) 5 句固定轮播（定位母版/写文件等）。修法：改 SSE；短期去掉假阶段词改「正在生成工程（大约需要几分钟）」，否则按 P2。
10. 【P2】LLM 遥测一行小字全是术语：fx/llm.js:5-52 formatLLMTelemetry（:25 未知操作回退蛇形名、:32 HTTP 200、:43-44 请求 xxxB·耗时 xxxms）；消费 generate-recommend.js:685-692、master.js:140-147、generate-tasks.js:931-936。修法：改「诊断信息」默认折叠 + opLabels 中文映射显示「最新：正在选模块」。
11. 【P2】母版提炼首批次前无进度条无「几分钟」提示：ui/master.js:103-121（start/batch_start）、165-178（p.phase==="" 时隐藏 prog-bar）、225-245 startProgress 无提示；对照 generate-tasks.js:1012,930,354 有「（分钟级调用，请等待）」。修法：startProgress 写「正在提炼，可能持续几分钟（逐批处理文件）」。
12. 【P2】推荐「已收敛」把进度条跳 100% 结果还没出：ui/generate-recommend.js:672-676 converged 事件设 rec-bar-fill 100%+「功能需求层已收敛」；finish() 只在 done（:693-700）；events.py:39 converged 非终态。修法：converged 设约 85%+「正在出最终结果…」。
13. 【P2】长跑屏幕（提炼/编译修复/修订深化）无「和 AI 商量」入口：index.html:2469-2471 全局商量（任务推进卡）、2514-2519 问 AI（参数速调卡）、fx/recommend.js:197 和 AI 商量（推荐 chip）；master.js/generate-fix.js/generate-revise.js 进度处理器无聊天入口。修法：加「有问题？去问 AI」链接跳全局商量。
14. 【P2】AI 商量发送后只加一行「AI 回应中…」无计时：events.py:124,128,132 buy_discuss/task_discuss/idea_chat 均同步返回（非 SSE）；ui/generate-tasks.js:644（全局商量：AI 回应中…）、626-661/1282-1303 apiPost 同步无计时器；ui/generate-recommend.js:426-435。修法：加「已等待 X」秒表+思考动画。

## 三、确认与撤销
15. 【P1】覆盖重生成备份 .bak 无恢复入口且二次覆盖静默删旧备份：ui/generate-core.js:615-622 confirmModal 文案「旧工程将先备份为 X.bak」；generation_output.py:198-214 backup_project_dir（:208-212 if backup.exists(): shutil.rmtree(backup) 先删旧备份，单份策略）；成功 toast generate-core.js:630；全站无工程级 .bak 恢复端点/按钮（grep 恢复/restore/undo 全是轮次 rollback）。修法：①确认框 message 加「如需找回旧工程，请到桌面把 X.bak 改回 X」；②生成结果区加「恢复覆盖前备份」按钮（后端加 .bak rename 回原名端点，同款 is_unsafe_path 校验）。
16. 【P2】删最近生成记录/想法草稿无确认无撤销：ui/recent.js:42-51 del 分支 apiDelete("/api/recent/"+id) 直发；ui/generate-tasks.js:782-804 tasksDraftDelete 直接 apiPost 删除；后端 webapp.py:1828-1835 recent_delete 只删记录不删磁盘。修法：接 confirmModal（recent 注明只移除记录、磁盘不受影响；draft 点名草稿前 20 字）+ toast 带撤销。
17. 【P2】删除确认弹窗不统一：工厂 confirmModal：reference.js:203、library.js:393、topic.js:309；手写 overlay：ui/master.js:392-423 openMasterDeleteConfirm、ui/pdf.js:104-128 openPdfTrashConfirm；工厂 ui/confirm.js:16、纯件 fx/overlay.js:19；confirm.js:16-23 默认 confirmText="确认"、danger=true 存在「忘传文案→光秃秃红色确认」风险。修法：迁移到 confirmModal（extra 塞元数据）；默认 confirmText 加 console.warn。

## 四、全局一致性
18. 【P2】第 8 步同卡并列两个主色按钮：index.html:2214-2216 btn-skeleton 与 btn-smoke 均 class="primary" 同 .row。修法：主动作留 primary，自检骨架降级。
19. 【P2】「检查能否生成」按钮非状态化（纯开关）：ui/generate-readiness.js:142-149 initReadinessCheck 只 toggle classList hidden，无 busy/spinner；对照 ui/generate-recommend.js:633-634 btn-recommend 忙碌禁用+spinner。修法：加忙碌态，或改「一键检查并滚动到第一条未就绪项」。
20. 【P2】「已验证」三处含义不同但都绿色：fx/module.js:15/143-146（模块已验证/未验证/硬件绑定）、fx/overview.js:27/77 与 generate-steps.js:168-171（步骤已就绪/默认布线）、generate-tasks.js:258（上板实测通过后标记已验证）；徽章 .badge.ok 绿（index.html:253）、.card-step-status.done 绿（:1447）；第 7 步默认布线用青是有意区分（index.html:1374-1375 注释）。修法：任务「已被验证」改名（如「上板通过」）或统一词汇表。

## 五、键盘与可达性
21. 【P2】顶栏页签不遵循 ARIA tabs 无方向键：index.html:1982-1995 数据 tab 按钮 role="group" 无 role="tab"/aria-selected；切换逻辑 index.html:3210-3215 只 toggle .active；对照 ui/guide.js:56-73、ui/revise-tabs.js:85-91（方向键循环+focus）。修法：加 role tablist/tab + aria-selected + roving tabindex + 方向键；快捷键提示唯一在 index.html:2082 推荐卡副标题。
22. 【P2】大量表单输入无关联 label：index.html:2105(ref-search)、2147(module-search)、2567(lib-search)、2647(ref-filter)、2745(pdf-filter)、2773(topic-filter)、2043(problem)、2232(main-c)、2122(qa-text) 裸 input/textarea；对照 2595/2599/2928-3001 用 label 包裹。修法：加 aria-label 或 label for。
23. 【P2】确认弹窗无焦点移入无焦点陷阱：ui/confirm.js:36-56 keydown 监听+body.appendChild(overlay) 无 .focus() 无陷阱。修法：打开聚焦确认/取消按钮、焦点陷阱、关闭还焦触发按钮。

## 六、视觉层残留
24. 【P2】圆角间距无令牌：.card 8px(index.html:176)、.badge 10px(245)、输入框 6px(185)、input[type=search] 999px(188)、顶栏 nav 999px(136)、.topic-detail-toggle 4px(1200)、.lib-chip 12px(699)、.master-health-pill 999px(1227)、button 默认 6px(198)；间距 button padding:7px 14px(198)、.env-row 5px 0(217)；令牌区 index.html:31-58 只令牌化颜色/阴影/时长，无 --radius-*/--space-*。修法：补 --radius-sm/md/lg/full + --space-*，圆角收敛 4 档：胶囊 --radius-full、卡片 --radius-md、控件 --radius-sm。
25. 【P2】未令牌化裸色值：index.html:1213 .topic-page img background:#fff 硬编码白底（扫描件？）、:144 header active 渐变终点 #8b5cf6、:1314/:1318 .step-dot.current .dot/.done .dot 写死 #001018/#04170c。修法：改用 --panel 等令牌；页面图白底若有意保留加注释。

## 只做 5 件事排序
1. 覆盖重生成 .bak 应用内恢复入口（#15）——唯一旧工程可能被二次覆盖静默删除。
2. 长任务可感知进度（#7/#8/#14）——推荐/修订/参数/编译修复/商量统一「已等待 X 分 Y 秒 + 阶段名」秒表（复用 progress.js fmtClock）。
3. 错误人话化+可复制（#1/#2）——OSError 按 errno 分派中文+步骤；500/长错误改常驻内联块。
4. 删除类补齐确认与撤销（#16/#17）——最近记录/想法草稿接 confirmModal；删除弹窗统一工厂。
5. 生成页进度与状态按钮一致性（#9/#19）——伪阶段轮播改通用文案；检查能否生成加忙碌态。

## 良好实践（非问题）
- ui/generate-recommend.js:654-658 与 ui/master.js:285-289 用 p.finished 正确区分「完成/仍在计算」，终态后流中断不误报。
- 母版提炼（master.js:165-178）批次百分比条+阶段 stepper+日志，全场进度最好，可作对标模板。
