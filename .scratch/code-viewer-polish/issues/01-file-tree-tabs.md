# 工单 01：文件树类型图标 + 顶栏文件标签

## 要做什么

代码查看器的「IDE 观感」第一步：
1. fx/codeview.js 新增 `fileIconHTML(path, isDir) -> string`——内联 stroke
   SVG 16px（风格照 fx/btn-icon.js：`fill="none" stroke="currentColor"
   stroke-width="1.5"`、viewBox 16）；按扩展名映射：文件夹 / .c / .h 系列 /
   .md .txt / .json .syscfg .uvprojx .cproject .xml / .s .S .asm /
   .o .obj .out .map .hex / 未知 → 通用文件图标。
2. `codeTreeHTML` 文件行与目录 summary 前渲染图标 span
   （`<span class="code-tree-icon" aria-hidden="true">…svg…</span>`）；
   目录 = 文件夹图标，文件 = 类型图标。
3. fx/codeview.js 新增 `codeFileTabHTML(path, lang) -> string`——
   `code-file-tab`（badge 徽标 + 文件名 + data-tab-path）；lang 徽标文案
   C / XML / TXT（plain → TXT）。
4. ui/codeview.js：openCodeFile 成功后 #code-current-path 渲染为 tab
   （title = 完整相对路径）；未打开文件保持空态文本。
5. index.html CSS：.code-tree-icon / .code-file-tab /
   .code-file-tab-badge（全部既有 token，不新造色值）。

## 被谁阻塞

无（code-viewer/01-06 已合入）。

## 状态

resolved

## 验收清单

- [x] fileIconHTML：.c/.h/.md/.json/.syscfg/未知 各返回带对应图标的 SVG，
      未知兜底通用图标；isDir 返回文件夹图标。
- [x] codeTreeHTML：文件行与目录均含 .code-tree-icon；既有
      data-code-file / details / summary 断言不破。
- [x] codeFileTabHTML：badge 文案映射 C/XML/TXT，data-tab-path 为相对
      路径，文件名经 esc 转义。
- [x] ui：打开文件后顶栏出现 tab（含徽标），title 为完整相对路径；
      未打开时无 tab。
- [x] tests/js codeview.test.mjs 新增用例绿；全量 js 测试绿（933）。
- [x] CDP 冒烟：树文件行含图标；打开 main.c 顶栏含 .code-file-tab 与
      badge「C」。
