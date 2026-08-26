# 05 — master 域模块化：fx/master.js（5 函数）

**要做什么：** 母版页全部被测试纯函数迁入 `static/js/fx/master.js`，master-browser.test.mjs 改为 import；页面母版 tab 行为零变化。

**被谁阻塞：** 01（core.js）

**状态：** resolved（2026-08-26；JS 416 全绿 + 浏览器冒烟 11/11）

## 实施记录

- 数字修正：工单标题「6」系估计，实际迁移 = 5 个纯函数（masterTableRowHTML / masterDeleteConfirmHTML / masterFileURL / masterKeyFileRowHTML / masterDetailHTML，以 master-browser.test.mjs 提取清单为准）；域内常量无。
- fx/master.js：函数体逐字搬移（含模板字符串）+ docstring 全保留；esc 单源取自 fx/core.js；masterKeyFileRowHTML 保留内部 MB/KB/B 三段格式化（与 core formatSize 语义不同——1MB 阈值 1048576、toFixed(1) KB 等，测试断言 17.2 KB / 2.5 MB / 909 B）；masterDetailHTML 引 masterKeyFileRowHTML（同模块直接引用）；尾部 window 桥 5 名。
- index.html：主体 module 顶部 import 行追加（topic.js 之后）；两处 CRLF 感知行区间删除（A 块 31 行 = masterTableRowHTML + masterDeleteConfirmHTML，B 块 45 行 = masterFileURL + masterKeyFileRowHTML + masterDetailHTML，0-based 边界校验「next 为 openMasterDeleteConfirm / 文件内容 memo」通过），替换为「已迁至 static/js/fx/master.js（工单 05）」注释；胶水留内联：masterCache / openMasterDeleteConfirm / masterFileCache / loadMasterFileState / renderMasterFileContent / openMasterFile / openMasterDetail / loadMasters。
- master-browser.test.mjs：整头替换为 import（fs/path/url/html/esc 全删——html 仅抽取用；测试体无 CSS 结构断言）。
- 验证：`node --test "tests/js/*.test.mjs"` 416 全绿；diag.mjs 零 EXC（favicon 404 既有噪音）；smoke.mjs 11/11（含母版 tab 切换）。

- [x] 新建 fx/master.js：masterTableRowHTML / masterDeleteConfirmHTML / masterFileURL / masterKeyFileRowHTML / masterDetailHTML 及域内常量；esc 从 fx/core.js import；尾部 window 桥
- [x] index.html 删除上述函数定义；加载 `<script type="module" src="/js/fx/master.js">`
- [x] master-browser.test.mjs 改 import（fx/master.js + fx/core.js）
- [x] `node --test` 全绿；冒烟母版 tab
