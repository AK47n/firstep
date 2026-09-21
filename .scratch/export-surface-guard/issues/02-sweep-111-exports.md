# 02 — 按判据清点处置 111 处（110 摘 export + 1 整条删）

**要做什么：** 让判据 D 从 **111 处违规**变成 **0 处**，且**页面行为零变化**：110 处摘掉多余的
`export`（定义、模块内部引用、模块底部的 window 探针桥**一字不动**），1 处整条删
（`ui/generate-recommend.js::groupChoiceGap()`，零引用）。做完之后"导出"重新等于"有人真的 import"。

**被谁阻塞：** 01（判据单源与红证）

**状态：** resolved

## 验收标准

- [x] 清点脚本 `.scratch/export-surface-guard/apply-sweep.mjs`：**自带校验**（逐处内容锚定；判定为
      违规的才动，改一处报一处；任何一处对不上就整体不写盘），产出 `.scratch/export-surface-guard/verify-sweep.txt`。
- [x] **110 处摘掉多余的 `export`**，形态照实测（`probe-03-sweep-shape` 读数）：
      **73 处 inline**（`export const/function/let/var` → 删 `export ` 前缀）；
      **30 处**从 `export { … }` 清单里摘名字（8 条清单行留下）；
      **7 处**所在的 4 条清单**整行删**（`ui/full-update.js` 1 名 / `ui/generate-fix.js:47` 2 名 /
      `ui/params-chat.js` 1 名 / `ui/params.js` 3 名）。这 37 处清单形态**全部是本文件声明的名字**
      （含 `export { x } from "…"` 的转手再导出），故**不得**产生"未使用具名 import"
      ——改完必须复跑 `import-usage-guard` 那条判据确认。
- [x] **1 处整条删**：`ui/generate-recommend.js::groupChoiceGap()`（含其上方注释块）。
      **代价如实记账**（写进 Comments）：`.scratch/group-choice-required/smoke-browser.mjs` 那张一次性
      探针里的 `rec.groupChoiceGap()` 会链接期报错——服务的是已 resolved 的 `group-choice-required`，
      本轮**不修**。
- [x] **行为零变化的证据**：`git diff --stat` 只涉及 `src/contest_generator/static/js/**`；
      **行数只减不增**；`git diff` 里 window 探针桥（`Object.assign(window, {…})` 那些行）**零改动**；
      555 个 id / `index.html` **零改动**。读数写进 Comments。
- [x] 复跑判据：**判据 D = 0 违规**；**`graphBreaks` 仍绿**（没有谁还在 import 一个已经不导出的名字）；
      `reachable` / `wiringViolations` / `registryProblems` 全绿（摘 `initTopicToolbar` 的 `export` 后，
      `ui/topic.js` 的登记体检仍由 `initTopicPanel` 的调用点满足——实测确认，见 Comments）。
- [x] **红证复跑**：`node .scratch/export-surface-guard/probe-04-red-proof.mjs` → ① base 自校验通过、
      ② 判据在 base 上红（111）、④ 强度自检 9/9、③ **当前工作树绿**（判据 D = 0，且判据 T／星号体检／
      取数面体检全绿——工作树这一半是硬判，不是打印）；覆盖写 `red-proof.txt`。
- [x] `node --test "tests/js/*.test.mjs"` 全绿（基线 **1679 passed**）。
- [x] **未顺手做**：常量形态、C6/C7、`.scratch` 探针修复、`import-usage-guard` 口径扩展。

## Comments

### 2026-09-21 实现记录

#### ① 清点读数（判据 D：**111 → 0**）

| 口径 | 读数 | 出处 |
|---|---|---|
| 清点零消费者导出 | **111** 处（与 base `27a7b46e` 同数，逐条销账 0 处仍红） | `verify-sweep.txt` ①/⑥ |
| 摘 `export` | **111** 处 = 73 前缀 + 30 清单摘名字 + 7 清单整行删 + **1 级联** | `verify-sweep.txt` ⑦ |
| 整条删 | **1** 处（`ui/generate-recommend.js::groupChoiceGap()`，5 行含注释） | 同上 |
| 孤儿 import | **2** 处（`ui/full-update.js::fullStateText`、`ui/generate-recommend.js::pendingGroupChoices`） | 同上 |
| 导出条目总数 | 995 → **883**（−112） | `verify-sweep.txt` ⑥ |
| 改动规模（`static/js`） | 49 个文件，**+85 / −107**，文件行数净 **−22**（只减不增） | `git diff --shortstat` |

**形态分布与工单的「73 / 30 / 7」逐条对齐**（`verify-sweep.txt` ① 的形态分布表，对不上就整体拒写）：

