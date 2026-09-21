# 02 — 清点处置 12 处死 import ＋ 1 处级联（真红证 ＋ 字节级归因）

**要做什么：** 让新判据从 **12 处违规**变成 **0 处**，且**行为零变化**：按 spec「处置规则」摘掉
11 条语句里的死名 ＋ 整条删 1 条空语句（`ui/code-compile.js:27`）＋ 1 处**级联**
（`fx/core.js:115` 摘 `export ` 前缀——它的唯一消费者正是本轮摘掉的那条死 import，
不摘判据 D 会从 0 变 1）。正文（函数体 / 监听器 / markup / CSS / 555 个 id / `window` 探针桥）一字不动，
**尾换行与行尾逐字节不变**。

**被谁阻塞：** 01（判据单源与合成红证）

**状态：** resolved

## 验收标准

- [x] `.scratch/module-import-usage/apply-removal.mjs`（清点执行器）：**逐处内容锚定**（12 处死名所在语句的
      原文切片 ＋ 级联那 1 处的声明行原文），改一处报一处；**任何一处对不上就整体拒绝写盘**；
      产出 `verify-removal.txt`。
- [x] **字节级证据（本单的硬判，不用归一化比对）**：对每个改动文件，取 base `f1c9e1c7` 的**原始字节**，
      按脚本记录的**删除区间**重放一次 → 结果必须与该文件落盘后的**原始字节逐字节相等**；
      并逐文件断言**行尾写法与尾部换行字节数未变**。读数落 `verify-removal.txt`。
- [x] 改动面：**11 处摘名 ＋ 1 处整条删 ＋ 1 处级联**，落点与 spec 表逐条一致；
      `git diff --name-only` 只含 `src/contest_generator/static/js/**` 与本工单产物（`.scratch/module-import-usage/**`）；
      且**行数只减不增**（摘名/整条删/摘 `export ` 前缀都不新增行）。
- [x] **既有判据全 0**（清点后复跑，逐条打印）：`graphBreaks` / `reachable.orphans` /
      `wiringViolations` / `registryProblems` / `bareLoads` / 判据 D / 判据 T / 星号体检 / 取数面体检 /
      `unusedImports`（装载根）。**特别复跑** `tests/js/fx-guard.test.mjs`（orphans）与
      `tests/js/ui-dom-contract.test.mjs`（`unreachableModules`）——**不许把任何模块变成孤岛**。
- [x] 真红证 `probe-02-base-red-proof.mjs` → `red-proof.txt`（退出码 0；失败非零并打印 base 身份）：
      ① **base 显式钉 `f1c9e1c7`**（**不写 HEAD**）＋ **base 自校验**：12 个钉子名各自的 import 语句
      在 base 上逐条内容锚定对上、级联那处 `export function downloadedPercent` 仍在、base 上既有判据全 0
      ——**选错 base 当场大声失败**；
      ② 判据在 base 上红 **12** 处（逐条点名，并标出哪 7 处**不在工单 02 §②-3 的 9 处点名清单里**）；
      ③ **当前工作树绿（硬判）**：判据 0 处 ＋ 全部既有判据 0 违规；
      ④ 合成自检全过（**import 01 的 `synthetic-cases.mjs`**，不抄第二份用例表）。
- [x] 独立机械证据 `probe-03-diff-proof.mjs` → `diff-proof.txt`：逐文件把 base（`git show f1c9e1c7:<path>`）
      与工作树比，**每一行都必须归得了因**（未改动老行 / 摘名 / 整条删 / 级联），并单独一行报
      **"尾部换行不一致的文件：0 个"**（口径与工单 02 §③ 的教训一致：不许折叠尾随差异）。
- [x] **三门禁各跑一遍并记数**（读数写进 Comments）：`node --test "tests/js/*.test.mjs"`（基线 1688）／
      `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`（基线 26，本轮改到
      `static/js/ui/` → **必跑**）／`python -m pytest -n auto -q`（基线 5049 passed + 1 skipped）。
- [x] **未顺手做**：常量形态 / C6 / C7 / `.scratch` 探针修复 / 零调用私有死函数 /
      新判据接闸门（03 的交付）。

## Comments

### 2026-09-21 实现记录

