# 13 — 场景 5 残余偶发的真因（之二）：切 tab 的 `checkCodeDiskChanges` 探测旧目录并覆盖新目录清单

**要做什么：** 定性并修复 `refine/smoke-01` 场景 5 的**残余偶发**——第十轮修掉第一个目录竞态
（`loadCodeDir` 交叠）之后仍剩 ≈1/4 的失败，形态从「`ta=null` 标签 `[]`」变成「打开成功后被第三方
清标签」。本单是第十一轮的定性结论 + 修复。

**被谁阻塞：** 无（已完成）。

**Type:** task
**Status:** resolved

**关联：** `.scratch/code-editor-refine/issues/12-save-switch-flake-diagnosis.md`（同一症状的**第一个**成因
——第十轮已修）；本单同轮的**脚本侧**加固在 `.scratch/code-editor-refine/smoke-01.mjs`
（取证辅助脚本在 `.scratch/code-editor-perf-structural/`）。

## Answer

**结论：又一个真产品缺陷**，与第十轮那个**成因不同、表象同形**（都是「标签显示新目录、树里是旧目录
的文件」）。签名 ②（保存未落盘）本轮 24 轮 + 20 轮均未复现，且取证脚本已能证明**写盘请求确实发出且
200**（见「签名 ② 的处置」）。

### 失败序列（CDP 观测器实测，`dir` + 调用链 + 标签采样三者对齐）

```
① openCodeViewer(B) 先 `btn.click()` 切「代码」tab
   → index.html:4495 的 nav 处理器**同步**调 checkCodeDiskChanges()
   → 此刻 codeDir 还是 A ⇒ 对 **A** 发起 POST /api/code/open   （观测：delay#1 a）
② 随后 setCodeDir(B) 才把 codeDir 改成 B ⇒ 对 **B** 发起探测    （观测：fast#2 b）
③ B 先返回（实测 7ms）、A 后返回（10ms）
   → 若 probeDiskBaseline **无条件**写 `codeFiles`，A 的清单就覆盖 B 的
   → 树渲染 main.c（A 的文件）而标签显示 b
   → 用户点 other.c 时树里根本没有这个节点 ⇒ `?.click()` 静默 no-op
   → 「没有活动标签 / 编辑器空白」（第十轮登记的表象）
```

`codeDirSeq`（第十轮加的）**只守 `loadCodeDir` 自己的快路径**：A 的探测是在
`loadCodeDir(B)` 认领序号**之前**发起的（它在 nav 点击里），而且 `probeDiskBaseline` 写 `codeFiles`
是**无条件**的、发生在 `loadCodeDir` 的 `stale()` 复核**之前**——所以那个守卫拦不住它。

### 证据

| 证据 | 脚本 | 结果 |
|---|---|---|
| 自然复现（每轮含整页 reload，8 轮 / 10 轮各一遍） | `.scratch/code-editor-refine/diag-batch-loop.mjs` | 失败 **2/8** 与 **2/10**，四次现场**完全同形**：`label=b` / `treeFiles=["main.c"]` / `openTabs=[]` / `ta=null`，而失败探针里那次现拉 `/api/code/open` 返回 `["other.c"]` |
| 请求 `dir` + 调用链 + 标签采样 | `smoke-01.mjs`（第十一轮加固的观测器） | `{dir:"b", loadCodeDir}` 与 `{dir:"a", checkCodeDiskChanges ← index.html:4495 nav click}` 两条；标签采样 `[{n:0,label:"b",tree:["main.c"]}]` |
| **确定性复现（A/B 对照）** | `.scratch/code-editor-perf-structural/diag-dir-race-tabclick.mjs`（新增） | fetch 垫片把「切 tab 那次对旧目录的请求」推迟 800ms → **基线必 FAIL**（标签 b / 树 `["main.c"]`）、**修复后必 PASS**（标签 b / 树 `["other.c"]`） |
| 修复后自然复现率 | `diag-batch-loop.mjs 14` + `20` | **1/14**（且那次是**另一种**红：`await openFile` 未落定的 top-level await，见「遗留」）与 **20/20 全绿** |

### 修复（产品）

`src/contest_generator/static/js/ui/codeview.js`：

1. **统一序号**：把只属于 `loadCodeDir` 的 `codeDirSeq` 提升为「目录树操作」的统一守卫，新增
   `claimCodeDirSeq()`（谓词工厂），**三个**会写 `codeFiles` / 渲染树 / 写徽章的入口全部认领：
   `loadCodeDir`、`checkCodeDiskChanges`、`refreshCodeTreeOnly`。
2. **`probeDiskBaseline(isCurrent, dir)` 在写 `codeFiles` 之前复核守卫**——这是本缺陷的正面修复：
   晚到响应连清单都不写（此前它无条件写，是新旧目录互相覆盖的**唯一**写入点）。
3. **目录归属锚点放在探测内部**：以**进入探测时刻**的 `codeDir` 为锚
   （`const target = codeDir; … codeDir === target`）。为什么不在 `claimCodeDirSeq` 里比目录——
   认领发生在 `setCodeDir` **之前**（那时 `codeDir` 还是上一个目录），在那里比目录会让**每次认领
   当场自我作废**：第十一轮首次实现即栽在这里（目录永远加载不出来、冒烟 `1-pre` 全红），已记入
   代码注释与守卫用例。
4. `applyDiskChanges(isCurrent, diff)` 的逐文件重载循环含 `await`：落徽章/面板/渲染**之前**同样复核。
5. 顺带修掉一个可见缺陷：`loadCodeDir` 原先把 `#code-tree` 清成「加载中…」**早于**三选确认，
   用户在「取消」后停在占位上空树；本轮把清树移到探测成功之后，取消分支现在**界面一概不动**。
