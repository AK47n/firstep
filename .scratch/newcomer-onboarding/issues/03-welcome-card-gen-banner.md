# 03 — 首次欢迎卡（生成页）+ gen-banner 行动化

**What to build:** 生成页顶部新增**首次欢迎卡**（一句话说明 + 三步走 + 两个行动按钮 + 「不再显示」），并给 **gen-banner（未配置 API key 横幅）加「去设置」按钮**，让「打开即知第一步做什么」并且**一键就能做**。

**Status:** resolved（2026-08-29 实施完成，评审记录见文末）

> 更正：spec 与工单初稿写「前端无 node 测试设施」——实为判断错误，仓库有
> tests/js/*.test.mjs（node:test）与 fx-guard 结构护栏，纯函数按先例直测。

## 决策记录（spec.md / clarify 2026-08-29，用户确认）

1. **欢迎卡 = 生成页顶部卡片（非浮层）**：放 `#generate-result` 之前、生成表单之上（首屏可见），不遮挡内容。
2. **localStorage 首见标记**：key `firstep.welcome-dismissed.v1`；未显示过 → 显示完整卡；点「不再显示」→ 写标记 → 隐藏；已标记 → 不再显示。**纯函数判定**：`welcomeMode(state) -> 'full' | 'compact' | 'hidden'`——输入 `{apiConfigured, hasDraft, dismissed}`，输出：dismissed → hidden；!apiConfigured → full；hasDraft → hidden；其余 → compact（一句话鼓励语，低打扰）。判定函数与渲染解耦（纯函数可读可测，无 node 测试设施则人工验收）。
3. **卡内容**：标题「欢迎使用电赛工程生成器」；一句话：贴赛题原文 → 自动生成双平台可编译工程；三步：① 右上「设置」填 DeepSeek API key ② 「一键补齐」+「检查环境」③ 粘贴赛题 → 生成。两按钮：「去配置 API key」= 切设置 tab 并聚焦 `#set-api-key`；「检查环境」= 切设置 tab 并触发 `#btn-env-check`（复用现有 env 体检逻辑，只跳转不重写）。
4. **gen-banner 加「去设置」按钮**：未配 key 时在 banner 内加按钮（跳转逻辑与欢迎卡按钮共用同一函数 `gotoSettings(tab, focusId?)`）。
5. **范围外**：不做首次引导浮层 / tour 步骤 / 四页签主次调整 / Y 系列其他项。
6. **验收**：前端无 node 测试设施（static/js 仅 package.json {"type":"module"}，无 scripts/test、无 *.test.js）→ 验收 = 人工 + node 语法检查（内联 JS `node --check` 沿用现有做法）。

## 实施

1. `static/js`（先确认 js 文件组织：app.js / index.html 内联？按现状就近）；新增 `welcomeMode` 纯函数 + 欢迎卡渲染 + dismiss 处理 + `gotoSettings` 复用函数。
2. `index.html`：欢迎卡 DOM（先 hidden，JS 按 welcomeMode 渲染）；gen-banner 加「去设置」按钮。
3. 语法检查：改完 `node --check`（沿用现有检查方式）。
4. 自查：首次（无 key）→ 完整卡；点不再显示 → 刷新不再出；配置 key 后（未 dismiss）→ compact；有草稿 → hidden。

## 验收标准

- [ ] 未配 key 首访：完整欢迎卡 + 三步清晰可见
- [ ] 「去配置 API key」：切到设置 tab 且输入框聚焦；「检查环境」：切设置 tab 且触发体检
- [ ] 「不再显示」持久（localStorage）；配置 key 后未点不再显示 → compact 卡；有草稿 → 不显示
- [ ] gen-banner 有「去设置」按钮且能跳
- [ ] node --check 通过

## 文件边界

- **改**：`src/contest_generator/static/index.html`、`src/contest_generator/static/js/*`（按现状就近）
- **不动**：后端 / 设置页逻辑（只跳转复用）/ 生成流程

## 实施记录（2026-08-29）

- fx/welcome.js（纯函数）：WELCOME_DISMISS_KEY = "firstep.welcome-dismissed.v1"；welcomeMode({apiConfigured, hasDraft, dismissed}) 四态单源；welcomeCardHTML(mode)（full 三步 + 三按钮 / compact 一句话 / hidden 空串）；window 桥导出。
- ui/welcome.js（胶水）：initWelcome 读 state.api_configured + draftLoad(localStorage) + dismissed → 渲染 #welcome-card；gotoKeyAction = 点 nav[data-tab=settings]（复用页签切换既有逻辑）+ 聚焦 #set-api-key——欢迎卡「去配置 API key」与 gen-banner「去设置」共用一个函数；env-check = 切设置页签 + 点 #btn-env-check；不再显示 = localStorage + 隐藏清空。
- index.html：`#welcome-card`（生成页顶部、gen-banner 之后）+ .welcome-card 样式（info 蓝系，同 banner 布局）+ host import 与 initWelcome() 调用（init() IIFE 内 restoreDraft 之后，state/草稿就绪）+ gen-banner 内嵌「去设置」按钮（#btn-banner-goto-settings）。
- 测试：tests/js/welcome.test.mjs 7 用例（四态判定 + 卡片文案/按钮 + key 常量）+ fx-guard.test.mjs DOMAINS 登记 welcome.js；全量 js 751 passed。
- 评审裁定（判断项不修）：bat 内探针/弹窗与 install.bat 重复、Popup 五行子例程化——批处理无模块系统且带参子例程引号不可靠，保持显式；_cjk_count 与 test_repo_language.py 重复定义——孤立测试文件可接受。
