# 设置页信息架构（settings-infoarch）：折叠分组 + 默认收起次要项

## 问题陈述

设置页（`#tab-settings`）现有 9 张卡片从上到下线性堆叠，总高度约 3–4 屏：
工具链路径、本地模型、视觉通道、库目录这四张「可选/不常改」卡占据大量滚动位，
但用户配好后几乎不再打开；AI API 卡内「计费」区是一长串价格输入，首次配置只需
上方的「连接」段。整体没有折叠分组，每次进设置页都要滚过全部卡片才能到「保存设置」。

## 方案

以「整卡折叠 + 默认收起次要项 + 状态记忆」为主题重构设置页信息架构：

1. **整卡折叠**：8 张带 `h2` 的卡片（保存设置卡除外——它不是卡片内容而是行动点，
   始终可见）复用生成页已有的卡片折叠机制：`h2` 点击或右上角 `▾` 切换折叠，
   收起时只留标题行。
2. **默认收起四张次要卡**：工具链、本地模型（可选）、视觉通道（可选）、库目录。
3. **卡内小节折叠一处**：AI API 卡内的「计费」段（价格输入 + 官方价格参考）做成
   卡内可折叠小节，默认收起；AI API 卡本卡默认展开——「连接」段（base_url / 模型 /
   API key）是首次配置的核心，留在首屏。这是用户「整卡折叠」+「计费区默认收起」
   两个选择的合成落法。
4. **状态记忆**：每张卡/小节的折叠状态存 `localStorage`（`firstep.settingsCollapse.v1`），
   刷新后保持用户的选择；无记录时按默认集展开/收起。
5. **总开关**：设置页首部一条工具栏——muted 提示文案 + 「全部收起 / 全部展开」按钮，
   一键切换全部卡片与计费小节并落盘。
6. **可及性**：折叠按钮 `aria-label` 区分对象（卡片 vs 计费区），读屏可感知状态。

## 用户故事

1. 作为用户，我希望打开设置页只看到关键内容（应用设置 / 用量统计 / AI API 连接 /
   最近工作流 / 保存设置），次要卡缩成一行标题，以便首屏不滚动即可到达保存按钮。
2. 作为用户，我希望点击卡片标题或右上角 `▾` 即可展开/收起该卡，以便按需查看。
3. 作为用户，我希望默认收起的四张卡（工具链 / 本地模型 / 视觉通道 / 库目录）需要时
   一键展开，以便路径配置与可选能力配置不丢。
4. 作为用户，我希望 AI API 卡的「计费」段默认收起但连接段保持展开，以便首屏配置
   API key 时不被价格输入干扰；需要时点击「计费」标题展开。
5. 作为用户，我希望我手动调整过的折叠状态在刷新后保持，以便不必每次重新折叠。
6. 作为用户，我希望页首「全部收起 / 全部展开」能一键切换整个设置页，以便找某一项
   时不用逐卡点。
7. 作为读屏用户，我希望折叠按钮的 `aria-label` 明确说出目标（「折叠该卡片」/
   「展开该卡片」/「折叠计费区」/「展开计费区」），以便感知当前状态。

## 实现决策

- **范围契约**：只改 `src/contest_generator/static/index.html`（HTML + CSS + JS），
  后端与 Python 测试零改动（沿 ui-polish-11 先例）。不新建独立 css/js 文件。
- **折叠身份契约**：每张可折叠卡与计费小节带 `data-collapse-id`（即持久化键），
  取值固定：`app` / `usage` / `llm-api` / `libs` / `toolchain` / `local-llm` /
  `vision` / `recent-wf` / `ai-billing`。保存设置卡不带（天然不可折叠）。
- **存储契约**：`localStorage` 键 `firstep.settingsCollapse.v1`（沿用
  `firstep.draft.v1` / `firstep.usage.v1` 命名惯例），值为 JSON 对象
  `{ "<data-collapse-id>": boolean }`，boolean = collapsed；解析失败按 `{}`；
  **不进 config.json、不进后端**（与草稿/主题/用量同层）。
- **默认集单源**：JS 常量 `SETTINGS_DEFAULT_COLLAPSED`（Set）：
  `libs` / `toolchain` / `local-llm` / `vision` / `ai-billing`；
  `llm-api` 卡默认展开（存「连接」段首屏可见）。默认集只在 JS 一处，HTML 不带
  `collapsed` 类（页面脚本在 body 末尾同步执行，首帧前应用，无闪烁）。
- **卡片折叠复用**：`h2` 内追加 `button.card-collapse`（`▾`），`h2` 点击 toggle，
  沿用 `.card.collapsed > *:not(h2) { display:none !important }` 与
  `syncCollapseBtn`（title + aria-label 同步，ui-polish-4/01 + ui-polish-11/05
  既有机制）；折叠按钮弱化样式（默认半透明、hover 显现）沿用。
