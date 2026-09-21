# spec — 导出面守卫（export-surface-guard）

## 问题陈述

工单 `frontend-boot-module/05` 把 337 行 `DOMAINS` 名字表退化成结构不变量时，**如实记下两条代价**
（写进了 `.scratch/backlog.md` 第 10 节末与 `tests/js/fx-guard.test.mjs` 文件头）：

1. **类型维度**：旧表 469 个名字里 28 个带 `typeof` 断言（`resetPinState: "fn"` 之类），
   新判据只看"有没有被 import / 有没有定义"，**不管形态**。
2. **死导出**：全图零引用的导出改名或删除不再变红，评审点出 7 个
   （`CCS_PIECE_NAMES` / `maincScrollToRange` / `codeEditorHighlight` / `HWCHECK_VERDICT_FALLBACK` /
   `BUY_DECISIONS_KEY` / `SETTINGS_DEFAULT_COLLAPSED` / `wfNum`）。

两条挂了账，于是导出面现在**没有任何东西管**：一个函数只要没人 import 就静默死去（改名、删掉、烂在原地
都不出声）；把某个 `export function` 换成同名的 `export const` 数据，全图 import↔export 对账照样绿
（名字还在），直到运行时那次调用炸成 `TypeError`。

本轮先做**实测**（探针与读数都在本节同目录），把两条代价的真实体量翻出来——结果与挂账时的判断**不一样**：

- **零消费者导出不是 7 个，是 111 个**（全部 995 条导出里），散在 47 个模块。评审那 7 个用的是
  "全仓零引用"这个**更松**的口径；按 **import 边**算，另外还有 101 个导出没有任何模块或测试真的
  import 过——它们只被**本模块内部**（95 个）或**模块底部的 window 探针桥**（15 个）用着，
  所以它们**不是死代码，是多余的 `export` 关键字**。真死的只有 1 个：
  `ui/generate-recommend.js::groupChoiceGap()`（零引用，只被一张 `.scratch` 一次性探针取用）。
- **类型维度里唯一会导致崩溃的那一轴完全可以不带名单恢复**：1112 条调用位导入名（把测试侧调用点
  也算上是 1719 条）在**解开再导出链与函数别名之后**，**0 违规、0 解不开**。

两条都指向同一件事：**导出面 = 模块的公开承诺，而这个承诺现在既没有下限（谁都能 export 没人用的
东西）也没有形态**。本轮把它补成一对互为正反的判据。

## 方案

在既有判据单源 `tests/js/boot-contract.mjs` 上加**两条互为一对、零名单、纯函数**的判据：

- **判据 D（零消费者导出）**——导出面的"下限"：每条 `export` 必须至少被**一条 import 边**消费
  （口径是**哪条导出**：`模块::名字`，不是"这个名字还有没有人用"——转手再导出
  `export { x } from "…"` 本身就是一条指回声明处的 import 边，所以"声明 + 转手"两侧都会被记上，
  而**没人取的转手再导出**会被判红）。消费者 = 页面模块图（`static/js/**`，含装载根 `boot.js`）
  ∪ `tests/js/*.mjs` ∪ `tests/browser/*.mjs`。**注释提及不算消费者**（工单 05 评审抓过"墓碑注释喂绿"），
  `.scratch` 探针也不算（它们是历史证据，不是闸门）。**零豁免名单**——这正是要拆掉 `DOMAINS`
  那种东西的原因。
- **判据 T（调用位 ⇒ 函数形态）**——导出面的"形态"：一条 import 边的本地名若在**被导入方处于调用位**
  （`name(`），那么它在导出侧必须解析为**函数形态**（`export function` / `export async function` /
  `export class` / `= (…) =>` / `= function` / `= <函数别名>`）。解析要跟随
  `export { x } from "…"` 的**再导出链**与 `export const x = 别的名字` 的**函数别名链**
  （实测：不做这两步，1112 条里会冒出 44 条假红——第一版探针就踩了）。

判据 D 的违规就是"该摘的 `export`"，判据 T 的违规就是"形态崩了"。两者进前端门禁
（`node --test "tests/js/*.test.mjs"`），**先出判据与红证，再照判据清点处置**。

## 用户故事

1. 作为维护者，我想让"export"这个词重新有分量——每个导出都真的有人 import，以便不读全图也知道
   哪些是活接口。
