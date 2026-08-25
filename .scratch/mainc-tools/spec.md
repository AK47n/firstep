# main.c 骨架编辑增强（全屏 / 复制 / 下载）

## 问题陈述

第 8 卡骨架编辑区目前只有字号缩放（80–200%）：写完或生成骨架后，用户想
把 main.c 拿去 IDE / 粘贴给下一个 AI 时，没有复制按钮（要手动全选）、
没有下载（要找文件）、窄屏下编辑区太小没有全屏（行号+高亮三明治整体
错位风险让自行放大不可行）。

## 方案

在骨架代码框右上角已有悬浮工具条（`.code-zoom`）内追加三个操作：
**复制 / 下载 / 全屏**（与缩放同一工具条，共用面板背景防压字样式）。

- **复制**：`navigator.clipboard.writeText`（约 127.0.0.1 属安全上下文直接可用），
  失败回退 `textarea.select() + document.execCommand("copy")`；成功/失败均 toast。
- **下载**：`Blob` + `a[download]="main.c"` + `URL.revokeObjectURL`。
- **全屏**：`.code-wrap` 原地加 `.fullscreen` 类（`position:fixed; inset:0`），
  不复制 DOM——行号/高亮/滚动三同步、字号缩放全部保留；身体加锁滚动类；
  Esc 或再次点击退出。
- 空内容时复制/下载给出提示不执行。

## 用户故事

- 作为用户，生成骨架后点「复制」即可粘贴去 IDE / 下一个 AI，不用手动全选。
- 作为用户，点「下载」得到 `main.c` 文件，不用去输出目录找。
- 作为用户，窄屏或长代码时点「全屏」，编辑区占满视口，行号对齐不错位。

## 实现决策

1. 悬浮工具条按钮走文字（复制/下载/全屏/退出全屏），不加 data-ico 图标
   （动态按钮路线，与 ov-fill/ov-generate 一致）。
2. 全屏 = 同一 DOM 原地加类（不复制三明治），滚动/高亮/缩放零改动零回归。
3. 纯函数 `maincContentEmpty(value)`（空内容判断）与
   `maincFullscreenLabel(active)`（按钮文案）抽出供 tests/js 抽取测试。
4. 只改 index.html + 新增 tests/js/mainc-tools.test.mjs，无后端改动。

## 测试决策

- tests/js/mainc-tools.test.mjs（括号配平抽取范式）：
  空/空白/非空内容判空；全屏按钮文案切换。
- headless 冒烟：三按钮点击后 DOM 状态（复制走剪贴板 API 在无权限探针下
  断言状态文案）；全屏类切换 + Esc 退出；截图目检。

## 范围外

- main.c 语法补全 / 格式化 / 高亮增强（已有高亮层）。
- 骨架自动刷新联动（已有 markStepDone(8)）。
- 多文件编辑（工程内其它 .c 文件）。