- **计费小节结构**：`<div class="settings-section settings-collapse"
  data-collapse-id="ai-billing">`，头部为
  `<button type="button" class="settings-collapse-head">计费 ▾</button>`，
  收起规则 `.settings-collapse.collapsed > :not(.settings-collapse-head)
  { display:none !important }`，`▾` 旋转复用 `.card.collapsed .card-collapse`
  的旋转样式思路（`.settings-collapse.collapsed .collapse-ico { transform:
  rotate(-90deg); }`）；包装块沿用 `.settings-section` 的虚线上边框 + muted
  小标题视觉，不改变内容结构（价格输入、官方价格参考 details、提示文案全部保留
  在体部，展开时与现状逐字节一致）。
- **总开关**：`#tab-settings` 首部新增 `.settings-toolbar`（flex 两端对齐）：
  muted 提示「点击卡片标题可折叠/展开，状态自动保存。」+
  `<button id="btn-settings-collapse-all">`；操作范围 = 全部 `[data-collapse-id]`
  元素（含 `ai-billing`）；操作后落盘并刷新自身标签。
- **新增纯函数**（供 `tests/js/*.test.mjs` 抽取，放在现有
  `collapseBtnLabel/syncCollapseBtn/collapseToggleAll` 块**之后**、不相邻插入，
  不破坏 card-collapse.test.mjs 的抽取正则）：
  - `parseSettingsCollapse(raw)` → 对象，JSON 解析失败/非对象回 `{}`；
  - `settingsDefaultCollapsed(id)` → `SETTINGS_DEFAULT_COLLAPSED.has(id)`；
  - `effectiveCollapsed(id, stored)` → stored 有该 id 取 stored 值，否则默认集；
  - `settingsMasterLabel(allCollapsed)` → `allCollapsed ? "全部展开" : "全部收起"`；
  - `sectionCollapseLabel(collapsed)` → `collapsed ? "展开计费区" : "折叠计费区"`；
  - `applySettingsCollapseState(elm, collapsed)` → 设置 `collapsed` 类 + 同步对应
    按钮的 title/aria-label（卡片走 `syncCollapseBtn`，计费小节走
    `sectionCollapseLabel`），可测；
  - DOM 装配 `initSettingsCollapse()`：读盘 → 逐元素应用默认/存储状态 →
    绑 h2/按钮点击 → 绑总开关（含每次 toggle 后重算总开关标签）；
    `saveSettingsCollapse(state)` 写盘（try/catch 忽略，沿主题/用量先例）。
- **重算口径**：总开关标签在每次折叠状态变化后重算——`allCollapsed` =
  全部 `[data-collapse-id]` 元素都处于折叠；不依赖按钮自身 class。

## 测试决策

- 沿用既有测试缝 `tests/js/*.test.mjs`（`node --test`，正则从 index.html 抽取
  JS 纯函数），**不新增 seams**（用户已确认范围只动前端）。
- 新增 `tests/js/settings-collapse.test.mjs`：
  - 抽取 `parseSettingsCollapse` / `settingsDefaultCollapsed` / `effectiveCollapsed` /
    `settingsMasterLabel` / `sectionCollapseLabel` / `applySettingsCollapseState`
    六函数，断言：默认集成员与 `llm-api` 不在默认集；stored 覆盖默认（含
    `false` 显式展开）；stored 缺字段回落默认；解析容忍垃圾输入；总开关标签
    双向；计费区标签双向；`applySettingsCollapseState` 对卡片假件（复用
    card-collapse.test.mjs 的 fakeCard 风格）与计费小节假件分别写对 class 与
    aria-label。
  - 存储键字符串常量抽测：`"firstep.settingsCollapse.v1"` 出现在 index.html。
- 回归：`node --test tests/js/*.test.mjs` 全绿（尤其 card-collapse.test.mjs 抽取
  正则不被新函数块破坏）；CDP 截图（.scratch/ui-decision/shot-all.ps1 先例）
  设置页亮/暗 1440px + 1000px 窄屏目检无布局回归。

## 范围外

- 不动生成页折叠机制与语义（`CARD_COLLAPSE_SELECTOR` / `collapseToggleAll` /
  收起已完成按钮保持原样）。
- 不做卡内小节折叠的通用化（仅「计费」一例）；不重构设置页为分栏/页签式。
- 不改任何设置项内容、后端保存逻辑、输入框 id 与行为。
- 不做设置页内锚点导航 / 粘性目录。
- 不调节默认收起集以外的卡片默认状态（应用设置 / 用量统计 / 最近工作流默认展开）。

## 补充说明

- 用户澄清结论（原文选择）：折叠粒度 = 整卡折叠；默认收起 = 工具链 / 本地模型 /
  视觉通道 / 库目录 / AI API 计费区；状态持久化 = localStorage 记住；加「全部
  展开/收起」总开关；范围 = 只改 index.html。「AI API 计费区」与「整卡折叠」
  的粒度冲突按上文合成：AI API 卡默认展开 + 计费段卡内折叠（两者都保留）。
- 折叠状态按 id 存取，未来设置页新增卡/小节只需加 `data-collapse-id` 与默认集
  条目，无需改存储形状。
- 「最近 LLM 工作流」卡默认展开：它是排障信息卡，且卡本身有下拉/复选框控件
  与刷新按钮，收起会隐藏可操作项——用户未勾选其默认收起，维持展开。
