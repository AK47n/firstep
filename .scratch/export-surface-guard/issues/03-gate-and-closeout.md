# 03 — 两条判据进闸门 ＋ 账本收尾

**要做什么：** 把 01 立的两条判据接进前端门禁（`node --test "tests/js/*.test.mjs"`），**当场生效**：
此后任何人新增一个没人 import 的导出、或把被调用的 `export function` 改成同名常量，
**推之前就红**。然后按仓库口径收尾：账本三处更新（`CONTEXT.md` / `fx-guard` 文件头 /
`backlog.md` 第 10 节两条挂账结清 ＋ 一条更正）、三门禁各跑一遍并记数。

**被谁阻塞：** 02（清点处置 111 处）

**状态：** resolved

## 验收标准

- [x] 两条判据进前端门禁，用例住**一处**并说明选择（"缝越少越好"）：优先接在既有守卫文件
      （`tests/js/fx-guard.test.mjs` 是"名字表退化"那件事的现场）还是新开
      `tests/js/export-surface-guard.test.mjs`，在 Comments 里写清取舍。
- [x] 用例含**正向对照**与"那种绿比红更坏"体检（先例 `ui-dom-contract.test.mjs`）：抽取器一旦静默失效
      必须报出，而不是断言为空导致真空绿；星号导入体检同样进闸门。
- [x] 判据 T 的**别名正向对照**进闸门（`export const x = 别的函数名;` 必须不报——防假红），
      连同再导出链感知各一条。
- [x] **共享解析器那处修复要有闸门内的直接单测**（工单 01 Comments ②）：`parseModuleImports` 对
      `import * as ns from "…"` 与 `export * as ns from "…"` 必须解析出 star 边（修复前两者**整条
      静默丢弃**，星号体检等于空转），`export * from "…"` 照旧。
- [x] **账本三处**：
      ① `CONTEXT.md`「前端纯函数单源」那一行的口径更新——旧的"类型维度与死导出不再守"要改成
      "**fn 轴已由判据 T 守（调用位 ⇒ 函数形态）；零消费者导出由判据 D 守；常量形态（number/string/object）
      仍不守**"；
      ② `tests/js/fx-guard.test.mjs` 文件头同样的口径更新（那段"代价如实记账"）；
      ③ `.scratch/backlog.md` 第 10 节末两条挂账**结清**，并写进那条**更正**：
      "更该做的是清点后删掉它们"是在"这 7 个是死代码"的假设下写的——实测它们是**活的定义 ＋ 多余的
      `export`**（都被本模块内部或 window 桥用着），真正该删的只有 1 个；且真实体量是 **111** 而不是 7。
- [x] **接住工单 02 §⑨ 留的两处**（它明写"留给下一张工单"，本工单就是那张）：
      ① **修掉清点之后失效的墓碑注释**（假契约）——`ui/generate-fix.js:296` / `:303` / `:422-425`、
      `ui/fix-center-core.js:49`、`boot.js:249-250`：它们仍宣称 `continueFixCenter` / `FIX_MAX_ROUNDS` /
      `fixLoop` 经检查表导出 / re-export，而 `:426` 的现存清单已经不是那样。**只改注释文字**，
      不碰任何导出面与代码；改完必须复跑判据 D/T + 前端门禁（并说明 `probe-11` 的"归不了因 0 处"
      是对**清点提交 `9048da22`** 的证据，此后工作树的注释改动不属它的证明面）。
      ② **`ui/generate-fix.js::runCompileOnce`（零调用私有死函数）记进 backlog**（spec「范围外」：
      判据 D 只摘关键字、不删定义，本轮**不删**），并说明它与 `groupChoiceGap` 的区别
      （后者是**导出**零消费者、在判据 D 清单里；前者从来就零消费者、只是摘了关键字）。
- [x] **三门禁各跑一遍并记数**：`python -m pytest -n auto -q`、
      `node --test "tests/js/*.test.mjs"`、`node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`
      ——读数（passed / failed / 耗时）写进 Comments；并按工单 02 §⑥ 记的那条环境事实注明
      **行尾（LF / CRLF 检出）**对读数的影响。
- [x] **未顺手做**（与 spec「范围外」一致，逐条列进 Comments）：常量形态恢复、C6（555 个 id 耦合）、
      C7（73 个私有符号）、`.scratch` 一次性探针的失效修复、导出面的 API 重设计、
      `import-usage-guard` 口径扩展、工单 `frontend-boot-module/01-05` 的其它挂账。

## Comments

### 2026-09-21 实现记录

#### ① 落点取舍：**新开 `tests/js/export-surface-guard.test.mjs`**（工单要求写清取舍）

不接进 `fx-guard.test.mjs`，理由两条：

