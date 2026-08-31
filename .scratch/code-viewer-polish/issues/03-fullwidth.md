# 03 代码 tab 全宽化（跳出 main 容器，左右贴边）

Status: resolved

## 要做什么

用户认为「屏幕两边留白太多」——代码 tab 被 `main` 的 max-width（1400/1640/1800）
与 `main > section.page` 的 1280/1400/1520 双重上限夹在页面中间（1554 视口时
两侧白 ≈137px），与 CCS 整窗编辑器对照观感差。把 `<section id="tab-code" class="page">`
从 `<main>` 内移至 `</main>` 之后成为 **body 直子**（block 宽度 auto 自然填满
client 区，无 100vw 含滚动条溢出坑），CSS 加 `#tab-code { margin: 20px 16px; }`
（顶部跟随 main 的 20px 节奏，两侧 16px 贴边）。其余 tab 的 max-width 节奏不动
（section 已非 main 子元素，`main > section.page:not(#tab-generate)` 选择器自然失效）。

备选方案均已推演弃用：负 margin 右溢出会引发横向滚动条；transform 布局框溢出
同样触发滚动条；main overflow-x: clip 会在 main 边框处裁剪右侧。

## 被谁阻塞

无（前端视觉打磨，工单 02 之后）。

## 验收清单

- [x] `#tab-code` 是 body 直子（DOM：`</main>` 之后）
- [x] 几何：左侧 16px、右侧贴 client 区 16px（滚动条另计）；布局宽 > 旧上限 1280
- [x] 纵向撑满：flex 列 + `height: calc(100vh - var(--header-h) - 32px)`——顶间隔
      20px（`main` 空块 margin 与 section 塌陷取大 max(20,16)）+ 底 12px，卡片底
      距视口底 12px 直达；`.card` 自带 `margin-bottom: var(--space-5)` 在 flex 列
      内留缝 → `#tab-code .card { margin-bottom: 0 }`；`.code-layout` 由
      `height: min(70vh,640px)` 改 `flex: 1 1 auto; min-height: 300px`（原 min 420
      会顶爆窄视口）
- [x] 交互冒烟 17/17 全绿（树/文件加载/大纲/搜索/Ctrl+F/最近卡按钮无回归）
- [x] tests/js 全量 933 绿（nav-tabs-guard / css-tokens 等静态守卫通过）
- [x] 截图 `.scratch/code-viewer/shot-fullwidth.png` 观感确认（三栏贯穿全窗、
      下方直达视口底，无大留白）
