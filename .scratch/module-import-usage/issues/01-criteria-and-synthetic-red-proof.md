# 01 — 判据单源：模板表达式感知的掩码 ＋ 模块级「零未使用具名」＋ 合成红证

**要做什么：** 让"零未使用具名 import"这条不变量**第一次能判模块**。判据单源仍住
`tests/js/boot-contract.mjs`（掩码/解析/可达性/消费边）与 `tests/js/import-usage.mjs`（本条不变量）：
把分词器扩成**模板表达式感知**（同一份实现加一个模式），判据正文换成它、判定改按**本地名**、
取数面从"只有装载根"扩到**任意模块**。并用**合成红证**证明它真有牙齿——每条判据各自的假绿反例必须报出，
每条防假红的反向对照必须不报。本工单**不接闸门**（03 的交付）、**不动 `static/js/**` 一行**（02 的交付）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

## 验收标准

- [x] `tests/js/boot-contract.mjs` 新增 `maskNonCode(text)`：注释 / 单双引号字符串 / 正则字面量照旧掩掉；
      模板串**文本段掩掉、`${…}` 表达式内部当代码**（内部照旧掩注释 / 字符串 / 正则 / 嵌套模板的文本段）。
      实现 = **同一分词器的同一份代码路径**加一个模式参数，**不许**另写一份掩码/解析器。
- [x] `maskCommentsAndStrings(text)` 的**语义与行为一字不变**（模板串整串掩掉，含 `${…}`）。
      判据方式：对所有 `static/js/**` 与 `tests/js/**` 源码，新实现下该函数的输出与"模式 = false 的行为"
      逐字符相同（同一个函数入口，构造上成立），并跑前端门禁确认既有判据 D / T / 图对账 / 接线无回归。
- [x] `tests/js/import-usage.mjs`：`unusedImports(script)` 成为**判据本体**（宿主可以是装载根，也可以是
      任意模块）；正文 = `maskNonCode(宿主) − import 语句切片`（剥语句**保长度、保换行**）；判定按
      **`locals`（本地名）**。`hostScript` / `parseImports` / `hostBody` 保留，且 `hostBody` 的注释写明
      **它不再是判据正文**（旧口径，给读旧版源码的红证用）。
- [x] 口径照 spec「实现决策」写进文件头注释：**注释 / 字符串 / 正则 / 模板文本段里的同名词不算"用了"**；
      **再导出清单**（`export { x };` / `export { x as y };`）算消费；**裸装载永远合法**；标识符边界用
      `(?<![\w$])…(?![\w$])` 不用 `\b`；**已知限制**（`${` 的两个字符留在正文里 → 含模板串的模块里名为
      `$` 的 import 可能假绿）如实写在注释里。
      → **比字面要求做得更彻底**：那条"已知限制"**没有留成限制，直接修掉了**（见 Comments ②）。
- [x] 合成红证 `.scratch/module-import-usage/synthetic-cases.mjs`（用例表单源，导出 `syntheticChecks()`）
      ＋ `probe-01-synthetic-red-proof.mjs`（CLI，产出 `synthetic-red-proof.txt`，全成立退出 0，否则非零）。
      用例**每条都自带"注入真的落上了"的自检**（防自检静默空转）。至少覆盖：
      - **假绿反例（必须报出）**：名字只出现在 `//` 注释 / `/* */` 块注释 / 行尾注释 / `"…"` / `'…'` /
        正则字面量 / 模板串**文本段** / 更长的标识符里（`escFoo` 不算用 `esc`）/ `$x` 与 `x$` 不算用 `$`；
      - **反向对照（必须不报，防假红）**：模板**表达式**里的使用（`` `${esc(x)}` ``、嵌套模板
        `` `${`${y}`}` ``）/ `export { x };` 再导出清单 / `import { A as B }` 里 `B` 被用 / 裸装载
        （`import "./x.js"`，零具名 → 判据不碰）；
      - **跨模块再导出链**：`import { x } from "M"; export { x };` 里的 `x` 不算死（那条语句是消费边）。
