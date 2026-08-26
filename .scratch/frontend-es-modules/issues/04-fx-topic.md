# 04 — topic 域模块化：fx/topic.js（16 函数）

**要做什么：** 题库全部被测试纯函数迁入 `static/js/fx/topic.js`，topic-browser / topic-cards / topic-detail / topic-edit 四个测试文件改为 import；页面题库 tab 行为零变化。

**被谁阻塞：** 01（core.js）

**状态：** resolved（2026-08-26；JS 416 全绿 + 浏览器冒烟 11/11）

## 实施记录

- 数字修正：工单标题「17」系估计，实际迁移 = 16 个纯函数（topicHasNotes / topicGroupVocabulary / topicDanglingGroups / topicHealthText / topicFilterEntries / topicSortEntries / topicStats / topicStatsText / topicChipRowHTML / topicDetailHTML / topicPagesHTML / topicPagesErrorHTML / topicEditHTML / topicEditValidate / topicEditPayload / topicCardHTML，以 4 个测试文件 Union 提取清单为准）；域内常量无。
- fx/topic.js：函数体逐字搬移 + docstring 全保留；esc 单源取自 fx/core.js（topicChipRowHTML / topicDetailHTML / topicPagesErrorHTML / topicEditHTML 用）；尾部 window 桥 16 名。
- **topicCardHTML 保留函数体内局部 esc，不合并 core esc**（与 01 的 cHighlight 先例相反）：局部 esc 有 null/undefined→"" 兜底，core esc 为 String() 直转（null→"null"）；topic-cards.test.mjs「空字段兜底：key/year/problem_text 缺失不抛错」（test:86-91）显式断言 `topicCardHTML({})` 渲染空 key/year——合并会破坏该测试。注释已标注原因（防后人误合并）。
- index.html：主体 module 顶部 import 行追加（reference.js 之后，16 名）；CRLF 感知行区间删除 300 行（1-based 7597..7896 为搬移块，0-based 边界校验「prev 为空行 + next 为 // 按钮图标」通过），替换为「已迁至 static/js/fx/topic.js（工单 04）」双行注释；胶水留内联：topicFilterContext() / topicUI / topicEntries / topicGroupVocab / topicLoading / initBtnIcons IIFE / renderTopics 等。
- 测试改造（4 文件整头替换）：topic-browser（html 仅抽取用 → fs/path/url/html/esc 全删）；topic-detail（保留 fs/path/url/html——118-120 有 CSS 结构断言 `.topic-detail-problem` / `.topic-pages`；删 esc）；topic-edit（fs/path/url/html/esc 全删）；topic-cards（保留 html——「#topic-grid 容器」结构断言 test:93-98；无 esc）。
- 验证：`node --test "tests/js/*.test.mjs"` 416 全绿；diag.mjs 零 EXC（favicon 404 既有噪音）；smoke.mjs 11/11（含题库 tab 切换）。

- [x] 新建 fx/topic.js：topicDanglingGroups / topicHasNotes / topicFilterEntries / topicSortEntries / topicStats / topicStatsText / topicGroupVocabulary / topicHealthText / topicChipRowHTML / topicCardHTML / topicDetailHTML / topicPagesHTML / topicPagesErrorHTML / topicEditHTML / topicEditValidate / topicEditPayload 及域内常量；esc 从 fx/core.js import；尾部 window 桥
- [x] index.html 删除上述函数定义；加载 `<script type="module" src="/js/fx/topic.js">`
- [x] topic-*.test.mjs 四个文件改 import（fx/topic.js + fx/core.js）
- [x] `node --test` 全绿；冒烟题库 tab
