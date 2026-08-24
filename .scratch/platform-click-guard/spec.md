# spec — 平台卡点击误触丢推荐勾选（platform-click-guard）

## 问题陈述

用户（2026-08-24 会话）报告「推荐好模块之后没有自动帮我选上」。排查结论：
自动勾选功能本身正常（CDP 实测真实载荷下勾选成功），**根因是平台卡点击处理**——
`renderPlatforms` 的卡片点击处理器（`src/contest_generator/static/index.html` 约 1624-1637 行）
无条件执行「换平台：下游全部重来」（`selectedSlugs = []; expanded = []; warnings = [];
pinBindings 等全清）。用户推荐完成后在第 2 步点过平台卡（含重复点击当前已选平台），
推荐刚勾选的模块被清空；推荐结果 chips 区不受影响（`rec-list` 不清），界面呈现
「有 chips 但第 6 步没选上 + 点展开报『请先选择至少一个模块』」。

## 方案

平台卡点击决策抽为纯函数 `platformClickAction(current, clicked)`：
- `current === clicked` → `"same"`：重复点击当前已选平台，**无操作**（纯误触防护，不丢选择）；
- `current === null` → `"first"`：首次选择平台（推荐前未选、推荐后选）——**保留既有选择**
  （含推荐勾选与 AI 猜的实例清单），只清 `expanded/warnings` 重渲染并按新平台 `runExpand()`
  做兼容检查；步骤 5（AI 推荐)保持已完成，不 unmark；
- 其它 → `"switch"`：真正切换平台，保留现有「下游全部重来」语义（unmark 5-12 + 清空
  选择/引脚/实例 + 重取板定义）。

## 用户故事

1. 作为用户，我希望推荐完成后重复点击已选平台卡不会丢失已勾选模块（防误触）。
2. 作为用户，我希望推荐前未选平台、推荐后再选平台时，推荐勾选的模块被保留并自动
   按所选平台展开。

## 验收标准

- [x] `platformClickAction` 纯函数 + `tests/js/platform-click-action.test.mjs` 单测绿
      (same / first / switch 三态)。
- [x] `renderPlatforms` 点击处理器按三态分支：same 直接 return；first 保留选择并
      runExpand；switch 保持原清空重来（unmark 5-12）。
- [x] 前端改动无需重启服务（静态文件即时生效）；测试：node --test tests/js 通过
      （127 pass）+ pytest 全量 2257 pass + CDP 端到端（真实服务 + 真实载荷）。
- [x] 提交信息中文。
