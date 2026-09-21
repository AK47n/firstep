# 03 — 新判据进闸门 ＋ 账本收尾

**要做什么：** 把 01 立的判据接进前端门禁（`node --test "tests/js/*.test.mjs"`），**当场生效**：
此后任何模块新增一个自己用不到的具名 import，**推之前就红**。然后按仓库口径收尾：账本更正
（`.scratch/backlog.md` §10 那条候选结清 ＋ **更正工单 02 的记账**）＋ 本机读数写回
`docs/agents/local-environment.md` ＋ 三门禁各跑一遍记数。

**被谁阻塞：** 02（清点处置 12 处 ＋ 级联）

**状态：** resolved

## 验收标准

- [x] 用例住**一处**并说明取舍：优先扩**既有** `tests/js/import-usage-guard.test.mjs`（这条不变量本就
      由它守，"一条判据一个文件"）还是新开文件——取舍写进 Comments。
- [x] 闸门内用例（**每条都能红，不是"断言为空"**）：
      ① **抽取器体检**：模块数 / 语句数 / 具名数三条**保守下限**都在，且**正向对照**——注入一条死 import
      必须报出（抽取器静默失效要当场红，而不是断言为空变真空绿；先例 `ui-dom-contract.test.mjs`
      「那种绿比红更坏」）；
      ② **判据 = 0**：`static/js/**` 全部 132 个模块（含 js/ 根 `app.js` / `boot.js`）零未使用具名；
      ③ **假绿反例与反向对照进闸门**（合成片段，注入自带自检）：注释 / 块注释 / 行尾注释 / 字符串 /
      正则 / 模板文本段 / 更长标识符 / `$` 边界里的同名词**必须报出**；模板表达式 / 再导出清单 /
      别名本地名 / 裸装载**必须不报**（防假红）。
- [x] 账本：
      ① `.scratch/backlog.md` §10 末那条候选（"9 处清点前就已死的模块级 import"）**结清**，
      并写进**更正**：正确口径实测 **12** 处（不是 17/18）；`WRITE_GUARD_ACTIONS ×4` 是**别名误报**
      （`WG.fix` / `WG.revise` / `WG.task` / `WG.params` 在正文里真被用着，实测是 ×5 处误报）；
      **新发现**：死 import 会给判据 D 当**假消费者**（`fx/core.js::downloadedPercent` 的唯一消费者
      就是一条死 import，本轮级联摘掉它的 `export`）；判据面已从装载根扩到 132 个模块并进闸门。
      ② `docs/agents/local-environment.md`：更新前端门禁 / 浏览器门禁 / pytest 三条读数，
      并补记本轮的判据面与落点（`tests/js/*.test.mjs` 自动进闸门；改动落 `static/js/ui/` 触发浏览器门禁）。
      ③ `CONTEXT.md`「前端纯函数单源」一带如需补一句口径（零未使用具名已覆盖每个模块），按实补。
      ④ **不改**已 resolved 的 `.scratch/export-surface-guard/issues/02-sweep-111-exports.md`
      （照工单 03 先例"那份记录属已 resolved 的工单，本轮不改，如实挂在这里"）——更正写在 ① 与本工单。
- [x] **三门禁各跑一遍并记数**（最终状态上）：`node --test "tests/js/*.test.mjs"`（基线 1688 ＋ 本工单新增）／
      `python -m pytest -n auto -q`（基线 5049 passed + 1 skipped）／
      `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`（基线 26）——读数与耗时写进 Comments；
      并按工单 02 §⑥ 那条环境事实注明**行尾（LF / CRLF 检出）**对读数的影响。
- [x] 工单 02 留下的读数复核（`red-proof.txt` / `diff-proof.txt` / `verify-removal.txt`）在**最终状态**上
      仍然成立（新增的守卫文件会进"消费侧模块"计数，若红证读数因此漂移，如实记账）。
- [x] **未顺手做**（与 spec「范围外」一致，逐条列进 Comments）：常量形态恢复、C6（555 个 id）、
      C7（73 个私有符号）、`.scratch` 一次性探针的失效修复、装载根"零裸装载"的重议、
      `tests/js/**` 与 `tests/browser/**` 自身的未使用具名、零调用私有死函数的清理。

## Comments

### 2026-09-21 实现记录

#### ① 落点取舍：**扩既有 `tests/js/import-usage-guard.test.mjs`**（工单要求写清取舍）

不新开文件，理由两条：

- **一条不变量一个文件**：这个文件从 `frontend-import-fossils/01` 起就是"导入面"这件事的现场
  （文件头记着 259 个化石名的代价），本单是把**同一个不变量**的取数面从装载根扩到每个模块——
  换个文件就成了"同一条不变量分两处守"（Divergent Change）。
