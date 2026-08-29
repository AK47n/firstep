# 01 — 顶部导航两段分组：组标签 + 归组 + 分隔样式 + 结构守卫

**要做什么：** 打开页面，顶部导航从「8 个按钮平铺」变为「做题 | 资料管理」两段分组：组标签是弱化小字、不可点击；生成/赛题库/设置归「做题」，模块库/参考文件库/PDF 资料库/母版/更新记录归「资料管理」；两段间有视觉分隔；8 个按钮的点击切换、激活态、分发加载、标签会话记忆行为完全不变。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved（2026-08-30 实施完成，评审记录见文末）

- [ ] `index.html` 顶部 `<nav>` 内两组容器：`<div class="tab-group" role="group" aria-label="做题">` 与 `<div class="tab-group" role="group" aria-label="资料管理">`，各含组标签 `<span class="tab-group-label" aria-hidden="true">`（文本「做题」「资料管理」，无 `data-tab`、不可点击）。
- [ ] 归组正确：做题组 = generate / topic / settings；资料管理组 = library / reference / pdf / master / changelog；组内顺序 = 现状顺序；8 个 `<button data-tab>` 原样保留（含 `class="active"` 的 generate）。
- [ ] 样式：组标签 `--muted` 小字（非按钮外观）、组内按钮间距沿用现状、第二组左侧 `--border` 细分隔线（`:nth` 或 `::before`），窄屏可换行/横向滚动不破。
- [ ] 既有 `nav button[data-tab]` 绑定选择器字符串与 tab 分发器（loadLibrary 等）零改动；`tab-nav-guard.test.mjs` 继续绿。
- [ ] 新增 `tests/js/nav-tabs-guard.test.mjs`（node:test，`readFileSync` 读 `index.html`，仿 `tab-nav-guard.test.mjs`）：① `.tab-group-label` 恰好 2 个且文本 = 做题/资料管理；② `nav button[data-tab]` 恰好 8 个、key 集合精确 = {generate, library, reference, pdf, topic, master, changelog, settings}；③ 按 `.tab-group` 容器锚定组归属（3 + 5）；④ `.tab-group-label` 无 `data-tab`。
- [ ] 手工验收：8 tab 点击切换正常、组标签点击无反应、进度条显隐与既有行为一致、刷新后标签会话记忆恢复原 tab。

## 实施记录（2026-08-30）

- `src/contest_generator/static/index.html`：nav 内两段分组——`<div class="tab-group" role="group" aria-label="做题|资料管理">` 各含 `<span class="tab-group-label" aria-hidden="true">`；做题组 = generate(active)/topic/settings，资料管理组 = library/reference/pdf/master/changelog（组内顺序 = 现状相对顺序）；CSS 新增 `header > nav { flex-wrap: wrap }`、`.tab-group`、`.tab-group + .tab-group`（`--border` 细则线 + 左距）、`.tab-group-label`（`--muted` 小字）；`nav button[data-tab]` 绑定选择器与 tab 分发器零改动。
- `tests/js/nav-tabs-guard.test.mjs`（新增，node:test 读 index.html）：5 用例——①组容器/组标签各恰好一次 ②8 键各恰好一次且总数 8 ③组归属与组内顺序 deepEqual ④组标签 span 非 button 且无 data-tab ⑤组先后顺序（做题在资料管理前）。
- 测试：`node --test "tests/js/**/*.test.mjs"` **756 pass / 0 fail**（tab-nav-guard 继续绿）；无运行期 JS 改动，无手工验收回归面。

## 评审记录（双轴，2026-08-30；整改已随工单落地）

- **Standards 轴**：无硬违规（分层/语言/中文注释/CSS 变量/防回归均过）。判断项 3 条：①守卫 `headerNavHTML()` 裸 `<nav>` 正则未锚定——头 nav 一旦加属性会静默改指别的 nav → **修复**：锚定 `<header>…<nav>`；②测试 4 按 `</span>` 位置切片取标签 → **修复**：正则抽 `<span class="tab-group-label">` 元素后判定；③`headerNavHTML`/`groupInnerHTML` 形状轻微重复 → **接受**（职责不同，微小）。
- **Spec 轴**：无实质缺失、无做错项；2 项裁定：
  - 范围蔓延：`@media (max-width:900px) { .tab-group-label { display:none } }` 不在 spec（spec 只要求窄屏换行/滚动不破），且窄屏恰恰是新手最需要组标签识别分组 → **修复**：删除该规则。
  - 弱覆盖：守卫只锁组内顺序、未锁两组先后 → **修复**：补用例 ⑤（做题在资料管理前）。
- 次要：用例 ④ 额外断言组标签非 `<button>`（超出 spec 「无 data-tab」字面）→ 接受（防分组拆解，与意图一致）。
