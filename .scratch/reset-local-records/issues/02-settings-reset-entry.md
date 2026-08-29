# 02 — 设置页「重置本地记录」入口（确认弹窗 + 浏览器记录清理 + 结果汇总 + 移除临时运维页）

**要做什么：** 设置页新增「重置本地记录」卡片：点按钮 → 确认弹窗（列出清除清单，danger）→ 确认后（a）清空浏览器 localStorage 中全部题相关记录（任务自检勾选 `firstep.checklist.v1.*`、题面草稿 `firstep.draft.v1`、评分核对 `score-checklist:*`、购买决策 `firstep.buy-decisions.v1`），UI 偏好（theme/mainc.zoom/settingsCollapse.v1/usage.v1）与 API 配置保留；（b）调用 01 的 `POST /api/reset-records` 清服务端记录；（c）显示结果汇总（本地 n 项 / recent m 条 / 缓存 k 个）。同时删除临时运维页 `/clear-cache.html`（路由 + 文件），由本入口取代。

**被谁阻塞：** 01（后端重置端点）

**状态：** resolved

- [x] `fx/reset.js` 纯件：`RESETTABLE_KEY_PREFIXES` / `isResettableKey(key)` / `collectResettableKeys(keys)`（判定单源；不命中保留键；另导出精确键清单 `RESETTABLE_EXACT_KEYS`）
- [x] `index.html` 设置页新增卡片（「最近 LLM 工作流」与「保存设置」之间；标题/按钮/说明；`data-collapse-id="reset-records"` 默认展开）
- [x] `ui/settings.js` 胶水：按钮 → confirmModal（确认文案「清空本地记录」）→ 枚举 localStorage 清除计数 → apiPost → 结果行（部分成功：POST 失败显示本地已清 + 原因）
- [x] 删除 `static/clear-cache.html` 与 `webapp.py` `/clear-cache.html` 路由
- [x] tests/js/reset.test.mjs：四类键命中 + 保留键不命中 + collect 保序去重（btn-icons.test.mjs 同步注册 trash 图标）
- [x] 全量 pytest + tests/js 绿

**评审：** 规格轴（78c9096d）整改项已落实（data-collapse-id 补上、确认按钮文案按 spec 用户故事 2 归一为「清空本地记录」、spec 措辞同步）；标准轴（46240693）无硬违规。全量 pytest 2807+ / tests/js 667 绿。
