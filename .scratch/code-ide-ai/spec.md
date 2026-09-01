# IDE × AI 协作（选中提问 + AI 改 + IDE 内修复 + 行级 diff 泛化）

> 会话/系列 slug：code-ide-ai。立项：2026-09（用户拍板：按 code-ide-flow 范围外评估
> 建议推进——C（C1 选中提问 + C2 AI 改）一期 → B 全配（fixLoop 进 IDE）→
> 非 main.c 行级 diff；第 8 步合并与 IDE 主驾驶舱化明确不做）。
> 前置：code-ide-flow 一期（基线感知/变更面板/一键修复直达）已完成并提交。

## 问题陈述（二期三块，承接一期）

一期打通了「AI 写盘 → IDE 感知 → 变更可视 → 一键修复直达」，但 IDE 内仍
无法**主动指挥 AI**：

1. **AI 交互不在 IDE 里**：想基于某段代码问 AI / 让 AI 改，要切去生成页
   任务推进（全局商量/任务），与编辑器割裂。
2. **修复进度仍要切页看**：一键修复直达只做到「跳转后自动开始」，循环进度
   画面在生成页，IDE 用户看不到；修复中心状态机与 IDE 无共享。
3. **AI 改了非 main.c 不可见行级变化**：变更面板只有 main.c 行级 diff；
   修复/任务/深化改的 .c/.h 只能看到文件级「变」徽章。

## 方案（一期 / 二期 / 三期）

### 一期：C1 选中提问 + C2 AI 改（核心）

**C1 选中提问**：
- 编辑器（textarea 三明治）选中文本 → 选区浮动按钮「问 AI」（VSCode/
  Copilot 风格：定位于高亮层选区末行 span 右端上方——高亮层逐行 span 已存在，
  行定位零成本；无行 span 兜底 = 编辑器工具条按钮，实现时以 DOM 实测为准）。
- 点击 → IDE 底部对话面板（`#code-ai-chat-panel`，与编译/变更面板同型并列、
  可折叠）打开，用户问题自动附带**选区引用**，消息发送走既有
  `/api/tasks/idea/chat/send` 契约（{output_dir: 当前代码目录, history}，
  服务端落 user+assistant 两条 + 历史落盘 .contest_idea_chat.json）；
  历史读盘 = `/api/tasks/idea/chat/read`。**零新增端点**。
- 选区上下文**前端拼装**进 user 消息（本地单用户工具，直接嵌入文本；
  格式 `【代码引用 · src/main.c · 第 10-25 行】\n```c\n<选区>\n````）——
  消息渲染为引用卡片样式（可折叠代码块）。

**C2 AI 改（结构化 diff 应用）**：
- **契约（spec 级定稿）**：AI 回复中若含改动，输出结构化 JSON diff 块
  （fence 内 `<DIFF>{...}</DIFF>`，与既有 main_diff 同构）：
  `{path, stats:{additions,deletions,hunks}, hunks:[{line,title,lines:[
  {kind:"ctx"|"del"|"add", text}]}]}`；`path` 为相对当前代码目录的路径。
  前端 fx 解析器严格校验（结构/kind 枚举/path 合法/行号范围）；无 diff 块
  = 纯回答。
- **新端点 `/api/code/apply-diff`**（POST）：`{dir, path, base_mtime_ns,
  hunks, preview: bool}`——hunks 应用对偶后端 fix/apply 既有算法（**单套
  实现在后端**，不做前端重建——spec 决策：与 fix center/deepen 共享后端
  应用逻辑，避免 mainc-diff 式双实现漂移）；`preview=true` 只算不写返回
  `{new_content, stats}`；写模式校验 base_mtime_ns（409 与 save 同口径）；
  非法 path / hunk 越界 / 行号不对齐 → 400 中文错误。
- **交互闭环**：解析到 diff 块 → 先读盘（/api/code/file 取当前内容与
  base_mtime_ns）→ preview → **确认模态**（渲染复用 fx/diff.js
  mainDiffHTML——diff 计算用主路径 fx：preview 返回 new_content 后前端
  maincDiffCompute(旧, 新) 生成 hunk 展示；确认/取消）+ 写盘守卫
  （guardCodeTabWrite，作用域=当前代码目录，不改目标文件不改语义）→
  确认 → apply（写）→ toast + 立即触发 `checkCodeDiskChanges()`（磁盘
  感知无缝显示变更面板——一期成果直接复用）。
- 应用后目标文件若为打开中的标签：由二期一致的磁盘感知自动重载（干净）/徽章
  （脏）——**不特殊处理，走统一事实源**。

### 二期：B 全配（fixLoop 进 IDE，双出口）

