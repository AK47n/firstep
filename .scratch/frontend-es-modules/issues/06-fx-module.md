# 06 — module 域模块化：fx/module.js（28 函数）

**要做什么：** 模块库（grid / info-dialog / library）与生成页模块配置（分组卡、多实例）全部被测试纯函数迁入 `static/js/fx/module.js`；module-grid / module-info-dialog / module-library / group-cards / instance-config 五个测试文件改为 import；页面零变化。

**被谁阻塞：** 01（core.js）

**状态：** resolved（2026-08-26；JS 416 全绿 + 浏览器冒烟 11/11）

## 实施记录

- 迁移 28 个纯函数（与工单清单一致）：moduleBadges / pythonArtifactSummary / groupOfSlug / applyGroupRadio / autoAddDedup / groupConflicts / renderGroupCards / groupRequirementNote / moduleGridPlatformLabel / moduleGridStatusText / moduleGridBadgeClass / moduleGridFilter / moduleGridCountText / moduleGridHTML / moduleInfoHTML / multiInstanceModules / instancePayload / ensureDefaultInstances / libFilterModules / libSortModules / danglingDependencies / libStats / libStatsText / libChipRowHTML / moduleRowHTML / editDescStatus / libIsValidHttpUrl / libPlatformKits。
- fx/module.js：函数体逐字搬移 + docstring 全保留；esc 单源取自 fx/core.js（moduleBadges / pythonArtifactSummary / renderGroupCards / groupRequirementNote / libChipRowHTML / moduleRowHTML 用）；**moduleGridHTML / moduleInfoHTML 保留函数体内局部 escHtml**——其 null/undefined→"" 兜底与 core esc 不同，照搬不合并（同 topicCardHTML 先例，头部注释已标注）。
- **多实例三函数参数化**（spec「特殊情形」+「被搬函数引用的模块级常量随迁」的落地）：multiInstanceModules / instancePayload / ensureDefaultInstances 原引用主体脚本模块级状态 expanded / instances（闭包捕获），迁入后改为显式参数传递——行为零变化，index.html 四处调用点同步传参（renderInstanceConfig 内 ensureDefaultInstances(expanded, instances) / multiInstanceModules(expanded)；generate 载荷 4157、4337 两处 instancePayload(expanded, instances)）；测试从「工厂传参」简化为直接调用（断言不变）。instList（instances[slug] 惰性初始化胶水）与 moduleColorMap（未测试）留内联。
- index.html：主体 module 顶部 import 行追加（master.js 之后，28 名）；9 处 CRLF 感知行区间删除（R1 23 行 moduleBadges+pythonArtifactSummary / R2 91 行功能组卡纯函数组 / R3 73 行模块网格纯函数组 / R4 76 行 moduleInfoHTML / R5a 7 行 / R5b 14 行 / R5c 14 行（多实例三函数）/ R6a 125 行模块库工具栏纯函数组 / R6b 34 行 editDescStatus+libIsValidHttpUrl+libPlatformKits），全部 0-based 内容锚定 + 指定 span 校验通过，替换为「已迁至 static/js/fx/module.js（工单 06）」注释（R5a-c 注明参数化）；胶水留内联：renderModulePool / openModuleInfo / renderRecommendResult / renderSelected / renderInstanceConfig / instanceBlock / renderLibraryChips / renderLibraryStats / renderLibraryTable / editDescription / editModule 等。
- 教训：PW 删除脚本里 `$starts[$k+1]`（字符串键拼接 → null → 降序 range）导致文件膨胀至 40966 行——已 git checkout 恢复后重做；本次改为显式 order 数组 + 末键单独收尾。
- 测试改造（5 文件）：module-grid / module-info-dialog / module-library / instance-config 整头换 import（fs/path/url/html/esc 全删——html 仅抽取用）；group-cards 删 extract + 本地 esc，**保留 html 读入**（164-167 行「推荐结果区接线」结构测试断言 index.html 调用点仍在——与 topic-cards 的 #topic-grid 测试同类）。
- 验证：`node --test "tests/js/*.test.mjs"` 416 全绿；diag.mjs 零 EXC（favicon 404 既有噪音）；smoke.mjs 11/11（含 generate / library 两 tab——module import 链 + moduleRowHTML 实况渲染即证）；`node .scratch/verify-instance-config.mjs` 跳过（需自起浏览器页，非必要项；实例路径由 416 单测 + 模块级 Parse/执行兜底）。

- [x] 新建 fx/module.js：moduleBadges / pythonArtifactSummary / moduleGridPlatformLabel / moduleGridStatusText / moduleGridBadgeClass / moduleGridFilter / moduleGridCountText / moduleGridHTML / moduleInfoHTML / danglingDependencies / libFilterModules / libSortModules / libStats / libStatsText / libChipRowHTML / moduleRowHTML / editDescStatus / libIsValidHttpUrl / libPlatformKits / applyGroupRadio / groupOfSlug / autoAddDedup / groupConflicts / groupRequirementNote / renderGroupCards / multiInstanceModules / instancePayload / ensureDefaultInstances 及域内常量；esc 从 fx/core.js import；尾部 window 桥
- [x] index.html 删除上述函数定义；加载 `<script type="module" src="/js/fx/module.js">`
- [x] 五个测试文件改 import（fx/module.js + fx/core.js）
- [x] `node --test` 全绿；冒烟模块库 tab
