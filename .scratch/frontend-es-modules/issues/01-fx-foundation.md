# 01 — 基础设施与桥接约定：core/env/btn-icon/platform/code 五模块 + 静态挂载

**要做什么：** 前端纯函数 ES 模块化的第一张切片：搭好整个流水线的地基并验证「window 同名惰性桥」约定成立——浏览器页面行为零变化、节点端测试可直接 import。含共享件 esc/formatSize（供全部域复用）与四个独立小域（环境检查 / 图标 / 平台点击 / C 代码工具）。从此 index.html 内联脚本不再新增纯函数。

**被谁阻塞：** 无——可立即开始（spec：.scratch/frontend-es-modules/spec.md）

**状态：** resolved（2026-08-26 合入；JS 416 全绿 + pytest 2465 全绿 + 浏览器冒烟 11/11（.scratch/frontend-es-modules/smoke.mjs））

## 实施记录

- 桥接方案 vs 工单原文升级：主体 `<script>` 改 `<script type="module">` + 顶部静态 import（module 语义保证 fx 先求值，顶层立即执行/IIFE 零改造）；独立 `<script type="module" src>` 标签不再需要。window 同名桥保留为兼容层（探针脚本按全局名取用仍可用）。见 spec「桥接约定 2」。
- 数字修正：搬移 = 15 个函数 + ENV_BADGE_GLYPH 常量（esc/formatSize、env 3、btnIcon、platformClickAction、code 8）。
- code-review 双轴：Standards 无硬违规；处理了「cHighlight 局部 esc 与 core 双源」（改 import core，行为零变化）、「CODE_ZOOM_MIN/MAX 死常量」（删除）、「fx 头注释措辞未跟上机制升级」（core.js 更新）；Spec 无缺失无范围蔓延（.scratch/backlog.md 的 M 是既有未提交改动，未纳入本工单）。

- [x] 新建 `src/contest_generator/static/js/package.json` = `{"type": "module"}`
- [x] webapp.py：`from fastapi.staticfiles import StaticFiles` + create_app 内 `app.mount("/js", StaticFiles(directory=STATIC_DIR / "js"), name="js")`；pytest 全绿
- [x] 新建 `static/js/fx/core.js`：esc、formatSize（函数体从 index.html 逐字搬移，语义零变化）+ 尾部 window 同名桥
- [x] 新建 `static/js/fx/env.js`：envRowHTML / envChannelHTML / envCheckStatusHTML + ENV_BADGE_GLYPH（同桥约定）
- [x] 新建 `static/js/fx/btn-icon.js`：btnIcon
- [x] 新建 `static/js/fx/platform.js`：platformClickAction
- [x] 新建 `static/js/fx/code.js`：cHighlight / cLineCount / codeZoomClamp / parseZoomStored / maincLineOffsetRange / isMainCPath / maincContentEmpty / maincFullscreenLabel
- [x] index.html：内联脚本删除以上 15 个被测试纯函数的定义（esc / formatSize / platformClickAction / env 3 / btnIcon / code 8）与 ENV_BADGE_GLYPH 常量；主体 `<script>` 改 `<script type="module">`，文件顶部静态 `import` 五个 fx 模块（升级版桥接：module 语义保证 fx 先求值，独立 `<script type="module" src>` 标签不再需要——见 spec「桥接约定 2」）；被搬函数引用的其余模块级常量随迁并 export（确保内联剩余代码零解析错误）
- [x] 测试改造：env-check-center / btn-icons / platform-click-action / mainc-tools / code-highlight / code-zoom / compile-error-jump 七个测试文件整体改 import；pdf-library / reference-library / master-browser / module-library / topic-browser / topic-detail / topic-edit（引用 esc 或 formatSize 的）改为从 fx/core.js import，其余 extract 不动
- [x] `node --test "tests/js/*.test.mjs"` 416 全绿（glob 形式）；浏览器冒烟：起服务打开页面，库/PDF/题库 tab 正常
- [x] grep 零残留：index.html 无 `function esc(` / `function formatSize(` / 上述 14 名定义


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
