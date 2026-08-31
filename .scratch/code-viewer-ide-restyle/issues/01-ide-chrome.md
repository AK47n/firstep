# 01 — 查看器 IDE 一体化 Chrome（全贴边工作台 + 无缝三栏 + 接线 tab + 编辑面）

**要做什么：** 「代码」tab 的查看器从「卡片套三卡片」变为全贴边 CCS/VS Code
式 IDE 工作台：外层卡片边框整个去掉（#tab-code margin 0、height calc(100vh -
header)，.card 去 bg/边框/圆角/内边距），工具栏成页面工具条（底 1px 分隔）；
三栏无缝拼接（无 gap、无独立圆角边框、1px 分隔线）、中列编辑器用深于页面与
面板的编辑面底色（--code-bg）、顶部 tab 条与编辑器「接线」（活动 tab 与编辑器
同底色、顶边 accent 线）、行号淡色与编辑器同底、当前行整行强调 + 左侧 accent
竖线、文件树/大纲活动行 flat 高亮 + 左 accent 竖线、面板标题改 section 头
（小字 muted、subtle 底、底部 1px 分隔、sticky）。全部 CSS-only（index.html
内嵌样式；如需要允许给树/大纲面板补最小包装结构）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 深色主题截图：三栏无缝、编辑面底色与面板分离、tab 条接线、当前行整行
      高亮带左 accent 线、树/大纲活动行 flat 高亮、section 头就位
- [x] 亮色主题截图同样协调（同结构性改动自动适配）
- [x] .scratch/code-viewer/smoke.mjs 全链路原样通过（零 DOM/行为回归）
- [x] 树宽拖拽手柄在 gap 归零后仍可拖（240↔±px 持久化冒烟项通过）
- [x] before/after 截图存档到 .scratch/code-viewer-ide-restyle/