2. 作为维护者，我想在删或改一个导出时门禁替我兜住"还有人在用"，以便不再靠运气。
3. 作为维护者，我想让"被调用的导出必须是函数形态"由判据保证，以便把 `export function` 悄悄换成
   同名常量的那次改动**当场变红**，而不是等运行时 `TypeError`。
4. 作为维护者，我想让这次清点**不改变任何页面行为**，以便 111 处摘除是纯减法、可以逐条复核。
5. 作为维护者，我想让两条判据都**零名单**（新增模块不必登记、忘了登记也不会静默漏保护），
   以便不重蹈 337 行 `DOMAINS` 的覆辙。
6. 作为维护者，我想让判据**能报出**（带正向对照与强度自检），以便不走"断言为空导致真空绿"那条老路。
7. 作为 review 的人，我想看到红证：同一套判据作用在 base（`27a7b46e`，**不写 HEAD**）上必须报出
   111 处零消费者（且形态面 0 处），作用在清点后的工作树上必须 **0 处**；注入若干类破坏必须当场红。
8. 作为页面使用者，我想让这次改动**感觉不到**（0 pageerror、行数只减不增、window 探针桥一字不动），
   以便既有证据与新证据可比。

## 实现决策

**判据落点与签名（判据单源 = `tests/js/boot-contract.mjs`，照 `graphBreaks` / `reachable` 先例）**

- **判据 D**：输入 = 页面模块表 ＋ 消费者模块表（测试侧），输出 = `[{ key, name }]`；空数组 = 合规。
  取数面要**归一说明符**：页面侧走 `resolveModuleKey`（键空间相对 `static/js`），测试侧说明符形如
  `../../src/contest_generator/static/js/fx/x.js`（实测：`tests/js` 与 `tests/browser` 全用这种相对形态，
  另有 `/js/…` 绝对形态），归一成同一个键空间后才能对账。
- **判据 T**：输入 = 页面模块表，输出 = `[{ from, to, name, form }]`；空数组 = 合规。
  形态解析的次序：`export function/async function/class` → `export const x = (…) =>|function…` →
  `export const x = <标识符>;`（先看本文件声明，再看它从哪个模块 import 进来，递归）→
  `export { x } from "…"`（递归进目标模块）。**解不开 = 违规**（不许静默跳过）。
- 两条判据**都要有体检**：判据 D 的消费集合取数面若静默失效（抽不到测试侧、说明符换了写法），
  会退化成"全红"或"全绿"；判据 T 的"调用位"若抽不到就会真空绿。故各配一条下限体检
  （消费者模块数下限 / 调用位条数下限）。

**判据 D 的两个已知边界（写进实现，不靠注释提醒）**

- **星号导入会让逐名判据静默失效**（`import * as ns` 之后"所有导出都被消费了"）。实测当前
  **触达前端的 `import * as` 是 0 处** → 判据不必处理它，但**必须体检**：一旦出现星号导入就报红，
  逼人显式决定（而不是判据悄悄变松）。
- **模板串插值**：本仓库的掩码件（`maskCommentsAndStrings`）会把反引号串整体掩掉，**连 `${…}` 里的
  代码一起**。所以"这个名字还有没有别处用"这类判断**必须用原文**（第一版探针就因此把
  `PANEL_LABELS` / `PIN_TYPE_ZH` 误判成"只有定义行"）。判据 D 只看 import 边（在掩码之外的
  import 语句上解析）故不受影响；判据 T 的调用位判据会**漏detect** 模板串里的调用——方向是保守的
  （漏报而非假红），如实记账。

**清点处置（111 处的机械形态，实测）**

- **110 处：摘掉多余的 `export`**——定义、模块内部引用、模块底部的 window 探针桥**一字不动**，
  行为零变化。其中 **73 处**是 inline 形态（`export const/function/let/var`，删 `export ` 前缀）、
  **30 处**从 `export { … }` 清单里摘名字（8 条清单行留下）、**7 处**所在的 4 条清单**整行删**
  （`ui/full-update.js` 1 名 / `ui/generate-fix.js:47` 2 名 / `ui/params-chat.js` 1 名 /
  `ui/params.js` 3 名）。实测这 37 处清单形态**全部是本文件声明的名字**（含
  `export { x } from "…"` 的转手再导出），**所以摘名字不会产生"未使用具名 import"**、不会碰
  `import-usage-guard` 那条"零未使用具名"。
