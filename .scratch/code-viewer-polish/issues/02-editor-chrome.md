# 工单 02：编辑区 IDE 化——当前行高亮 + 行号联动

## 要做什么

1. 当前行（用户选择「要」）：#code-viewer 容器点击委托
   `closest('.code-pre-line')` → 清除旧 .active、给目标行加 .active
   （持续淡色背景）；renderFindPanel / 搜索结果跳转时同步。
2. jumpToLine 增加 active 移动：目标 gutter 行 + 内容行都设 .active
   （flash 1.2s 瞬态保留，结束后 active 继续存在）——大纲 / 搜索 / 文件内
   命中跳行共用。
3. 行号联动 CSS：`.code-gutter-line.active`（加粗 + accent 色）；
   `.code-pre-line.active`（`rgba(var(--accent-rgb), .07)` 淡背景，双主题
   自适应）；flash 保持 `--accent-dim(.12)` 略强于 active。
   **不新造颜色值**（:root 允许 rgba(var(--accent-rgb), a) 变体）。
4. gutter 宽度随最大行号位数自适应（css min-width 或字符计数，≥3 位
   加宽），行号与代码行高对齐不变（1.55 / --mono 不动）。

## 被谁阻塞

工单 01（树图标与标签先落地）。

## 状态

resolved

## 验收清单

- [x] 点击任意代码行 → 该行 .code-pre-line.active + 同索引
      .code-gutter-line.active（同 data-code-line 键），之前 active 移走。
- [x] 大纲 / 搜索结果 / 文件内命中跳行 → active 移动到目标行且 flash
      仍生效。
- [x] 深浅主题下 active 背景均协调（rgba accent 变体）且不破既有
      flash 观感。
- [x] gutter 行号 3 位以上不溢出（min-width 3ch 生效）。
- [x] CDP 冒烟扩展：点击第 3 行 → active 在第 3 行（内容 + gutter）；
      大纲跳行 → active 移走（17/17 全绿）。
- [x] tests/js 全量（933）绿 + pytest 全量（2989）绿。