- [x] 抽取器体检读数落 `.scratch/module-import-usage/survey-01-face.txt`：模块数 132（含 js/ 根
      `app.js`/`boot.js`）、有 import 边的模块 106、语句 496、具名 1249、裸装载 0、星号 0；
      并给出三条**保守下限**（供 03 的闸门用例使用）。
- [x] **未顺手做**：不动 `static/js/**` 一行；不把判据接进守卫用例（03 的交付）；
      不修 `.scratch` 一次性探针；不碰常量形态 / C6 / C7 / 零调用私有死函数。

## Comments

### 2026-09-21 实现记录

#### ① 判据落点（判据单源 = `tests/js/boot-contract.mjs` ＋ `tests/js/import-usage.mjs`）

| 件 | 说明 |
|---|---|
| `boot-contract.mjs::mask(text, templateExpressions)` | **全仓唯一一份分词**（内部件，不导出）：`false` = 今天的行为（模板串整串掩掉），`true` = 模板表达式感知 |
| `boot-contract.mjs::maskCommentsAndStrings(text)` | 语义**一字不变**，实现变成 `mask(text, false)` |
| `boot-contract.mjs::maskNonCode(text)` | 新增：`mask(text, true)` —— `${…}` 表达式内部保留为代码，`${` 两个字符本身也掩掉 |
| `import-usage.mjs::unusedImports(script)` | 判据本体（宿主 = 装载根或任意模块）；正文走 `criterionBody`（`maskNonCode` − import 切片，保长度保换行），按 **`locals`** 判 |
| `import-usage.mjs::hostBody` | **保留但降级**：不再是判据正文；给旧版 `index.html` 那一代的红证与合成用例当"旧口径"样本 |

`parseImports` 多返回一个 `locals`（薄适配器），原有 `{ spec, names, raw }` 消费方不受影响。

#### ② 一处**超出工单字面**的处置（都必要，必须记账）

工单要求把"`${` 留在正文里 → 名为 `$` 的 import 可能假绿"**如实写成已知限制**。实现时先复现了它
（`import { $ } from "/js/app.js";\nconst s = \`a${x}b\`;` → 判据 `[]`，**漏报**），然后**直接修掉**：

```js
if (c === "$" && next === "{") { blank(i, i + 1); tplStack.push({ depth: 0 }); inTplText = false; i += 2; continue; }
```

`$` 是**替换语法**、不是标识符（`{` 留着无所谓，所以只掩 `$`）。修完这条限制不再存在：
正文里只剩真正的标识符 `$`。**为什么算必要而不是顺手做**：不修的话，任何含模板串的模块里
名为 `$` 的 import 都是判据的盲区——而判据的全部意义就是"零盲区地"报出死 import。
合成用例 `dollar-template-substitution` 钉住它（`expect: ["$"]`）。

#### ③ 合成红证（`synthetic-red-proof.txt`，**25/25 成立**，退出码 0）

用例表 `.scratch/module-import-usage/synthetic-cases.mjs`（**单源**：02 的真红证第 ④ 段 import 同一张表）。
三类字段：`expect`（判据应报出的名字）／`bodyIncludes`（**注入自检**：语料里 import 之外真的写过这个名字）／
**差分校准**（同一条语料在别的口径下的预期结果）：

| 校准 | 口径 | 用来证明什么 |
|---|---|---|
| `oldCaliber` | 工单 02 的旧口径（`hostBody` 正文 ＋ 按**源名**判） | 假绿反例在旧口径下**是绿的** → 是本轮的口径修正抓到了它 |
| `naiveMask` | 只用 `maskCommentsAndStrings` | 模板表达式里的真使用在它眼里**是死的** → `maskNonCode` 必需 |
| `naiveSubstring` | 丢掉标识符边界的朴素子串 | `escFoo` / `$x` / `y$` 在它眼里**算用过** → 边界的必要性 |