- **1 处：整条删**——`ui/generate-recommend.js::groupChoiceGap()`（`pendingGroupChoices(...)` 的一层
  薄壳，语义已由同文件的 `groupChoiceGapMessage()` 覆盖）。**代价如实记账**：
  `.scratch/group-choice-required/smoke-browser.mjs` 那张一次性探针里的 `rec.groupChoiceGap()`
  会链接期报错——那张探针服务于已 resolved 的 `group-choice-required`，**本轮不修**。
- 清点**用脚本做**，自带校验：改完复跑判据 D 必须 0、`graphBreaks` 必须仍绿（没有谁还在 import
  一个已经不导出的名字）、前端门禁全绿。脚本与读数落 `.scratch/export-surface-guard/`。

**不做的事（各有理由，别当已做）**

- **常量形态**（number/string/object，旧表那 28 条里的另一部分）：全仓 **97 个值形态导出**，
  判"这个常量该是数字还是字符串"**无法从用法派生**，只能靠名单或生成式快照——而两者都是
  工单 05 拆掉的那种东西。本轮**只恢复函数形态那一轴**，并把这条代价继续写在
  `CONTEXT.md` 与 `fx-guard.test.mjs` 文件头（口径更新：不再是"类型维度整体不守"，
  而是"**fn 轴已由判据 T 守；常量形态不守**"）。
- **window 探针桥**（`Object.assign(window, {…})`）是兼容层（CDP 探针 / devtools 按全局名取用），
  本轮不动。摘 `export` 不影响它——那 15 个被摘的名字在 `window` 上照旧取得到（判据 D 按「哪条导出」算，正是为了这 15 个与其背后的 3 处转手再导出能被分辨）。
- **`.scratch` 探针算不算消费者**：不算。判据只认 import 边；探针失效如实记账、不修。
- C6（555 个 id 耦合）、C7（73 个私有符号）、`ui/delivery.js` 挂桥的既有事实、F5 竞态。

**闸门落点**

- 落点跟随：新判据住在 `tests/js/boot-contract.mjs`（**已有**的共享件，`frontend-boot-module/05`
  已把它接进前端门禁），无需改 `tools/prepush.py`。工单 05 §⑥ 记的那条历史事实
  （共享件改动在**本地**带不起浏览器门禁、CI 照跑）**照旧**，不属本轮。

## 测试决策

- **缝（唯一一条，已存在）**：`tests/js/boot-contract.mjs` ＝ 判据单源 ＋ 既有守卫文件的取数面。
  不新开缝——这正是工单 `frontend-boot-module/01` 立这个共享件的原因（"判据要被守卫本体、红证脚本、
  强度自检三处用"）。
- **先红证后动手**（先例 `.scratch/frontend-boot-module/probe-01-red-proof.mjs`）：判据写成纯函数，
  喂**清点前那个提交**（base 显式钉 `27a7b46e`，**不写 HEAD**）证明它能红。base 自校验 =
  "base 上零消费者导出 **111** 处、形态违规 **0** 处、且 `fx/code.js` 的 `maincScrollToRange`
  仍带 `export`"——选错 base 当场大声失败，绝不产出假绿。
- **强度自检（内存注入，逐条列出）**：
  1. 摘掉某导出的一条真 import 边 → 判据 D 报出；
  2. 判据 D 的**正向对照**：注入一个假模块导出（无人 import）→ 必须报出（防"断言为空"的真空绿）；
  3. **注释喂绿自检**：把某零消费者导出的名字塞进**别的模块的注释**里 → 判据 D **仍须报出**
     （注释不是消费者）；放 `boot.js`（满是墓碑注释）同理；
  4. **测试侧消费者真的算数**：把某导出在 `tests/js` 里的 import 摘掉 → 报出；
  5. **星号导入体检**：内存注入 `import * as ns from "/js/fx/x.js"` → 体检必须红（判据不许静默变松）；
  6. 把一个**被调用**的 `export function` 改成 `export const x = 数据` → 判据 T 报出；
  7. 再导出链感知：`export { x } from "…"` 链上的一环改成数据 → 报出；
  8. **别名正向对照**：`export const x = 别的函数名;` 必须**不**报（防假红）；
  9. 注释感知：注释里的 `x(` **不算**调用位 → 不报。