#### ① 逐条销账（13 处 = 摘名 11 ＋ 整条删 1 ＋ 级联 1）

清点执行器 `.scratch/module-import-usage/apply-removal.mjs`（逐处**内容锚定**：目标模块 + 具名清单；
任何一处对不上就整体拒写）。落点与 spec 处置表逐条一致：

| # | 模块 | 死名 | 删除区间（base 上实测） | 形态 |
|---|---|---|---|---|
| 1 | `fx/codeview.js` | `languageOf` | `"languageOf, "` | 摘名（同行） |
| 2 | `fx/full-update.js` | `downloadedPercent` | `", downloadedPercent"` | 摘名（本行末尾，前导逗号一起摘 → 不留行尾空格） |
| 3 | `ui/code-compile.js` | `getMainCDiskDir` | 整条语句 ＋ 行尾换行 | **整条删**（模块另有 9 条边） |
| 4 | `ui/code-tree-ops.js` | `getCodeTreeFiles` | `"  getCodeTreeFiles,\n"` | 摘名（该名独占一行） |
| 5 | `ui/codeeditor.js` | `isTabSavable` | `"  isTabSavable,\n"` | 摘名（独占一行） |
| 6 | `ui/flash.js` | `$` | `"$, "` | 摘名（同行） |
| 7 | `ui/generate-readiness.js` | `readinessRowHTML` | `", readinessRowHTML"` | 摘名（本行末尾） |
| 8 | `ui/generate-tasks.js` | `resourcesOverviewHTML` | `"resourcesOverviewHTML, "` | 摘名（同行） |
| 9 | `ui/materials-update.js` | `aggregateSelection` | `"  aggregateSelection,\n"` | 摘名（独占一行） |
| 10 | `ui/md.js` | `toastError` | `"toastError, "` | 摘名（同行） |
| 11 | `ui/pdf.js` | `pdfDupRemainText` | `"pdfDupRemainText, "` | 摘名（同行） |
| 12 | `ui/resource-board.js` | `resourcesToolbarHTML` | `"resourcesToolbarHTML, "` | 摘名（同行） |
| 13 | `fx/core.js` | （级联） | `"export "` | 摘 `export ` 前缀（定义/内部调用/window 桥一字未动） |

**「唯一 import 边 → 改裸装载」这条支路：实测 0 处触发**（`verify-removal.txt` 里有一行明写）。
规则照 spec 写在脚本里：真遇到时**当场拒写**逼人显式决定（不许静默把模块变成孤岛）——
`ui/code-compile.js` 那条走的正是"否则整条删"（它另有 9 条边）。

#### ② 字节级重放（本单的硬判）

对每个改动文件，取 base `f1c9e1c7` 的**原始字节**，按锚点**独立重算**删除区间 → 重放 →
与该文件**落盘后的原始字节逐字节相等**（`Buffer.equals`，零归一化）：

```
PASS fx/codeview.js 21566 → 21554 (Δ-12) 末 6 字节 7d293b0a7d0a → 7d293b0a7d0a
PASS fx/core.js     6535  → 6528  (Δ-7)  ...
（13/13 PASS，读数与逐文件字节数在 verify-removal.txt）
```

另加两条约束（逐文件断言）：**行尾计数差**必须正好等于被整行删掉的行数、**文件末字节序列**逐字节不变。

#### ③ 独立机械证据（`probe-03-diff-proof.mjs` → `diff-proof.txt`）

只看 `git diff --unified=0` 的 hunk 形状与 base/工作树的字节，**不读执行器的中间数据**：

```
归因：未改动老行 7359 行 / 摘名 8 行 / 整行摘名 3 行 / 整条删 1 行 / 级联 1 行
**归不了因的差异：0 处**
**尾部换行/行尾不一致的文件：0 个**
→ PASS
```

**分类口径（评审整改，见 ⑥）**：判"整条删"看的是**语句**（base 与工作树各跑一次
`parseModuleImports`，语句数从 10→9 才算整条删），不是 hunk 形状——多行具名清单里"名字独占一行"
被删掉时也只有 `-` 行，但语句还活着（= **整行摘名**，属"摘名"）。所以 `摘名 = 8 + 3 = 11`。
三条计数**钉死**（11/1/1），与 spec 处置表对不上就 FAIL。

