# 14 — 生成页 · main.c 工具：static/js/ui/generate-mainc.js

**要做什么：** generate tab 的「main.c 预览工具」小簇迁入 `static/js/ui/generate-mainc.js`（高亮同步 / 缩放 / 工具栏：复制/下载/全屏）。**被谁阻塞：** 02（app.js）

**状态：** resolved（2026-08-27；JS 442 全绿、pytest 2465 全绿、diag 零 EXC、smoke 11/11、probe-14 生成页实况 15/15）

## 实施记录

- **行号修正**：关键事实行号（4014-4134）为工单切割时估计；实施 grep 复核实际位于 2330-2440（工单 12/13 删除上方区块后行号前移）。三节结构：main.c 行号 + 语法着色（syncMainCHighlight 2330 / IIFE initMainCHighlight 2338）/ 代码字号缩放（CODE_ZOOM_STEP=10 / CODE_ZOOM_BASE=13, CODE_ZOOM_KEY="firstep.mainc.zoom" / currentCodeZoomPct 2354 / applyCodeZoom 2359 / IIFE initCodeZoom 2368）/ main.c 工具栏（initMainCTools 2384，nested copyValue / downloadValue / setFullscreen）。无跨簇边、无状态随迁（3 常量模块内私有），最小票属实。
- **常量名修正**：工单「CODE_ZOOM_MIN/MAX 随迁」为过时表述——实际常量是 `CODE_ZOOM_STEP` / `CODE_ZOOM_BASE` / `CODE_ZOOM_KEY`（`const CODE_ZOOM_BASE = 13, CODE_ZOOM_KEY = "..."` 同行声明）；缩放 clamp 的下限 80 / 上限 200 在 fx/code.js codeZoomClamp 内（阶段 1 已迁，自包含常量），无 MIN/MAX 常量可迁。
- **fx/code.js 依赖清单**：本簇实际 import 6 名（cHighlight / cLineCount / codeZoomClamp / parseZoomStored / maincContentEmpty / maincFullscreenLabel）；maincLineOffsetRange / isMainCPath 属行跳转簇（maincJumpToLine 3044 / fixToggleSource 3074，host 保留至工单 16），未 import（头部注释已说明）。
- **host 调用点**（顶部 import 活绑定，2 名）：syncMainCHighlight@generateMain 2472（骨架写入后重同步）+@restoreDraft 4130（草稿恢复后重同步）；initMainCTools@启动区 4469（DOM 已就绪，纯本地交互）。currentCodeZoomPct / applyCodeZoom 随票导出（探针/后续使用），host 无调用点。
- **结构钉**：无——tests/js 无本簇函数断言（code-zoom.test.mjs 只测 fx 纯函数，不重指向）；fx-guard DOMAINS 零增（无新纯函数）。markup id（btn-main-c-copy / btn-main-c-download / btn-main-c-fullscreen / code-zoom-label / btn-code-zoom-in / btn-code-zoom-out / main-c-nums / main-c-hl）全部不动。
- **风险点验证（setFullscreen）**：全屏 = 同一 DOM 原地 fixed（`wrap.classList.toggle("fullscreen")` + `document.body.classList.toggle("code-full-body-lock")` + 按钮文案 maincFullscreenLabel），**不走浏览器 Fullscreen API**——probe-14 实况验证进入（wrap.fullscreen + body lock +「退出全屏」）与 Esc 退出（类全清 +「全屏」）均通过。
- **static/js/ui/generate-mainc.js**（新建 138 行，LF）：4 函数 + 2 IIFE + 3 常量逐字搬移（含三节原始注释）+ 头部注释（依赖 / 状态所有权 / 源自工单 14）+ 导出面（initMainCTools / syncMainCHighlight / currentCodeZoomPct / applyCodeZoom）。import app.js（$ / toast）+ fx/code.js（6 名）。IIFE 在 import 时自执行（module 延迟执行，DOM 已就绪，时序与迁前一致：zoom 初始化先于 host 启动 IIFE 的 restoreDraft）。
- **index.html（apply-14.mjs，4481→4374 行）**：①host import 行追加（generate-pins import 之后，4 名代理）；②簇体 2325-2441 → 注记（含三节头）。校验：6 函数/IIFE 零定义残留 + 3 常量零残留 + 启动 initMainCTools 调用与两处 syncMainCHighlight 调用完好 + import 恰好 1 行。
- **验证**：node --test 442 全绿；pytest 2465 全绿（bg）；diag 零 EXC（仅既有 favicon 404 噪声）；smoke 11/11（含 main.c 高亮项）；probe-14.mjs 15/15（动态 import 无错 / 高亮同步行号列 6 行 + tok-pre/tok-kw/tok-com 着色 / 缩放 100→110→100→90→80 下限 clamp + label + font-size 联动 + localStorage 持久化重载恢复 90% / 复制真实鼠标点击 →「main.c 已复制」toast（用户手势走 navigator.clipboard）/ 下载 →「main.c 已下载」toast / 全屏进出 / 全程零 EXC 零 4xx）。
- **探针教训**：①样例源码不带行尾 `\n`——带则 split 多出空行号（cLineCount 既有行为，非回归）；②Log.entryAdded 的 404 噪声 URL 在 `entry.url` 字段，需并入过滤（favicon）；③复制须真实鼠标点击（CDP Input.dispatchMouseEvent）+ scrollIntoView，JS 点击无用户手势会让 navigator.clipboard 走失败回退。

## 检查表

- [x] 新建 `static/js/ui/generate-mainc.js`：上述件逐字搬移 + import（app.js / fx/code.js）+ export（initMainCTools / syncMainCHighlight / currentCodeZoomPct / applyCodeZoom）+ 头部注释
- [x] index.html：CRLF 感知行区间删除（2325-2441；**物理升序**）+ 顶部 import 行追加
- [x] `node --test` 全绿（442）+ pytest 2465 全绿 + diag 零 EXC + smoke 11/11（main.c 高亮项在内）+ probe-14 15/15 + grep 零残留（`function syncMainCHighlight(` 等 6 名 index.html 无定义）
- [x] 中文提交

## 关键事实（行号经实施 grep 修正，见实施记录）

- 函数（原估 4014-4134，实际 2330-2440）：syncMainCHighlight / IIFE initMainCHighlight / currentCodeZoomPct / applyCodeZoom / IIFE initCodeZoom / initMainCTools（nested copyValue / downloadValue / setFullscreen）。
- 依赖：`$`（app.js）、常量 CODE_ZOOM_STEP / CODE_ZOOM_BASE / CODE_ZOOM_KEY（随簇，模块内私有）、mainc 域纯件（fx/code.js：cHighlight / cLineCount / codeZoomClamp / parseZoomStored / maincContentEmpty / maincFullscreenLabel —— 胶水 import 调用）。
- markup：按钮 id（btn-main-c-copy / btn-main-c-download / btn-main-c-fullscreen 等，grep 确认）不动。
- host 启动 initMainCTools 调用——host import；generateMain / restoreDraft 的 syncMainCHighlight 调用点同样走 import。

## 风险点

- 本票最小、无跨簇边——适合在 12/13 之后快速消解 generate 簇的零头。
- initMainCTools 的 setFullscreen 若调用 fl/fs API（浏览器 Fullscreen API），逐字搬移 + 浏览器冒烟验证全屏行为。
