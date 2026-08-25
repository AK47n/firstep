# 02 — AI API 卡内「计费」小节折叠

**要做什么：** AI API 卡（llm-api 卡默认展开）内的「计费」段（价格输入 + 官方价格参考 details + 提示文案）改成卡内可折叠小节：默认收起，点「计费 ▾」独立展开/收起；状态与卡片同库（`ai-billing` id）记忆，刷新保持；aria-label 用「展开计费区」/「折叠计费区」区分于卡片语义。展开时内容与现状逐字节一致。

**被谁阻塞：** 01（复用存储读写与 applySettingsCollapseState 纯函数）

**状态：** resolved

- [x] 计费段包进 `<div class="settings-section settings-collapse" data-collapse-id="ai-billing">`，头部为 `<button type="button" class="settings-collapse-head">计费 ▾</button>`
- [x] 默认收起（SETTINGS_DEFAULT_COLLAPSED 含 ai-billing）；点头部按钮/标题区切换，▾ 旋转指示
- [x] 收起规则 `.settings-collapse.collapsed > :not(.settings-collapse-head) { display:none !important }`，体部（价格输入三行 + price-reference details + muted 提示）展开时与现状一致
- [x] aria-label = sectionCollapseLabel：collapsed ? 「展开计费区」 : 「折叠计费区」，title 随状态同步
- [x] 状态与卡片同键 `firstep.settingsCollapse.v1` 持久化，刷新保持
- [x] `node --test tests/js/*.test.mjs` 全绿：settings-collapse.test.mjs 增加 sectionCollapseLabel 双向断言 + 计费小节假件 applySettingsCollapseState 断言
- [x] CDP 截图：AI API 卡展开、计费段默认收起；展开后内容与改动前一致

## 实施记录（2026-xx）

**CDP 验证暴露两个真 bug（均已修复并补回归测试）：**

1. **祖先卡片误判为计费小节（根治）**：`applySettingsCollapseState` / `initSettingsCollapse` 原用 `elm.querySelector(".settings-collapse-head")` 判别小节分支——`querySelector` 查整棵子树，而 `llm-api` 卡（`.card[data-collapse-id="llm-api"]`）是 `ai-billing` wrapper 的祖先，后代查询命中 wrapper 的 head → 卡片被误入 head 分支：跳过该卡 ▾ 按钮创建（continue）、给同一 head 按钮再绑一个闭包 c=卡片/id=llm-api 的点击 handler → 点击「计费」头会连动收起整个 AI API 卡并写盘 `"llm-api":true`（CDP stored 输出 + 展开态截图 AI API 卡被收起即此 bug）。**修复**：判别改为看元素自身 `elm.classList.contains("settings-collapse")`（wrapper 带此类，卡片不带），仅在确认为小节后再查 head；新增回归测试「卡片内嵌计费小节 head 后代仍走卡片分支」（tests/js/settings-collapse.test.mjs 的 fakeCardEl 增 withNestedHead 参数 + classList.contains 假件方法）。
2. **初始按钮 aria 未同步（01 重构回声）**：重构把 `applySettingsCollapseState(c, collapsed)` 放在 `h2.appendChild(btn)` 之前，而卡片分支经 `querySelector(".card-collapse")` 找按钮——未挂载时查不到 → 初始 title/aria-label 为空（此前 CDP 只在点击后断言 aria，未捕获）。**修复**：先 `h2.appendChild(btn)` 再应用状态。

**测试**：node --test 175 例全绿（新增 1 例回归）；check-01/check-02 CDP 复验全过（check-02 增补断言：初始 head aria=「展开计费区」、llm-api 卡 ▾ 按钮存在且默认展开、点击计费头不联动卡片）。

## 复审记录（2026-xx，双轴 review 对 8faf683..工作区 diff）

**Standards 轴**：无硬性违规；三条建议已全部落实：
- 注释工单引用统一为完整 slug「（工单 settings-infoarch/02）」；
- 设区判别抽 `settingsSectionHead(elm)`（applySettingsCollapseState 与 initSettingsCollapse 共用），消除复制；
- 「toggle→state→apply→save→syncMasterLabel」五连收敛为 `toggleSettingsCollapse(c)`（计费头/▾/标题三处共用）。
- 判断项「`.settings-collapse-body` 体部未重缩进」：随 Spec 轴一并移除该容器，不再成立。

**Spec 轴**：7 条验收全落地、两 bug 修复判据正确、无实质缺失；两处越界判断已处理：
- 移除多余 `<div class="settings-collapse-body">`（spec「不改变内容结构」未要求；收起规则 `> :not(.settings-collapse-head)` 直接作用于 wrapper 内容孩子）；
- 删除未要求装饰 CSS：`.settings-collapse { position:relative }`（无用）、`.collapse-ico { font-size:10px }`；保留 head `:hover{color:var(--accent)}` 与 `transition: transform .25s ease`——沿 `.card-collapse` 既有惯例（ui-polish-11/05 transition 含 transform + hover accent）。
- head `title`「展开/折叠」维持（spec 仅要求 aria-label 用 sectionCollapseLabel、title 随状态同步；与卡片 syncCollapseBtn 语义一致）。

**最终验证**：重构+收紧后 node --test 175 例全绿；check-01/check-02 CDP 全过（含初始 aria、按钮存在、卡不联动、收起 details 隐藏）。