- **"缝越少越好"指判据单源**，那一条没变：判据本体仍在 `tests/js/import-usage.mjs`，
  掩码在 `tests/js/boot-contract.mjs`，本文件只是闸门内的调用点。
- **合成用例表单源**：`tests/js/import-usage-cases.mjs`（工单 03 双轴评审收敛）——
  闸门与 `.scratch` 的红证脚本（`probe-01` / `probe-02`，经 `.scratch/.../synthetic-cases.mjs` 薄再导出）
  **共用同一张 25 条表**。为什么要搬进 `tests/js/`：闸门不许依赖 `.scratch/` 这种一次性证据目录，
  但"各抄一份"已经实测分叉过（第一版闸门内联 19 条 vs `.scratch` 24 条，缺 5 条、且只有一侧带注入自检）。

#### ② 闸门内 7 条用例（每条都能红——不是"断言为空"）

| 用例 | 保证什么 |
|---|---|
| 抽取器不静默失效（装载清单） | 原用例：≥40 条 import、说明符全在 `/js/` 下、≥50 个具名 |
| **判据取数面体检（全模块）** | ≥120 个模块 / ≥400 条语句 / ≥1000 个具名；**正向对照**：往 `ui/flash.js` 注入一条死 import **必须报出**，且注入本身自检（锚点键错会当场红；用 `.some(...)` 而不是 `.find(...).text`——后者在键缺失时抛 TypeError，那句自检提示反而永远打不出来，双轴评审实测） |
| **零未使用具名（装载根 ＋ 全部 132 个模块）** | 本单的主判据；失败时逐条打印 `模块 ← 说明符: 名字` |
| **合成用例表（单源）** | 跑 `tests/js/import-usage-cases.mjs` 的全部 25 条：假绿反例（注释 / 块注释 / 行尾块注释 / 单双引号串 / 正则 / 模板**文本段** / `${` 语法 / 更长标识符 / `$x`·`y$`）**必须报出**；反向对照（模板表达式 / 嵌套模板 / 对象字面量花括号 / 注释与代码并存 / 再导出清单 / `import` 后连写再导出 / 别名本地名 / 裸装载 / 正则里的引号 / `$` 的真使用）**必须不报**；每条**自带注入自检**（`bodyIncludes`）与**差分校准**（旧口径 / naive 掩码 / 朴素子串） |
| **合成用例表自身体检** | 假绿反例 ≥8 条、反向对照 ≥8 条、带差分校准 ≥8 条；**每条必须有 `bodyIncludes` 或属于"语料本就该零出现"的形态**（防"用例写歪了两边都空"） |
| 装载根的具名清单非空且无重复名 | 原用例（口径写明**装载根**——它只查 boot.js，评审指出名字会误导） |
| 装载根零裸装载 | 原用例（裸装载是那次退场的隐式边） |

#### ③ 判据强度自检（`probe-04-guard-strength.mjs` → `guard-strength.txt`）

「真源码上全绿」证明不了判据有牙齿，所以把**真源码里的判据**改坏再跑闸门，期望**变红**：

```
① 前置干净性：注入前跑一次闸门 → 绿
  PASS  旧口径-不掩注释字符串            闸门退出码 1（首条红：零未使用具名）
  PASS  naive 掩码-模板表达式一起掩掉     闸门退出码 1（首条红：零未使用具名）
  PASS  取数面缩回只有装载根              闸门退出码 1（首条红：判据取数面体检）
复原复核：所有被注入文件与注入前**逐字节相同**
**强度自检：PASS**
```

**第三条注入的期望是"首条红 = 判据取数面体检"**（03 评审指出：把它写成"模块级死 import 无人报"
名不副实——那条注入只把 `ALL` 缩成 `boot.js`，**零未使用那条照样绿**，拦住它的是取数面下限绊线；
不设下限这条注入会静默溜过）。现在探针**逐条断言首条红是哪条用例**，对不上就 FAIL——
"名不副实的自检比不做还坏"。

⚠ 本件**会真改库内文件**（`tests/js/import-usage.mjs` / 守卫本身），跑完逐字节复原并在收尾再核一次
——**别和测试套件同时跑**（工单 `module-hwcheck/09` 记过这个坑）。

#### ④ 账本四处

