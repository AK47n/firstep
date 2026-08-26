# 08 — 参考库 tab：static/js/ui/reference.js

**要做什么：** 参考文件库 tab 全部 DOM 胶水迁入 `static/js/ui/reference.js`（chips/stats/列表/过滤器/工具栏/词汇表加载/条目加载/删除/编辑弹窗/文件打开/详情/文件引用收集）。**被谁阻塞：** 02（app.js）+ 06（files.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 区段 = 6198-6647：renderReferenceChips 6198 / renderReferenceStats 6215 / renderReferences 6225 / clearReferenceFilter 6252 / initReferenceToolbar 6258 / loadKitVocabulary 6294 / loadReferences 6321 / deleteReference 6342 / editReference 6356（含 6352-6353 区段注释「参考库编辑弹窗（工单 03）：改元数据 + 文件增删，一次 PUT 落盘」）/ referenceFileUrl 6510 / openReferenceFile 6517 / viewReferenceDetail 6535 / showReferenceDetail 6543 / refCollectFiles 6583（=`collectFiles($("ref-files"))`，import 自 ui/files.js）。
- 引用链：editReference 内 addFileRow / collectFiles / bindFilePicker（files.js）；esc / handle / apiGet / apiPost / apiDelete（app.js / fx/core.js）。
- reference 域纯件已迁 fx/reference.js（15 函数：refChipRowHTML / refRowHTML / refStatsText / refEditValidate / refEditPayload 等）——胶水经 import 调用。
- markup：tab-reference @1786-1881；#reference-root / 工具栏 / 表格 / 编辑弹窗 / 查看器 id 全不动。
- host 页签分发器 import loadReferences + loadKitVocabulary。

## 检查表

- [ ] 新建 `static/js/ui/reference.js`：上述 13 函数逐字搬移 + import（app.js / fx/reference.js / fx/core.js / ui/files.js）+ export（loadReferences / loadKitVocabulary / initReferenceToolbar / deleteReference / editReference / openReferenceFile / viewReferenceDetail）+ 头部注释
- [ ] index.html：CRLF 感知行区间删除（6198-6647 内 13 名 + 区段注释；**物理升序**）+ 顶部 import 行追加
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11 + 参考 tab 实况探针（probe-03 先例：154 条渲染 + 编辑弹窗一次）
- [ ] grep 零残留：index.html 无 `function loadReferences(` 等 13 名定义
- [ ] 中文提交

## 风险点

- editReference 大函数（6356-6509，~150 行）含文件行增删 + PUT 组装——契约断言 editReference 内「一次 PUT 落盘」（若 test 钉 index.html 内该函数体，重指向 ui/reference.js 并核对断言可读）。
- refCollectFiles 若与 library 簇的 collectFiles 同体，确保只 import 一次（files.js 单源）。
