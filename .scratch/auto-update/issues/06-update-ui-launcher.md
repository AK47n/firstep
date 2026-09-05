# 06 — 前端：设置页「软件更新」区 + 启动器「更新中」提示

**要做什么：** 用户在设置页看到当前版本、点「检查更新」得到结果卡（最新版本 / 大小 / 说明 + 一键更新按钮）、点「一键更新」看到进度与最终中文结果；更新期间双击启动器会得到「更新进行中」提示而不是拉起旧版。

**被谁阻塞：** 05（进度与结果来自状态轮询端点）

**状态：** resolved

- [x] 设置页「软件更新」区：当前版本行（吃 `/api/health` 的 version）+「检查更新」按钮 + 结果卡（版本 / 大小 / 说明 / 一键更新按钮）+ 成功 / 失败中文提示
- [x] 一键更新交互：点击 → 确认弹窗（说明将停服并自动重启，数据不丢）→ 进度显示（先「正在下载」再轮询 `/api/update/status`：applying 提示 / done 完成提示「已更新到 vX，浏览器将重新打开」/ failed 中文错误 + 备份位置）→ 服务重启瞬间轮询断网容忍 3 次后提示刷新
- [x] 无网 / 失败：中文错误 + 可再次「检查更新 / 一键更新」，页面不崩
- [x] 启动器（start-app.bat，GBK 编码保持）检测「更新中 / 待更新」标记：updating.lock → 弹窗「firstep 正在更新中，请稍候片刻再启动」；pending-update.json 残留 → 弹窗提示处理方式（重试 / 看 updater.log），均在端口探测之前
- [x] 复用前端既有组件风格与测试先例（纯函数 fx/update.js + ui/update.js 薄封装 + tests/js/update.test.mjs 7 项 + fx-guard 登记）

## Answer

设置页新增「软件更新」卡（index.html，重置记录卡之前）；纯函数 `fx/update.js`（updateCheckCardHTML / updateStatusHTML / updateStateText，XSS 转义）+ DOM 胶水 `ui/update.js`（initUpdatePanel：health 版本 + 检查更新 → 确认弹窗 → apply → 2s 轮询 status）。start-app.bat 顶部插入标记检测（Python GBK 写入；原文件本就是 `\r\r\n` 怪换行，保持原样只加标准 CRLF 新行）。测试：node 7 项 + fx-guard 61 项全绿。
