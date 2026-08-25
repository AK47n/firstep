# 02 — AI API 卡内「计费」小节折叠

**要做什么：** AI API 卡（llm-api 卡默认展开）内的「计费」段（价格输入 + 官方价格参考 details + 提示文案）改成卡内可折叠小节：默认收起，点「计费 ▾」独立展开/收起；状态与卡片同库（`ai-billing` id）记忆，刷新保持；aria-label 用「展开计费区」/「折叠计费区」区分于卡片语义。展开时内容与现状逐字节一致。

**被谁阻塞：** 01（复用存储读写与 applySettingsCollapseState 纯函数）

**状态：** ready-for-agent

- [ ] 计费段包进 `<div class="settings-section settings-collapse" data-collapse-id="ai-billing">`，头部为 `<button type="button" class="settings-collapse-head">计费 ▾</button>`
- [ ] 默认收起（SETTINGS_DEFAULT_COLLAPSED 含 ai-billing）；点头部按钮/标题区切换，▾ 旋转指示
- [ ] 收起规则 `.settings-collapse.collapsed > :not(.settings-collapse-head) { display:none !important }`，体部（价格输入三行 + price-reference details + muted 提示）展开时与现状一致
- [ ] aria-label = sectionCollapseLabel：collapsed ? 「展开计费区」 : 「折叠计费区」，title 随状态同步
- [ ] 状态与卡片同键 `firstep.settingsCollapse.v1` 持久化，刷新保持
- [ ] `node --test tests/js/*.test.mjs` 全绿：settings-collapse.test.mjs 增加 sectionCollapseLabel 双向断言 + 计费小节假件 applySettingsCollapseState 断言
- [ ] CDP 截图：AI API 卡展开、计费段默认收起；展开后内容与改动前一致
