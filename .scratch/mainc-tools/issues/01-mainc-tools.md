# 工单 01：main.c 工具栏（复制 / 下载 / 全屏）

Status: resolved
Slug: mainc-tools
依赖：无（纯前端，只改 index.html + 新增 1 测试文件）

## 背景

骨架编辑区（第 8 卡 `.code-wrap` 三明治：行号 + 高亮层 + textarea）右上角
已有 `.code-zoom` 悬浮工具条（−/100%/＋）。本工单在工具条内追加三个操作。

## 验收标准

- [x] `.code-zoom` 内新增分隔符 + 三个按钮：`btn-main-c-copy`（复制）、
      `btn-main-c-download`（下载）、`btn-main-c-fullscreen`（全屏）。
- [x] 复制：内容非空 → 剪贴板写入 + toast「main.c 已复制」；剪贴板 API
      失败回退 select+execCommand；内容为空/纯空白 → toast「main.c 还没有内容，
      先生成骨架」（不抛错）。
- [x] 下载：内容非空 → 生成 `main.c` 文件下载 + toast「main.c 已下载」；
      空内容同复制提示。
- [x] 全屏：点按钮 `.code-wrap` 加 `.fullscreen`（fixed 撑满视口，行号/高亮
      /滚动/缩放保留）→ 按钮文案变「退出全屏」；再点或按 Esc 退出并恢复文案。
- [x] 全屏时 `body` 加锁滚动类（滚轮不再卷动背景页）。
- [x] 纯函数 `maincContentEmpty(value)` / `maincFullscreenLabel(active)`
      自包含（不引用模块级常量），tests/js/mainc-tools.test.mjs 覆盖。
- [x] 新增测试文件全部通过；既有 JS 测试不回归。

## 实现说明

- CSS 插入位置：`.code-zoom` 规则后（约 956 行区）：`.code-zoom .sep`、
  `.code-wrap.fullscreen` + `body.code-full-body-lock`。
- JS：`initMainCTools()` 挂在 initCodeZoom IIFE 之后；Esc 监听 document
  keydown（仅全屏时退出）。
- 工具条按钮复用 `.code-zoom button` 既有样式（字号 13px）；操作按钮加
  `.act` 类覆写 `width/height:auto`（既有 22px 定宽会裁掉「复制/下载/全屏」
  两字文案）——code-review 记录的**必要偏离**，与工单「无需新增按钮样式」
  字面不同，按评审意见已注明。