- fixLoop 状态机（generate-fix.js startFixCenter/continueFixCenter/
  fixRounds/fixLoop）**抽为共享模块**（ui/）：流程逻辑去 DOM 化——状态更新
  经事件回调广播（onState/onErrors/onApply/onRound/onTelemetry 等）；
  generate-fix.js 变薄（绑定生成页 DOM 回调，第 10 步修复中心照旧——
  打勾保留）；新 UI 簇 = IDE 底部第三面板 `#code-fix-panel`（与编译/变更
  面板同型并列）绑定同回调，编译失败面板按钮增设「在此修复」（IDE 内跑
  B低配的跳转按钮保留——双入口并存）。
- **单实例**：fixLoop.running 防重入沿用（已有，跨出口天然共享）；双面板
  同时打开时状态同步（同回调广播，各自渲染）。
- 写盘守卫语义不变（guardCodeTabWrite(WG.fix)——IDE 内即写盘现场，更自然）。
- 生成页修复中心按钮态（btn-fix-center disabled 判据）不动。

### 三期：非 main.c 行级 diff（按需内容快照）

- **快照规则（折中定案）**：基线 store 每文件条目增可选 `content` 快照
  （cap 256KB/文件，超限不存）；**仅「曾经通过 IDE 打开过的文件」持有**——
  打开时若文件 mtime == 基线 mtime（未变）→ 快照 = 读盘内容（零额外读盘）；
  基线推进（onFileSaved/树操作/清空确认）对该文件 re-fetch（≤cap 才存）
  保持快照新鲜；mtime 已变 → 保留旧快照（diff 基准 = 用户确认版）。
  从未打开过的文件 → 无内容快照 → 无行级（文件级变更照常）——存储与读盘
  成本与「打开过的文件才有行级」等价。
- 渲染：change-panel 行级 diff 区从「仅 main.c」泛化为「任何 modified 且
  有 content 快照的文件」——fx/change-panel.js 与 ui/codeview.js 的
  isMainCPath 限制移除（判定改为 entry.snapshotAvailable）；
  mainc-diff.js 无需改（LCS 通用）。main.c 特例语义（快照必然存在）保持。
- 成本：基线 store 每目录仅多存「打开过的 ≤256KB 文件内容」——上界
  8 目录 × 开过的文件数，实际远低于配额；evict 整目录连带（沿用）。

## 用户故事

1. 作为用户，我在 IDE 里选中一段代码 → 点「问 AI」 → 提问得到回答，希望
   不需要切页、上下文自动带上选中代码（含文件/行号）。
2. 作为用户，我让 AI 改代码 → 希望先看到改动预览（diff）→ 确认后应用，
   未保存编辑经守卫保护；应用后 IDE 磁盘感知照常显示变更。
3. 作为用户，我在 IDE 内编译失败 → 希望直接「在此修复」看到循环进度
   （状态/错误列表/轮次），不必切生成页；生成页修复中心仍可用（同一循环，
   单实例）。
4. 作为用户，AI 改了非 main.c 的 .c/.h → 我希望变更面板里也能展开行级
   diff（只对我在 IDE 里打开过的文件，未打开的给文件级）。
5. 作为用户，AI 改坏了 → 我希望有确认/取消入口（预览模态取消=不写盘），
   且写盘有 mtime 冲突保护（409 与 save 同口径）。

## 实现决策（汇总）

- **契约复用最大化**：对话走 idea/chat/send|read 三端点（零新增）；diff
  渲染复用 fx/diff.js + mainc-diff.js（零新渲染器）；感知/守卫/三选冲突
  全复用一期。新端点仅 `/api/code/apply-diff` 一个（hunk 应用是**新业务**
  ——后端单套实现，前端只解析契约 + 预览 + 确认）。
- **AI 输出 = 结构化 JSON 而非 unified 文本**：LLM 输出 JSON 更稳、校验器
  便宜、与 main_diff 同构有现成验证语义；版本策略=输出契约版本号字段可后加
  （v1 起）。
- **对话面板与全局商量区分**：IDE 对话 = 代码上下文的轻量问答（附选区），
  落盘同一 .contest_idea_chat.json（目录维度共享——同目录生成页全局商量
  历史可见，语义「围绕该工程"的对话」一致）；不做独立文件（避免双份历史
  割裂）。
- **hunk 应用对偶约束**：apply-diff 的应用算法与后端 fix/apply、deepen
  共享/对齐（spec 决策：复用后端既有 apply 函数族，不复制）；preview 不落盘
  无副作用。
- **「在此修复」双入口**：IDE 第三面板 + 生成页第 10 步修复中心共存；共享
  状态机，单实例锁；不做「生成页入口移除」。
