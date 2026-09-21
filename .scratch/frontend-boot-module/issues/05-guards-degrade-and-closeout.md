# 05 — 337 行登记表退化 + 不变量进闸门 + 收尾

**要做什么：** 把两张手工守护网换成结构不变量：`fx-guard` 的 337 行 `DOMAINS` 名字表删掉，
`static-import-guard` 的"装载根对账"扩成**全图对账**；新增的不变量（从 boot 可达 / 求值期
零副作用）进前端门禁。然后按仓库口径收尾：红证复跑（base 红 / 工作树绿）、三门禁各一遍、
账本更新。

**被谁阻塞：** 04

**状态：** resolved

## 验收标准

- [x] `tests/js/fx-guard.test.mjs` 的 `DOMAINS` 表**删除**（337 行 → 结构不变量），换成：
      ① `index.html` 零 JS 定义（`function`/`const`/`let`/`var`，含 `export` 前缀写法）；
      ② **装载根 `boot.js` 零 `function` 定义**（纯函数单源在 fx/——宿主块搬进 boot.js 之后，
      "双源回退"的检查面必须跟过去，只判 index.html 会半盲；这条同时替代原来逐名正则的
      "宿主不得重定义"语义，且更严：装载根一个 `function` 都不许有）；
      ③ 每个 fx/ui 模块从装载根（boot.js）可达（掉出模块图 = 静默失效，2026-09-12 那类）
- [x] `tests/js/static-import-guard.test.mjs`：保留"index.html 零 import"＋"清单↔导出对账"
      （根 = boot.js），**新增全图 import↔export 对账**：每个前端模块的每条具名 import 都
      必须是目标模块真导出的名字（解析器要**注释感知**——`import {\n // 注释\n name\n}` 形态
      在现状里真实存在，探针第一版就在这里误报过）
- [x] `tests/js/import-usage-guard.test.mjs`：根 = boot.js ＋ **零裸装载**（裸装载正是本次
      退场的那条边；清单里再有裸装载 = 回退）
- [x] **接线不变量进闸门**：boot 装载的 ui 模块中，凡"boot 是唯一装载来源"者 ＋
      `EXPLICIT_WIRING_MODULES` 登记的 11 个，求值期列 0 副作用必须为 0（判据住
      `tests/js/boot-contract.mjs`；登记表自带的 `registryProblems` 体检也要绿——
      "登记了却没搬/没调用"当场红）
- [x] 守卫自身健康检查：抽取器不静默失效（零 import / 清单条数 / 可达模块数下限），
      照既有守卫先例
- [x] **红证复跑**：`node .scratch/frontend-boot-module/probe-01-red-proof.mjs` →
      ① base 自校验通过、② ①③ 判据在 base 上红、④ 强度自检四条全成立、③ **当前工作树绿**；
      输出落 `.scratch/frontend-boot-module/red-proof.txt`
- [x] 收尾三门禁各跑一遍并记数：`python -m pytest -n auto -q`、
      `node --test "tests/js/*.test.mjs"`、`node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`
- [x] 账本更新：`CONTEXT.md`（前端纯函数单源/架构要点里"index.html 模块区仅剩 …"那句要
      改成"装载根 = boot.js"的口径）、`.scratch/backlog.md` 第 10 / 13 节那两条挂账结清；
      实测读数（前端门禁 / 浏览器门禁 / pytest 条数）写进 Comments
- [x] 未顺手做：C6（555 个 id 耦合）、C7（73 个私有符号）、删墓碑注释、9 个"另有 importer"
      模块的顶层接线、`ui/delivery.js` 挂桥的既有事实、F5 竞态

## Comments

### 2026-09-21 实现记录

**① 登记表退化**（验收物）：

| 文件 | 变化 |
|---|---|
| `tests/js/fx-guard.test.mjs` | **333 行 → 86 行**：`DOMAINS`（337 行里那张逐名登记表）**删除**，换成 5 条用例——抽取器体检（带**正向对照**：注入的定义必须被报出）＋ ① `index.html` 零顶层定义 ＋ ② 装载根 `boot.js` 零顶层定义 ＋ ③ `index.html` 脚本块恰好两处（head 主题 + 装载标签）＋ ④ 每个 fx/ui 模块从装载根可达 |
| `tests/js/static-import-guard.test.mjs` | 5 条用例：① index.html 零 import；② 装载标签唯一 + 清单路径存在；③ **全图 import↔export 对账**（替代被删的名字表提供的"被 import 的导出存在性"保护；原先那条"装载根清单↔导出"是它的弱副本，已删）；④ **分层禁环**（任何 ui/app 不得 import boot）；⑤ 抽取器体检 |
| `tests/js/ui-dom-contract.test.mjs` | ＋2 条闸门判据：**接线不变量**（boot 唯一来源 ＋ `EXPLICIT_WIRING_MODULES` 11 项求值期零接线）与**登记表体检**（单向：登记了却没搬 / 搬了却没调用都红） |
| `tests/js/boot-contract.mjs` | ＋`topLevelDefinitions` / `anyDepthDefinitions`（HTML 侧判任意缩进）＋ `modulesImportingLoadRoot`（禁环判据）；**零消费方导出降为内部件**（`LOAD_ROOT_KEY` / `inlineScripts` / `topLevelEffects` / `withoutInitDefinitions` / `reachableWithBodies`）；`scriptBlocks` 因 fx-guard 新判据要用而**保留导出**（评审第 1 轮把它降级打崩了 `wrap-wiring.mjs`，已改回并复跑该脚本） |

