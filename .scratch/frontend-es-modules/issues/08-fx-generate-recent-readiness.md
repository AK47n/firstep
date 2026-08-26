# 08 — 生成主流程域：fx/generate.js + fx/recent.js + fx/readiness.js（20 函数 + CONFLICT_MSG_PREFIX）

**要做什么：** 生成流程（覆盖冲突 / 阶段播报 / 折叠 / 庆祝 / 输出目录 / 结果模块摘要 / 绑定收集）/ 最近任务 / 就绪检查全部被测试纯函数迁出对应模块；generate-overwrite / stage-report / card-collapse / celebrate / generation-output-dir-payload / format-res-modules / collect-bindings / recent-jobs / readiness-checks 测试改为 import；页面零变化。

**被谁阻塞：** 01（core.js）

**状态：** resolved（2026-08-26；JS 416 全绿 + pytest 锚点单测绿 + 浏览器冒烟 11/11）

## 实施记录

- 迁移 20 个纯函数 + 1 常量（工单标题「≈21」吻合）：
  - **fx/generate.js**（12 函数 + CONFLICT_MSG_PREFIX）：isConflictError / conflictDirName / genStageTexts / fmtWait / generationOutputDirPayload / collectBindings / formatResModules / attachCelebrate / collapseBtnLabel / syncCollapseBtn / collapseToggleAll（+ CONFLICT_MSG_PREFIX 常量）。
    - **syncCollapseBtn 随迁**（工单清单未列）：collapseToggleAll 引用它，且 card-collapse / settings-collapse 两测试按「同一 Function 作用域拼接」抽取三相邻函数——按 spec「特殊情形」处理；index.html 内 initCardCollapse / applySettingsCollapseState 经 import 绑定照常调用，零改动。
    - formatResModules 内 `typeof expanded === "undefined"` 守卫在模块中自然成立（模块作用域无 expanded / pythonTemplates）→ 逐字搬移，行为零变化。
  - **fx/recent.js**（6 函数）：recentStatusMeta / recentTimeLabel / recentPlatformLabel / recentChipHTML（保留局部 esc：null 兜底与 core 不同）/ recentListHTML / recentStatusNow。
  - **fx/readiness.js**（4 函数）：generateReadinessChecks / readinessSoftChecks / readinessRowHTML（保留局部 esc：仅 &<>" 且无 null 兜底）/ readinessRowsHTML（readiness-checks.test.mjs 实际测试它——工单清单未列，随迁）。
- **renderPriceReference 明确不迁**（工单清单偏离）：它引用主体脚本模块级 `$` 与 DOM（document.createElement / appendChild），迁入模块会 ReferenceError（`$` 非全局）；其测试 price-reference-clear.test.mjs 是源码结构断言（清空语句在追加前 + tbody 存在），对函数体的检查改走 import 的 toString 反而脆弱——保持内联 + 测试原样，待工单 10（settings 域）以 DOM 注入方案另行处理。
- **CONFLICT_MSG_PREFIX 随迁 generate.js 并 export**：tests/test_webapp.py::test_conflict_message_prefix_anchored_both_sides 改读 fx/generate.js（原断言 index.html 含字面前缀——迁后不再有，必须随迁更新；docstring 同步）；tests/js/generate-overwrite.test.mjs 静态断言改为「index.html 不再定义 const CONFLICT_MSG_PREFIX（单源防回退）」。
- index.html：主体 module 顶部 import 行追加三行（draft.js 之后）；9 处 CRLF 感知行区间删除（G1 12 行冲突识别 / G2 11 行播报文案 / G3 4 行输出目录载荷 / G4 13 行绑定收集 / G5 30 行产物摘要 / G6 12 行庆祝 / G7 23 行折叠三函数 / G8 61 行 recent 六函数 / G9 53 行 readiness 四函数），内容锚定 + span 校验通过；胶水留内联：renderGenerateSuccess / desktopTopicOutputEnabled / renderRecentList / refreshRecent / reportRecentStatus / initRecent / readinessState / renderReadinessPanel / initReadinessCheck / initCardCollapse / renderPriceReference / periodPlaceholders / collectLlmPrices / syncStep7 等。
- 教训：本批删除区域在文件中的物理顺序 ≠ 工单列表顺序（recent 8912 < collapse 9177；readiness 9039 < collapse 9177）——$order 数组曾按列表序导致降序 range 注入 578 行垃圾 + 20 个定义残留；已 git checkout 恢复，按文件物理序重排后一次成功。**教训固化：删除脚本的 order 必须以 grep 出的 start 位置升序为准，不能按工单清单序。**
- 测试改造（9 文件整头换 import）：generate-overwrite（保留 html——单源防回退断言）、stage-report / card-collapse / celebrate / generation-output-dir-payload / format-res-modules / collect-bindings / recent-jobs / readiness-checks（fs/html/extract 全删）；**settings-collapse.test.mjs 联动调整（本批额外）**：核心块改 import { syncCollapseBtn } from fx/generate.js + 设置页折叠块仍从 index.html 抽取（注入 syncCollapseBtn 重拼 Function 作用域——spec「特殊情形」先例），html 保留（存储键契约断言）。
- 验证：`node --test "tests/js/*.test.mjs"` 416 全绿；`python -m pytest tests/test_webapp.py::test_conflict_message_prefix_anchored_both_sides -q` 1 passed；diag.mjs 零 EXC（favicon 404 既有噪音）；smoke.mjs 11/11；grep 零残留（20 名无 `function <name>(` 定义）。

- [x] 新建 fx/generate.js：isConflictError / conflictDirName / genStageTexts / fmtWait / collapseToggleAll / collapseBtnLabel / attachCelebrate / generationOutputDirPayload / formatResModules / collectBindings 及域内常量（CONFLICT_MSG_PREFIX 等）；尾部 window 桥（syncCollapseBtn 随迁，见记录）
- [x] 新建 fx/recent.js：recentStatusMeta / recentTimeLabel / recentPlatformLabel / recentStatusNow / recentChipHTML / recentListHTML 及域内常量；尾部 window 桥
- [x] 新建 fx/readiness.js：generateReadinessChecks / readinessSoftChecks / readinessRowHTML（+ readinessRowsHTML 随迁）及域内常量；尾部 window 桥
- [x] index.html 删除上述定义；加载三个模块 script（renderPriceReference 不迁——DOM 胶水，见记录）
- [x] 对应测试文件改 import
- [x] `node --test` 全绿；冒烟生成页 + 设置页价格参考