- **快照折中**按方案三期（打开过的文件才有行级 diff）。

## 测试决策

- **node 单测（fx 主 seam）**：AI diff 契约解析/校验器（合法/非法/无块/
  kind 非法/path 越界）；选区上下文拼装格式；hunk → 行号对齐辅助（若有
  前端校验逻辑：apply 前的行对齐检查纯件化）。
- **pytest（apply-diff）**：preview 不落盘 / 写成功 mtime 推进 / 409
  base_mtime 不匹配 / hunk 越界 400 / 非法 path 400 / stats 准确性；
  现有全量回归保持绿。
- **CDP 冒烟（smoke-05+）**：①选区浮动按钮出现 → 面板打开 → 发送（页面
  fetch 桩：polish-chat probe 先例——劫持 /api/tasks/idea/chat/send
  返回假 chat）→ 消息渲染；②回复含 DIFF 块（桩返回编好文本）→ 预览模态
  出现（diff 渲染可见）→ 取消不写盘 → 确认写盘 → 磁盘感知变更面板出现；
  ③B 全配：IDE 内「在此修复」→ 面板状态流转（无工具链 → notool 早退提示
  为界，smoke-04 同款）；④三期：打开非 main.c 后外部改 → 面板行级区出现。
- 后端改动（apply-diff）后必须重启 webapp（教训：02 曾因未重启冒烟全红）。

## 范围外（本期不做）

- 第 8 步 main.c 编辑框与 IDE 编辑器合并（风险高、收益中，已有「查看工程」跳转）。
- IDE 主驾驶舱化（生成流程嵌入布局）。
- 流式对话（idea/chat/send 为同步端点，先例如此）。
- 多文件一次应用（DIFF 块单 path；多文件 = 多轮）。
- AI 直接新建文件（范围=修改既有文件；新增走 file tree 新建 + 对话建议）。
- 对话历史与生成页全局商量的 UI 合流（共享落盘，但 UI 各自渲染）。

## 评审确认

**s1（工单 01/03 双轴评审后）**：
- 01：isSafeRelPath 复刻后端 is_unsafe_path 四规则（entry_store.py:145-152）——
  前端预筛、后端 _resolve_in_root 权威兜底；锚点守卫（每 hunk ≥1 非 add 行）
  为拆 02 后追加决策；line↔lines 不做解析器钉死（后端 old 段匹配为锚、
  line 仅展示语义——行号错位天然免疫，01/02 两工单闭环）。
- 02：unified 语义（替换 = del+add、插入 = ctx+add）；应用以 old 段整行
  精确匹配为锚；「行号不对齐→400」验收文本过期（实测 line=999 内容匹配仍
  成功——与锚点设计一致，保留）；_apply_hunks_to_lines 新写必要（后端无
  hunk-apply 既有函数；单套实现不复制）。
- 03：引用卡片（user 消息中【代码引用…】+ 围栏 → details 折叠卡）为 C1
  本体交付（验收 2）；busy 复用全局 aiAction 横幅（crate 先例 params-chat
  同）；「首次展开读历史」实现为「目录打开即读」（打开即见历史，展开纯
  UI，体验更优——偏离记录）；选区 endLine 以 \n 结尾时 -1（与 caretLineOf
  语义对齐）；浮动按钮「右端贴合行」而非字面「上方」（VS Code 式）。
- 面板与生成页全局商量 UI 不合并（范围外最后一条）；气泡渲染跨簇同构
  （fx/task.js globalChatMessageHTML）暂不抽共享件（task 版带三操作按钮、
  语义不同）。

**s4（工单 04 双轴评审后）**：
- 守卫范围扩为 anyDir：AI diff 应用在 IDE 内发起（不限于生成上下文目录），
  脏标签都该先确认——guardCodeTabWrite 加 opts.anyDir（smoke 实测样本目录
  非上下文时原语义直通、验收 3 无法满足，规范语义实为「任何目录」）。
- 409 优先顺序：apply_code_diff 写模式 base_mtime_ns 校验提前到 hunk 应用
  之前——外部改盘后 hunk 通常也不再匹配，报 409「已被外部修改」（与
  save_code_file 同口径）而非 400「未匹配」（用户无法区分谁改了什么）；
  preview 无需 mtime 不变。
- 成功 toast 用 kind "ok"（全仓库 ok/error/info 约定；"success" 渲染
  .toast.success 无图标——踩坑记录）。
- 守卫经动态 import 破静态环（code-write-guard→codeview→code-ai-chat）。
- DIFF 剥离占位 = aiChatMessageHTML assistant 分支（stripDiffBlock 私有）；
  按钮注入在 ui 层（renderPanel 后 attachDiffButtons，parseAiDiff 单源）。