**② 红证复跑**（`red-proof.txt`，退出码 0）：① base 自校验通过；② 判据在 base 上红
（① 45 条 import / ③-a 5 条裸装载 / ③-b 11 个模块 96 条接线）；④ **强度自检 9/9**（删装载→
可达性红、摘导出→对账红、塞 function→零定义红、指向不存在模块→对账红、init 忘调→调用点红、
注释感知、**登记那一半兜底**、**装载根塞顶层定义→报出**、**给已显式化的模块加一条求值期接线→
接线不变量报出**）；③ **当前工作树绿**（收口状态）。

**③ 收尾三门禁**（各一遍）：

| 门禁 | 读数 |
|---|---|
| `python -m pytest -n auto -q` | **5049 passed + 1 skipped / 0 fail（201.7s）** |
| `node --test "tests/js/*.test.mjs"` | **1679 passed / 0 fail**（退化前后：1717 → 1679。旧 `DOMAINS` 是**每域文件一条**用例、实为 **46** 条；删 46 → 1717−46=1671，新增 8 条结构判据（fx-guard 5 ＋ static-import-guard 净 +1 ＋ ui-dom-contract 2）→ 1679，闭合） |
| `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` | **26 passed / 0 fail（≈113s）** |

真浏览器冒烟最后一遍：`smoke-final.txt` —— 434 条记账 / 指纹 `4288323085`、0 pageerror、
fx 探针桥 6 个全在、**工单 03 的 5 个 + 工单 04 的 6 个模块接线全在**、`#delivery-actions`
加载即写、点击有反应、各渲染读数一致。

**④ 账本**：`CONTEXT.md` 两处定稿（`ui 层测试缝` 行的装载根口径 ＋ `架构要点`「前端纯函数单源」
那一整行：装载根 / 零 import 零定义 / 显式 init 与判据 / 三条结构不变量 / 全图对账 / 名字表已删）；
`.scratch/backlog.md` 第 10 节与第 13 节两条挂账**结清**（含"墓碑注释现在住在 boot.js"
与"delivery 挂桥挪进 initDelivery、语义不变"两条更正）。

**⑤ 未顺手做**（与工单一致）：C6（555 个 id 耦合改造——本轮 id 数 555 一个没变）、C7（73 个
私有符号公开化）、删迁移墓碑注释、其余 9 个"另有 importer"模块的顶层接线、`ui/delivery.js`
挂桥的既有事实本身、F5 竞态。

**⑥ 一处记账（本轮发现、未改）**：本地 pre-push 的浏览器门禁落点只认
`tests/browser/`、`static/js/ui/`、`static/index.html`、`static/js/boot.js`、`static/js/app.js`
——而 `tests/js/boot-contract.mjs` / `import-usage.mjs` / `ui-dom-contract.mjs` 这几个**判据共享件**
被浏览器夹具间接 import（`ui-contract-fixture.mjs` → `import-usage.mjs` → `boot-contract.mjs`），
只改它们**本地**不会带起浏览器门禁（**CI 的 `browser-suite` job 不受路径筛选影响，照跑**）。
落点表要不要跟着"共享件"再扩一次，属闸门选择策略的独立话题，另立。

**⑦ 证据目录的三处增删（如实记账）**：删了 `probe-01-red-proof.txt`（`tee` 缺省命名的重复落档，
内容与 `red-proof.txt` 同时段重复）、`smoke-03.txt`（固定 sleep 时代的**假读数**留档：592→421 那条
时序竞态，已被 `smoke-03-before/after.txt` 与随后的确定性就绪信号取代）、`survey2.txt`（`survey-02-toplevel.txt`
的孤儿副本，且内容自相矛盾）；新增 `smoke-final.txt`（收口那一遍）。三处的"删"都是为了不留
**互相矛盾**的证据，不是为了少留证据。

### 2026-09-21 双轴评审整改（规范轴 6 条 / spec 轴待回）

评审独立复跑并核对现场后给出 6 条，**三条硬的都真**，逐条整改：

- **（硬 1）收口过度打崩消费方**：`topLevelEffects` 降为内部件时漏看 `.scratch` 探针
  （`wrap-wiring.mjs` 仍具名 import 它）→ 该脚本会链接期报错。已改成只用
  `maskCommentsAndStrings` + `wiringEffects`；并**当场复跑**该脚本确认能跑（`params.js` 现在
  0 条接线，脚本正确走空分支）。`scriptBlocks` 因为 fx-guard 新判据要用，**改回导出**。
