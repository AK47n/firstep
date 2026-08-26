# 03 — reference 域模块化：fx/reference.js（17 函数 + referencePlatformChip）

**要做什么：** 参考文件库全部被测试纯函数迁入 `static/js/fx/reference.js`，reference-library.test.mjs 改为 import；页面参考 tab 行为零变化。

**被谁阻塞：** 01（core.js）

**状态：** resolved（2026-08-26；JS 416 全绿 + 浏览器冒烟 11/11 + 参考 tab 实况渲染 154 条）

## 实施记录

- 数字修正：搬移 = 15 个函数（工单标题「17」系初稿估计）；实际清单 = referencePlatformChip + 14 个 ref*（refFilterEntries / refDanglingAnchors / refSortEntries / refStats / refStatsText / refMatchFiles / refAnchorBadge / refChipRowHTML / refRowHTML / refDetailHTML / refEditState / refEditValidate / refEditFilePlan / refEditPayload），与 reference-library.test.mjs 提取清单一致。
- fx/reference.js：15 函数逐字搬移（docstring 全保留）；域内常量无；esc/formatSize import 自 fx/core.js；尾部 window 桥。
- index.html：主体 module 顶部 import 行追加；删除 15 个定义（含 referencePlatformChip，注释改「已迁至 static/js/fx/reference.js」）；referenceAnchorLabel / referenceFileUrl / refCollectFiles 等胶水留内联（domain 边界：只搬被测试纯函数）。大块删除用 CRLF 感知的行区间脚本（244 行块），编辑后 diag.mjs 验证零 EXC（无悬空签名）。
- reference-library.test.mjs：两段提取（头部全函数 + 编辑弹窗 4 函数）整体换 import；esc/formatSize 不被测试体直接使用，core.js import 一并移除。
- 探针 probe-03-reference.mjs：window 桥 4 项 function + 参考 tab 实况渲染正常（共 154 条参考 · ANY 6 · STM32 8 · MSPM0 140 · 赛题 4 · 套件 2 · 未锚定 148 · 总体积 7.1 MB）。

- [x] 新建 fx/reference.js：refDanglingAnchors / refFilterEntries / refSortEntries / refStats / refStatsText / refMatchFiles / refAnchorBadge / refChipRowHTML / refRowHTML / refDetailHTML / refEditState / refEditValidate / refEditFilePlan / refEditPayload / referencePlatformChip 及域内常量；esc/formatSize 从 fx/core.js import；尾部 window 桥
- [x] index.html 删除上述函数定义；加载 `<script type="module" src="/js/fx/reference.js">`
- [x] reference-library.test.mjs：改 import（fx/reference.js + fx/core.js）
- [x] `node --test` 全绿；冒烟参考 tab
