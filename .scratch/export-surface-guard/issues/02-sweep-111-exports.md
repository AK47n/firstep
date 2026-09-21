# 02 — 按判据清点处置 111 处（110 摘 export + 1 整条删）

**要做什么：** 让判据 D 从 **111 处违规**变成 **0 处**，且**页面行为零变化**：110 处摘掉多余的
`export`（定义、模块内部引用、模块底部的 window 探针桥**一字不动**），1 处整条删
（`ui/generate-recommend.js::groupChoiceGap()`，零引用）。做完之后"导出"重新等于"有人真的 import"。

**被谁阻塞：** 01（判据单源与红证）

**状态：** ready-for-agent

## 验收标准

- [ ] 清点脚本 `.scratch/export-surface-guard/apply-sweep.mjs`：**自带校验**（逐处内容锚定；判定为
      违规的才动，改一处报一处；任何一处对不上就整体不写盘），产出 `.scratch/export-surface-guard/verify-sweep.txt`。
- [ ] **110 处摘掉多余的 `export`**，形态照实测（`probe-03-sweep-shape` 读数）：
      **73 处 inline**（`export const/function/let/var` → 删 `export ` 前缀）；
      **30 处**从 `export { … }` 清单里摘名字（8 条清单行留下）；
      **7 处**所在的 4 条清单**整行删**（`ui/full-update.js` 1 名 / `ui/generate-fix.js:47` 2 名 /
      `ui/params-chat.js` 1 名 / `ui/params.js` 3 名）。这 37 处清单形态**全部是本文件声明的名字**
      （含 `export { x } from "…"` 的转手再导出），故**不得**产生"未使用具名 import"
      ——改完必须复跑 `import-usage-guard` 那条判据确认。
- [ ] **1 处整条删**：`ui/generate-recommend.js::groupChoiceGap()`（含其上方注释块）。
      **代价如实记账**（写进 Comments）：`.scratch/group-choice-required/smoke-browser.mjs` 那张一次性
      探针里的 `rec.groupChoiceGap()` 会链接期报错——服务的是已 resolved 的 `group-choice-required`，
      本轮**不修**。
- [ ] **行为零变化的证据**：`git diff --stat` 只涉及 `src/contest_generator/static/js/**`；
      **行数只减不增**；`git diff` 里 window 探针桥（`Object.assign(window, {…})` 那些行）**零改动**；
      555 个 id / `index.html` **零改动**。读数写进 Comments。
- [ ] 复跑判据：**判据 D = 0 违规**；**`graphBreaks` 仍绿**（没有谁还在 import 一个已经不导出的名字）；
      `reachable` / `wiringViolations` / `registryProblems` 全绿（摘 `initTopicToolbar` 的 `export` 后，
      `ui/topic.js` 的登记体检仍由 `initTopicPanel` 的调用点满足——实测确认，见 Comments）。
- [ ] **红证复跑**：`node .scratch/export-surface-guard/probe-04-red-proof.mjs` → ① base 自校验通过、
      ② 判据在 base 上红（111）、④ 强度自检 9/9、③ **当前工作树绿**（判据 D = 0，且判据 T／星号体检／
      取数面体检全绿——工作树这一半是硬判，不是打印）；覆盖写 `red-proof.txt`。
- [ ] `node --test "tests/js/*.test.mjs"` 全绿（基线 **1679 passed**）。
- [ ] **未顺手做**：常量形态、C6/C7、`.scratch` 探针修复、`import-usage-guard` 口径扩展。

## Comments