- **73 处 inline** 删 `export ` 前缀；
- **30 处**从**留下的 8 条** `export {…}` 清单里摘名字；
- **7 处**所在的 **4 条**清单整行删：`ui/full-update.js:150`（1 名）、`ui/generate-fix.js:47`（2 名）、
  `ui/params-chat.js:225`（1 名）、`ui/params.js:366`（3 名）——落点与工单列的一致。

**两条数字口径的澄清**（工单 01 Comments ④ 的先例：读数要能自洽）：

- spec「方案」写 73 inline，spec「补充说明」引 probe-03 写 inline **74** —— **不矛盾**，差的那 1 处是
  `ui/generate-recommend.js::groupChoiceGap()`：它的**声明形态**是 inline，但**处置动作**是"整条删"。
  即 `74 inline = 73 摘前缀 + 1 整条删`，`37 清单 = 30 摘名 + 7 整行删`，`73+30+7 = 110`（spec 的处置口径），
  `+1 = 111`（probe-03 的形态口径）。现场实测见 `survey-06-sweep-inventory.txt:1` 与 `verify-sweep.txt` ①。
- 「**行数只减不增**」的口径：`git diff` 的 85 条 insertions 全是**改写行**（摘掉 `export ` 前缀后的同一行），
  逐条都能在删除行里找到出处（`diff-proof.txt` 归因：74 条摘前缀 + 25 条名单重写）。
  **文件行数**净 −22，且 apply-sweep 逐文件核对"不得增加"。

#### ② 三处超出工单字面的处置（都必要，但必须记账）

工单写的是"**110 处摘 export + 1 处整条删**"。实测做了 **111 处摘 export + 1 处整条删 + 2 处孤儿 import**，
多出来的 3 处各有硬理由——**不是顺手做**（**三处都由"判据 D = 0"或"不得产生未使用具名"这两条判据强制**，
不是可以商量的附加项）：

1. **级联 1 处：`ui/fix-center-core.js:51` 的 `fixLoop` 摘 `export`。**
   它原来的**唯一消费者**就是 ③ 里 `ui/generate-fix.js:47` 那条
   `export { FIX_MAX_ROUNDS, fixLoop } from "/js/ui/fix-center-core.js"`——转手再导出本身就是一条
   指向 `fix-center-core` 的 import 边（`boot-contract.mjs:751-753` 明写它算消费者）。
   摘掉那条，`fixLoop` 就成零消费者；**判据 D 要 0，这一处必须一起摘**。
   在摘之前算不出它（当时它还有消费者），所以它不在那 111 处清单里 —— 这是清点**暴露**出来的必然结果。
   安全性：`fixLoop` 在本模块内仍有 **42 处**引用（单实例状态机：`running/round/batch/resume`），
   `export const` → `const` 只是摘关键字、不删定义；对外读面另有 `fixLoopSnapshot()` / `isFixRunning()`
   （`tests/js/fix-center-core.test.mjs` 消费）；`tests/test_generate_check_contract.py:687` 那条
   `fixLoop.resume` 结构钉读的是**源码文本**，不依赖 `export`，实测仍绿。
   **须记账的一处反转**：`.scratch/code-ide-ai/issues/05-fix-core-shared.md:37` 写的那条契约
   "re-export `FIX_MAX_ROUNDS` / `fixLoop` 自核心"，本轮被清点**各去掉一半**：
   `FIX_MAX_ROUNDS` 的 export 留着（它有真消费者 —— `ui/code-fix-panel.js:27` import、
   `:197` 读值），`fixLoop` 的 export 摘了（它的唯一消费者就是那条 re-export 自己）。
   那份记录属已 resolved 的工单，本轮不改，如实挂在这里。
2. **孤儿 import 2 处**：改动**前**有人用、改动**后**没人用（用仓库自己的 `unusedImports` 判据算）：
   - `ui/full-update.js:11` 的 `fullStateText`：它只为 `export { fullStateText };` 那条再导出而存在，
     摘掉 export 后就成了死 import → 从说明符里摘掉（`import` 还剩 3 个名字，不是整条删）。
   - `ui/generate-recommend.js:30` 的 `pendingGroupChoices`：唯一调用者就是被 ④ 整条删掉的
     `groupChoiceGap()`。**这是双轴评审抓出的硬违规**：第一版扫描器只认"本轮被摘名的 import"
     （`swept.has(name)`），认不出"被别处删除带死的 import"，于是清点自己造出一条死 import。
     已把 ⑤/⑤-b 改成**不动点循环**（一轮一轮地找连带改动直到稳定），并补一条收尾硬判：
     **模块级未使用具名不得比清点前多**（实测 18 → 17 处，本轮未新增）。