#### ④ 真红证（`probe-02-base-red-proof.mjs` → `red-proof.txt`，退出码 0）

base **显式钉 `f1c9e1c7`**（源码里明写「**不要**改成 HEAD」）。四段：

① **base 自校验**：base 解析得到；base 与工作树的差异**恰好**是本轮那 13 个文件；12 处锚点语句
（目标模块 + 具名清单含死名）＋ 级联锚点逐条还在；`INVISIBLE_TO_OLD` 是期望集的 7 元子集。
② **判据在 base 上红 12 处**（逐条点名，其中 **7 处**标了「不在工单 02 §②-3 的 9 处点名清单里」——
注意口径：那 7 处**不是"旧口径看不见"**，`C − A = 0`，旧口径同样报出它们，只是工单 02 没点名）；
base 上既有判据全 0（含 `unreachableModules`）。
③ **当前工作树绿（硬判）**：判据 0 处 ＋ 既有判据全 0。
④ **合成自检 25/25**（用例表 import 自 01 的 `synthetic-cases.mjs`，不抄第二份）。

**base 自校验有牙齿（实测）**：把 `BASE` 改成另一个提交（`27a7b46e`）→ **exit 1**，三条独立自检同时炸：
差异面 58 ≠ 13、base 违规集 13 ≠ 12、base 判据 D = 111 ≠ 0。改回 `f1c9e1c7` 后复跑 PASS。

#### ⑤ 既有判据复跑（清点后，`verify-removal.txt`）

```
✓ 未使用具名（全模块）0 / graphBreaks 0 / orphans 0 / wiring 0 / registry 0 / bareLoads 0 /
  判据 D 0 / 判据 T 0 / starImports 0 / 取数面体检 0 /
  ui-dom-contract：孤立模块 / import 了却没人调 0     → 全部为 0 ✓
```

**级联的必要性（本轮最重要的发现）**：清点前先做了**内存模拟**（`probe-00f-simulate-removal.mjs`，
读数 `survey-00-simulate.txt`）：摘掉 12 处之后**唯一变化是判据 D 从 0 → 1**，成因
`fx/core.js::downloadedPercent` —— 它的**唯一消费者**就是本轮摘掉的那条死 import
（`fx/full-update.js` 从没用过它）。即"**一条死 import 能给一个真没人用的导出当假消费者**"。
按 spec 处置规则级联摘掉它的 `export ` 前缀后，判据 D 回到 0；`downloadedPercent` 仍定义在
`fx/core.js:115`、仍被 `downloadFailureText`（:86）调用、仍在 window 探针桥（:126）。

#### ⑥ 双轴评审整改（`code-review`：Standards ＋ Spec 并行，只报告不修改）

**两轴独立收敛到的同一条（硬，已改）**：`probe-03` 的归因分类把"名字独占一行的整行摘名"
误记成"整条删"（落盘读数 摘名 8 / 整条删 4），与工单/spec 的"11 摘名 ＋ 1 整条删 ＋ 1 级联"
对不上——**同一改动三份机器证据给出三个分类读数**。已改成"看语句不看 hunk 形状"（见 ③），
并把 11/1/1 **钉死**为断言（不是只打印）。

其余整改：

- **（硬，已改）dry-run 会覆盖落盘证据**：评审复跑 `apply-removal.mjs`（dry-run）把
  `verify-removal.txt` 覆盖成了"比**意图**字节"，而工单硬判要求"比**落盘**字节"。
  已分开：dry-run 写 `verify-removal-dry-run.txt`，只有 `--write` 才写 `verify-removal.txt`。
- **（硬，已改）`unreachableModules` 没有显式复跑**：工单明写"特别复跑 `fx-guard.test.mjs`（orphans）
  与 `ui-dom-contract.test.mjs`（unreachableModules）"——前者在清单里、后者只在"前端门禁全绿"里间接交代。
  已把它并进 `apply-removal` 与 `probe-02` 的判据清单，两代都显式打印 `unreachableModules=0`。