25 条覆盖：行注释 / 块注释 / 行尾块注释 / 单双引号串 / 正则 / 模板文本段 / 模板表达式内的注释 /
更长标识符 / `$` 的三种形态（`$x`、`y$`、`${`）/ 零出现 ＝ **假绿反例**；
代码调用 / 模板表达式（含嵌套、含对象字面量花括号深度）/ 正则里的引号 / 再导出清单 /
**`import … ; export …;` 连写** / 别名本地名 / 裸装载 / `$` 的真使用 ＝ **反向对照**；
多名字同语句只报没用的那个。

**注入自检有牙齿**（评审要求"每条都能真的失败"）：把 `comment-line` 的语料里 `esc` 抹掉后重跑 →
该条当场 FAIL（`注入自检：正文里找不到 esc`）——已实测，不是声明。

#### ④ 取数面与下限（`survey-01-face.txt`，供 03 的闸门用例用）

| 项 | 实测 | 闸门下限 |
|---|---|---|
| 模块文件数（`static/js/**`，含 js/ 根 `app.js`/`boot.js`） | **132** | ≥ 120 |
| 有 import 边的模块 / 零 import 的模块 | 106 / 26 | — |
| import 语句总数 | **496** | ≥ 400 |
| 具名导入名字总数 | **1249** | ≥ 1000 |
| 裸装载 / 星号导入 | 0 / 0 | — |
| **本条判据当前读数**（清点是 02 的交付） | **12 处**（逐条在 `survey-01-face.txt`） | 0（02 做完） |

#### ⑤ 口径核对（逐条对账，与工单 02 的记账差集）

| 口径 | 读数 | 出处 |
|---|---|---|
| A 旧口径（`hostBody` 正文 ＋ 按**源名**） | **17** | `survey-00b-criteria-delta.txt` / `survey-00-criteria-delta.txt` |
| B naive 掩码（`maskCommentsAndStrings` ＋ 按本地名） | **45** | 同上 |
| C 本轮判据（`maskNonCode` ＋ 按本地名） | **12** | 同上 |

- **A − C = 5 处全是别名误报**：`WRITE_GUARD_ACTIONS as WG` 的 5 处（`ui/code-fix-panel.js` /
  `generate-fix.js` / `generate-revise.js` / `generate-tasks.js` / `params.js`）——正文里写的是
  `WG.fix` / `WG.continueFix` / `WG.revise` / `WG.deepen` / `WG.task` / `WG.params`，**全都在用**。
  工单 02 记的"`WRITE_GUARD_ACTIONS` ×4 是死的"**是误报**，实测按同一错误口径是 **5** 处。
- **B − A = 33 处是模板表达式假红**（`${esc(x)}` 这类真使用）——这正是 `maskNonCode` 的存在理由。
- **C − A = 0 处**（这条要写对）：**旧口径在 base 上同样报出那 12 个名字**——它的 17 = 这 12 个
  ＋ 5 处 WG 别名误报。正确口径**只少报假红、不多报真死**。工单 02 §②-3 的 9 处点名清单里没有的那 7 处
  （`languageOf` / `downloadedPercent` / `getCodeTreeFiles` / `$` / `aggregateSelection` / `toastError` /
  `pdfDupRemainText`）**不是"旧口径看不见"**，是"同一口径也报了、只是没点名"（03 评审实测更正，
  原措辞已改）。
- 12 处的逐条现场（语句原文 / 剩下谁 / 是否唯一 import 边）＝ `survey-00-dead-detail.txt`；
  内存模拟清点后复跑全部既有判据 ＝ `survey-00-simulate.txt`（**唯一变化：判据 D 0 → 1**，
  成因 `fx/core.js::downloadedPercent`，处置进 02）。

#### ⑥ `maskCommentsAndStrings` 行为不变的**硬判**（`probe-01a-mask-equivalence.mjs`）

把 base `f1c9e1c7` 的 `boot-contract.mjs` 取到临时目录 import，与新版逐文件比输出：

```
扫描文件：287
maskCommentsAndStrings vs base 输出不同的文件：0（必须 0）
maskNonCode 与它不同的文件（= 含模板表达式）：65（>0 说明新口径真的在起作用）
```