3. **`import-usage-guard` 的口径错配（如实记账）**：`tests/js/import-usage.mjs:13` 的取数面
   **只有 `boot.js`**，所以"装载根 0 处未使用具名"对**模块级**没有证明力。工单 ② 要求"复跑
   `import-usage-guard` 确认"，但那条判据根本不看 ui/fx 模块。apply-sweep 现在自己把口径补全
   （`verify-sweep.txt` ⑥ 的"模块级未使用具名"一行）。**另有 9 处 import 在本轮之前就已经是死的**
   （`WRITE_GUARD_ACTIONS` ×4、`resourcesOverviewHTML`、`readinessRowHTML`、`getMainCDiskDir`、
   `isTabSavable`、`resourcesToolbarHTML`）——不在判据 D 的 111 处清单里、也不由本轮造成，
   **本轮不动**，如实记账（见工单 ⑧ 与 spec「范围外」）。

#### ③ 行尾与尾部换行（双轴评审抓出并修掉的一处假绿）

`apply-sweep` 全程按 LF 切行；落盘前按清点前那个文件**逐字节还原**行尾写法与尾部换行数。
第一版漏了这一步，在 4 个文件尾部留下多余空行（`fx/hwcheck.js` / `ui/full-update.js` /
`ui/params-chat.js` / `ui/params.js`），而归一化比对里的 `\n+$` 折叠把它从证据里**抹掉了**——
"正文逐字节相同"因此是**假绿**。已修：去掉收尾折叠（尾随差异必须现形）+ 落盘前还原 + 逐文件断言
（`verify-sweep.txt` ⑤ 的"行尾写法与尾部换行数逐文件还原 ✓"）。现在的机械证据是
`diff-proof.txt` 里的"**尾部换行不一致的文件：0 个**"。

#### ④ 独立机械证据（不依赖清点脚本的自述）

`.scratch/export-surface-guard/probe-11-diff-proof.mjs` → `diff-proof.txt`：逐文件把清点前
（`git show d0f3e843:<path>`）与工作树的文本规范化后逐行比，**每一行都必须归得了因**：

```
归因：未被改动的老行 22235 行 / 摘 export 前缀 74 行 / 名单重写 25 行 /
      删函数体 5 行 / 孤儿 import 2 行 / 空行 0 行
**归不了因的差异：0 处**   → PASS
```

（74 = 73 inline + 1 级联；25 = 30 摘名字涉及的清单行 + 整行删的收尾行；5 = `groupChoiceGap` 函数体。）

#### ⑤ 红证复跑（`red-proof.txt`，覆盖写）

- ① base 自校验通过（`base=27a7b46e`，**不写 HEAD**）：base 上零消费者 **111**、形态违规 0、星号 0、
  取数面体检干净、三个钉子名仍在；
- ② 判据 D 在 base 上红 **111** 处（backlog 点名的 7 个 7/7 在清单里），判据 T 绿 0；
- ③ **当前工作树绿**：判据 D = **0**，判据 T / 星号体检 / 取数面体检全绿（工作树这一半是**硬判**）；
- ④ **强度自检 9/9**；`PASS`。
- **一处必要的探针修改**：自检 5（星号导入体检）原先把锚点写死在 `fx/code.js::maincScrollToRange`，
  而这个名字清点后**已经不是导出**了 —— 不改则清点后这条自检假红。已改成**内存注入专用锚点**
  （`export function probeStarAnchor(){}` + `probeNs.probeStarAnchor()`），不再依赖任何真实导出。
  这属于对工单 01 交付件的改动，如实记账（spec「范围外」未列此项，但不改就没法复跑）。

#### ⑥ 三门禁读数

| 门禁 | 读数 |
|---|---|
| `node --test "tests/js/*.test.mjs"` | **1679 passed / 0 fail**（与基线同数，本轮没动用例） |
| `python -m pytest -n auto -q` | **5049 passed / 1 skipped**（基线同数） |
| `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` | **26 passed / 0 fail** |

首轮全量跑时各有一例在并行负载下**假红**（`tests/test_js_gate.py` 与 `tests/browser/hwcheck.spec.mjs`），
两者**单独复跑与随后全量复跑都全绿**，与清点无关（`hwcheck` 那条也单独跑过：10 passed）。

**一条环境事实（与清点无关，但会影响本地读数，如实记账）**：两条前端"源码形态"用例按**字面 LF**
断言源码，因此对检出时的行尾敏感：

- `tests/js/ai-action-refs.test.mjs:138`（`coreSrc` 正则里有一个字面 `\n`）
- `tests/js/module-intro-detail.test.mjs:166`（`renderRecommendResult(...);\n  runExpand();`）

