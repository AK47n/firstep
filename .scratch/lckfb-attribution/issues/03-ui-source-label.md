# 03 — UI 模块详情：来源链接标签语义化

**要做什么：** 模块详情弹窗中，source_url 为 wiki 页面的模块显示「来源（立创 wiki）」标签，
其余（淘宝等购买链接）维持「购买链接」；用户打开链接前即知链接性质。

**被谁阻塞：** 01（判据单源，JS 侧镜像同构）。

**状态：** resolved

- [x] `fx/module.js`：来源链接渲染按 URL 分支标签文案（wiki → 来源（立创 wiki），否则购买链接）
- [x] 扩充 JS 测试（module-info-dialog.test.mjs）：wiki URL → 标签断言；淘宝 URL → 购买链接断言
- [x] `tests/js` 相关测试通过（12/12）