- **职责不同**：fx-guard 管"纯函数有没有回流到 HTML / 装载根"（四条结构不变量）；导出面管
  "这条导出谁在用、被用的形态对不对"。塞在一起就是一个文件为两件事而改（Divergent Change）。
- **命名与先例一致**：仓库的守卫本来就是"一条判据一个文件"（`static-import-guard` /
  `import-usage-guard` / `ui-cycle` / `ui-dom-contract`）。"缝越少越好"指**判据单源**——那一条
  没变：判据本体仍在 `tests/js/boot-contract.mjs`，本文件只是调用点。

`fx-guard.test.mjs` 的文件头同步改写：原来记的"两条代价"，现在写明一条已由判据 D、一条（fn 轴）
已由判据 T 收回，并保留"**仍不守**：常量的值形态"这条如实记账。

#### ② 闸门内 9 条用例（每条都能红——不是"断言为空"）

| 用例 | 保证什么 |
|---|---|
| 抽取器体检 | 三条下限都在；**正向对照**：漏喂装载根 / 消费侧一个不喂都**真的会报** |
| 判据 D = 0 | 每个导出都有人 import |
| 判据 D 正向对照 | 注入无人 import 的导出 → 报出（防抽取器静默失效） |
| 判据 D 注释喂绿 | 名字只出现在注释（含 boot.js 墓碑注释与**消费侧**注释）→ 仍报出；**注入本身也自检**（键写错会当场红，不让这条自检静默空转） |
| 判据 D 测试侧消费者算数 | 摘掉"只被测试 import"的那条边 → 报出 |
| 星号导入体检 | 现状 0；注入 `import * as ns` → 报出 |
| 判据 T = 0 | 调用位的导出都解析成函数形态 |
| 判据 T 形态链 | 别名链与再导出链**不假红**；翻转后必须报出 **`form === "value"`**（链不跟通只会得到"解不开"——只看名字太弱） |
| 共享解析器单测 | `import * as ns` / `export * as ns` / `export *` 都解析出 star 边（修复前前两者**整条被丢**），具名导入不受影响 |

#### ③ 判据单源再收敛一处（评审判断项，已改）

两轴评审都指出：守卫里抄了一份走图代码（`probe-04` 里还有一份）。已把这遍遍历抽成
`boot-contract.mjs::consumptionEdges(pageEntries, consumerEntries)`：判据 D、守卫的自检锚点、
红证的 9 条强度自检**三处共用同一遍**，锚点计数也改成 `target::name`（与判据 D 同口径，不再是
名字级）。红证随之复跑（见 ⑦）。

#### ④ 接住工单 02 §⑨ 的两处

- **五处失效墓碑注释已改**（只改注释：`git diff` 的新增/删除行**逐行都是注释行**，已核）：
  `ui/generate-fix.js:296/303/310`（三处"导出面保持"）、`:420-431`（簇导出面说明，含"经检查表
  导出为模块 API"与那条 re-export 的旧说法）、`ui/fix-center-core.js:49`（"壳层 re-export"）、
  `boot.js:249-252`（墓碑注释里 FIX_MAX_ROUNDS / fixLoop 的去向）。**没有**碰任何导出面与代码。
  口径说明：`probe-11` 的"归不了因 0 处"是对**清点提交 `9048da22`** 的证据，本工单的注释改动
  不属它的证明面（后续若复跑 `probe-11`，这些注释行会以"归不了因"现形——这是**预期**）。
- **`ui/generate-fix.js::runCompileOnce`（零调用私有死函数）不改、记进 backlog**：它与
  `groupChoiceGap` 的区别写进了 backlog §10——后者是**导出**零消费者（在判据 D 清单里、已整条删），
  前者**从来就零消费者**（判据 D 管不到"函数没人调"），本轮只摘 `export`。

#### ⑤ 账本三处 ＋ 两处追加

1. `CONTEXT.md`「前端纯函数单源」：旧的"代价如实记账（类型维度与死导出不再守）"改成
   **"两条代价已由导出面守卫收回"**（判据 D 守零消费者导出、判据 T 守 fn 轴），并写明
   **仍不守常量值形态**；另按评审把判据 T 的适用面写清（**页面模块图内**，测试侧不在内）。
2. `tests/js/fx-guard.test.mjs` 文件头：同口径改写（见 ①）。
3. `.scratch/backlog.md` §10：两条挂账**结清** ＋ 那条**更正**（"清点后删掉"是在"这 7 个是死代码"
   的假设下写的——实测是**活的定义 ＋ 多余的 `export`**，真死只有 1 个；体量是 **111** 不是 7）。