本机 `core.autocrlf=true` → **CRLF 检出**下这两条必红（实测 **1677 passed / 2 fail**），
**LF 检出**下全绿（**1679 / 0**）。已在**纯净克隆**上双向复核（同一提交 `d0f3e843`）：

```
CRLF 检出（autocrlf=true） : tests 1679 / pass 1677 / fail 2   ← 两条都是上面那两个
LF   检出（autocrlf=false）: tests 1679 / pass 1679 / fail 0   ← 与工单记的基线一致
```

清点**不碰这两处的断言目标**（`ui/generate-core.js` 与 `ui/generate-recommend.js` 的正文一字未改，
只摘了导出关键字）。收尾时把落盘文件**一律归一成 LF**（= 仓库存储形态，也是那两条用例的前提），
使落盘形态与 `git show` **本来**就一致、不再依赖 autocrlf 的检出副作用；这条归一已并进
`apply-sweep.mjs` 的落盘步骤（每次清点自动做，读数里有一行"行尾归一（CRLF → LF）：N 个文件"）。
比对仍用 `git diff --ignore-cr-at-eol` 复核：**49 个文件、只含导出面改动、0 处纯行尾噪声**
（剩下 4 条纯空行差异全部是"整行删那条清单时连它上面的空行一起收掉"，逐条在 `diff-proof.txt` 里归因）。

#### ⑦ 行为零变化的证据

- `git diff --name-only`：`static/js` 之外只有 `.scratch/export-surface-guard/**`（工单产物）；
- **`window` 探针桥（`Object.assign(window, {…})`）：diff 命中 0 处，零改动**；
- **`index.html` / 555 个 id：零改动**（本轮只碰 `static/js`）；
- `initTopicToolbar`：摘 `export` 后登记体检仍绿 —— 它的**代码**调用点在 `ui/topic.js:255`（定义处）与
  `:394`（`initTopicPanel()` 内），`registryProblems` 0 处（`probe-14-topic-pin.mjs`）；
- `graphBreaks` / `reachable` / `wiringViolations` / `registryProblems` 全 0（没有谁还在 import
  一个已经不导出的名字）。

#### ⑧ 未顺手做（与 spec「范围外」一致）

常量形态（number/string/object）的恢复、C6（555 个 id 耦合）、C7（73 个私有符号）、
`.scratch` 一次性探针的失效修复（含 `group-choice-required/smoke-browser.mjs` 里
`rec.groupChoiceGap()` 会链接期报错——服务的是已 resolved 的工单，**本轮不修**）、
导出面的 API 重设计、`import-usage-guard` 的口径扩展、工单 `frontend-boot-module/01-05` 的其它挂账。

#### ⑨ 双轴评审后**留给下一张工单**的两处（本轮明令不动，只记账）

1. **新墓碑注释（假契约）**：`ui/generate-fix.js:296`「（导出面保持——检查表 import 用）」、
   `:303`「（导出面保持）」、`:422-425`「continueFixCenter / FIX_MAX_ROUNDS / fixLoop 经检查表
   导出为模块 API／re-export 自 fix-center-core.js」——对照它下面 `:426` 的现存清单，**全部失效**；
   `ui/fix-center-core.js:49`「壳层 re-export」同样失效；`boot.js:249-250` 的墓碑注释仍称二者在
   `generate-fix.js`。**本轮不改**：工单 §要做什么 与 §⑧ 明令"定义、模块内部引用、window 探针桥
   一字不动"，改注释会毁掉 `probe-11` 那条"归不了因 0 处"的证据链。
2. **零调用私有死函数**：`ui/generate-fix.js:297` 的 `runCompileOnce` 在摘掉 `export` 后全仓只剩
   定义行 1 处引用（`probe-14` / 评审实测）；同理可查 `ui/hwcheck.js` 一侧。
   按 spec 口径它不在判据 D 的清单里（它从来就零消费者），本轮只摘关键字、不删定义。

#### ⑩ 工具与产物（都在本目录）

`apply-sweep.mjs`（清点执行器：逐处内容锚定 + 逐处自校验 + 全量归一化比对 + 行尾还原 + 不动点连带扫描
+ 收尾复跑 8 条判据，任何一条不过就**整体拒绝写盘**）、`verify-sweep.txt`（它的读数）、
`sweep-run.log`（同一次运行的完整 stdout）、`probe-06-sweep-inventory.mjs` + `survey-06-sweep-inventory.txt`
（清点前逐条盘点）、`probe-11-diff-proof.mjs` + `diff-proof.txt`（独立机械证据）、
`probe-14-topic-pin.mjs`（工单⑤点名的登记体检 + `initTopicToolbar` 调用点核对）。

