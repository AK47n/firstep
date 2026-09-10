# 12 — 「保存全部并切换」偶发红的定性：目录加载竞态（真产品缺陷）

**要做什么：** 定性 `refine/smoke-01` 场景 5（「保存全部并切换 → 重开该文件内容一致」）的偶发红。
第九轮收口把它登记为两个签名（① 无活动标签；② `ta=777` 而磁盘仍旧值），并判定「先记为脚本/
环境层面的偶发，若要定性需专门补一张诊断工单」——本单就是那张诊断工单。

**被谁阻塞：** 无（已完成）。

**Type:** task
**Status:** resolved

## Answer

**结论：签名 ① 不是脚本问题，是产品缺陷——`loadCodeDir` 的目录加载竞态**（晚到的旧目录响应
覆盖新目录的文件清单）。签名 ② **未能复现**，其历史观测可由签名 ① 的次生现象解释（见下）。

### 复现与定性证据（全部真机：webapp 8000 + Chrome headless CDP 9251）

| 步骤 | 脚本 | 结果 |
|---|---|---|
| ① 自然复现（10 轮，每轮硬重置两目录 + 整页 reload） | `.scratch/code-editor-perf-structural/diag-save-switch-flake.mjs 10` | 签名 ① **1/10**：`label=b` 而 `treeFiles=["main.c"]`（A 的文件）→ 点 `other.c` 是 `?.click()` 空转 → `ta=null` / `标签=[]`；签名 ② **0/10** |
| ② 自然复现（基线 = `git stash push -- src/`，6 轮） | 同上 | 0/6（偶发率太低，样本不足 → 改走确定性复现） |
| ③ **确定性复现**（fetch 垫片把「先发起的那次 `/api/code/open` 推迟 800ms」固定下来） | `.scratch/code-editor-perf-structural/diag-dir-race-deterministic.mjs` | **基线必现**：`标签=b` / 树 = `["main.c"]`（FAIL）；**修复后必过**：`标签=b` / 树 = `["other.c"]`（PASS） |
| ④ 根因请求有多慢 | `.scratch/pdf-library-ui/diag-refs-timing.mjs`（同机端点墙钟） | `/api/pdfs` 495/499ms、`/api/pdf/…/refs` 538/521ms —— 本机端点普遍 ≈500ms，竞态窗口足够宽（真实用户机器更小，故现象只在自动化下高频） |

**根因（代码）**：`ui/codeview.js` 的 `loadCodeDir` 是 `async`，`probeDiskBaseline()`（内部
`await apiPost("/api/code/open")`）返回后**无条件**写模块级 `codeFiles = data.files`。两次
`loadCodeDir` 交叠时（快速连点两个目录、外部桥连发、冒烟脚本连续 `openCodeViewer`），
后发起的通常先返回，而**先发起的晚到响应**把 `codeFiles` 覆盖成旧目录清单 → 树显示旧目录的
文件；旧清单里没有新目录的文件 → 用户点目标文件是空转（`?.click()` 静默 no-op）→
「没有活动标签 / 编辑器空白」。这与第八轮修掉的「打开文件竞态」（`codeeditor.js` `openSeq`）
是**同一类**问题，只是发生在目录这一层。

**签名 ② 的残余（本轮如实留口，未取得根因证据）**：脚本加固后把失败点收窄到了**唯一的一步**
——场景 5 末尾「切回 B → 重开 `other.c` → 断言内容 = 777」。当前形态：

| 观测 | 数据 |
|---|---|
| 失败点在整条场景里的位置 | `5-pre`~`5-pre5` 全绿（打开 main.c / 改脏 / 打开 other.c / 改脏 / 切 A 弹窗 / **点保存后目录确实切到 A**）；`5a` 绿（label = A）；**只有 5b 红** |
| 磁盘 | 断言里那次 `/api/code/file` 直读 = `"int b = 777;\n"`（**保存落盘是好的**） |
| 编辑器 | `ta=null`、`openTabPaths()=[]`（无活动标签、无标签） |
| 复现率（改版后） | 批内 6 轮 2 次失败；A 组单跑 2 次 1 次失败；另一批内 5 轮 0 次；最终全批复跑 1 次（≈1/3，随机） |
| `openFile("other.c")` 的返回 | **true**（`getActiveTab()?.path === "other.c"` 曾成立）→ 失败探针（按 `!reopened` 触发）**没触发** ⇒ **有第三方在断言前把标签清空了** |

