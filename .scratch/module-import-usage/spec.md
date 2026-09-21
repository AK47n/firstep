# spec — 零未使用具名 import：从装载根扩到每个模块（`module-import-usage`）

## 问题陈述

「页面不许导入它不使用的名字」这条不变量住在 `tests/js/import-usage.mjs`，而它的**取数面只有
`static/js/boot.js`**（装载根，工单 `frontend-boot-module/02` 定的）。所以判据宣布的"零未使用具名"
只对**装载根那 60 多条 import** 有证明力，对 106 个有 import 边的模块**一点证明力都没有**。

代价分两截：

- **已经发生的**：模块级一堆死 import 没人看着。清点（工单 `export-surface-guard/02` §②-3）
  自己把口径补在清点脚本里、按"不得比清点前多"过了关——而"清点前"本身就是 17 处红的。
- **正在发生的**：死 import 不只是"多写几个字"。它还是**判据 D（零消费者导出）眼里的一条消费者**——
  一条死 import 能把一个真正没人用的导出**喂绿**。本轮实测到一处活样本：
  `fx/core.js::downloadedPercent` 的唯一消费者，就是 `fx/full-update.js` 里那条从没用过它的 import。

还有一截是**口径本身错了**（本轮复核实测）：

| 口径 | 读数 | 问题 |
|---|---|---|
| 工单 02 用的那个（`unusedImports`：正文只剥整行 `//`，按**源名**查） | **17** 处 | 块注释 / 行尾注释 / 字符串 / 模板串里的同名词都算"用了"（假绿）；`import { A as B }` 按 `A` 查而不按 `B`（**假红**：5 处 `WRITE_GUARD_ACTIONS as WG` 全被误判成死的，其中 `WG.fix` / `WG.revise` / `WG.task` / `WG.params` 在正文里真被用着） |
| naive 掩码（`maskCommentsAndStrings` + 按本地名） | **45** 处 | 掩码件把模板串 `${…}` 的**表达式**也一并掩掉 → `${esc(x)}` 里的 `esc` 被判死。**33 处是这种假红**，照它删就是运行时 `ReferenceError` |

正确口径（模板表达式感知 + 按本地名）实测 **12** 处。

## 方案

把这条不变量**扩到每个模块**，并把这 12 处处置掉。

1. **判据单源仍在 `tests/js/boot-contract.mjs`**：把掩码分词器扩成**模板表达式感知**——同一份实现，
   新增 `maskNonCode(text)`；`maskCommentsAndStrings(text)` 的语义、调用路径、所有既有判据（D / T /
   图对账 / 接线）**一字不变**。
2. **判据本体仍在 `tests/js/import-usage.mjs`**（这条不变量的家）：正文换成 `maskNonCode`，
   判定改按**本地名**，取数面从"只有装载根"变成"任意模块"——同一核心函数，装载根不再特殊。
3. **处置 12 处死 import**：11 处从具名清单里摘掉那个名字，1 处（`ui/code-compile.js` 那条）语句整条变空
   → 整条删。**正文（函数体 / 监听器 / markup / CSS / 555 个 id）一字不动**，尾换行逐字节不变。
4. **1 处级联**：`fx/core.js::downloadedPercent` 的唯一消费者正是本轮要摘的那条死 import ——
   摘完判据 D（已在闸门里）会从 0 变 1。照工单 `export-surface-guard/02` 的级联先例，
   **摘掉 `fx/core.js:115` 的 `export ` 前缀**（定义、内部调用者 `downloadFailureText`、
   `window` 探针桥一字不动）。这条必须记账：它是"死 import 给判据 D 当假消费者"的第一个实证。
5. **进闸门**：新口径的用例落进前端门禁（`node --test "tests/js/*.test.mjs"`）。

## 用户故事

1. 作为**维护者**，我想要"零未使用具名 import"这条不变量覆盖**每一个模块**（不只是装载根），
   以便任何一处死 import 在推之前就红，而不是靠某次清点顺手扫出来。
2. 作为**维护者**，我想要判据判的是"这个名字在**代码**里有没有出现"（注释 / 字符串 / 正则 /
   模板串的文本段里的同名词都不算），以便不再出现"注释把一个死 import 喂绿"。
