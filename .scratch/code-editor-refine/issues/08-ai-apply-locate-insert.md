# 08 — AI diff 应用后跳转 + 「插入到光标/选区」

**要做什么：** 两件事：(a) AI diff 应用成功后自动跳转到首处改动行（目标文件已打开则激活+定位，未打开则打开后定位——复用 editJumpToFile）；(b) AI 回复代码块新增「插入到光标/选区」按钮：取活动标签光标/选区，将代码块插入（无选区）或替换（有选区），写入编辑缓冲（脏、进入撤销栈），不自动落盘，用户 Ctrl+S 走既有保存冲突/写盘守卫。零后端改动。

**被谁阻塞：** 无（与 07 独立；若 07 先行，按钮浮层复用其样式）。

**Type:** task
**Status:** claimed

## 实现要点

- (a) previewDiff 确认应用成功分支后，从 diff 首 hunk 解析首行号 → 目标文件定位；打开路径复用 openCodeDir/openEditorFile 语义。
- (b) 新 fx 纯件 insertAtPosition(content, text, {start, end}) 返回新内容与光标位（node 单测：插入/替换/空选区/边界）；识别 assistant 消息首个 ```code``` fence 块（无 fence 则整段）；按钮放消息工具条。
- 插入后 toast「已插入，Ctrl+S 保存」；多代码块时仅第一块并提示。

## 验收 checklist

- [ ] AI diff 应用后正确跳转首 hunk 文件与行（CDP 断言 active file + 行号）。
- [ ] 选中一段 → 插入替换选区；无选区 → 插入光标处；插入后脏标志、Ctrl+S 正常落盘；409 冲突路径不回归。
- [ ] 多代码块仅插第一块并提示；无标点/中文内容插入正常。
- [ ] node 单测 insertAtPosition；CDP 冒烟 smoke-08。

(End of file - total 21 lines)
</content>