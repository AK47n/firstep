# 09 — 题库 tab + 校对：static/js/ui/topic.js

**要做什么：** 题库 tab 全部 DOM 胶水迁入 `static/js/ui/topic.js`（archive 链接 / 年份 chips / stats / 列表 / 分页 / 详情弹窗 / 编辑弹窗 / 过滤器 / 工具栏 / 词汇表 / 删除 / 校对行编辑器）。`useTopic`（题面载入事务）归生成推荐簇（工单 12），本票**不迁**——题 tab 的「载入到生成页」按钮经 import 调用。**被谁阻塞：** 02（app.js）

**状态：** resolved（2026-08-27；JS 442 全绿、pytest 2465 全绿、diag 零 EXC、smoke 11/11、probe-09 题库实况 7/7）

## 实施记录

- **static/js/ui/topic.js**（新建 ~430 行）：9 状态（topicRows / topicPdfFile / topicArchiveLoaded / topicUI / topicEntries / topicGroupVocab / topicSearchTimer / topicLoading / topicPageCache）+ 15 函数逐字搬移（loadTopicArchiveLink / topicFilterContext / renderTopicYearChips / renderTopicStats / renderTopics / loadTopicPageState / renderTopicPages / viewTopicDetail / viewTopicEdit / clearTopicFilter / initTopicToolbar / loadTopicGroupVocabulary / loadTopics / deleteTopic / renderProofreadRows）+ 拆条录入监听（btn-topic-split / btn-topic-confirm）；initTopicToolbar() 顶层调用随迁（import 时绑定）。import app.js（$ / apiGet / apiPut / apiDelete / toast / handle）/ fx/core.js（esc）/ fx/topic.js（12 纯名）/ **ui/generate-recommend.js（useTopic——卡片「用此题生成」+ 详情弹窗按钮；12 交付后直接 import，无代理期）** / **fx/pdf.js（pdfFileUrl——见单源修正）**。export：loadTopics / loadTopicGroupVocabulary / initTopicToolbar / viewTopicDetail / viewTopicEdit / deleteTopic / renderProofreadRows。
- **pdfFileUrl 单源修正（顺带，05 遗留潜 bug）**：05 迁移时把 host 的 `function pdfFileUrl` 删掉却未在 fx/pdf.js 补导出——题库 archive 链接点击回调直接 ReferenceError（topic 簇调用点在 host 未触发过，无探针覆盖）。本票下沉纯函数 `pdfFileUrl(relPath) = "/api/pdfs/" + pdfEncodedPath(relPath)` 到 fx/pdf.js；ui/pdf.js 删本地副本改 import（顺带裁掉已不用的 pdfEncodedPath import）；无测试钉旧解，fx-guard DOMAINS 登记新名。
- **index.html（apply-09.mjs，6204→5829 行）**：①host import 行（topic.js 7 名代理）+ generate-recommend 代理行**裁 useTopic**（调用点随簇迁入 topic.js，host 不再用）；②赛题库整簇（区段头 → btn-topic-confirm 监听末）→注记。校验：15 函数 + 9 状态零残留、host 保留 `loadTopics(); loadTopicGroupVocabulary();`（tab 分发器）、useTopic / pdfFileUrl 调用点零残留。
- 验证：node --test 442 全绿（topic-cards.test.mjs 的 2 条卡片接线断言重指向 topic.js——按归属复核；fx-guard 增 pdfFileUrl）；pytest 2465 全绿（bg）；diag 零 EXC；smoke 11/11；probe-09.mjs 7/7（切 tab → loadTopics + loadTopicGroupVocabulary → 15 卡 + 年份 chips 8 + 统计「共 15 题 · 含附带程序 9 · 含图注 6 · 题面合计 ~38.1K 字」+ archive 链接 → 详情弹窗（页图懒取容器）→ 详情内「用此题生成」（useTopic 接线）→ 详情内「编辑」（viewTopicEdit 预填 1093 字题面）→ 拆条表单 → 零 EXC）。

## 检查表

- [x] 新建 `static/js/ui/topic.js`：15 函数 + 9 状态 + 监听逐字搬移 + import（app.js / fx/topic.js / fx/core.js / fx/pdf.js / ui/generate-recommend.js）+ export + 头部注释
- [x] index.html：apply-09.mjs（CRLF 感知 1 大段删除 + import 行 + 代理行裁 useTopic）
- [x] pdfFileUrl 单源修正（fx/pdf.js 导出 + gurad 登记 + ui/pdf.js 改 import）
- [x] `node --test` 442 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + probe-09 题库实况 7/7
- [x] grep 零残留：index.html 无 15 函数定义 / 无 topic 状态 / 无 useTopic 调用点
- [x] 中文提交

## 风险点 / 跟踪

- **host import 代理 7 名**：loadTopics / loadTopicGroupVocabulary（tab 分发器）真实使用；initTopicToolbar / viewTopicDetail / viewTopicEdit / deleteTopic / renderProofreadRows 自本票起 host 不再直接调用——收尾工单 20 统一核对裁代理。
- **topic.js → ui/generate-recommend.js 单向 import（useTopic）**：generate-recommend 不 import topic.js，无环；12 的 clusterDeps / setOnStepChange 接缝不受本票影响。
- **fx/topic.js 在 host 的 import 行（2224 一带）自本票起零使用**；fx/reference.js 自 08 后、fx/module.js 自 07 后亦可能零使用——20 收尾统一核对裁剪（勿逐票删，避免误伤其它 host 引用点如 fx/pdf.js——host 仍用 pdfPagesUrl 等？确认：pdf 域已全迁 ui/pdf.js，host 侧 fx/pdf.js 仅剩 topic.js 用过 pdfFileUrl——现由模块 import，host 的 fx/pdf.js import 行亦零使用）。
- **卡片无「编辑」按钮**（详见探针校正）：编辑入口只在详情弹窗内（topicDetailHTML 带 data-topic-edit；topicCardHTML 只有 view/use/del）——行为未变，探针初版误按卡片编辑按钮而假失败。
