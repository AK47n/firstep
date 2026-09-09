# 03 — 设置页未配置横幅定位（去设置/去填写 → 展开 AI API 卡并聚焦）

**要做什么：** 设置页「尚未配置」横幅在「应用设置」卡内，但 key 输入框在下方可折叠的「AI API」卡——横幅与入口断链。修复：生成页 gen-banner「去设置」与设置页 settings-banner（改为带「去填写」按钮）走同一条路径：展开 AI API 卡 → 切到设置页 → 聚焦 key 输入框。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实现记录：** ui/nav-jump.js 新增 gotoSettingsKey（先 expandSettingsCollapse("llm-api")
再 gotoNavTab("settings","set-api-key")，无回边依赖）；welcome.js 三入口统一走
gotoSettingsKey（gen-banner / settings-banner 新按钮 / 欢迎卡 full 态）；index.html
settings-banner 加「去填写」按钮；CDP 冒烟 probe-t03.mjs 全 PASS（前置先折叠
AI API 卡验证展开+聚焦；探针启用 clearBrowserCache 防旧模块缓存）。

- [x] 新增共享跳转助手：先展开 AI API 卡（复用既有设置折叠展开原语），再切页签并聚焦 #set-api-key；卡已展开时无副作用
- [x] 生成页 gen-banner「去设置」按钮改用该助手（现状只切页签+聚焦，折叠时无效）
- [x] 设置页 settings-banner 文案改为带「去填写」按钮，点击走同一助手
- [x] AI API 卡被用户手动折叠过也能正确展开（与既有 expandSettingsCollapse 落盘行为一致）
- [x] 横幅在已配置时仍隐藏，行为不变


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