1. `.scratch/backlog.md` §10 末那条候选（"9 处清点前就已死的模块级 import"）**结清**，
   并写进**三处更正**：① 真实体量 **12** 处（旧口径 17 = 12 真死 ＋ 5 别名误报）；
   ② `WRITE_GUARD_ACTIONS` **是误报**（`WG.fix` 等真在用，实测 ×5 而非 ×4）；③ 那 7 处"**工单 02 §②-3
   没点名、但同一旧口径其实也报了**"的名单（**不是**"旧口径看不见"——`C − A = 0 处`，03 评审实测更正）；另记**新发现**："一条死 import 会给判据 D 当**假消费者**"（`fx/core.js::downloadedPercent`
   的唯一消费者就是一条死 import，本轮级联摘它的 `export`）。
2. `docs/agents/local-environment.md`：本单读数（前端门禁 **1691** / 浏览器 **26** / pytest **5049+1**）
   与本轮两条口径事实（两种掩码口径**不得混用**；`tests/js/import-usage.mjs` 与 `boot-contract.mjs`
   属"判据共享件"，只改它们时本地 pre-push 不带起浏览器门禁——与那条已知本地/CI 落差同源）
   写进「三个 spec / 26 条用例」那一段之后。
3. `CONTEXT.md`「前端纯函数单源」那条长句里补一句**导入面**的口径（本地名 / 注释字符串模板文本段不算 /
   模板表达式算 / 再导出算消费 / 裸装载合法 / 两种掩码口径）。
4. **不改**已 resolved 的 `.scratch/export-surface-guard/issues/02-sweep-111-exports.md`
   （照 `export-surface-guard/03` 的先例："那份记录属已 resolved 的工单，本轮不改，如实挂在这里"）
   ——更正写在 ① 与本单 Comments。

#### ⑤ 三门禁读数（最终状态上各一遍）

| 门禁 | 读数 |
|---|---|
| `node --test "tests/js/*.test.mjs"` | **1691 passed / 0 fail**（6.4s；基线 1688 ＋ 本单 3 条） |
| `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` | **26 passed / 0 fail**（80.7s；另一次 79.1s） |
| `python -m pytest -n auto -q` | **5049 passed / 1 skipped / 0 fail**（138.9s；另两次 135.0s / 138.0s 同数） |

读数形态：本机工作树是 **LF 检出**，`tests/js/ai-action-refs.test.mjs` 与
`tests/js/module-intro-detail.test.mjs` 按字面 LF 断言源码，LF 下全绿（CRLF 检出会 2 red，
见 `local-environment.md` 那条环境事实）——上面三个数**都是 LF 检出下测的**。
本单只动 `tests/js/**` 与文档，未触浏览器门禁落点，但**仍在最终状态上复跑了一遍**（26 绿）。

**一条同轮量到的既有偶发（与本次改动无关，已记进 `local-environment.md`）**：
评审那一轮 `python -m pytest -n auto -q` 报 **5048 passed + 1 failed + 1 skipped**，
红的是 `tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest`——它在 `--full` 路径上**真的会跑
整支浏览器门禁**（26 条真浏览器用例），并行争用下某个 spec 超时。同一工作树证据：该文件单跑
**29 passed / 79s**、整支 `-n auto` 两次复跑都是 **5049 + 1 skipped**、独立浏览器门禁 **26 passed**。
与工单 `export-surface-guard/02` §⑥ 记的两条"并行负载下假红"同源。

#### ⑥ 工单 02 留下的读数复核

清点后的读数（`red-proof.txt` / `diff-proof.txt` / `verify-removal.txt`）在最终状态上仍成立：
本单**没有新增任何文件**、也没动任何产品源码（`static/js/**` 零改动）——唯一变化是给既有守卫
`tests/js/import-usage-guard.test.mjs` 加用例、把合成用例表搬进新增的
`tests/js/import-usage-cases.mjs`（**判据共享件**，不是守卫；它跑得动只是因为被守卫 import）。
判据 D 的消费者集合按 `tests/js` 的 `.mjs` 文件算，这两处改动不新增页面侧的消费边，
故判据读数一格没动（实测 `red-proof.txt` 复跑同数）。
（**评审更正**：本节第一版写"新增的守卫文件会让消费侧计数 +1"——查无实据，已改。）

#### ⑧ 双轴评审整改（`code-review`：Standards ＋ Spec 并行，只报告不修改）

**两轴独立收敛到的同一条（硬，已改）**：**闸门里的合成用例是第二份手抄表、且已经与 `.scratch` 的
那张分叉**（19 条 vs 24 条，少 5 条；只有 `.scratch` 那份带注入自检与差分校准）。已把用例表
**搬进 `tests/js/import-usage-cases.mjs`**（闸门与 `.scratch` 红证脚本共用同一张 25 条表），
`.scratch/.../synthetic-cases.mjs` 降为薄再导出——仓库自订的"同一件事不抄两份"在闸门这一侧同样成立。

