# 02 — 批跑器判定与取证补口：挑页唯一化 / 「无判定行」标注 / 首跑输出落盘 / 退出码按终局

**要做什么：** 第十四轮拿第十三轮做好的机制（红即复跑 + 非绿落盘事件序列）去给第十一轮挂账的两处
批内偶发定性时，**复现**出了第一处（`code-editor-vscode-polish/smoke-03` 首跑 `PASS 4 / FAIL 4`，
复跑 8/8 绿），但当场**定不了性**：落盘的现场缺三样东西。本单把这四处判定与取证口径补齐——
它们都是「工具让人看不清现场」，不是产品缺陷：

1. **挑页唯一化**：`rebuildTab()` 此前只关**一个** page（`pageTarget(anyPage:true)` = 列表第一个），
   长连跑里因此留下**永不被关闭的孤儿页**（实测 9251 上 `1C933610` 跨数十支次恒定存在，白占一个渲染进程）；
   而 50+ 支脚本挑页用的是 `list.find(...)` = 列表第一个匹配页 —— 「脚本跑在哪个页上」于是变成
   依赖 `/json/list` **顺序语义**（实测「新页在前」，见 `.scratch/batch-runner-self-heal/probe-list-order.mjs`），
   当前恰好命中刚重建的页，但那是**未文档化的假设**，不是构造保证。
2. **「非零退出 + 无判定行」单独标注**：第十一轮记录的库 UI 偶发签名（`exit=1` 且无 FAIL 行）
   与「断言红」在判定上完全不可区分，只能靠人去看输出。
3. **非绿支次落盘自己的输出**：此前只留 `tail` 两行，而 tail 往往取的是**复跑那次**（绿的）输出
   —— 于是「到底哪几条断言红了」在落盘里看不到，必须再复现一次才能查（本轮就卡在这里）。
4. **退出码按终局判定**：汇总里 `FAIL` 计的是**首跑**，而退出码此前直接取 `fails`，
   于是「只有偶发（首红复绿）」也会 `exit 1`，与第十三轮记录的口径（真红 → 1，只有偶发 → 0）自相矛盾。

**被谁阻塞：** 无。

**状态：** resolved

- [x] `cdp-harness.mjs` 新增纯函数 `planRebuildTargets(list, pageUrl)`：有匹配页 → 返回**全部**匹配页；
      一个都没有 → 退回旧行为（关一个任意 page，不把无关页卷进来）；非 `page` 目标一律不选
- [x] `rebuildTab()` 改为关掉计划里的**每一个**目标；重建后若仍有 >1 匹配页则打 `[harness] 警告`
- [x] `classifyAttempt` 新增 `noVerdictLine` 与信号「非零退出且无判定行（脚本在打印汇总前中断：未捕获异常/传输层）」；
      新增 `VERDICT_LINE_RE` 收全各脚本汇总措辞（`ALL PASS` / `n PASS / m FAIL` / `SMOKE PASS` /
      `n 全 PASS` / `全部通过` / `n passed` / `FAILED`）
- [x] `renderDiagText` 新增「该支次 stdout / stderr」段；`cdp-smoke-run.mjs` 非绿时落盘
      **该支次自己**的输出（stdout 尾 80 行 / stderr 尾 40 行，写进 `.json` 与 `.txt`）；
      控制台现场摘要与 `stderr/stdout` 打印改为取**首跑**（此前取最后一次 = 多是绿的复跑，真现场被盖掉）
- [x] 批跑器退出码改按终局判定（`realFails || realHangs`）：只有偶发 → `0`；汇总加打一行判定口径
- [x] `tests/js/cdp-harness-verdict.test.mjs` **19 例全绿**（原 13 + 新增 6：`planRebuildTargets` ×2、
      `noVerdictLine`、`VERDICT_LINE_RE` 措辞、落盘含自身输出、静态守卫「不得回退成只关一个 / 退出码按终局 / 落盘 stdout」）
- [x] 实测（Chrome 9251 + webapp 8000）：孤儿页消失——重建后匹配页**恒为 1**（修复前恒为 2），
      且 `find()` 挑中的就是刚重建的那个（`.scratch/batch-runner-self-heal/probe-wrong-tab-after-fix.log`，
      对照 `probe-wrong-tab.log` + `probe-list-order.log`）
- [x] 实测：修复后 ① `overhaul+polish` 17 支 × 10 轮 = **170 支次**、② 全量 56 支 × 2 轮 = **112 支次**
      ——合计 **282 支次 0 偶发 / 0 真失败**，退出码 **0**
      （`verify-14-after-fix-overhaul-polish-17x10.txt` / `verify-14-after-fix-longrun-56x2.txt`）
- [x] 无回归：`python -m pytest -q` → **3928 passed, 3 warnings**；
      `node --test tests/js/*.test.mjs` → **1422 pass / 0 fail**（原 1416 + 本轮 6 条新增）

## Comments

- 2026-09-10 第十四轮（按第十三轮「下一轮建议」第 1 项）：给两处批内偶发定性时挖出这四处缺口，
  全部落地并实测。**产品代码零改动**（改的是 `.scratch/` 下的共用件与批跑器 + `tests/js` 单测）。

  **触发这一切的那次复现**（修复前）：十批全量长连跑 56 支 × 3 轮 = 168 支次，
  `code-editor-vscode-polish/smoke-03.mjs` 第 3 轮首跑 `exit=1`、耗时 26.3s、`tail = PASS 4 / FAIL 4 | FAILED`，
  复跑 1.5s **8/8 ALL PASS** → 新机制自动判定**偶发**（不计失败）并落盘
  （源 `.scratch/cdp-smoke-runs/1789038021261-r3-code-editor-vscode-polish-smoke-03.{json,txt}`，
  随仓库留档：`verify-14-flake-r3-polish-smoke-03.{json,txt}`）。
  与第十一轮记录的形态（「长连跑里红、单支复跑全绿」）**同形**。

  **时间线自证清白**：两条探针（`probe-wrong-tab.mjs` 采样窗 10:56:04Z–10:58:24Z、
  `probe-list-order.mjs` 约 10:57:0xZ）都不在该支次窗口（10:59:55Z–11:00:21Z）内，复现不是探针扰动所致。

  **如实留口**：那条偶发首跑 26.3s（正常 1.5s）≈ 3 个 8s 的 `waitFor` 超时，断言 **4 红 4 绿**
  （脚本把 8 条断言全跑完了 ⇒ 四个标签当时都在）——失败集中在「标签数量/顺序」一族，
  属脚本**起步态**问题、非产品缺陷；但**逐条定性仍差一步**：当时落盘只有 tail 两行且它取自复跑那次
  → 已按本单第 3 项补上「非绿支次落盘自身输出尾 80 行」，**下次再现即可直接定性**。
  库 UI 那处（`exit=1 无 FAIL 行`）本轮 **450 支次未复现**，但签名现在可判（第 2 项）。

  **本轮实测的两个工具侧事实**（都写进上面 checklist 的落地物里）：
  ① `/json/list` 是**新页在前**（后建的页下标更小，实测 A@1 / B@0）；
  ② 由此 `rebuildTab()`「只关第一个」= 关最新那个 ⇒ 列表里原有的第二个匹配页**永生**（孤儿页）。
  另：`.scratch/cdp-smoke-runs/` 在 `.gitignore` 里，故本轮把关键现场另存到本目录 `verify-14-*.{txt,json}`。