3. 作为**维护者**，我想要判据**不把模板表达式里的真使用误判成死**（`${esc(x)}` 里的 `esc` 算用），
   以便清点的处置不是我删一个名字、页面运行时炸一片。
4. 作为**维护者**，我想要 `import { A as B }` 按**本地名 B** 判定，以便别名导入不再被误报成死的
   （本轮实测 5 处别名里 5 处都被误报过）。
5. 作为**维护者**，我想要 `import "./x.js"` 这类**裸装载永远合法**（它有零个具名，判据不碰它），
   以便"这个模块存在的意义就是被加载"这种正当形态不被判据误伤。
6. 作为**维护者**，我想要那条从"唯一 import 边"删空语句时**改成裸装载**的处置规则写死在 spec 里
   （保住可达性），以便下次真遇到时不用现场发明。
7. 作为**维护者**，我想要 12 处死 import 一次处置干净，并且**动过的字节能逐行归因**，
   以便"行为零变化"是可验证的事实而不是声明。
8. 作为**维护者**，我想要清点后**既有判据一条都不红**（全图对账 / 可达性 / 零消费者导出 /
   调用位形态 / 接线 / 登记体检），以便清点不会把某个模块变成孤岛、也不会让一条导出失去消费者。
9. 作为**评审者**，我想要判据有**合成红证**（每条判据各自的假绿反例：注释 / 块注释 / 字符串 /
   正则 / 模板文本段 / 更长标识符 / `$` 的边界）+ **真红证**（base 显式钉那个提交、自校验选对），
   以便"判据有牙齿"和"判据在正确的那一代上真的会红"都能被独立复算。
10. 作为**维护者**，我想要清点那一步的**行尾与尾部换行逐字节不变**（用原始字节重放比对，
    不用归一化比对），以便不重演"多一个空行 / 少一个换行"那类只有逐字节才看得见的漂移。
11. 作为**维护者**，我想要账本里**更正工单 02 的记账**（真实体量 12 不是 17/18；`WRITE_GUARD_ACTIONS ×4`
    是误报不是真死；并记下"死 import 会给判据 D 当假消费者"），以便下一轮读账本的人不被旧数字误导。
12. 作为**维护者**，我想要三道闸门读数在收尾时各跑一遍并记进 Comments，以便"行为零变化"有机器证据。

## 实现决策

### 判据（单源，不许第二份解析器）

- **`tests/js/boot-contract.mjs`**（唯一 ESM 分词器/解析器所在）：
  - `maskCommentsAndStrings(text)` —— **语义与行为一字不变**（模板串整串掩掉，含 `${…}`）。
    既有判据 D / T / 图对账 / 接线全依赖它，改它就是改四条判据。
  - `maskNonCode(text)`（新增）—— 注释 / 单双引号字符串 / 正则字面量照旧掩掉；**模板串**按
    "文本段掩掉、`${…}` 表达式内部**当代码**（内部照旧掩注释 / 字符串 / 正则 / 嵌套模板的文本段）"
    处理。实现 = 同一分词器的同一份代码路径加一个模式参数（`maskCommentsAndStrings` 走 `模式=false`，
    行为与今天逐字符相同）。
  - **方向的理由**：掩码件对判据 T（"调用位 ⇒ 函数形态"）是**保守**的（模板表达式里的调用被漏掉 =
    漏报，不假红）；但对"未使用"方向**相反**，会把真使用判成死（假红）。
- **`tests/js/import-usage.mjs`**（判据本体的家）：
  - `unusedImports(script)` → `[{ spec, unused }]`：**判据本体**，宿主可以是装载根也可以是任意模块。
    正文 = `maskNonCode(宿主) − import 语句切片`（剥语句时**保长度、保换行**）。
  - 判定按 **`locals`（本地名）**：`import { A as B }` 里正文该出现的是 `B`。`names`（源名）
    只用于对账输出。
  - `hostScript` / `parseImports` / `hostBody` 保留（旧版源码红证与夹具的静态锚点仍用它们），
    但 `hostBody` 在注释里写明**不再是判据正文**（它是旧口径）。