6. 第 4 个写入点补齐：`clearCodeDiskChanges()` 也在 `await baselineCommitDisk` 之后渲染树，
   同样认领 + 复核（本轮把 `codeFiles` 的**全部**写入点过了一遍：模块内 3 处 + 本处，
   现无未守卫的写入路径）。

### 全批实跑（本轮，分组跑 + 组间 2s 停顿）

`overhaul` 9 / `refine` 10 / `viewer` 11 / `polish` 8 / `ideai` 4 / `treeops` 1 / `ideflow` 3 /
`bridge` 5 / `fem` 1 / 库 UI 4（17/47/51/75）= **65 支次全绿**。
长连跑（十批一口气）时出现过 2 次批内偶发（`polish/smoke-03`、`module-library-ui`），
**单支复跑即全绿** —— 与第十轮记录的 `polish/smoke-03` 同族（浏览器侧劣化，非脚本/产品缺陷），
已记入盘点第十一轮收口。

### 守卫与验收

- `tests/js/code-editor-window-guard.test.mjs`：新增
  「`probeDiskBaseline`：清单写入受守卫（第二个目录竞态 —— 切 tab 的 checkCodeDiskChanges）」
  （静态源断言：签名带守卫、复核**早于** `codeFiles` 写入、目录锚点在探测内、
  `checkCodeDiskChanges`/`refreshCodeTreeOnly` 是认领者、`applyDiskChanges` 落界面之前复核、
  确定性复现脚本在位且判据未被放宽）；同时更新了第十轮那条 `loadCodeDir` 守卫用例到新结构。
- 确定性复现脚本 `diag-dir-race-tabclick.mjs` 即本单验收脚本（基线 FAIL / 修复 PASS，单轮判定）。
- 回归：`tests/js` **1403 pass / 0 fail**、`pytest` **3928 passed**、CDP `refine` 10 支复跑
  **9/10 → 单支复跑全绿**（批内偶发见「遗留」）、`code-editor-perf-structural` 冒烟全绿。

## 脚本侧（同轮加固，属于「是脚本竞态就修脚本」那一半）

`.scratch/code-editor-refine/smoke-01.mjs`：

1. `setText` 现在**回读模型**（`dirtyTabPaths().length > 0`）才算改脏 —— 老版只写 `ta.value` 并
   返回「值是否写进去」，而窗口化渲染器可能在写入与读取之间按模型重装窗口把直写的值盖回去；
   那时后续断言会以「磁盘没落盘」的形态红，**掩盖真因**。
2. 新增**观测器**（只记不改）：包装 `window.fetch` 记 `/api/code/*` 的 `dir`/状态码/耗时/**调用链**；
   打开成功后按 20ms 采样标签数 1.2s。
3. 新增断言「5b-supp 打开成功后标签未被第三方清空」——把第十轮残余签名变成**机器判据**
   （此前只有打印、没有断言）。断言数 20 → 21。

## 签名 ②（保存未落盘）的处置

**本轮结论：不成立，且已能直证。** 取证脚本
`.scratch/code-editor-perf-structural/diag-save-switch-flake.mjs` 本轮重写后：分开计数两个签名、
修正了第十轮的口径错误（此前「裸点丢一次」即记 `sigNoTab`，即便守卫救回、内容比对全好 → 假红）、
并在签名 ② 上补齐第九轮要求的两项证据（**toast 文案** + **写盘请求状态码**）：

- 24 轮实测：每一次都是 `POST /api/code/save → 200`（6–12ms），落盘后磁盘 24/24 为
  `"int b = 777;\n"`；
- 基线 20 轮（旧版未加固脚本）出现过 1 次 `sigStaleDisk`，但那一轮**没有任何写盘请求**、
  且其后一轮磁盘即为 777 ⇒ 那是脚本侧 `setText` 未校验返回值的假红（真因 = 直写被窗口重装
  盖回，模型未改脏 → `saveAllDirtyTabs` 无脏可存），已在「脚本侧」第 1 条加固。
- 产品写入路径本身另有护栏（`setCodeDir` → `saveAllDirtyTabs` 任一未落定即 `return false` 不切换；
  `applySavedState` 在 POST 之后才更新 `savedContent`）。

## 遗留（本轮如实留口）

修复后 14 轮长跑里仍有 **1 次**红，但**是另一种红**、且与本缺陷无关：

```
Warning: Detected unsettled top-level await at smoke-01.mjs:228
check("5-pre 打开 other.c（树点击命中且成为活动标签）", await openFile("other.c"));
```

即 `openFile` 里那次 `await` 未落定、进程带 exit code 13 退出（*不是*断言失败；此前 10 支全红那次
也是同一形态）。发生在长连跑的第 8 轮，随后单支复跑立即全绿 —— 指向**长连跑下渲染进程/标签页
劣化**（与第十轮记录的 `polish/smoke-03` 同族），而非产品缺陷。**未取得根因证据，不写结论**；
下一步方向：给 `openFile` 的 `waitFor` 加**总预算上限**（现在单次 3s×3 次但未覆盖 `Eval` 本身
挂住的情形），或复用 `cdp-harness` 的命令级超时守卫（smoke-01 目前是自带的迷你 CDP 客户端，
没有超时守卫）。

## Comments

- 2026-09-10 第十一轮：新开本单。定性结论 + 修复 + 确定性复现 + 守卫 + 实跑数据见上。
  与 12 号单的关系：**同一症状、不同成因**，两个成因都修完 `smoke-01` 场景 5 才稳
  （12 号修「目录加载交叠」，本单修「切 tab 的旧目录探测」）。
