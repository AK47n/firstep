# 01 — 两条判据单源（零消费者导出 + 调用位⇒函数形态）与红证

**要做什么：** 让"导出面"这件事**第一次可判定**：在既有判据共享件 `tests/js/boot-contract.mjs` 上
落两条纯函数判据（**判据 D** = 每个导出必须被一条 import 边消费；**判据 T** = 被调用的导出必须是
函数形态），并用红证证明它们**真有牙齿**——喂清点前那个提交（base 显式钉 `27a7b46e`）必须报出
**111** 处零消费者导出，注入 9 类破坏（含注释喂绿、星号导入、别名假红三个已知坑）必须逐条报出。
本工单**只出判据与证据，不动任何产品源码**。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

## 验收标准

- [x] `tests/js/boot-contract.mjs` 新增两条纯函数判据，语义与签名照 spec「实现决策」：
      **判据 D** `[{ key, name }]`（输入 = 页面模块表 ＋ 测试侧消费者模块表；说明符归一成同一键空间
      ——页面侧走 `resolveModuleKey`，测试侧 `../../src/contest_generator/static/js/…` 与 `/js/…`
      两种形态都要收）；**判据 T** `[{ from, to, name, form }]`（输入 = 页面模块表）。
- [x] 判据 T 的形态解析**跟随两条链**：`export { x } from "…"` 再导出链、`export const x = <标识符>;`
      函数别名链（先看本文件声明，再看它 import 自哪个模块，递归）；**解不开 = 违规**，不许静默跳过。
      实测依据：不做这两步，1112 条调用位里会冒出 **44** 条假红（spec「方案」）。
- [x] 两条判据各带**取数面体检**（消费者模块数下限 / 调用位条数下限），并单独一条**星号导入体检**：
      内存或源码里出现触达前端的 `import * as ns` 即报红（当前实测 **0** 处；判据不许悄悄变松）。
- [x] 无消费方的导出**不导出**（模块内部件化），照工单 `frontend-boot-module/01` 评审口径。
- [x] 红证脚本 `.scratch/export-surface-guard/probe-04-red-proof.mjs`：
      ① **base 显式钉 `27a7b46e`**（不写 HEAD）、**base 自校验**（base 上零消费者 = **111**、
      形态违规 = **0**、且 `fx/code.js` 的 `maincScrollToRange` 仍带 `export`——选错 base 当场大声失败）；
      ② 判据 D 在 base 上红（111 处）；③ 判据 T／星号体检／取数面体检在 base 与当前工作树上都是 **0** 违规（工作树这一半要**硬判**，不能只打印）
      （0 违规 ≠ 判据没用——由自检 6/7 证明它有牙齿）；④ **强度自检 9 条全成立**：
      摘真 import 边 → D 报出；**正向对照**注入无人 import 的假导出 → D 报出；
      **注释喂绿自检**（名字只出现在别的模块注释与 `boot.js` 墓碑注释里）→ D **仍须报出**；
      摘测试侧 import → D 报出；注入星号导入 → 体检报红；被调用的 `export function` 改成同名数据
      → T 报出；再导出链一环改成数据 → T 报出；**别名正向对照**（`= 别的函数名` → 不报）；
      注释里的 `x(` 不算调用位 → 不报。
- [x] 红证输出落 `.scratch/export-surface-guard/red-proof.txt`（退出码 0），失败时非零退出并打印 base 身份。
- [x] **未顺手做**：不动 `static/js/**` 一行（清点是 02 的交付）；不把判据接进守卫用例（03 的交付）。

## Comments

### 2026-09-21 实现记录

**① 判据落点**（判据单源 = `tests/js/boot-contract.mjs`，＋约 255 行）：

| 件 | 说明 |
|---|---|
| `unconsumedExports(pageEntries, consumerEntries)` | **判据 D** → `[{ key, name }]`；口径是**哪条导出**（`模块::名字`），页面侧边与消费侧边都算消费者 |
| `nonFunctionCallees(pageEntries)` | **判据 T** → `[{ from, to, name, form }]`；`form` 取 `"value"` 或 `"解不开"`（**解不开也算违规**） |
| `consumerSpecToKey(spec)` | 消费侧说明符归一（`../../src/contest_generator/static/js/…` 与 `/js/…` → 页面键空间） |
| `readConsumerModules(repoRoot)` | 消费侧取数面：`tests/js` ＋ `tests/browser` 的 `.mjs`（含子目录），实测 **164** 个 |
| `starImports(pageEntries, consumerEntries)` | 星号导入体检（现状 **0** 处） |
| `exportFaceProblems(pageEntries, consumerEntries)` | 取数面体检：装载根在不在 ＋ 三条下限（导出条目 800 / 调用位 800 / 消费侧 120） |
| `callPositionEdges` / `exportFormOf` / `importSourceOf` / `isReexportEdge` | 内部件（无消费方不导出）：调用位、形态解链（再导出链 ＋ 函数别名链）、再导出判定 |

