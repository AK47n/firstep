# 工单 01：空编辑器行号「1」与占位文字重叠

- Status: resolved
- 依赖：无

## 现象（用户报告）

第 8 步「main.c 骨架」卡片，未生成骨架时 textarea 的占位文字
「点击「生成骨架」后这里会出现 main.c 内容，可手动编辑...」与左侧行号列的「1」视觉重叠，
用户描述为「main.c 内容和 1 重复」。

## 根因

`src/contest_generator/static/index.html` 的 `.code-wrap` 编辑器三层布局（行号列 / 高亮层 /
textarea，约 695-712 行）：

- `.code-wrap textarea, .code-wrap .hl-layer` 共用 `padding: 12px`；
- `.hl-layer`（代码显示层）`position: absolute; left: 44px`（+padding 12 = 内容从 56px 起）；
- `.line-nums`（行号列）绝对定位占 `left: 0; width: 44px`（x 288-332，行号右对齐约 x≈317）；
- textarea 全宽（无左 padding 补偿），`padding: 12px` → 内容/占位从 x≈300 起 ——
  与行号列区域（288-332）重叠：空状态时行号「1」（x≈317）叠在占位文字首字上。

附带：textarea 文本坐标（x≈300）与高亮层代码坐标（x≈344）长期错位 44px（光标/文本透明层
与高亮层未对齐），一并修正。

## 方案

`.code-wrap textarea` 增加 `padding-left: 56px`（44 行号 + 12 内边距）：
- 占位文字/光标从 x≈344 起，与高亮层代码对齐，且完全避开行号列（右边界 332）；
- 行号「1」与占位文字不再重叠。

## 验证

DOM 探针（headless CDP）：textarea computedStyle padding-left = 56px；文本内容起点
（x = textarea.x + 56 ≈ 344）> 行号列右边界（x ≈ 332）。

## 影响面

CSS 一处；仅 main.c 编辑器（`.code-wrap` 仅此一处使用）。