- **口径（先定死，写进这里的才算数）**：
  - **「被使用」** = 该 import 的**本地名**出现在宿主模块的**代码**里
    （注释 / 字符串 / 正则 / 模板串**文本段**里的同名词不算），**或**经**再导出链被消费**
    （`export { x };` / `export { x as y };` 的清单里出现——那本身就是一条消费边）。
  - **裸装载**（`import "./x.js"`，零具名）**永远合法**：判据不碰它。
  - 标识符边界用 lookaround `(?<![\w$])名字(?![\w$])`，**不用 `\b`**（`$` 是非单词字符，
    `\b$\b` 恒假——这个坑记在 `import-usage.mjs` 注释里）。
  - **`$` 的假绿：01 交付时已修掉（不是"已知限制"）**。原计划是把"`${` 那两个字符留在掩码正文里、
    于是含模板串的模块里名为 `$` 的 import 会被喂绿"如实记成已知限制；实现在 01 里**直接修了**——
    文本段遇到 `${` 时把 `$` 也掩掉（`$` 是替换语法、不是标识符，`{` 留着无所谓）。合成用例
    `dollar-template-substitution` 钉住它（`expect: ["$"]`）。见 `issues/01-*.md` Comments ②。

### 取数面

- 判据面 = **`static/js/**` 全部 132 个 .js**（含 js/ 根的 `app.js` / `boot.js`）。实测：106 个模块
  有 import 边（共 **496** 条语句 / **1249** 个具名），26 个零 import；裸装载 0、星号 0。
- 装载根不再是特殊宿主：同一核心函数跑同一遍。既有守卫（`import-usage-guard.test.mjs` 的
  "零裸装载"）**照旧只对装载根**——那条不变量是装载根独有的，本轮不动。

### 处置规则（本轮的，不是判据）

按这个顺序逐条判：

1. 摘掉那条语句里的死名；
2. 摘完语句**变空**时：
   - 该语句是**该模块唯一的 import 边** → **改裸装载**（`import "./x.js";`，保可达性）；
   - 否则 → **整条删**（模块还有别的边，可达性不受影响；裸装载在这里是多余的）；
3. 摘掉后若某条**导出**失去唯一消费者（判据 D 会红）→ **级联**：摘掉那条导出的 `export ` 前缀
   （**定义、模块内部引用、window 探针桥一字不动**）。

**逐条实测（12 处，见 `.scratch/module-import-usage/probe-00e-dead-detail.mjs` 的读数）**：
11 处语句里还有别的名字（只摘名）；1 处（`ui/code-compile.js:27`）语句整条空、而该模块另有 9 条边
（整条删）。**"唯一 import 边 → 改裸装载"这条支路本轮 0 处触发**——规则照写，读数如实记 0。

| # | 模块:行 | 死名 | 目标模块 | 处置 |
|---|---|---|---|---|
| 1 | `fx/codeview.js:9` | `languageOf` | `./highlight.js` | 摘名（留 `highlightText`） |
| 2 | `fx/full-update.js:11` | `downloadedPercent` | `./core.js` | 摘名（留 7 个）+ **级联**：`fx/core.js:115` 摘 `export ` |
| 3 | `ui/code-compile.js:27` | `getMainCDiskDir` | `/js/ui/generate-mainc-sync.js` | **整条删**（该模块另有 9 条边） |
| 4 | `ui/code-tree-ops.js:24` | `getCodeTreeFiles` | `/js/ui/codeview.js` | 摘名（留 3 个） |
| 5 | `ui/codeeditor.js:27` | `isTabSavable` | `/js/fx/codeeditor.js` | 摘名（留 17 个） |
| 6 | `ui/flash.js:8` | `$` | `/js/app.js` | 摘名（留 `apiPost, toast`） |
| 7 | `ui/generate-readiness.js:18` | `readinessRowHTML` | `/js/fx/readiness.js` | 摘名（留 5 个） |
| 8 | `ui/generate-tasks.js:28` | `resourcesOverviewHTML` | `/js/fx/task.js` | 摘名（留 24 个） |
| 9 | `ui/materials-update.js:10` | `aggregateSelection` | `/js/fx/materials-update.js` | 摘名（留 4 个） |
| 10 | `ui/md.js:8` | `toastError` | `/js/app.js` | 摘名（留 4 个） |
| 11 | `ui/pdf.js:9` | `pdfDupRemainText` | `/js/fx/pdf.js` | 摘名（留 16 个） |
| 12 | `ui/resource-board.js:9` | `resourcesToolbarHTML` | `/js/fx/resource-board.js` | 摘名（留 2 个） |

