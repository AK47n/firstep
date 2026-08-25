# UI 细节打磨 D 系列：动效统一 / 状态色三处统一 / 修复·修订卡内分组

## 问题陈述

生成页三处步骤状态视觉（左侧 step-nav / 顶部总览 chips / 卡片标题徽章）中，done/current 已统一（绿/青渐变 + 同款底色），但 **warn 态只在 chips 与徽章有，step-nav 没有**——第 6/7 步有警告时导航不告警；且 step-nav 的 done 无容器底色，与另两处（ok-dim 底色）不同构。动效时长散落（.15s/.2s/.25s/.3s/.4s 混用，无统一令牌）。第 10 修复中心与第 11 修订深化卡信息密集，h3 分组无视觉层次。

## 方案

### D1 动效令牌化（保守收敛）
- `:root` 定义 `--dur-fast: 150ms / --dur-base: 200ms / --dur-slow: 300ms / --ease-ui: cubic-bezier(.25, .1, .25, 1)`。
- 替换主要 UI 过渡：tab nav（.2s）、按钮（.15s）、卡片（.2s）、折叠图标（.25s）、状态组件三处（.2s/.25s）、toast in/out（.25s/.3s）、step-nav（.25s）。
- 保留特色动画：btn-breathe（呼吸）、celebrate（庆祝）、ovFillPulse（补齐高亮）、prog-bar 进度、brand-blink。
- 为徽章补 `transition: color/transform` 轻微动效。

### D2 状态色三处统一
- step-nav 补 `.warn` 态（黄 dot + warn-dim 底色 + 黄 label），与 ov-chip.warn 同构；`refreshGenOverview` 在 chips 循环里同步导航 dot 的 warn 类（done/current 仍由既有 markStep* 路径维护，避免冲突）。
- step-nav `.done` 补容器底色（ok-dim + 绿边框），与 chips/徽章 done 完全同构。
- 三处状态判定继续同源（stepDoneSet + genOverviewWarn），不新增状态源。

### D3 修复/修订卡内分组
- 定义 `.card-group`（分组容器：panel-2 底 + 边框 + 圆角 + 内边距）与 `.card-group-title`（11px muted uppercase 小标题 + 分隔）。
- 卡 10：把「编译输出（自动采集）」「手动模式（无工具链回退）」两个 h3 段包成 card-group；主操作区（按钮行 + 状态）不动。
- 卡 11：「上下文入口」（入口 1 当前会话 + 入口 2 历史目录）合成一个 group；已加载上下文 / 影响分析 / 确认并执行 三个 box 加 .card-group（内部 h3 换 .card-group-title）。
- JS 零依赖（只改 class/标签，id 全保留；box 的 hidden 切换不受影响）。

## 用户故事

- 第 6/7 步有平台警告时，左侧导航对应步骤也亮黄 ⚠，与顶部 chips、卡片徽章一致。
- 鼠标划过按钮/卡片/导航的动效节奏统一，不再有快有慢。
- 修复中心与修订深化内容按组分区，一眼看清「自动修复 / 编译输出 / 手动模式」「入口 / 上下文 / 分析 / 执行」。

## 实现决策

1. D1 只做「时长/缓动令牌化 + 采样替换」，不动动画内容本身（呼吸/庆祝等特色保留）——避免视觉回归，快速交付。
2. D2 导航 dot 的 warn 由 refreshGenOverview 单向维护（每次 scroll/sync 重算），markStepDone/Undone 不动 warn——两者互不覆盖。
3. D3 只改 HTML class 与 h3 标签 + 新增一段 CSS；不新增/更改任何 id 或 JS 选择器（JS 引用 h3 的地方先 grep 确认）。

## 测试决策

- 无新纯函数：回归 node --test tests/js/*.test.mjs + headless 截图目检（导航 warn 态 / 分组视觉）。
- 语法检查（new Function 两块 script 解析）。

## 范围外

- 动效内容的重新设计（时长曲线大改）、庆祝/呼吸动画的推翻。
- 改 JS 对状态源的重构（三处仍共用 stepDoneSet + genOverviewWarn）。
- 其它页面（模块库/设置等）的分组改造（本轮只做生成页 10/11 卡）。
