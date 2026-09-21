# 04 — "boot 是唯一装载来源"的 6 个模块给出显式 init()

**要做什么：** 把剩下 6 个"页面靠 boot 装载它才接线"的模块（别的模块都不 import 它们）
也改成显式 `init*()`——它们的监听器绑定与首帧 DOM 写从求值期搬进 init，由 boot 调用。
做完这一步，"boot 装载且 boot 是唯一来源 ⇒ 求值期零副作用"是一条**对全清单都成立**的
结构不变量（工单 05 把它钉进闸门）。

**被谁阻塞：** 03（同一套搬运手法先在小簇上验证一次）

**状态：** resolved

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

- [x] 6 个模块求值期列 0 副作用清零（`subscribeFixCenter` 那条并入既有 init）
- [x] boot.js 接线区按 import 顺序显式调用新 init；**不新增/不改既有启动区调用的顺序**
- [x] 被其它函数读的模块作用域声明（`distPanel` / `refUI` / `topicPageCache` / `libUI` 等）
      留在原地（只搬副作用）
- [x] 真浏览器冒烟（改前 / 改后各一次）：加载期监听器记账里这 6 个模块的绑定**逐条相同**；
      `#platforms` 平台卡、母版页扫描/提炼按钮、模块库新增表单、参考库录入表单、赛题库拆条
      的接线都在；0 pageerror
- [x] 判据自证：boot 装载的 11 个模块里，"boot 是唯一装载来源"的那 6 个 列 0 副作用 = 0
- [x] `node --test "tests/js/*.test.mjs"` 全绿、浏览器门禁 26 条全绿、`python -m pytest -n auto -q` 全绿

## Comments

### 2026-09-21 实现记录

**6 个模块各得一个显式 init**（散的接线用脚本机械搬，避免手抄 156 行语句）：

| 模块 | init | 搬走的语句 / 块 |
|---|---|---|
| `ui/generate-core.js` | `initGenerateActions()` | 17 条 → 9 块（114–115 / 188–207 / 212–218 / 220–225 / 393–481 / 483–494 / 496–503 / 521–561 / 564–696） |
| `ui/master.js` | `initMasterWorkflow()` | 8 条 → 7 块（43–69 / 71–89 / 221–224 / 269–295 / 346–382 / 573 / 575–634） |
| `ui/library.js` | `initLibraryAddForm()` | 6 条 → 4 块（431–434 / 436–440 / 458–479 / 481–500） |
| `ui/reference.js` | `initReferenceAddForm()` | 7 条 → 5 块（155–159 / 454–455 / 459–479 / 481–518 / 520–523） |
| `ui/topic.js` | `initTopicPanel()` | 3 条 → 3 块（292 顶部自调 `initTopicToolbar()` / 388–416 / 418–445） |
| `ui/code-fix-panel.js` | 并入既有 `initCodeFixPanel()` | 1 条（`subscribeFixCenter(fixCb)`，搬进函数体最前——订阅仍在绑定之前，与原顺序一致） |

**搬运工具**：`.scratch/frontend-boot-module/wrap-wiring.mjs`（判据单源找接线 → 括号配平算语句
范围 → 连注释整块搬 → 拼成 init 插到文件末尾），**自校验不过就拒绝写盘**：① 搬走的块"缩进复原
后逐字相同"；② 搬完 `wiringEffects` 必须为 0。5 个模块全部一次通过（`generate-core` 第一次
因块内空行让比较口径出错，修正比较口径后通过——是脚本自身的问题，不是模块的问题）。

**boot.js**：`initMasterWorkflow` / `initGenerateActions` / `initLibraryAddForm` /
`initReferenceAddForm` / `initTopicPanel` 按 import 顺序插进接线区；**`code-fix-panel` 刻意
不动调用位置**——它原本就在文末启动区被调，现在那个调用顺带承担原来在求值期做的
`subscribeFixCenter`（少一次重复绑定）。

**判据自证**（`probe-01-red-proof.mjs`）：
- 判据③-b「接线不住求值期」：11 个模块红 → **0 个模块绿**（全部 11 个模块求值期零接线）；
- 登记表体检（11 项）：3 红 → **全绿**（每项都"导出了 init* 且装载根真的调用"）；
- 判据③-a 零裸装载：0 条绿；判据④-a 对账 0 处断裂、④-b 131/131 可达；
- 强度自检 **7/7** 成立。

