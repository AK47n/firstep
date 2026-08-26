# 08 — 参考库 tab：static/js/ui/reference.js

**要做什么：** 参考文件库 tab 全部 DOM 胶水迁入 `static/js/ui/reference.js`（chips/stats/列表/过滤器/工具栏/词汇表加载/条目加载/删除/编辑弹窗/文件打开/详情/文件引用收集）。**被谁阻塞：** 02（app.js）+ 06（files.js）

**状态：** resolved（2026-08-27；JS 442 全绿、pytest 2465 全绿、diag 零 EXC、smoke 11/11、probe-08 参考库实况 6/6）

## 实施记录

- **static/js/ui/reference.js**（新建 ~545 行）：6 状态（refUI / refFilterContext / refSearchTimer / kitVocabulary / refEntryCache / refTopicKeys）+ 14 函数逐字搬移（renderReferenceChips / renderReferenceStats / renderReferences / clearReferenceFilter / initReferenceToolbar / loadKitVocabulary / loadReferences / deleteReference / editReference / referenceFileUrl / openReferenceFile / viewReferenceDetail / showReferenceDetail / refCollectFiles）+ REF_TEXT_EXTENSIONS 常量 + 录入表单接线（ref-anchor-kind 监听 / btn-ref-add-file-row + addFileRow($("ref-files")) 初始行 / btn-ref-draft-desc / btn-ref-add / **两个 ref 文件选择绑定**——07 留 host 的 btn-ref-pick-files / btn-ref-pick-dir 按计划随簇带走）。import app.js（$ / apiGet / apiPost / apiPut / apiDelete / toast——本簇无 handle / state 引用）/ fx/core.js（esc / formatSize）/ fx/reference.js（11 纯名）/ ui/files.js（addFileRow / collectFiles / pickFilesInto / bindFilePicker）。export：loadReferences / loadKitVocabulary / initReferenceToolbar / deleteReference / editReference / openReferenceFile / viewReferenceDetail / referenceFileUrl（host 代理 3 名 + 收尾核对用）。
- **index.html（apply-08.mjs，6655→6204 行）**：①host import 行（reference 7 名代理）；②段 A（ref 绑定注记 + 绑定对 + 参考库整簇区段头 → btn-ref-add 监听末）→注记。校验：14 函数 + 6 状态 + REF_TEXT_EXTENSIONS 零残留、host 保留 `loadReferences(); loadKitVocabulary();`（tab 分发器）/ `initReferenceToolbar();`（启动区）、ref 绑定对零残留（随簇）。
- 验证：node --test 442 全绿（无新测试——本票纯胶水；fx 单源 fx-guard 亦绿）；pytest 2465 全绿（bg）；diag 零 EXC；smoke 11/11；probe-08.mjs 6/6（切 tab → loadReferences + loadKitVocabulary → 154 行 + 统计「共 154 条参考 · ANY 6 · STM32 8 · MSPM0 140 · 赛题 4 · 套件 2 · 未锚定 148 · 总体积 7.1 MB」+ chips 4 + kit 词表 2 → 详情弹层（viewReferenceDetail，条目名实况）→ 编辑弹窗（editReference 预填标题）→ 录入表单初始文件行 1 + ref 文件选择绑定 → 零 EXC）。

## 检查表

- [x] 新建 `static/js/ui/reference.js`：14 函数 + 6 状态 + 常量逐字搬移 + import（app.js / fx/reference.js / fx/core.js / ui/files.js）+ export + 头部注释
- [x] index.html：apply-08.mjs（CRLF 感知 1 大段删除 + import 行）
- [x] `node --test` 442 全绿 + pytest 2465 全绿 + diag 零 EXC + smoke 11/11 + probe-08 参考库实况 6/6
- [x] grep 零残留：index.html 无 14 函数定义 / 无 ref 状态 / 无 ref 绑定对
- [x] 中文提交

## 风险点 / 跟踪

- **host import 代理 7 名**：loadReferences / loadKitVocabulary（tab 分发器）/ initReferenceToolbar（启动区）真实使用；deleteReference / editReference / openReferenceFile / viewReferenceDetail 自本票起 host 不再直接调用——收尾工单 20 统一核对裁代理。
- **files.js 共享件双方齐用**：本簇（addFileRow / collectFiles / pickFilesInto / bindFilePicker）与 module 库簇（07 后自 ui/files.js import 相同名）——单源仍成立；host 的 files.js 代理名自 07/08 后仅剩参考库编辑弹窗？——**无**：参考簇已全部迁出，host 的 files.js import 行（2241）现为**零使用**（bindFilePicker 绑定对 / addFileRow / collectFiles / pickFilesInto 调用点全部随 07/08 迁走）——**收尾工单 20 裁减**（注意 readPickedText 同样零使用）。
- **无跨簇互读**：参考选择器（generate-recommend.js 的 loadReferencePicker / renderReferencePicker）走 /api/references 直连，不经本簇 refEntryCache——本簇缓存仅 tab 内用（详情/删除/编辑同源快照；潜在漂移点已在 03 设计接受）。
