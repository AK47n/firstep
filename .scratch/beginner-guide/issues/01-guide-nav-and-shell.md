# 01 — 导航「指南」组 + 教程页骨架

**要做什么：** 顶部导航出现第三组「指南」，内含「新手指引」入口；点击进入教程页——页面有标题、四个子页签按钮（准备 / 做题主线 / 编译与上板 / 交付与收尾）与四个占位面板。新用户打开 firstep 第一眼能看到「指南」入口。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] 顶部导航新增 `<div class="tab-group">`「指南」组（组标签 span，aria-hidden），内含 `<button data-tab="guide">` 文案「新手指引」，title 为中文且 ≥8 字；位置在「资料管理」组之后
- [x] 新增 `<section id="tab-guide" class="page">`：页标题 + 四子页签按钮条（`data-guide-tab`：prepare / build / compile / deliver）+ 四个面板容器（面板内为占位提示，02/03 填充）
- [x] 点击「新手指引」正确切换到教程页并隐藏其他页签；切回其他页签正常（复用通用 `nav button[data-tab]` 切换逻辑）
- [x] tests/js：`nav-tabs-guard.test.mjs` 更新——GROUPS 增第三组 `{ label: "指南", keys: ["guide"] }`、总数 9 键、组序断言（做题 → 资料管理 → 指南）、组标签非 button 无 data-tab、title 中文 ≥8 字
- [x] 样式就位：复用现有 `.tab` / `.btn` / `.card` / `var(--*)` 令牌，亮/暗主题下页面渲染正常
- [x] 全量 tests/js（node --test）与 pytest 无回归

### 评审记录（双轴，2026-08-30）

- **Standards**：硬违规 1 处——纯逻辑（子页签定义/面板 id 映射/方向键回绕）未落 fx 单源（CONTEXT.md 分层：fx/*.js 可测纯函数单源，ui 只做 DOM 胶水）。**已整改**：新建 `fx/guide.js`（GUIDE_TABS / guidePanelFor / guideTabNext + window 桥），ui/guide.js 改为 import；补 `tests/js/guide.test.mjs`（纯函数 3 项 + index.html 静态契约守卫：按钮/面板/顺序与 GUIDE_TABS 一一对应）+ fx-guard 登记。判断项：`.guide-tab` 与 `.revise-tab`/`.res-view-btn` 胶囊样式三处近似（仓库既有先例，本工单抽出共享类会牵动既有两处，判为可接受、留待后续统一）；`initGuide()` 缩进列 0 的格式 nit 已修。
- **Spec**：无缺失；唯一实质问题 (c-1)——静态标记只有首按钮带 active，四按钮 tabindex 全 0，初始态未应用 roving tabindex/aria（与交互后状态不一致）。**已整改**：`initGuide()` 启动即 `applyActive()` 一次给全。键盘导航（Arrow/Home/End）属「简化版 revise-tabs 模式」的合理延伸，非范围蔓延。
- 验收：探针 `.scratch/beginner-guide/probe-01-nav.mjs` 26 项全 PASS（导航三组/进入教程页/默认 prepare/子页签点击切换 panel 互斥 + aria + roving/方向键焦点跟随/切回生成页/零 JS 错误）；tests/js 785 通过、pytest 2827 通过。
