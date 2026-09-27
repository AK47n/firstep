# 09 — 拆 fx 第一步：按职责拆成六件（旧文件暂转再导出）

**要做什么：** 纯函数层那一个 1365 行的大文件，按**已有段落**整段搬进六个按职责划分的模块；
旧文件暂时只做"转手再导出"，于**同一笔提交内**保证全部门禁绿。**只搬不改**：函数体与注释逐字保留，
唯一允许变化的是 import / export 语句与文件头说明。

**被谁阻塞：** **01**（桥守卫先立，搬迁才有"不许顺手引入桥依赖"的判据）、
**02**（字面星号先在原地修完，diff 才干净）。执行纪律：与 10 是同一场搬迁的两步，
中间态（barrel 存在）**只允许活一笔提交**。

**状态：** resolved

**来源**：评审「三、工程卫生」与 P2-12（按行数切是错的，按职责切才对）。

## 现状（实测：段落边界与导出数）

| 段（行） | 职责 | 导出 | 拟新模块 |
|---|---|---|---|
| 1–171 | 状态归一 / 载荷 / 平台卡 / 提示与错误文案 | 17 | `static/js/fx/hwcheck-state.js` |
| 172–427 | 生成 / 编译降级 / 上板清单 / 最近几次检测 | 20 | `static/js/fx/hwcheck-project.js` |
| 428–702 | 器件选择 / 接线表 / 默认脚冲突 / 建议顺序 | 13 | `static/js/fx/hwcheck-wiring.js` |
| 703–829 | 逐件小节 / 未专精点名 | 6 | `static/js/fx/hwcheck-plan.js` |
| 830–919 | 串口命令台 | 3 | ↳ 并入 `hwcheck-plan.js`（同属"这一趟测什么、怎么复测"） |
| 920–1069 | 现象回填 / AI 排障 | 10 | `static/js/fx/hwcheck-triage.js` |
| 1070–1153 | 自建件的检测计划 | 3 | ↳ 并入 `hwcheck-plan.js` |
| 1154–1365 | 检测页 → 生成页衔接 + window 桥 + 导出清单 | 5 | `static/js/fx/hwcheck-handoff.js` |

合计 **77 个导出**。（模块名可在实施时就近调整，但"六件 + 按职责"这条不许改。）

> **⚠ 核实过的现场更正**（照 spec.md「核实过的现场更正」先例，开工时逐条实测；下表按实测读，
> 票面原表只作历史）：
>
> | 票面原文 | 实测 |
> |---|---|
> | 合计 **77 个导出** | **78 个**：多出来的是 `hwcheckPinCapacityNoteHTML`（工单 04 加的，本表写在它之前）。分件实测：state 17 / project 20 / wiring **14** / plan 12 / triage 10 / handoff 5 |
> | wiring 段「13」 | **14**（同上）。段落行号区间整体后移：文件实测 **1380 行**（票面写的 1365 是更早一版） |
> | 段表只列了**导出**行 | 段与段之间还夹着 **4 个非导出私有件**：`hwcheckSameExclusiveGroup` / `hwcheckRoleLabeler` / `HWCHECK_ORDER_DESC_CHARS`（→ wiring）、`HWCHECK_VERDICT_FALLBACK`（→ triage）。判据 = "间隙跟**下一个**声明单元走"，逐字一并搬走，**判据面覆盖全部顶层声明**（不只是导出） |
> | （约束）「由 `ui` 层 import 它们即可满足」可达 | 10 号单之前，可达性走的是 **barrel 的再导出边**（`ui/hwcheck.js` 这一笔一个字没动）；10 号单之后再走 ui 的直接 import |
> | （约束）「零未使用具名 import」 | 与 barrel 形态**直接冲突**：`export { … } from` 在旧口径下逐条报"未使用"（量具 `probe-09-barrel-forms-before-fix.txt`）→ 口径按"再导出边不绑本地名"修正，见「结论」里那张表

## 约束（拆完必须同时成立）

- **每个新模块从装载根可达**（`fx-guard` 判据④）——由 `ui` 层 import 它们即可满足。
- **全图 import↔export 逐名对账**（`static-import-guard` 判据④）——barrel 期间的再导出必须能被解析。
- **导出面判据 D/T**（`export-surface-guard`）：`export { … } from "…"` 会被算作一条消费边，
  所以 barrel 期间判据仍绿；**判据 T（被调用的导入名必须解析成函数形态）**要跟着再导出链，
  搬迁后若出现"解不开"按违规算。
- **零未使用具名 import**（`import-usage-guard`）。
- **`window` 桥的发布名字集合搬前搬后完全相等**：每个新模块发布自己那一段的桥条目，
  barrel 不再发布；`Object.assign(window, { … })` 的**并集**必须逐名相同（用脚本对账，不许人眼）。
- **不碰 DOM、不发请求**（fx 层约定）：搬迁不许把任何 ui 侧胶水带进来。

