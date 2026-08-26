# 06 — module 域模块化：fx/module.js（模块库 / 分组 / 多实例 ≈28 函数）

**要做什么：** 模块库（grid / info-dialog / library）与生成页模块配置（分组卡、多实例）全部被测试纯函数迁入 `static/js/fx/module.js`；module-grid / module-info-dialog / module-library / group-cards / instance-config 五个测试文件改为 import；页面零变化。

**被谁阻塞：** 01（core.js）

**状态：** ready-for-agent

- [ ] 新建 fx/module.js：moduleBadges / pythonArtifactSummary / moduleGridPlatformLabel / moduleGridStatusText / moduleGridBadgeClass / moduleGridFilter / moduleGridCountText / moduleGridHTML / moduleInfoHTML / danglingDependencies / libFilterModules / libSortModules / libStats / libStatsText / libChipRowHTML / moduleRowHTML / editDescStatus / libIsValidHttpUrl / libPlatformKits / applyGroupRadio / groupOfSlug / autoAddDedup / groupConflicts / groupRequirementNote / renderGroupCards / multiInstanceModules / instancePayload / ensureDefaultInstances 及域内常量；esc 从 fx/core.js import；尾部 window 桥
- [ ] index.html 删除上述函数定义；加载 `<script type="module" src="/js/fx/module.js">`
- [ ] 五个测试文件改 import（fx/module.js + fx/core.js）
- [ ] `node --test` 全绿；冒烟模块库 tab
