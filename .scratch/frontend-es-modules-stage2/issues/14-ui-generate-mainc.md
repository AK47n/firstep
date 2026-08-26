# 14 — 生成页 · main.c 工具：static/js/ui/generate-mainc.js

**要做什么：** generate tab 的「main.c 预览工具」小簇迁入 `static/js/ui/generate-mainc.js`（高亮同步 / 缩放 / 工具栏：复制/下载/全屏）。**被谁阻塞：** 02（app.js）

**状态：** 待实施

## 关键事实（1-based 行号，实施时以 grep 复核）

- 函数（4014-4134）：syncMainCHighlight 4014 / IIFE initMainCHighlight 4022 / currentCodeZoomPct 4038 / applyCodeZoom 4043 / IIFE initCodeZoom 4052 / initMainCTools 4068（nested copyValue 4084 / downloadValue 4098 / setFullscreen 4113）。
- 依赖：`$`（app.js）、CODE_ZOOM_MIN/MAX（本簇自有常量，随迁）、mainc 域纯件（fx/code.js：cHighlight / cLineCount / codeZoomClamp / parseZoomStored / maincLineOffsetRange / isMainCPath / maincContentEmpty / maincFullscreenLabel —— 胶水 import 调用）。
- markup：按钮 id（btn-mainc-copy / btn-mainc-download / btn-mainc-fullscreen 等，grep 确认）不动。
- host 启动 initMainCTools 调用（init* 清单 9032-9042 内）——host import。

## 检查表

- [ ] 新建 `static/js/ui/generate-mainc.js`：上述件逐字搬移 + import（app.js / fx/code.js）+ export（initMainCTools / syncMainCHighlight / currentCodeZoomPct / applyCodeZoom）+ 头部注释
- [ ] index.html：CRLF 感知行区间删除（4014-4134；**物理升序**）+ 顶部 import 行追加
- [ ] `node --test` 全绿 + pytest + diag 零 EXC + smoke 11/11（main.c 高亮项在 smoke 11 项内）+ grep 零残留（`function initMainCTools(` 等 6 名）
- [ ] 中文提交

## 风险点

- 本票最小、无跨簇边——适合在 12/13 之后快速消解 generate 簇的零头。
- initMainCTools 的 setFullscreen 若调用 fl/fs API（浏览器 Fullscreen API），逐字搬移 + 浏览器冒烟验证全屏行为。