## 验收标准

- [x] 六个新模块就位，旧 `fx/hwcheck.js` 仅剩 barrel（再导出）+ 文件头说明（写清"本文件是过渡态，
      由 10 号单删除"）。**函数体逐字**：除 import / export / 文件头，搬迁前后逐字相同。
- [x] 新增**搬迁完整性自检**（本批唯一为拆分新造的判据，放 `tests/js/`）：
      ① 导出名集合相等（旧文件导出清单 = 六件并集，逐名比对）；
      ② 每个导出对应的函数体/常量声明**逐字相同**（按名字对齐后归一化空白比对）；
      ③ `window` 桥名字并集相等。
      这条自检在 10 号单删掉旧文件后**必须仍然可跑**（把"旧文件"那一侧改成"搬前快照"文件，
      快照随 10 号单一并留档在本目录）。
- [x] **反证**：从某个新模块里删掉一个导出（或改一个字）→ 自检红；复原后逐字节相同
      （`.scratch/hwcheck-hygiene/probe-09-red.py` / `probe-09-red.txt`）。
- [x] 读数：`node --test "tests/js/*.test.mjs"`（前端门禁）与
      `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`（浏览器门禁）全绿并落盘
      ——**浏览器门禁必须跑**，这一单虽然零行为变化，但整页脚本是否还能起来只有它能作证。

## 结论（读数与账）

**这笔做了什么。** 1380 行 / **78 个导出** / 77 条 window 桥的 `fx/hwcheck.js` 按职责整段搬进
六件（票面「现状」表写的是 77 个导出——实测 **78**：多出来的那个是 `hwcheckPinCapacityNoteHTML`，
工单 04 加的，那张表写在它之前）；旧文件只剩 **barrel**（六条 `export { … } from "…"` ＋ 文件头）。
barrel 按票面要求**只活一笔提交**，10 号单删它并迁移消费者。

**四个非导出私有件住在"间隙"里**（票面的段落表只列了导出行）：`hwcheckSameExclusiveGroup` /
`hwcheckRoleLabeler` / `HWCHECK_ORDER_DESC_CHARS` 跟着 `hwcheckDevicePick` /
`hwcheckBoardSharesHTML` / `hwcheckOrderDesc` 进 wiring，`HWCHECK_VERDICT_FALLBACK` 跟着
`hwcheckSymptomText` 进 triage——判据 = "间隙跟**下一个**声明单元走"，`apply-09-split.py` 干跑
会把这四处连代码一起打印出来给人核对。

**搬迁怎么自证的（两道，互不依据）。**

| 手段 | 判据 |
|---|---|
| `apply-09-split.py`（搬迁脚本自己） | **分区完备**：文件头 ＋ 78 个声明单元 ＋ 桥块拼回来与原文件**逐字节相同**；桥"每条有且只有一个家" |
| `tests/js/hwcheck-split-integrity.test.mjs`（本批唯一为拆分新造的判据，在前端门禁内） | ① 导出名集合 ② 每个导出的"声明单元（含紧邻上方注释块）"归一化空白后逐字相同 ③ 桥并集 ④ 跨件调用必须 import/本件声明 |

**快照即"搬前那一份"**：`.scratch/hwcheck-hygiene/fx-hwcheck-before-split.js` 与
`git show HEAD:src/contest_generator/static/js/fx/hwcheck.js` **逐字节相同**
（76041 B / sha256 `6f2591af…`）——10 号单删掉旧文件后这条自检照样可跑（它从来只读快照）。

**判据先红后绿抓到的两个真问题**（都不是"搬完才发现"，是判据当场报的）：

| 抓到它的判据 | 问题 | 若没抓到 |
|---|---|---|
| `window-bridge-guard` 判据 ⑧ | `hwcheck-project.js` 用了 `hwcheckDeviceSlugs` 却没 import | 点「生成检测工程」直接 `ReferenceError` |
| 本单自检 ③ | `HWCHECK_VERDICT_FALLBACK` 是**未导出**的私有桥条目，第一版按"导出名"认领桥把它漏了 | 页面/探针取不到这个全局名——而"页面还能跑"的所有验证照样绿 |

**为让 barrel 成立而动的一处既有判据口径**（量具：`probe-09-barrel-forms.mjs`，
**两份读数都留着**——改口径前的 `-before-fix.txt` 才是"为什么必须动"的现场）：

| 再导出形态 | 判据 D | 判据 T | 图对账 | import-usage（旧口径 → 新口径） |
|---|---|---|---|---|
| A `export { … } from "M"` | ✓ | ✓ | ✓ | **✗ 逐条报"未使用"** → ✓ |
| B `import { … } …; export { … };` | ✓ | **✗ 解不开** | ✓ | ✓ → ✓ |
| C 再导出 ＋ 正文真用（`ui/nav-jump.js` 那一形态） | ✓ | ✓ | ✓ | ✓ → ✓ |