- **（硬 2，最严重）登记表体检能被墓碑注释喂绿**：`registryProblems` 原先在**未掩码**的 boot.js
  全文上判调用点——删掉真调用 `initGenerateActions();` 后，体检命中的是墓碑注释里的同名文字，
  照样报绿。已改成在 `maskCommentsAndStrings(rootText)` 上判；并新增强度自检 ⑩
  **"删掉真调用、只留注释里的同名文字 → 体检必须红"**（实测：报出 `ui/generate-core.js`）。
- **（硬 3）"双向体检"是过度声称**：`registryProblems` 只查"登记了的必须成立"，反向
  "搬了却没登记"没有可判定的结构标记。已把函数文档、用例名与断言文案、`CONTEXT.md` 的说法
  统一改成**单向**，并写明为什么反向不可判定。
- **（判断 4）退化确实少了两块，此前没说明**：旧表 469 个名字里 28 个带 `typeof` 断言
  （**类型维度整体消失**）；`graphBreaks` 只覆盖"被 import 的名字"，评审点出 7 个全图零引用的
  导出（`CCS_PIECE_NAMES` / `maincScrollToRange` / `codeEditorHighlight` /
  `HWCHECK_VERDICT_FALLBACK` / `BUY_DECISIONS_KEY` / `SETTINGS_DEFAULT_COLLAPSED` / `wfNum`）
  改名或删除不再变红。已把这两条**写进 `fx-guard.test.mjs` 的文件头与 `CONTEXT.md`**（如实记账），
  并把"死导出清点"记进 backlog 另立。
- **（判断 5）列 0 口径有缝 + 断言为空缺正向对照**：`(function(){…})()` 这类**表达式形态**的
  内联 JS 既不是 import 也不是"顶层定义"，①② 都抓不到。已加第四条不变量：**index.html 的脚本块
  恰好两处**（head 主题脚本 ＋ 一条装载标签）；同时给 fx-guard 加**正向对照**（把
  `function probeControl(){}` / `<script>const probeControl = 1;</script>` 喂给抽取器，必须报出
  ——先例 `ui-dom-contract.test.mjs`「那种绿比红更坏」）。
- **（判断 6）重复与弱副本**：`topLevelDefinitions` 与 `DECLARATION_RE` 的同一正则写两遍 → 已
  合成一处；`static-import-guard` 的"清单↔导出对账"被"全图对账"完全包含 → **删掉弱副本**，
  只留全图对账（"缝越少越好"）。

**整改后**：红证强度自检 **12/12**（新增 ⑩ 登记体检注释喂绿、⑪ IIFE 内联脚本、⑫ 调用点判据注释喂绿
三条）、工作树仍绿；前端门禁 **1679 passed / 0 fail**。

### 2026-09-21 spec 轴评审整改（该轴 7 条）

- **（最严重，实测）判据 ②/① 只认列 0，缩进形态溜得过去**：往 head 内联脚本塞**缩进四格**的
  `const` → `inlineDefinitions` 报 0、脚本块仍 2 个 → fx-guard ①③ 全绿；而它替代的旧逐名正则
  不锚列，**这一处比原表更弱**。已加 `anyDepthDefinitions`（HTML 侧判**任意缩进**，装载根那侧
  仍用列 0——boot.js 的回调体里满是缩进的 `const`，混用会全假红），自检 ③ 改成注入缩进形态
  （实测报出 7 条）。
- **（实测）"init 没人调"判据仍注释盲**：把 `initScoreChecklist();` 之类注释掉后判据报 0。
  根因在 `ui-dom-contract.unreachableModules` 拿**未掩码**正文判调用点。已在拼 `bodyText` 时
  掩码；新增自检 ⑫（注释掉 `initGlossary();` → 必须报出，实测报出）。
- **工单 Comments ① 表未随整改更新**（仍写 59 行 / 4 条 / ③ = 可达）：已按现码改写
  （86 行 / 5 条 / ③ = 脚本块恰好两处 / `scriptBlocks` 已改回导出）。
- **读数口径**：1717 → 1679 的差额此前写成"少 57 条"，实为旧 `DOMAINS` **每域文件一条**用例
  = **46** 条（1717−46+8 = 1679 闭合），已更正。
- **AC 复选框与状态**：本工单与 01-04 的验收标准已逐条勾选，状态置 `resolved`。
- **证据三处增删**：见 §⑦（都为了不留互相矛盾的证据）。
- 评审另注：它复跑浏览器门禁时首跑 24/2，疑与实现者同时改 `boot-contract.mjs` 相撞——复核后
  连跑两遍均 **26/0**，判定为并发写盘期间的读数，不是产品问题。
