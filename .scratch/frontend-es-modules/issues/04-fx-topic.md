# 04 — topic 域模块化：fx/topic.js（17 函数）

**要做什么：** 题库全部被测试纯函数迁入 `static/js/fx/topic.js`，topic-browser / topic-cards / topic-detail / topic-edit 四个测试文件改为 import；页面题库 tab 行为零变化。

**被谁阻塞：** 01（core.js）

**状态：** ready-for-agent

- [ ] 新建 fx/topic.js：topicDanglingGroups / topicHasNotes / topicFilterEntries / topicSortEntries / topicStats / topicStatsText / topicGroupVocabulary / topicHealthText / topicChipRowHTML / topicCardHTML / topicDetailHTML / topicPagesHTML / topicPagesErrorHTML / topicEditHTML / topicEditValidate / topicEditPayload 及域内常量；esc 从 fx/core.js import；尾部 window 桥
- [ ] index.html 删除上述函数定义；加载 `<script type="module" src="/js/fx/topic.js">`
- [ ] topic-*.test.mjs 四个文件改 import（fx/topic.js + fx/core.js）
- [ ] `node --test` 全绿；冒烟题库 tab