纯 barrel 只有 A 可行，而 A 与 import-usage 的旧口径**直接冲突**（两条守卫对同一份源码结论相反）
→ `import-usage.mjs` 不再把**再导出边**当"导入的名字必须被使用"（它不绑本地名）；
判定复用 `boot-contract.mjs` 导出的 `isReexportEdge`（**单源**，别再写第二遍正则）。
牙齿没拔：用例表补两条对照（再导出边免检；`import { x } …; export { x } from 别处` 的
import 边照旧报），口径注释里写明"名字不存在归判据③、没人消费归判据 D"。

**跟着搬迁走的两处读路径与两处源码串断言**（不改就**变瞎**，不是抢 10/12 的活）：
`tests/test_hwcheck.py` 两处改指新家（`hwcheck-project.js` / `hwcheck-state.js`）；
`tests/js/hwcheck.test.mjs` 的「fx 不得 import ui / 碰 DOM / 发请求」改成对**六件逐个**断言
（钉在 barrel 上恒真 = 守卫闭眼），「单平台件不误导」改成读整层文本
（**这一处的判据面确实被放宽了**：`item.message` 现在只出现在 `hwcheck-wiring.js`——
12 号单重算「56 处」基线时按新的两处算，别再按 56 起算）。其余源码串断言的批量迁移归 12 号单。

**双轴评审（Standards / Spec，2026-09-27）与整改。**

| 轴 | 发现 | 处置 |
|---|---|---|
| Spec 硬 | 「函数体逐字」只覆盖 78 个导出，**4 个私有件没有任何判据看着**（评审手工比对才确认它们同快照） | 判据 ② 的取数面改成**全部顶层声明**（`DECL_RE` 去掉 `^export` 强制），并补一条正向对照（改 `HWCHECK_ORDER_DESC_CHARS = 60` → 必须报）+ 体检"声明单元数 > 导出数" |
| Spec 硬 | barrel 文件头自述「消费者与用例一个字没动」与同笔改动矛盾（`tests/js/hwcheck.test.mjs` / `tests/test_hwcheck.py` 都动了） | 自述改成事实：消费者里的 **import** 一个字没动，跟着搬的是两处**读源码文件**的断言（并写明不改它们会恒真/红） |
| Spec 硬 | 票面「现状」表 77 导出 / wiring 13 / 1365 行与实测不符，偏离只落在读数文件里 | 票面加「⚠ 核实过的现场更正」块（照 spec.md 先例），实测值 78 / 14 / 1380 与私有件那条一并写进去 |
| Spec 判 | 口径改动的读数取自改口径**之前**，txt 未标注 | 拆成两份：`-before-fix.txt`（改前，A 行报未使用）与 `probe-09-barrel-forms.txt`（改后，A 行四条全绿），探针文件头写明该读哪份 |
| Standards 判 | `import-usage.mjs` 自己写了一遍再导出判定（与 `boot-contract.mjs` 的 `isReexportEdge` 重复） | 改成 import 那个函数（**单源**），并在它的文档里注明两个消费方 |
| Standards 判 | 搬迁脚本对快照不做校验，快照可被静默替换 | `SNAPSHOT_SHA256` 写死并在 `build()` 里断言（换快照必须连指纹一起改并说明理由） |
| Standards 判 | 「1365 行」与实测 1380 不符；「77」在桥名数与导出数之间混用 | 探针/自检/barrel 头一律写「1380 行 / 78 个导出 / 77 条桥」，口径分明 |
| Standards 判 | 六件文件头逐字重复同一段约定（含依赖方向），无判据看着 | 约定块**只写一份**（`hwcheck-state.js` 头部＝单源），其余五件两行转引它 |

**读数（本机实跑，落盘在本目录）。**

| 闸门 | 读数 | 文件 |
|---|---|---|
| 全套 pytest | **5604 passed + 11 skipped**（与 08 同基线） | `09-pytest-full.txt` |
| 前端门禁 | **1826 / 0**（基线 1819；+7 = 本单新自检，含「改私有件必须报」那条对照） | `09-js-gate.txt` |
| 浏览器门禁 | **48 / 0**（零 `[afterEach]` 告警） | `09-browser-gate.txt` |
| 反证 | **4/4 段**：摘导出 / 改一个字 / 摘一条桥 / 摘一条 import，各注入即红、复原 sha256 逐字节相同 | `probe-09-red.txt` |
| 独立复核 | 零掉队模块；桥搬前 77 = 六件并集 77（逐名）；barrel 零发布、导出 78 | `probe-09-reachability.txt` |
| 搬迁脚本 | 分区完备 ＋ 桥认领对账 ＋ 快照指纹校验 | `09-split-write.txt` |

**未上板**：本单是纯搬迁 + 判据，**没有任何板上行为被验证**（本机没有板子）。
