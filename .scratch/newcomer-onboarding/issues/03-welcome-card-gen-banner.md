# 03 — 首次欢迎卡（生成页）+ gen-banner 行动化

**What to build:** 生成页顶部新增**首次欢迎卡**（一句话说明 + 三步走 + 两个行动按钮 + 「不再显示」），并给 **gen-banner（未配置 API key 横幅）加「去设置」按钮**，让「打开即知第一步做什么」并且**一键就能做**。

**Status:** pending（Blocked by 无 — 纯前端，可与 01/02 并行）

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