4. **追加（评审抓出的本仓约定）**：`docs/agents/local-environment.md` 里钉的前端门禁读数已从
   **1679 → 1688**，并补记 LF/CRLF 那条环境事实——CLAUDE.md 明写"凡改动它描述的东西，
   **当场回去改那份文件**"。
5. **追加（本轮暴露的新候选，写进 backlog 别当已做）**：9 处清点前就已死的模块级 import
   （`WRITE_GUARD_ACTIONS` ×4 等）——`tests/js/import-usage.mjs` 的取数面**只有 `boot.js`**，
   所以"零未使用具名"对模块级没有证明力。口径要不要扩，未立项。

#### ⑥ 双轴评审整改（`code-review`，Standards ＋ Spec 并行；两轴**独立收敛到同一条**）

- **（硬，两轴都报，已改）新注释自己造了一条假契约**：`ui/generate-fix.js` 的更正里写
  "`fixLoop` 只在本模块 mutate"——"本模块"在该文件里读作 generate-fix.js，而 `fixLoop` 住在
  `ui/fix-center-core.js`（generate-fix.js 连引用都没有）。已改成"与 `FIX_MAX_ROUNDS` 一样住在
  `ui/fix-center-core.js`、**只在那里** mutate（本模块连引用都没有）"。**教训**：修假契约的注释
  本身也要按同一把尺子核一遍。
- **（硬，两轴都报，已改）一条会静默空转的自检**：注释喂绿自检里
  `patch(PAGE, "tests/js/export-surface-guard.test.mjs", …)` 是**空操作**（PAGE 的键是页面键空间，
  永远不含 `tests/…`）——想注入的"消费侧注释"从没注入，用例照样绿。已改成 patch `CONSUMERS`，
  并**给注入本身加自检**（键写错当场红）。`probe-04` 里同一处也修了（那份是复制过去的）。
- **（硬，两轴都报，已改）再导出链的断言弱于注释**：原来只断言"有个叫 gotoNavTab 的违规"，
  而翻转后存在**直连边**（`ui/settings.js → ui/goto-nav.js`）就能让它绿，证明不了链。已改成断言
  **`to === "ui/nav-jump.js" && form === "value"`**——`"value"` 只能靠沿链走到声明处解出来
  （不跟通只会"解不开"）。`probe-04` 自检 7 同步加严。**共同教训**：断言要能区分"判据对了"与
  "判据瞎了但兜底规则救了它"。
- **（判断，已改）重复与口径分叉**：走图代码三处 → 收敛成 `consumptionEdges`（见 ③）；
  守卫的锚点计数从名字级改成 `target::name`。
- **（判断，已改）注释/文档口径**：`CONTEXT.md` 与守卫文件头把判据 T 的适用面写明是页面模块图。
- **（判断，保留）backlog 多记的那条新候选**：评审称"未被要求"，但它是本轮**实测暴露**的事实，
  记账比丢掉强（已在本 Comments 与 backlog 双处写明）。
- **（判断，保留）`red-proof.txt` 被覆盖写**：重跑红证是必须的（判据单源改了），漂移只有一行
  "消费侧 164 → 165 个 .mjs"（新增的守卫文件本身也是消费侧模块）——如实记账。

#### ⑦ 三门禁读数（**最终状态**上各一遍）

| 门禁 | 读数 |
|---|---|
| `node --test "tests/js/*.test.mjs"` | **1688 passed / 0 fail**（基线 1679 ＋ 本工单 9 条；耗时 14.2s） |
| `python -m pytest -n auto -q` | **5049 passed / 1 skipped / 0 fail**（164s） |
| `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` | **26 passed / 0 fail**（85.4s） |

**环境事实（工单 02 §⑥ 首记，这里复核）**：`tests/js/ai-action-refs.test.mjs` 与
`tests/js/module-intro-detail.test.mjs` 按**字面 LF** 断言源码——本机 `core.autocrlf=true` 时
**CRLF 检出**下这两条必红（1677 / 2 fail），**LF 检出**下全绿。上面 1688 / 0 是**当前工作树
（LF）**上的读数；已并进 `docs/agents/local-environment.md`。

#### ⑧ 未顺手做（与 spec「范围外」一致）

常量值形态（number/string/object）的恢复、C6（555 个 id 耦合）、C7（73 个私有符号）、
`.scratch` 一次性探针的失效修复（`group-choice-required/smoke-browser.mjs` 的
`rec.groupChoiceGap()` 仍会链接期报错）、导出面的 API 重设计、`import-usage-guard` 口径扩展
（已作新候选记进 backlog）、`runCompileOnce` 这类零调用私有死函数的清理（同样进 backlog）、
工单 `frontend-boot-module/01-05` 的其它挂账。