- **（硬，已改）工单未 claim 就先动手**（流程违规，评审点名）：照 `docs/agents/workflow.md` Step 4.1，
  本张工单动手**之前**就该把 `Status:` 改成 `claimed`。本单**跳过了一步**（实现完才发现），
  如实记在这里；收尾直接落 `resolved`。**下一张（03）照规矩先 claim 再动手。**
- **（判断，已改）`probe-03` 的切口搜索是 O(n²) 穷举**：改成"对每个起点解出唯一终点"的 O(n) 版本。
  **但第一版 O(n) 改错了**（只从"第一处错位"起扫）：删掉的名字常与后一个名字**共享前缀**
  （`pdfDupRemainText, pdfTrashBodyHTML`、`resourcesToolbarHTML, resourceTaskColorMap`），
  那种扫法会给出跨过名字边界的假切口 → 分类器认不出那 2 处。最终版保留"所有起点"、
  由分类器按形状挑真切口，读数恢复 11/1/1。**教训**：省复杂度的改写要拿读数复核，
  差 2 处就是真 bug。
- **（判断，已改）`apply-removal` 的 `cascade: true` 字段没人读**（重放段自己重判类型）→ 删掉。
- **（判断，已改）读数口径统一**：计划行、`verify-removal.txt`、`diff-proof.txt`、工单 AC 四处
  原来各说各的（"12 处摘名/整行删"这种含糊写法）→ 统一成 **摘名 11 / 整条删 1 / 级联 1**。
- **（判断，已改）spec 里 `$` 那段是旧口径**（仍写成"已知限制"）——01 已把它修掉。spec 与
  「范围外」两处已同步更正（评审里"spec 与判据互相矛盾"那条）。
- **（判断，不采纳）两张锚点表（`apply-removal.NAME_EDITS` 与 `probe-02.ANCHORS`）重复**：
  评审自己也标了"独立性必须保留"——真红证要自己钉死预期，共用执行器的表等于互相掩护。
  采纳了它的**另一半**：`probe-02` 里的 `EXPECTED` 原本是同文件内的第三份手抄，已改成
  从 `ANCHORS` 推出，并加"`INVISIBLE_TO_OLD` 是它的 7 元子集"的自检。

#### ⑦ 三门禁读数（最终状态上各一遍）

| 门禁 | 读数 |
|---|---|
| `node --test "tests/js/*.test.mjs"` | **1688 passed / 0 fail**（6.3s，与基线同数） |
| `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` | **26 passed / 0 fail**（84.1s） |
| `python -m pytest -n auto -q` | **5049 passed / 1 skipped / 0 fail**（156.8s） |

本轮改到 `static/js/ui/` → 浏览器门禁必跑（已跑）。读数形态说明：本机工作树是 **LF 检出**
（`git check-attr`/`core.autocrlf=true` 下 Git 会警告"LF will be replaced by CRLF"），
`tests/js/ai-action-refs.test.mjs` 与 `tests/js/module-intro-detail.test.mjs` 按字面 LF 断言源码，
故 LF 检出下前端门禁全绿（工单 02 §⑥ 首记的那条环境事实，本轮未变）。

#### ⑧ 行为零变化的证据

- `git diff --name-only f1c9e1c7` 的**产品面**只有那 13 个 `static/js/**` 文件；
- **行数只减不增**（`git diff --numstat`）：**4 个文件**各整行删 1 行（`ui/code-compile.js` 整条语句、
  `ui/code-tree-ops.js` / `ui/codeeditor.js` / `ui/materials-update.js` 各删"名字独占的一行"）→ 行数 −1；
  另 **9 个文件**是改写 1 行（8 处摘名 ＋ 1 处级联）→ 行数不变。合计 `9 insertions / 13 deletions`；
- `window` 探针桥、`index.html`、555 个 id：**零改动**（本轮不碰它们）；
- 尾部换行与行尾：`diff-proof.txt` 的"尾部换行/行尾不一致的文件：**0 个**"（逐字节，含末 6 字节 hex）。

#### ⑨ 未顺手做（与 spec「范围外」一致）

常量形态、C6、C7、`.scratch` 一次性探针的失效修复、零调用私有死函数、新判据接闸门（03 的交付）、
`parseModuleImports` 返回形状的重构（见 01 Comments ⑦）。