- **前端门禁**：`node --test "tests/js/*.test.mjs"` 全绿（现状基线 **1679 passed**，本轮净增新用例数）。
- **真浏览器与整套**：清点不触碰 ui 行为（只摘 `export` 关键字），故按仓库口径仍跑三门禁各一遍
  （`python -m pytest -n auto -q` ＋ 前端门禁 ＋ 浏览器门禁），读数写进 Comments。
- **不变的既有判据**：`graphBreaks`（全图 import↔export 对账）、`reachable`、`wiringViolations`、
  `registryProblems` 全绿——**判据 D 是它们的反向补集，不是替代**。

## 范围外

- **常量形态（number/string/object）的恢复**：本轮明确不守（见"实现决策·不做的事"）。
- **C6**：`index.html` 与 ui 的 555 个 id 耦合改造。
- **C7**：73 个私有符号公开化。
- **`.scratch` 一次性探针的失效修复**（含 `group-choice-required/smoke-browser.mjs`）。
- **导出面的 API 重设计**：摘 `export` 只是词法减法，不重排模块职责、不合并模块、不动 window 桥。
- **`import-usage-guard` 的口径扩展**：本轮不动那条"零未使用具名"。
- 工单 `frontend-boot-module/01-05` 的其它挂账（墓碑注释、9 个"另有 importer"模块的顶层接线等）。

## 补充说明

- **每个数字都有出处**，原始读数与工具都在 `.scratch/export-surface-guard/`：
  - `probe-00-survey.mjs` / `survey-00-survey.txt`：导出面普查（995 个导出 / 131 个模块 / 零**页面图**
    消费者的 262 个）。
  - `probe-01-consume-and-form.mjs` / `survey-01-consume.txt`：把测试侧算消费者 → 零消费者 108（**口径修正前**
    按「名字」算的读数，保留备查）、形态分布（函数 898 / 值 97）。
  - `probe-02-taxonomy.mjs` / `survey-02-taxonomy.txt`：111 的三分类（**仅内部用 95 / window 桥 15 /
    真死 1**）、backlog 那 7 个的落点、形态判定解链后的读数（1112 条调用位、0 违规、0 解不开）。
  - `probe-03-sweep-shape.mjs` / `survey-03-sweep-shape.txt`：清扫形态（inline **74** / 清单 **37**；
    4 条清单整行删）、星号导入 **0** 处、清单形态的来源逐条。
  - `probe-05-duplicate-names.mjs` / `survey-05-duplicates.txt`：**口径修正的证据**——全仓 5 个名字被
    ≥2 个模块导出；按「名字」算 108，按「哪条导出」算 111，差额 3 处**全是没人取的转手再导出**
    （`ui/full-update.js::fullStateText`、`ui/generate-fix.js::{FIX_MAX_ROUNDS, fixLoop}`）；反向不会假红
    （`gotoNavTab` 的"声明 + 转手"两侧都被正确判为有人用）。
  - `probe-04-red-proof.mjs` / `red-proof.txt`：真红证（base 自校验 + base 红 + 工作树读数 + 9 条强度自检）。
- **一条实现口径的更正（工单 01 双轴评审抓出）**：判据 D 起初按**全局名字集**判消费，于是
  "同名导出被别的模块导出、且那个被消费了"时会漏报——实测**不是**注释里写的"0 例"，而是 **3 例**
  （见 `probe-05`）。已改成按**「哪条导出」（`模块::名字`）**判，与 spec「每条 `export` 必须至少被
  一条 import 边消费」的字面口径一致；清点体量因此从 108 变 **111**，工单 02/03 的数字已同步。
- **命名纪律**：「**判据 D**」= 零消费者导出；「**判据 T**」= 调用位 ⇒ 函数形态；「**消费者**」特指
  **一条 import 边**（不含注释提及、不含 `.scratch` 探针）；「**摘 export**」特指删掉 `export`
  关键字/清单项，**不是**删定义；「**值形态导出**」= 解析结果不是函数的导出（97 个）。
- **现场基线（清点前的提交）**：`27a7b46e`（`chore: 自动更新 CHANGELOG`，工作树干净）。
- **诚实记账的一条更正**：backlog 第 10 节原话"更该做的是**清点后删掉**它们"是在"这 7 个是死代码"
  的假设下写的；实测它们是**活的定义 + 多余的 `export`**（都被本模块内部或 window 桥用着），
  真正该删的只有 1 个。本轮按实测处置，并把这条更正写回 backlog。
