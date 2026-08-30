# 走查发现：生成主流程（子代理 3974a24d 报告，只读）

范围：赛题预读 → AI推荐 → 模块清单/多实例 → 引脚板图点选 → main.c骨架 → 输出并生成 → 修复中心 → 修订与深化（任务推进/参数速调/交付）。共 23 条，交叉验证，未改文件。

## P0（风险最高）
1. 覆盖式重生成无确认：ui/generate-revise.js reviseApply()(306-351) 无 confirmModal（对比 reviseRollback():445-450 有 danger 确认）；按钮 index.html:2426；事件文案 :326「重生成中…（覆盖式重建输出目录）」。修法：reviseApply 开头加 danger confirmModal，展示模块集 diff + 「将覆盖重建输出目录 + 已整树备份」。
2. 多实例配置卡游离于步骤系统：index.html:2159(id=card-instance-config, hidden)、:2160 h2 无 step-no；step-state.js:185-187 导航只收带 .step-no 卡；fx/draft.js:18 parseInt 只认整数；generate-pins.js:95-96 仅多实例模块非空才 remove hidden；generate-steps.js:228/95-96 关键/推荐步无 6.5。修法：6.5 卡配非数字 data-step 纳入提示（步骤6卡顶部徽章/引导），或未配实例计入摘要「还差」。

## P1
3. 平台切换静默清空下游（已选模块+多实例+引脚绑定）无确认：ui/generate-recommend.js:95-101 switch 分支清 selectedSlugs/expanded/warnings+resetPinState+resetInstances，仅 :87 防 same 重按。修法：先 confirmModal「切换平台将清空已选模块/引脚/实例，继续？」。
4. 改题面静默作废下游+残留撕裂：ui/generate-recommend.js:264-269 problem input→clearTopicPreread；:286-300 只 unmarkSteps[2,5..12]+清预读/评分点，不清 rec-list/selectedSlugs/引脚/实例。修法：改题面同步清结果/选中/引脚渲染，回显「题面已变更，请重新预读/推荐」。
5. 「全部还原默认」无确认即清空全部绑定：ui/generate-pins.js:815-818 btn-pin-reset 直接 pinBindings={};pinUnbound=new Set()；该按钮有任意绑定即显示(:470)。修法：confirmModal 或 toast「已将 N 个绑定还原默认」。
6. 实例配/清/删脚不触发步骤7同步：ui/generate-pins.js assignInstancePin(218-225)/clearInstancePin(209-216)/delInstance(194-200) 只调 renderInstanceConfig+renderPinBoard；renderPinBoard(551) 不调 renderPinCard(含 syncStep7@505)；对比 bindRole(889)/unbindRole(871) 调 renderPinCard/syncStep7；fx/draft.js step7DoneState 依赖 instBound(99-103)。修法：三处实例函数补 syncStep7 或改调 renderPinCard。
7. 预读失败按钮卡「AI 预读中…」：ui/generate-recommend.js:317-342；:322 设 spinner，成功 :334 重置「重新预读」，catch(:336-337)/finally(:339-341) 不重置。修法：finally 重置为「预读题面」+disabled=false。
8. 上传并抽取文字无加载反馈：ui/generate-recommend.js:120-128 btn-upload 无 disabled/spinner，upload-msg 仅开始清空 :122。修法：点击即 disabled+「抽取中…」，可复用 makeProgressPanel。
9. 赛题预读长任务无进度/无取消：ui/generate-recommend.js:317-325 单选 apiPost 仅 spinner；对比 :661-716 makeProgressPanel（round 轮数+进度条+双计时+llm_telemetry）。修法：预读复用 makeProgressPanel，或至少加「AI 正在读题面…」+取消。
10. 步骤6「已就绪」只看 selectedSlugs：ui/generate-recommend.js:892 renderSelected：selectedSlugs.length 即 markStepDone(6)；:870-882 runExpand 失败仅 $("expand-msg").textContent=e.message 不撤销步骤6。修法：门槛改「展开成功且 expanded 非空」，失败升级警告盒+markStepUndone(6)。
11. 第11步默认落任务推进页签但内容被「修订」加载上下文挡住；刷新不自动回读：ui/revise-tabs.js:12 active="tasks"；fx/revise-tabs.js:9 REVISE_TABS[0]="tasks"；上下文仅经 reviseLoad(ui/generate-revise.js:107)；index.html:2441 tasks-empty-hint 引导去修订加载。修法：生成成功/revise-context-loaded 后自动 reviseLoad(reviseCurrentDir())，或把「从当前会话加载」按钮放进任务推进空态。
12. 裸 backup_id 暴露用户（两处）：ui/generate-tasks.js:516 renderIdeaFixResult「备份：<span class=slug>+backupId」；fx/params.js:106 paramResultHTML 同款；对比 fx/task.js:1039-1043 taskChangesHTML 只「已备份·回滚按钮」。修法：删裸 id 只留「已备份·回滚」。
13. 「深化」三入口命名打架：「执行后深化」勾选 / 按钮「直接深化(快速兜底)」/ 任务推进「逐步深化」，都走 reviseRunDeepen：index.html:2424/2427/2446；ui/generate-revise.js:390；差异藏 :2449 details。修法：统一命名定位，任务推进顶部加「何时用逐步/何时用直接兜底」。
14. 分钟级长任务无取消/无超时/无进度（拆解/执行/深化/参数/AI对话）只有一行「…(分钟级调用，请等待)」：ui/generate-tasks.js:930；ui/generate-revise.js:290；fx/params-chat.js:90；SSE 运行器 ui/generate-revise.js:190 仅「连接中断」提示「可安全重试」无取消路径。修法：加取消（AbortController），或至少显示已耗时时长+「可安全离开/重试」。
15. 桌面选项文案「同名目录自动加时间」与行为不符：index.html:2241；真正加时间的 unique_desktop_topic_dir generation_output.py:109-133 已 [DEPRECATED]；webapp.py:1702-1714 新裁决 exists→400 或 .bak+覆盖；ui/generate-core.js:610-631。修法：删「自动加时间」，改「同名完整工程会先弹确认，备份为 .bak 再覆盖；同题换平台自动用带平台后缀新目录」。