即：不是「点击丢失」（那会让 `openFile` 返回 false 并触发探针），而是**打开成功之后、
断言之前，标签被清空**——与 `setCodeDir` 清标签的形态一致，怀疑是另一个目录加载请求
（或迟到的 `loadCodeDir`）在 `openDir(DIR_B)` 之后又跑了一遍 `setCodeDir`。
**证据不足，不写结论**；下一步取证方向见「Comments」。

### 修复（产品 + 脚本两层）

1. **产品**（`src/contest_generator/static/js/ui/codeview.js`）：`loadCodeDir` 加目录加载序号
   `codeDirSeq`（照 `openEditorFile` 的 `openSeq` 先例）——只有**最新**一次加载的响应可以提交
   状态（清单 / 徽章 / 渲染 / 错误态 / 打开指定文件）；晚到响应在 `probeDiskBaseline` 之后与
   `catch` 里各早退一次（旧目录的失败也不该把新目录的树写成错误态）。
2. **脚本**（`.scratch/code-editor-refine/smoke-01.mjs`）：`openFile` 的守卫（点前等节点稳定 +
   打开失败重试 3 次、每次 1.5s 看是否成为活动标签）是第九轮加的，本轮取证显示它**确实兜住了**
   自然竞态的一部分——但它在「树被旧清单覆盖」这一形态下必然三次都判「节点不稳定」而放弃
   （因为目标文件根本不在树里）。产品修好之后该守卫回到它本来的职责（覆盖清树瞬间的点击丢失）。

### 守卫与验收

- `tests/js/code-editor-window-guard.test.mjs` 新增「`loadCodeDir`：晚到的旧目录响应不覆盖新目录
  清单（`codeDirSeq` 守卫）」——静态源断言：序号登记、`stale` 判定、`probeDiskBaseline` 之后
  必须有早退、模块级序号声明。
- 确定性复现脚本 `diag-dir-race-deterministic.mjs` 即本单的验收脚本（基线 FAIL / 修复 PASS，
  200ms 内单轮判定，不靠偶发率）。
- 复跑：`refine` 10 支、`viewer` 11 支、`overhaul` 9 支、`bridge` 5 支、`ideflow` 3 支、
  `treeops` 1 支、`ideai` 4 支、库 UI 4 支、`fem` 1 支 —— 见
  `.scratch/tracker-audit/2026-09-09-在途盘点.md`「第十轮收口」的实跑表。

## Comments

- 2026-09-09 第九轮：场景 5 偶发首次登记（两个签名），当时判定为「脚本竞态」并给 `openFile`
  加了守卫；因为「性能改动在该场景里是可证明的 no-op」，没有继续定性。
- 2026-09-09 第十轮（本单）：按第九轮「下一轮建议」第 1 项专门定性 —— 找到**真产品缺陷**
  （目录加载竞态），修复 + 确定性复现 + 守卫；保存落盘（原签名 ② 的字面读法）16 轮全好。
- 2026-09-09 第十轮续（同会话，脚本加固后的剩余偶发）：失败点已收窄到唯一一步（见「残余」表），
  且 `openFile` 返回 true ⇒ 形态是「打开成功后被第三方清标签」，不是点击丢失。
  **下一步取证方向**（本轮未做）：
  1. 垫 `codeeditor.js` 内部函数时注意：**改模块命名空间对象无效**（`codeview.js` 里是
     import 活绑定，`wrap(ed, 'setCodeDir')` 拿不到调用——本轮 `diag-save-action-trace.mjs`
     就是这么失效的）。可行做法：给 `setCodeDir` 加一个仅测试用的 `window.__codeDirCalls`
     计数（产品侧一行，或经 `window` 桥），或把 trace 写进 `loadCodeDir` 内部（临时改产品码
     跑一轮取证后回滚）。
  2. 观察目标 = 「`openFile` 成功之后到断言之间，谁调了 `setCodeDir`」——重点怀疑
     `openDir(DIR_B)` 触发的第二次加载与 A 的收尾交叠（`setCodeDir` 会 `tabs = []`）。
  3. 失败现场已自动落盘（`.scratch/code-editor-refine/batch-loop-fail-*.txt`），
     每次失败都会带树实况 + 端点实况 + `openTabPaths()`，可直接增量取证。
- 第十轮顺带（同批实跑暴露出，同属「脚本写死等待」这一类，已修）：
  `pdf-library-ui/smoke.mjs` 场景 06 用 `sleep(400)` 等删除确认弹窗，而该弹窗前面有一次
  ≈500ms 的 `/api/pdfs/{rel}/refs` 请求（实测弹窗首现 518ms）→ **确定性红**；改为轮询等到场
  （`.scratch/pdf-library-ui/diag-trash-modal-flake.mjs` 为取证脚本）。