**② 顺带修掉共享解析器的一处真 bug**：`parseModuleImports` 对 `import * as ns from "…"` 与
`export * as ns from "…"` **整条静默丢弃**（`as` 之后的别名标识符没吃掉，`from` 判在 `"ns from …"` 上）。
星号体检没有它就等于空转，故就地修（1 行）——`graphBreaks` 本来就跳过 star 边，`reachable` 与现有
四条判据实测无影响（前端门禁 1679 条全绿）。**已在工单 03 的验收清单补一条**：给这处加闸门内的直接单测。

**③ 红证**（`probe-04-red-proof.mjs` → `red-proof.txt`，退出码 0）：base 显式钉 `27a7b46e`；
① base 自校验（**111** 处零消费者 / 0 处形态违规 / 0 处星号导入 / base 那一代还没有这两条判据 /
三个钉子名仍在）；② 判据 D 在 base 上红 **111** 处（backlog 点名的 7 个 **7/7** 在清单里）；③ 判据 T
在 base 与工作树上都是 **0** 违规，星号体检与取数面体检全绿；④ **强度自检 9/9**：
摘真 import 边 → 报出；注入无人 import 的假导出 → 报出（正向对照）；注释喂绿（含 boot.js 墓碑注释
与消费侧注释）→ 仍报出；摘测试侧 import → 报出；注入 `import * as ns` → 体检报出（并如实记下
判据 D 对命名空间是瞎的）；被调用的 `export function` 改成同名数据 → 判据 T 报出；再导出链上那一环
改成数据 → 报出（基线不报＝链真跟通了）；函数别名 `= 别的函数名` **不报**（防假红）＋ 改成数据就报出；
代码形态调用报出而注释形态不报（注释感知）。

**④ 双轴评审整改**（`code-review`：Standards 与 Spec 并行，只报告不修改）：

- **（硬，已改）判据 D 口径写错、且注释里"实测 0 例"是假读数**：原实现用**全局名字集**判消费，
  会放过"同名导出被别的模块导出、且那个被消费"的冗余转手再导出。实测差额 **3 处**
  （`probe-05-duplicate-names` / `survey-05-duplicates.txt`）：`ui/full-update.js::fullStateText`、
  `ui/generate-fix.js::{FIX_MAX_ROUNDS, fixLoop}`——后两处还带着**过期注释**说"check_contract /
  generate-core 活引用"，而 `_fix_src()` 读的是 `ui/fix-center-core.js`、`generate-core` 也不 import 它们。
  已改成按**哪条导出**判（与 spec「每条 `export`」的字面口径一致），清点体量 **108 → 111**，
  spec / 工单 02（含文件名）/ 工单 03 / 红证基线同步更正。
- **（硬，已改）下限按清点"前"取 = 下一张工单自己把体检判红**：`exports` 下限原取 900，而清点后
  导出条目是 884。已改成 800，并在注释里写明"下限按清点后取"。
- **（硬，已改）漏喂装载根的假红没人拦**：`readJsModules` 按文档不含 `boot.js`，调用方漏拼就丢掉
  装载清单那 60 多条边——实测判据 D 从 111 飙到 **189** 处假红，而消费侧计数照旧"正常"。
  已在 `exportFaceProblems` 加"装载根在不在"这条体检。
- **（硬，已改）工作树那一半只打印不硬判**：spec 轴实测"工作树上判据 T 崩了、体检红了，脚本照样
  PASS 退出 0"。已把判据 T／星号体检／取数面体检并进 `ok`。
- **（判断，已改）重复与口径分叉**：`/^export/` 判定写两遍 → 提成 `isReexportEdge`；`starImports`
  的 double-scan 与无谓包装去掉；**探针 02/03 里自抄的判据与形态解析已删、改调判据本体**
  （自抄那份还带着 44 条假红的旧 bug）；文件头标题「四类不变量」→「五类」。
- **（判断，不采纳）"`consumerSpecToKey` 是零消费方导出"**：复核为**误报**——`probe-04` 第 187 行
  就在用它。其余新导出都有消费方（红证脚本），工单 03 接闸门后还会再加一处。
- **（判断，记账不改）两处超工单之举**：修共享解析器（②，星号体检的必要条件）与多一条 `exports`
  下限，都记在本 Comments；探针 base 自校验的钉子比工单要求的多，属更强的自校验。
- **（留给 03）**共享解析器这处修复目前没有闸门内的直接单测——已写进工单 03 验收清单。

**⑤ 读数**：`node --test "tests/js/*.test.mjs"` = **1679 passed / 0 fail**（与基线同数，本次没动任何用例）；
`static/js/**` **零改动**（清点是 02 的交付）。
