# 06 — 前端：设置页资料库区 + 软件更新器式选择弹窗 + 进度

**要做什么：** 用户像用软件更新器一样：设置页看到资料库版本 → 点检查 → 弹窗展示更新内容（版本 / 批次 / 变更数 / 大小）→ 勾选子集或一键全选 → 开始下载见总进度（速度 / 剩余时间）→ 完成或失败得到明确中文结果；无基线 / 空间不足有指引。

**被谁阻塞：** 03/04/05

**状态：** resolved

- [x] 设置页「软件更新」卡下新增「资料库更新」区：当前资料库版本行（吃 check 响应或本地清单 version）+「检查更新」按钮 + 结果区
- [x] 发现新版本 → 弹窗（复用 `.ref-files-overlay` 模态骨架，新容器样式）：版本头 + 批次勾选列表（名称 / 新增·修改·删除文件数 / 增量大小）+ 全选 / 反选 + 底部已选大小与「开始下载 / 稍后」
- [x] 下载中弹窗改进度视图：总进度条（已下 / 总量）+ 当前卷名 + 速度 + 剩余时间 +「后台继续（关闭弹窗）/ 取消」
- [x] 完成：中文结果（更新 N 个批次，资料库已到 vX）；失败 / 取消：中文 + 可重试（已完成卷跳过）；`baseline_missing`：明确指引（完整包或联系发布者）；空间不足：提示换磁盘
- [x] 纯函数 `fx/materials-update.js`（勾选聚合 / 进度 HTML / 状态文案 / XSS 转义）+ 薄胶水 `ui/materials-update.js`，结构与 auto-update（fx/update.js + ui/update.js）同构
- [x] 测试：`tests/js/` node 纯函数测试（全选聚合 / 部分勾选 / 总大小 / 进度格式化 / 状态文案），fx-guard 登记

## Answer

`fx/materials-update.js`（materialsCheckCardHTML / aggregateSelection / materialsPickHTML / materialsPickFooterHTML / materialsProgressHTML / materialsStateText，全部 esc 转义）+ `ui/materials-update.js`（initMaterialsUpdate：检查按钮 → 结果区；「选择下载」弹窗 = overlayConfirmHTML 骨架 + 批次勾选 + 全选/反选 + 已选大小；「全部下载」= 全选直接 apply；apply 后 2s 轮询 status → 进度视图 + 取消按钮；done/failed/cancelled/partial 四终态 toast）。index.html：设置页新卡 + .materials-* 样式 + 导入/初始化接线；fx-guard 登记 6 个新纯函数。测试 tests/js/materials-update.test.mjs 10 项全绿；真实浏览器冒烟（8123 + Chrome CDP）：设置页卡渲染 → 检查 → baseline-missing 中文指引显示、无 JS 异常（截图 .scratch/materials-update/mats-settings.png）。