## P2
16. 「展开依赖并检查平台」无进行中反馈按钮不禁用可重复点：ui/generate-recommend.js:870-882 runExpand 先清 msg/await/成功才 render；:884 未 disabled。修法：await 期间 disabled+「正在展开依赖并检查平台…」。
17. 删除已选模块/推荐 chip 后静默清空「展开+平台警告」：ui/generate-recommend.js:578-583、:941-950 expanded=[];warnings=[]、:973-976 expanded 空则不渲染 #warnings。修法：选择集变化后仍有选中则自动 runExpand() 或显示「展开已失效，点此重新检查平台」。
18. 两个骨架按钮外观完全一致差异藏折叠 details：index.html:2215-2216 两按钮同 primary+code；差异 :2211-2212；ui/generate-core.js:48-51 SKELETON_MODES。修法：按钮下加一行短说明。
19. 生成成功即自动滚到步骤10并自动开跑编译，结果区被挤出视口：ui/generate-core.js:133-134 scrollIntoView+setTimeout(startFixCenter,100)；:120-123 结果写步骤9；ui/generate-fix.js:281-315 running/success/fail 写步骤9 #compile-banner。修法：自动编译不抢滚屏，停步骤9结果面板，修复中心仅给「自动编译中」提示。
20. 无工具链 notool 提示浅且指错方向：index.html:399-401 .notool 浅灰细线；ui/generate-core.js:136「可在设置页填 uv4_path/gmake_path」；ui/generate-fix.js:199-204、:220-225。修法：notool 横幅补「无工具链可用修复中心『开始修复(贴文本)』粘贴 IDE 报错」+样式提亮。
21. 手动输出目录已存在且非空，硬检查不拦：fx/readiness.js:15-16 硬检查只校验 !!outputDir；:82-90 occupied 为 soft 软警告；webapp.py:1771-1785 occupied verdict。修法：occupied 升级硬阻断，或后端拒绝时给「清空该目录/换个位置」入口。
22. 「检查能否生成」软 ⚠ 让新手误以为没就绪，且无「都就绪→点生成工程」桥接：fx/readiness.js:20-52 readinessSoftChecks 产 ⚠；readinessRowHTML soft→⚠；ui/generate-readiness.js:52-61 硬+软拼无「去生成」汇总行、:146-149 点击仅 toggle。修法：面板顶部加绿色总结「硬判据就绪→点生成工程即可」；软 ⚠ 改中性「可选项」。
23. 术语表漏 自备/词表/重推/选型/补问 等黑话：fx/glossary.js:7-22（无这些词）对比 index.html:2127「库外建议需自备(不进工程)」、fx/recommend.js:35「词表推荐方案」/:75「选型参考」、index.html:2123「Q&A 修改后重推」。修法：术语表补词。

## 只做 5 件事排序（风险×频率）
1. 覆盖式修订加确认弹窗（P0-1）——最高数据丢失风险。
2. 6.5 多实例卡纳入步骤系统/加引导（P0-2）——主流程最大发现性死胡同。
3. 平台切换静默清空下游加确认（P1-3）——第二处数据丢失风险。
4. 分钟级长任务加取消/进度（P1-14）——最影响顺畅度。
5. 「全部还原默认」加确认（P1-5）——第三处数据丢失风险，绑定配置易误点清零。