- 评审子代理超时中断（60+ 分钟无产出）→ 自查收尾（读全部改动文件 +
  git diff 核对 + 全量测试复核），判断项：setSendEnabled 复用
  （input 监听处原重复判定，已修）。

**s5（工单 05 双轴评审后）**：
- 回调集实现为 13 个（issue 列的 onErrors(list)/onRollback 有出入）：
  onErrors(list) 语义分拆 onError(text)+onList(parsed,fixes,round)（事件
  触达粒度不同）；onRollback 未入核心——回滚=壳层交互+API 调用，非状态机
  事件（onDone 的 backup_id 驱动回滚按钮态）——两处均记录为可接受偏离。
- 手动贴文本模式（runFixOnceCore）单实例化（Standards 整改）：原基线手动/
  自动循环可并发（互相清空共享态 fixLoop.resume/lastFixDone）；改后运行中
  触发抛「修复循环进行中」——写工程文件的动作为何不能并发（同 fixLoop.
  running 语义）。
- check_contract 3 结构钉（FIX_MAX_ROUNDS regex / 轮上限文案 / resume 快照）
  指向核心模块 fix-center-core.js（issue「导出面保持」的钉迁移）。
- 核心用相对路径 import fx 纯件（区别于 ui 簇 /js/ 绝对路径）：node 直测
  需要；浏览器相对 URL 解析等价（fx 内部同先例）。
- 判断项记录不整改：Middle Man（*Core 转发壳——导出面保持）：
  Speculative Generality（*Core 三件套 + 回调为 06 预留——issue 字面）；
  onApply 与 fixRenderResults 重复建行（既有基线）；fixLoopSnapshot 现仅
  测试用（06 将用）；核心经 onState 组合用户态文案（Feature Envy 轻——按
  工单决策核心管状态+文案）。

**s6（工单 06 双轴评审后）**：
- 核心广播改**订阅制**（spec 二期「双面板同时打开时状态同步」落地方式）：
  subscribeFixCenter(cb)+退订；事件全走 emitAll。**H1 整改（双轴评审一致
  找出）**：触发方 input.callbacks 经 subscribeTrigger **原始对象**临时订阅
  （fixSubs.has 去重 + 仅本次新增才退订）——原 withCbs 包装新对象使「长驻 +
  触发方」双引用并存 → 事件双发（onApply 重复行 / recordLLMUsage 双计 /
  生成页双 toast）；修复后同对象 Set 天然去重（单测「同组去重」补触发组
  单发断言 + onBanner 不双发回归钉）。
- **J5 语义修正（评审后）**：「在此修复」显隐 = 编译失败且非超时（**任意
  打开目录**均可——与 startFixHere 空 problemText 降级、guardCodeTabWrite
  anyDir 语义一致）；「去生成页一键编译修复」= 编译失败且非超时 **且
  isMainCDiskDir()**（去生成页修复中心需要赛题/AI 上下文）。smoke-07 S1 改
  为非上下文场景（fix-here 现 / goto 藏）+ S1.5 上下文场景（goto 现）。
- 入口双按钮实现为**并列双按钮**（issue 06 措辞「替代为二选/旁」选旁）。
- fix-here/continue 守卫用 **anyDir:true**（与工单 04 AI apply 同语义——
  IDE 内发起任意目录防脏标签覆盖；生成页入口保持上下文目录语义）。
- fixRenderResults 参数化（listEl/onRowClick）供 IDE 复用——生成页行点击
  fixToggleSource、IDE 行点击 openEditorFile+editJumpToLine（语义不同，
  共享重建逻辑而非点击行为）；J2 记录不整改（fixRenderResults 仍
  createElement 建行——待修复/新增与已修复/跳过标签语义不同，强行合并需
  额外参数——部分整改记录）。
- IDE 面板 onLog/onBanner/onTelemetry 空实现（渲染属生成页上下文）——
  记录偏离（banner 文案在两端点已由核心 onBanner 广播，仅 IDE 侧不渲染）。
- 单实例锁的烟测边界：smoke-07 S5 验证生成页入口存在与拦截文案；循环中
  再触发被忽略由核心单测（fix-center-core.test.mjs「单实例：running 中
  第二次触发被忽略」）覆盖——双层验证，未在 smoke 复现竞态。
- fx/fix-rows.js 补 window 同名桥（fx/*.js 模块约定兼容层——H2 整改）。
- index.html #code-fix-panel 去掉无 CSS 引用的死 class `code-fix-panel`
  （样式走 #id——J6 整改）。
