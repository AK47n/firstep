# 07 — 右侧栏收起：大纲/搜索贴右缘 40px 竖向轨道（展开 ⇄ 收起）

**要做什么：** 「代码」tab 右侧栏（大纲/搜索）支持收起——默认展开 300px；
收起时机 = 展开态点当前活动页签（大纲或搜索），收起后仅留贴右缘 40px 的
竖向页签轨道（writing-mode: vertical-rl），点击轨道条目重新展开并切到对应
面板；Ctrl+F 强制自动展开（聚焦查找框需要面板可见）；收起状态
localStorage 持久化，刷新保持。用户原话：「右边的大纲和搜索那一栏做成收起
的形式，可以向右贴边收起不影响视野」。

**被谁阻塞：** 无（纯前端布局小改，06 顶栏移除后代码区起点已定）。

**07c 增补（用户反馈后追加）：** 用户反馈「代码第一行上面有一行啥也没有的
空行，这行有什么意义吗」——根因 = `.code-file-path` 信息条空态仍占 30px
（动作按钮全 hidden：普通 .c 未编辑时「编辑源码/返回预览/保存」全隐藏）。
修复 = 空态折叠 `.empty`（display:none）：判定与按钮可见性同源（在
ui/codeview.js onActiveTabChanged 回调内 `[btn, editMd, save].some(!hidden)`
→ toggle empty），同步点唯一——所有按钮可见性路径（openEditorFile /
setMdMode / applySavedState / closeTab）均经 notifyActive 汇聚到该回调，
不引入 :has()（无仓库先例）；CSS 增量 `.code-file-path.empty { display: none; }`。
冒烟 smoke-07 8 项全过（未编辑折叠/代码区紧贴标签条 gap<4/脏时出现/
保存后重折叠/md 两态往返显示/关活动 tab 折叠）；smoke-02/03/04/05/06
全量回归全绿（70 项）；node 996 全绿。

**状态：** resolved

**07b 增补（用户反馈后追加）：** 用户反馈「这个收起方式没有任何提示，搞这么神秘」——加显式「收起 »」按钮常驻侧栏 tab 条右端（title 说明收起后右缘出现竖排的大纲/搜索按钮），「点活动页签收起」降级为快捷方式（保留）；rail 竖排按钮 title（展开大纲/展开搜索）已有；CSS/JS 增量各一处（.code-side-collapse + 单点绑定，独立于 [data-code-side] 三分支，避免与收起按钮语义混淆）；smoke-06 追加 4 项（按钮常驻/点击收起/rail title 提示/最终收尾）共 18 项全过；node 996 全绿。

**实现笔记：** 布局单源 = `.code-layout` grid 第三列改为
`var(--code-side-w, 300px)`，收起 = 类 `.side-collapsed` 把变量压到 40px
（grid 联动、编辑区自动吃满、无 JS 宽度计算——与树调宽
`--code-tree-w` 先例同族）；CSS 只加 `.code-side-rail`（默认 display:none，
收起态 flex 列向 + `.code-side-tabs`/`[data-code-side-panel]` display:none）
与 `.code-side-rail-btn`（竖排按钮，on = accent）。JS 在 ui/codeview.js：
`activeSide` + `setCodeSideCollapsed(collapsed, persist)` + 键
`firstep.codeSideCollapsed`（"1"=收起）+ `restoreCodeSideCollapsed()`
（initCodeViewer 调用）；点击语义三分支——收起态点轨道条目 = 展开并切换、
展开态点活动页签 = 收起、展开态点非活动页签 = 仅切换；Ctrl+F 追加
`setCodeSideCollapsed(false, true)`（评审自查：聚焦隐藏输入框是死胡同）；
持久化走 localStorage 只进胶水层（fx 无副作用约定同 firstep.codeTreeWidth
先例）。测试：smoke-06 新增 14 项（初始展开/点活动页签收起/rail 可见 40px/
键="1"/编辑区吃满 [890→1150]/点 rail 搜索展开/键="0"/tab 条 on 跟随/
再收起/Ctrl+F 自动展开+聚焦/非活动仅切换/收起态仍可编辑/收尾展开态）；node
tests/js 996 全绿；smoke-02/03/04/05 全量回归全绿（66 项冒烟）。

- [x] 收起/展开：展开态点活动页签收起（rail 出现、面板与页签条隐藏、右列 40px、编辑区吃满）。
- [x] 轨道按钮：竖排「大纲/搜索」，点击展开并切换；on 高亮跟随活动页签。
- [x] Ctrl+F 强制展开并聚焦查找框（收起态）。
- [x] 持久化：localStorage `firstep.codeSideCollapsed`（"1"=收起），刷新恢复；收尾脚本归位展开态。
- [x] smoke-06 14 项 + 既有冒烟全量回归 + node tests/js 全绿；提交信息中文。

**07d 增补（历史布局 bug 修复）：** 用户反馈「所有栏底部都能看到代码
编辑器」——根因 = `#tab-code { display: flex; ... }`（工单 code-viewer/04-05
以来的 id 级规则）**压过** `section.page { display: none }`（id 优先级 ≥
class），代码栏从未被页签切换机制隐藏过（旧 CSS 下激活任意栏都双栏同现，
滚动到底部永远能看到代码编辑器）。修复 = 基础规则去掉 display，改
`#tab-code.active { display: flex; }`（未激活回落 section.page{display:none}）。
排查其余 `#tab-*` id 级规则：无同类问题（仅 #tab-code 一处）。护栏 =
smoke-08 13 项（10 栏逐一激活断言唯一可见 section = 目标、代码栏激活
display:flex、切回生成栏代码栏 none、编辑器结构在）；既有 02-07 冒烟 78 项
全量回归全绿；修复前后对照截图 .scratch/code-viewer-editor/
diag-generate-bottom.png（修复后生成栏底部 = 生成页内容，无代码编辑器）。

**07e 增补（信息条初始空态折叠）：** 用户反馈「中间那行黑的空隙不需要留，
直接顶满」——未打开目录/无活动 tab 时 `.code-file-path` 空态 30px 黑带
残留：空态同步逻辑在 onActiveTabChanged 回调内，初始从未触发。修复 =
抽 `syncInfoBar()` 单源 + initCodeViewer 尾部显式调用一次；冒烟 smoke-09
6 项（初始空态折叠/gap<4/空态提示在/开目录仍折叠/开文件折叠/编辑出现）
+ smoke-07/08 回归全绿 + node 996 全绿。

**07f 增补（代码栏视口锁定：用户反馈「这个代码栏不要下拉到底，点开看就能
看到，你下拉到底就看不到了」）**：根因 = 代码栏在 `main` 之后，而
`main { margin: 20px auto }` 在代码栏激活（main 内 9 个 section 全
display:none、高度 0）时塌缩成 20px 空隙把 `#tab-code` 推下 20px——其
`height: calc(100vh - var(--header-h))` 按顶部 48px 计算，底部溢出 20px →
body/html 可滚，「下拉到底代码栏滚出视口」。修复 = ① DOM 移动：`#tab-code`
从 `</main>` 之后移到 `</header>` 之后（header 直连，空隙归零，top=48、
bottom=视口底，body 高度=视口）——md/JS 全为 id+类选择器零顺序依赖；
② `#tab-code.active ~ main { margin: 0 auto; }` 兄弟选择器（代码栏激活时
main 空置边距归零，消除 html 层面 20px 塌缩余高；非代码栏激活时 main 正常
margin 不变）。验证：scrollHeight=clientHeight（不可滚）、diag 高度链
top48/height852/bottom900；smoke-02~09 共 97 项全回归全绿 + node 996。