**真浏览器冒烟**：`smoke-04.txt` —— 记账 **434 条**、排序后指纹 **4288323085**，与 02 状态
（`smoke-03-before.txt`）**多重集逐条相同**（排序后逐条相等）；0 pageerror、6 个 fx 探针桥全在、
5 个模块接线全在、`#delivery-actions` 加载即写、点击有反应、各渲染读数一致。
**顺序位移**（设计如此，如实记账）：`#btn-pick-dirs#click` 3 → 71、`#btn-generate#click`
135 → 93、`#btn-revise-analyze#click` 52 → 97。

**门禁**：前端门禁 **1717 passed / 0 fail**；浏览器门禁与 pytest 读数见下。

### 2026-09-21 双轴评审整改（两轴覆盖工单 03+04 一起）

两轴都独立复跑并逐字核对：**11 个模块代码多重集逐字一致**（只多出 `export function init*() {` 与
`}` 两行，零语句丢失/改动）、绑定 target+事件类型集合 HEAD vs 工作树**完全相同**、delivery 桥
5 键不变、前端门禁 1717/0、冒烟 434 条 / 指纹 `4288323085`（三份证据 SHA256 一致）。
**确认达标**：求值期接线 96 → 0；接线区调用顺序 = import 顺序（逐行对得上）。

**规范轴（硬违规 2）**

- **判据又被抄了一份**：`wrap-wiring.mjs` 自己 `.filter(e => !e.bridge)` 而不用导出的
  `wiringEffects()`——已改成调单源。
- **注释失实 9 处**：6 个 ui 模块文件头仍写"在 import 时绑定"，boot.js 三处同病。全部改成
  "由 init*() 绑定，装载根接线区显式调用"；**不在本轮范围的模块**（generate-steps / settings /
  generate-fix / generate-mainc / generate-pins / generate-recommend）保持原文——它们确实仍在
  求值期接线，注释是对的。

**规范轴（判断题 4）**

- **（最重）搬运脚本的"自校验"是恒等式**：原实现拿块数组与"块数组 ±2 格缩进"比，永远为真。
  已改成**查产物**：从生成的文本里重新抠出函数体（签名 → 收尾 `}`），去掉块间空行、复原缩进，
  与原文块逐行比——装配粘错块 / 丢行 / 插错空行都会红。加上原有"搬完 `wiringEffects` = 0"。
- **同一变换两份实现**：`apply-03-tasks.mjs`（03 用，块边界靠"最后一个 `});`"猜）已**删除**，
  统一用参数化的 `wrap-wiring.mjs`（它按括号配平算语句范围）。
- **boot.js 两条"接线区"标题叠置**（03 残留）：合并成一条。
- **`import-usage-guard` 注释方向写反**（"上面那条"实为文件末尾那条）：已改。

**spec 轴（3 条，都是"仪器没跟上"）**

- **（最重）工单 04 的 AC#4 没有仪器承接**：冒烟的 `BINDINGS` 只列了 03 的 5 个模块，04 的 6 个只
  靠 434 条全量指纹间接覆盖。已拆成 `BINDINGS_03` / `BINDINGS_04` 两张表 + 两条独立断言
  （`initGenerateActions` / `initMasterWorkflow` / `initLibraryAddForm` / `initReferenceAddForm` /
  `initTopicPanel` / `initCodeFixPanel` 的代表性绑定各判一次）。
- **就绪信号仍是时间拍**：原来"容器出现 + 固定 300ms"。现在改成**监听器计数连续两次采样不变**
  （最多 5 秒），不再用固定睡眠——上一版正是被固定睡眠坑过一次（模块池 171 条 checkbox 在机器
  忙时漏记，读数出现"592 → 421"的假差异）。
- **`survey2.mjs` 取数面漏改**（仍从 index.html 的宿主块取，恒打印 0 条）：已改成**缺省从
  `git show b52022f1` 取**（那是工单 03/04 的作业单），`--worktree` 才量当前树。
  相应重录证据：`survey-02-toplevel.txt` = **96 条**（收走前，自相矛盾的旧文件已覆盖）、
  `survey-05-worktree-wiring.txt` = **0 条**（当前树）。