第二行是**正向对照**：新口径不是"没接上"，是真的在 65 个文件上改了行为。

#### ⑦ 双轴评审整改（`code-review`：Standards ＋ Spec 并行，只报告不修改）

**两轴独立收敛到的同一条（硬，已改）**：合成用例的**注入自检恒真**。原写法是
`[...names].some((n) => c.src.includes(n))` —— 而 `mk()` **必然**把名字写进 import 语句，所以恒成立；
更糟的是它只覆盖 `esc|WG|$` 三种名字（`multi-name-partial` 的 `formatSize` 连这段代码都不进）。
已改成 `bodyIncludes`：**import 语句之外**必须真的出现过这个名字，逐条显式声明；并用"把语料打断 →
该条必须 FAIL"实测它有牙齿（见 ③）。

其余整改：

- **（硬，已改）文件头的消费方清单越位**：声称"守卫覆盖装载根 ＋ 全部 132 个模块"（那是 03 的交付）、
  列出当时还不存在的 `probe-02-base-red-proof.mjs`。已改成如实分票（03 起覆盖全模块；02 交付真红证）。
- **（硬，已改）`$` 的假绿**：见 ②——不是记进已知限制，而是修掉。合成用例钉住。
- **（硬，已改）`locals[i] || n` 是"看起来实现、其实退化成错口径"的兜底**：退回按源名判会静默误报
  （正是本轮要修的 bug）。已换成**大声失败**的等长断言（`names/locals` 不等长即抛）。
- **（硬，已改）边界用例没有差分牙齿**：`longer-identifier` / `dollar-suffix` 在"朴素子串"口径下
  也报同样的结果 → 证明不了边界。已加第三类校准 `naiveSubstring`，两条现在都能区分。
- **（硬，已改）工单点名的连写形态缺失**：补 `import-then-reexport`（`import { x } … ; export { x };`）。
- **（判断，已改）重复代码**：`probe-00d/00e/00f` 原先各自内联了一整份模板感知掩码 ＋ 本地
  `identRe`（还是**静默跳过**版，与落地版的"大声失败"已经分叉）。已全部改成 import 单源
  （`unusedImports` / `maskCommentsAndStrings` / `hostBody`）；`probe-00-survey.mjs` 与有行号
  归因 bug 的旧 `probe-00c` 一并重写/删除（旧 00c 把 import 切片替成**不含换行**的等长空格，
  行号整体偏移——已改成保留换行）。
- **（判断，不采纳）`parseModuleImports` 的 `names`/`locals` 平行数组**：评审建议合成
  `bindings: [{source, local}]`。不采纳的理由：那是**既有**解析器契约，被判据 D / T / 图对账 /
  `reachable` / `callPositionEdges` 共用；本条工单的硬约束是最小爆炸半径，换返回形状属独立重构。
  已记账（`.scratch/backlog.md` §10 未立项候选里带一句）。
- **（判断，不采纳）改名 `maskCommentsAndStrings` / `maskNonCode`**：评审指出两者不是平行命名。
  不采纳的理由：前者是**既有**公开名（多份文件头与判据都点名引用它），改名的收益（对称）小于
  全仓改引用的风险；新名 `maskNonCode` 说的是"掩掉非代码的部分"，与实现一致。

#### ⑧ 门禁读数

| 门禁 | 读数 |
|---|---|
| `node --test "tests/js/*.test.mjs"` | **1688 passed / 0 fail**（与基线同数——本工单没动用例，03 才加） |

`static/js/**` **零改动**（清点是 02 的交付），故浏览器门禁与 pytest 本单不必跑（02 会跑全三支）。

#### ⑨ 未顺手做（与 spec「范围外」一致）

常量值形态、C6、C7、`.scratch` 一次性探针的失效修复（`frontend-import-fossils/guard-red-proof.mjs`
一类读**旧版源码**的探针本轮不碰）、零调用私有死函数、`tests/js/**` 与 `tests/browser/**` 自身的未使用具名、
`parseModuleImports` 的返回形状重构（见 ⑦）。
