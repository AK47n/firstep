# 03 — 生成结果卡「复制输出路径」

**要做什么：** 生成完成结果卡「输出目录」行加「复制路径」按钮（生成成功才显示），点击复制目录到剪贴板 + toast。

**被谁阻塞：** 无。

**状态：** resolved

- [x] 结果卡输出目录行加 `#btn-copy-dir`（初始 hidden）
- [x] 生成成功后显示按钮；点击复制 `res-dir` 全文 + toast「已复制输出路径」
- [x] CDP 验证：模拟生成成功（generate-result 可见）后按钮真实渲染且在视口内；点击后 mock clipboard 捕获 `C:/tmp/demo-output`；toast 出现
- [x] 全量测试