其余整改：

- **（硬，已改）闸门那 19 条没有"注入落上"自检**（评审实测：把 `mk("const a = 1; // esc 在这里")`
  降级成 `mk("const a = 1;")` 后用例照过）——即"注释里不算使用"这些用例证明不了自己宣称的形态。
  搬进单源表后，每条都带 `bodyIncludes` 注入自检与差分校准；另加一条**用例表自身体检**用例
  （正反两向条数下限 ＋ 每条必须有自检或属"本就该零出现"形态）。
- **（硬，已改）自检自身先炸**：取数面体检里 `patched.find(...).text` 在锚点键缺失时抛 TypeError，
  那句"注入没落上会静默空转"的提示反而永远打不出来 → 改用 `.some(...)`（先例
  `export-surface-guard.test.mjs`）。
- **（硬，已改）"7 处旧口径看不见"是错的因果**（Spec 轴实测反驳）：`survey-00-criteria-delta.txt`
  明写 `C − A = 0 处`——那 7 个名字**旧口径同样报出**（17 = 12 ＋ 5 别名误报），它们的准确身份是
  "**同一口径也报了、只是工单 02 §②-3 没点名**"。已更正 spec 两处、`backlog` §10、工单 01/02/03 的
  相应措辞，并把 `probe-02` 的 `INVISIBLE_TO_OLD` 改名为 `NOT_IN_TICKET02_LIST`（打印文案同步改）。
- **（硬，已改）`local-environment` 抄了工单 02 的旧耗时且自相矛盾**：新段原写
  "浏览器 84.1s（本轮改到 `static/js/ui/` → 必跑）/ pytest 156.8s"，而本单只动 `tests/js/**` 与文档
  ——已改成本轮实测（79.1s / 135.0s）＋ 明确"这三个数都在 LF 检出下测得"，删掉那句张冠李戴的理由。
- **（硬，已改）probe-04 第三条注入名不副实**：它只把 `ALL` 缩成 `boot.js`，首条红其实是取数面
  **下限绊线**，不是"模块级死 import 无人报"。已改注释与期望，并让探针**逐条断言首条红的用例名**。
- **（硬，已改）"新增守卫文件 → 消费侧 +1"查无实据** → 见 ⑥ 末尾的更正。
- **（判断，已改）闸门用例改名**：`具名清单非空且无重复名` → `装载根的具名清单非空且无重复名`
  （它只查 boot.js）。
- **（判断，不采纳）把 `[{ key: "boot.js", … }, ...MODULES]` 提成 `boot-contract.readPageModules()`**：
  那是跨守卫/跨探针的公共面改动，本条工单的硬约束是最小爆炸半径；如实记账不采纳。
- **（判断，不采纳）"勾选工单 02 的验收框违反了 spec 第 143 行"**：那一行说的是**不改
  `export-surface-guard/02` 那份已 resolved 的工单**（"那份"指前文那个），而 `module-import-usage/02`
  是本特性自己的工单，按 `docs/agents/workflow.md` Step 4 就该 `- [x]` ＋ `resolved`。评审读错了指代。
- **（判断，已改）清点执行器在清点提交之后一度跑不动**：`apply-removal.mjs` 的 base 自校验要求
  "base 与 HEAD 的 `static/js` 逐字节相同"——那只在清点**前**成立；清点提交之后重跑会（正确地）拒写，
  但工具就此变成死件。已改成**状态感知**：`HEAD == base`（清点前）或 `HEAD == base − 删除区间`（清点后）
  都算"base 选对"，其它一律拒写。现在重跑会打印 `HEAD 状态：清点后（HEAD 已是清点结果）`，
  并**重新证明**"盘上的字节 == base − 锚点区间"；`verify-removal.txt` 已按新报告复算
  （同一命令 `--write` 落盘后 `git status -- src/contest_generator/static` 为空 = **逐字节幂等**）。

#### ⑨ 未顺手做（与 spec「范围外」一致）

常量形态（number/string/object）、C6（555 个 id）、C7（73 个私有符号）、`.scratch` 一次性探针的
失效修复、装载根"零裸装载"的重议、`tests/js/**` 与 `tests/browser/**` 自身的未使用具名
（判据面只到 `static/js/**`）、零调用私有死函数（`ui/generate-fix.js::runCompileOnce` 一类）、
`parseModuleImports` 返回形状的重构（01 Comments ⑦ 记了不采纳的理由）。
