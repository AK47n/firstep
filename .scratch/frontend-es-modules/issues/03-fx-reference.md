# 03 — reference 域模块化：fx/reference.js（17 函数 + referencePlatformChip）

**要做什么：** 参考文件库全部被测试纯函数迁入 `static/js/fx/reference.js`，reference-library.test.mjs 改为 import；页面参考 tab 行为零变化。

**被谁阻塞：** 01（core.js）

**状态：** ready-for-agent

- [ ] 新建 fx/reference.js：refDanglingAnchors / refFilterEntries / refSortEntries / refStats / refStatsText / refMatchFiles / refAnchorBadge / refChipRowHTML / refRowHTML / refDetailHTML / refEditState / refEditValidate / refEditFilePlan / refEditPayload / referencePlatformChip 及域内常量；esc/formatSize 从 fx/core.js import；尾部 window 桥
- [ ] index.html 删除上述函数定义；加载 `<script type="module" src="/js/fx/reference.js">`
- [ ] reference-library.test.mjs：改 import（fx/reference.js + fx/core.js）
- [ ] `node --test` 全绿；冒烟参考 tab
