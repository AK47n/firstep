# 04 — "boot 是唯一装载来源"的 6 个模块给出显式 init()

**要做什么：** 把剩下 6 个"页面靠 boot 装载它才接线"的模块（别的模块都不 import 它们）
也改成显式 `init*()`——它们的监听器绑定与首帧 DOM 写从求值期搬进 init，由 boot 调用。
做完这一步，"boot 装载且 boot 是唯一来源 ⇒ 求值期零副作用"是一条**对全清单都成立**的
结构不变量（工单 05 把它钉进闸门）。

**被谁阻塞：** 03（同一套搬运手法先在小簇上验证一次）

**状态：** ready-for-agent

## 范围（实测清单见 spec「实现决策」）

| 模块 | 求值期副作用 | 说明 |
|---|---|---|
| `ui/generate-core.js` | 17 条（`#btn-skeleton` / `#btn-smoke` / `#btn-restore-bak` / `#desktop-topic-output` / `#btn-pick-output-dir` / `#btn-handoff`(+copy) / `#btn-copy-dir` / `#btn-flash` / 3 条 `#btn-goto-*` / `#btn-edit-mainc` / `document` 委托 / `#btn-generate`，＋首帧置灰两行） | 最大的一个；`initScoreChecklist()` 仍在 boot 启动区调用，**不动** |
| `ui/library.js` | 6 条（`#btn-add-file-row` ＋首帧 `addFileRow()` / 2 条 `bindFilePicker` / `#btn-draft-desc` / `#btn-add-module-submit`） | `initLibraryToolbar` / `initAddSections` 的既有调用**不动** |
| `ui/master.js` | 8 条（`#btn-pick-dirs` / `#pick-dirs` / `#btn-scan` / `#prog-log-head` / `#btn-distill` / `#btn-confirm` / `#btn-direct-import` / `#import-pick-dirs`） | `distPanel` 等声明留原地 |
| `ui/reference.js` | 7 条（`#ref-anchor-kind` / `#btn-ref-add-file-row` ＋首帧 `addFileRow()` / `#btn-ref-draft-desc` / `#btn-ref-add` / 2 条 `bindFilePicker`） | 同上 |
| `ui/topic.js` | 3 条（`#btn-topic-split` / `#btn-topic-confirm` / 顶部自调 `initTopicToolbar()`） | 自调点随接线搬进新 init（或由 boot 显式调用），**调用时机语义保留** |
| `ui/code-fix-panel.js` | 1 条（`subscribeFixCenter(fixCb)`） | 并入既有 `initCodeFixPanel()`（boot 已在调） |

## 验收标准

- [ ] 6 个模块求值期列 0 副作用清零（`subscribeFixCenter` 那条并入既有 init）
- [ ] boot.js 接线区按 import 顺序显式调用新 init；**不新增/不改既有启动区调用的顺序**
- [ ] 被其它函数读的模块作用域声明（`distPanel` / `refUI` / `topicPageCache` / `libUI` 等）
      留在原地（只搬副作用）
- [ ] 真浏览器冒烟（改前 / 改后各一次）：加载期监听器记账里这 6 个模块的绑定**逐条相同**；
      `#platforms` 平台卡、母版页扫描/提炼按钮、模块库新增表单、参考库录入表单、赛题库拆条
      的接线都在；0 pageerror
- [ ] 判据自证：boot 装载的 11 个模块里，"boot 是唯一装载来源"的那 6 个 列 0 副作用 = 0
- [ ] `node --test "tests/js/*.test.mjs"` 全绿、浏览器门禁 26 条全绿、`python -m pytest -n auto -q` 全绿

## Comments

（实现时补：各模块 init 名、冒烟对照读数）
