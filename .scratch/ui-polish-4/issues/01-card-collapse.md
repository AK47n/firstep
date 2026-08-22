# 01 — 生成页卡片折叠

**要做什么：** 生成页卡片标题行右侧折叠按钮（▾）+ 标题行点击 toggle；步骤导航底部「收起已完成 / 全部展开」一键切换；折叠与滚动高亮/跳转兼容。

**被谁阻塞：** 无。

**状态：** resolved

- [x] CSS：`.card-collapse` 按钮样式；`.card.collapsed > *:not(h2)` 隐藏（!important 压行内 display）；折叠时按钮旋转 -90°
- [x] JS：动态注入折叠按钮 + h2 点击 toggle（stopPropagation 防双触发）；`collapseToggleAll` 纯函数（已完成折叠 / 未完成保持 / 全部展开 / 无徽章卡不折叠）
- [x] 步骤导航底部「收起已完成 / 全部展开」切换按钮，联动 stepDoneSet
- [x] `tests/js/card-collapse.test.mjs`：4 个边界用例，全绿
- [x] CDP 验证：单卡 toggle（h2 与按钮）、收起已完成（1-3 折叠 4+ 展开）、全部展开、折叠后滚动高亮仍正常（current=5）；截图目检通过
- [x] 修复 TDZ bug：`initCardCollapse()` 原调用位置在 `CARD_COLLAPSE_SELECTOR`（const）初始化之前 → ReferenceError 中断整个 script（init 不执行）；已移到脚本末尾
