# Spec：字号体系美化（ui-polish-7）

> 用户反馈：格式（布局）已满意，下一步优化各种字体大小。目标：建立清晰的字号阶梯，提升标题对比，统一正文层级。

## 问题陈述

当前字号阶梯 `18 → 15 → 14 → 13 → 12 → 11 → 10`：
- 主流「正文级」元素（label、textarea、错误/横幅、推荐理由、警告框、引脚说明、决策行）大量用 **13px**，比 body 基础 14px 还小，整体偏小偏挤；
- 卡片标题 15px 与正文 14px 对比仅 1px，层级不明显；
- textarea 13px 与 input（继承 14px）不一致，main.c 代码区偏小。

## 方案

**新阶梯**：`20（品牌）→ 16（卡片标题）→ 14（正文/控件/表单）→ 13（密集数据）→ 12（辅助）→ 11（徽标）`

| 元素 | 现状 | 调整 |
|---|---|---|
| header h1（品牌） | 18px | 20px |
| .card h2（卡片标题） | 15px | 16px |
| label | 13px | 14px（与输入框对齐） |
| textarea（含 main.c 代码区） | 13px | 14px（与 input 一致） |
| .error / .banner | 13px | 14px（重要反馈） |
| .item .reason（推荐理由） | 13px | 14px |
| .warn-box | 13px | 14px |
| .pin-intro（引脚说明） | 13px | 14px |
| .decision 决策行 | 13px | 14px |
| 表格 / 引脚密集区 / 进度区 / chips / ref-pick / fix 列表 / 徽标 / .muted / stepper | 保持 | 数据密集区不动，避免变挤 |

## 实现决策

- 只改 `src/contest_generator/static/index.html` 的 CSS font-size 单值；零 JS、零测试缝改动；
- 不引入 CSS 变量字号（保持简单，直接改值）；
- 密集数据区（table 13px、pin 12px、prog 12px、chip 13px、fix 13px、ref-pick 12/13px、badge 11px、muted 12px）全部不动。

## 验证

- CDP 截图改前/改后对比（生成页：题面输入框、main.c、模块清单、决策行；设置页）；
- 断言关键元素计算字号：h2=16px、label=14px、textarea=14px、.error=14px；
- js 84/84 + 契约 50/50 全绿。

## 范围外

- 不动行高/字重体系（line-height 1.6 已有）；不做响应式字号（clamp）；
- 不改数据密集区字号（若用户后续觉得表格小再单独调）。
