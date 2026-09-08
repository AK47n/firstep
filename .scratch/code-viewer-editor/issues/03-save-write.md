# 03 — 保存写盘链路：Ctrl+S / 保存按钮 → POST /api/code/save

**要做什么：** 把编辑状态接到磁盘：Ctrl/Cmd+S（仅 tab-code 活动时截获）与
顶栏「保存」按钮（仅活动脏 tab 可见/可用）→ `POST /api/code/save`
（{dir, path, content, base_mtime_ns}，后端 = 工单 01）→ 成功：toast
「已保存」、脏点清除、大纲刷新（save 响应内 outline）、树中该文件大小
更新重渲染；失败：中文 toast（400 业务 / 网络可重试，memo 口径不变）。
只读边界：非 UTF-8 文件（utf8=false）禁止保存（点击 → 中文 toast 说明
「文件不是 UTF-8 编码，为免损坏请用外部编辑器保存」）；二进制 />1MB
拒绝面由后端兜底（前端打开时已受限）。409 冲突本票只做「显示中文错误
提示」占位，完整冲突模态 = 工单 04。

**被谁阻塞：** 01（后端端点）、02（编辑器/脏点）。

**状态：** resolved

**实现笔记：** saveActiveTab（in-flight 合并/按钮禁用「保存中…」/成功 4 步：savedContent+mtime_ns（字符串响应）+outline 直用+toast ok/失败 400→toastError、409→中文 toast 占位、脏点保留可重试）；Ctrl+S 全局（tab-code 活动才截获）+ 顶栏保存按钮（isTabSavable 单源判定可见性——fx 纯函数，评审整改：跨 codeview/codeeditor 保存判据消重）；onFileSaved 回调链（树大小刷新 + 大纲显式重渲——renderOutline 无路径去重，onFileSaved 直调不受 onActiveTabChanged 的 lastOutlinePath 影响）。Spec 轴确认 base_mtime_ns 字符串回传、重复触发合并、只读拦截、409 占位全部合规；main.c→步骤 8 联动按拆分规划在工单 05（用户已拍板拆票）。测试：node 17 项 + smoke-03 11 项、smoke-02 20 项全过；全量 pytest 3044 绿。

- [ ] 保存触发：Ctrl/Cmd+S 全局监听（codeTabActive 才 preventDefault）+ 保存按钮；保存中按钮禁用 + 「保存中…」；450ms 内重复触发合并（防抖或 in-flight 判定）。
- [ ] 成功路径：toast('ok')、脏点清除、大纲刷新（响应的 outline 直用）、codeFiles 里 size_bytes 更新 + renderCodeTree、tab.savedContent/mtime_ns 更新。
- [ ] 失败路径：400 → toast('error', 中文)；网络/≥500 → 可重试（脏点保留）。
- [ ] 非 UTF-8 只读：保存尝试 → toast 中文说明；无脏点（02 已标只读）。
- [ ] 后端 409 在本票走「带 status 的错误 → toast 中文」占位（04 前不弹模态）。
- [ ] smoke-03：编辑 → Ctrl+S → 服务端断言文件内容已写盘 + 页面 toast/脏点清除/大纲刷新；pytest 与 node --test 全绿。
