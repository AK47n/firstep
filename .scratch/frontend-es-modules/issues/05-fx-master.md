# 05 — master 域模块化：fx/master.js（6 函数）

**要做什么：** 母版页全部被测试纯函数迁入 `static/js/fx/master.js`，master-browser.test.mjs 改为 import；页面母版 tab 行为零变化。

**被谁阻塞：** 01（core.js）

**状态：** ready-for-agent

- [ ] 新建 fx/master.js：masterTableRowHTML / masterDeleteConfirmHTML / masterFileURL / masterKeyFileRowHTML / masterDetailHTML 及域内常量；esc 从 fx/core.js import；尾部 window 桥
- [ ] index.html 删除上述函数定义；加载 `<script type="module" src="/js/fx/master.js">`
- [ ] master-browser.test.mjs 改 import（fx/master.js + fx/core.js）
- [ ] `node --test` 全绿；冒烟母版 tab