**与工单 02 记账的关系（要更正的三条）**：它记的 17/18 处里，**5 处是真死**
（`resourcesOverviewHTML` / `readinessRowHTML` / `getMainCDiskDir` / `isTabSavable` / `resourcesToolbarHTML`），
**4 处 `WRITE_GUARD_ACTIONS` 是误报**（别名按源名查），**另 7 处是它没点名的**
（`languageOf` / `downloadedPercent` / `getCodeTreeFiles` / `$` / `aggregateSelection` / `toastError` /
`pdfDupRemainText`）。**注意口径**：这 7 处**不是"旧口径看不见"**——实测旧口径在 base 上同样报出它们
（`C − A = 0 处`，见 `survey-00-criteria-delta.txt`），它们的准确身份是"**同一口径其实也报了、
只是工单 02 §②-3 的 9 处点名清单里没有**"。**不改那份已 resolved 的工单**（照工单 03 的先例），
更正写进 `.scratch/backlog.md` §10 与本轮工单 Comments。

### 硬约束（不许碰的）

- **只摘死的具名 import**（＋那 1 处级联的 `export ` 前缀）；**不动任何执行语句**。
- **正文一字不动**：函数体 / 监听器 / markup / CSS / 555 个 id / `window` 探针桥。
- **尾换行与行尾不许变**：用**原始字节**比对（把 base 的字节按删除区间重放，必须与落盘字节逐字节相等），
  **不用归一化比对**（工单 02 §③ 的教训：归一化里的 `\n+$` 折叠会把真差异抹成假绿）。
- 判据是**事实不是形状**：不以"代码外观"为主判据（不数 `export` 关键字个数、不钉语句行数）。
- **不做**：常量形态（number/string/object）、C6（555 个 id 耦合）、C7（73 个私有符号）、
  `.scratch` 一次性探针的失效修复、零调用私有死函数（`ui/generate-fix.js::runCompileOnce` 一类）。

## 测试决策

- **判据单源**：`tests/js/boot-contract.mjs`（解析器/掩码/可达性/消费边）＋ `tests/js/import-usage.mjs`
  （本条不变量）。**不新造解析器，不抄第二份走图**。
- **守卫落点**：扩**既有** `tests/js/import-usage-guard.test.mjs`（这条不变量本来就是它在守；
  "一条判据一个文件"），用例含：
  - 抽取器体检（模块数 / 语句数 / 具名数三条下限，取保守值）＋**正向对照**（注入一条死 import 必须报出）；
  - 全 132 个模块（含装载根）**0 处未使用具名**；
  - **假绿反例进闸门**：名字只出现在 `//` / `/* */` / `"…"` / `'…'` / 正则 / 模板**文本段** / 更长标识符
    里的，必须报出；出现在模板**表达式** `${…}` / `export { x };` 再导出清单 / 别名本地名里的，
    必须**不**报（防假红）；裸装载不报。
- **好测试的判据**：只断言"报出 / 不报出"这个**事实**，不钉源码形状；每条注入**自带自检**
  （断言语料真的落上，防自检静默空转——先例 `export-surface-guard.test.mjs` 的注释喂绿自检）。
- **红证两份**：
  - **合成片段**（`.scratch/module-import-usage/synthetic-cases.mjs` + `probe-01-*`）：上表每条判据的
    假绿反例 + 反向对照，逐条报 PASS/FAIL，产出 `synthetic-red-proof.txt`；
  - **真红证**（`probe-02-base-red-proof.mjs` → `red-proof.txt`）：base **显式钉 `f1c9e1c7`**（**不写 HEAD**）
    + **base 自校验**（12 个钉子名在 base 上逐条内容锚定对上；选错 base 当场大声失败）+
    判据在 base 上红 **12** 处 + **当前工作树绿（硬判）** + 合成自检全过。
