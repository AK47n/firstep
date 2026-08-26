# 09 — 题库 tab + 校对：static/js/ui/topic.js

**要做什么：** 题库 tab 全部 DOM 胶水迁入 `static/js/ui/topic.js`（archive 链接 / 年份 chips / stats / 列表 / 分页 / 详情弹窗 / 编辑弹窗 / 过滤器 / 工具栏 / 词汇表 / 删除 / 校对行编辑器）。`useTopic`（题面载入事务）归生成推荐簇（工单 12），本票**不迁**——题 tab 的「载入到生成页」按钮经 import 调用。**被谁阻塞：** 02（app.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 区段 = 6937-7332：loadTopicArchiveLink 6937 / topicFilterContext 6976 / renderTopicYearChips 6985 / renderTopicStats 6995 / renderTopics 7004 / loadTopicPageState 7043 / renderTopicPages 7057 / viewTopicDetail 7066（弹窗内「载入到生成页」调 useTopic @7088——import 自 ui/generate-recommend.js，工单 12 未迁前先经主体 import 代理名）/ viewTopicEdit 7111 / clearTopicFilter 7166 / initTopicToolbar 7172 / loadTopicGroupVocabulary 7203 / loadTopics 7210 / deleteTopic 7224 / renderProofreadRows 7251 + 校对其余（7251-7332：proofread 状态/按钮/提交，容器 #topic-proofread-rows @1936 markup 在题库 tab）；状态 topicRows 6926 / topicEntries 6971（写作点在 above 函数内，grep 复核）。
- **跳过区**：6963 initBtnIcons IIFE（归 app.js，工单 02 已迁）；7234 useTopic（归 12）。
- topic 域纯件已迁 fx/topic.js（16 函数：topicChipRowHTML / topicDetailHTML / topicPagesHTML / topicEditHTML / topicCardHTML 等）——胶水 import 调用；esc 自 fx/core.js。
- markup：tab-topic @1908-1947；#topic-grid / 分页 / 弹窗 / proofread id 全不动。
- host 页签分发器 import loadTopics + loadTopicGroupVocabulary + loadTopicArchiveLink（若分发器调用）。

## 检查表

- [ ] 新建 `static/js/ui/topic.js`：上述 15 函数逐字搬移 + import（app.js / fx/topic.js / fx/core.js）+ export（loadTopics / loadTopicGroupVocabulary / initTopicToolbar / viewTopicDetail / viewTopicEdit / deleteTopic / renderProofreadRows）+ 头部注释
- [ ] index.html：CRLF 感知行区间删除（6937-7332 内目标名；**物理升序**；避开 6963 initBtnIcons 与 7234 useTopic）+ 顶部 import 行追加
- [ ] 「载入到生成页」按钮接线：viewTopicDetail 内经 import { useTopic }（工单 12 前：主体/模块 import 代理）调用——实施时以 grep 确认调用点形态，保持行为零变化
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 题库 tab 实况探针（loadTopics 后卡片数 > 0）
- [ ] grep 零残留：index.html 无 `function loadTopics(` 等 15 名定义
- [ ] 中文提交

## 风险点

- 本票与工单 12 的 useTopic 归属交界：12 未迁时，viewTopicDetail 内裸引用 useTopic 仍有效（主体作用域）；12 迁走后本模块 import。工单 12 实施时**必须**回查本模块调用点。
- viewTopicEdit（7111-7165）含证明题编辑/提交逻辑，若引用 `state`（主题/平台）——补 import。