- **独立机械证据**：`probe-03-diff-proof.mjs` → `diff-proof.txt`：`git diff` 每一行**必须归得了因**
  （摘名 / 整条删 / 级联 / 未改动老行），并**逐文件逐字节**断言行尾写法与尾部换行数未变。
- **既有判据复跑清单**（清点后必须全 0）：`graphBreaks` / `reachable.orphans` /
  `wiringViolations` / `registryProblems` / `bareLoads` / 判据 D / 判据 T / 星号体检 / 取数面体检 /
  `unusedImports`（装载根）/ `ui-dom-contract` 的 `unreachableModules`。
- **三门禁**：`node --test "tests/js/*.test.mjs"`（基线 **1688 passed**）、
  `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`（**26 passed**，
  本轮改到 `static/js/ui/` → 必跑）、`python -m pytest -n auto -q`（基线 **5049 passed + 1 skipped**）。

## 范围外

- 常量值形态（number/string/object）的判据、C6、C7、导出面 API 重设计。
- `.scratch` 一次性探针的失效修复（含 `frontend-import-fossils/guard-red-proof.mjs` 与
  `frontend-boot-module/probe-01-red-proof.mjs` 读旧版 `index.html` 的那两处——判据口径改了，
  它们对**旧版源码**的读数可能变化，本轮只记账不修）。
- 零调用私有死函数（`runCompileOnce` 一类）的清理。
- `tests/js/**` 自身与 `tests/browser/**` 的未使用具名（判据面只到 `static/js/**`）。
- 装载根"零裸装载"这条既有不变量的重议（本轮不动）。
- ~~判据对 `$` 的已知假绿（含模板串的模块）的彻底修复。~~ → **不适用**：那条假绿在 01 里已修掉
  （掩码文本段遇到 `${` 时把 `$` 一并掩掉），不再是范围外事项。

## 补充说明

- **本轮的口径更正有先例**：工单 `export-surface-guard/01` 的评审也发现过"判据 D 口径写错、
  且注释里'实测 0 例'是假读数"，处理方式是**当场改判据 + 在 Comments 里更正读数**。
  本轮同理：账本数字要按实测更正，不是"顺着旧数字写"。
- **数字口径自洽（逐条对账，不留"差不多"）**：

  | 集合 | 条数 | 内容 |
  |---|---|---|
  | 工单 02 的口径（`unusedImports`：不掩注释字符串、按源名） | **17** | 清点后实测（清点前 18） |
  | 正确口径（`maskNonCode` ＋ 按本地名） | **12** | 本轮要处置的全部 |
  | 差集 17 − 12 = **5** | 5 | **全是 `WRITE_GUARD_ACTIONS` 的别名误报**（工单记成 ×4，实测 ×5） |
  | 工单 02 点名的"9 处早已死" | 9 | 5 真死（`resourcesOverviewHTML` / `readinessRowHTML` / `getMainCDiskDir` / `isTabSavable` / `resourcesToolbarHTML`）＋ 4 处 WG 误报（实测也是 5） |
  | 正确口径 12 处里**工单 02 没点名**的 | **7** | `languageOf` / `downloadedPercent` / `getCodeTreeFiles` / `$` / `aggregateSelection` / `toastError` / `pdfDupRemainText`——**它们不是"旧口径看不见"**：`C − A = 0 处`（旧口径同样报出），只是不在 §②-3 的点名清单里 |
  | 正确口径 − 旧口径（`C − A`） | **0** | 反向也说明白：新口径**没有**报出任何旧口径报不出的东西，它只**少报**了 5 处假红 |

  即 `12 = 5（工单点名且真死）＋ 7（同一口径报出、但工单 02 没点名）`。实现时把这张表按**逐条销账**复核一遍。
- **本机读数基线**（`docs/agents/local-environment.md`）：前端门禁 1688 / 浏览器 26 /
  pytest 5049 + 1 skipped。收尾时把新读数写回去（**收尾实测：1691 / 26 / 5049 + 1 skipped**）。
