# 01 状态色三处统一（导航补 warn 态 + done 同构）（ui-detail）

Status: resolved

## 验收标准

- [ ] step-nav .step-dot 新增 `.warn` 态（黄 dot + warn-dim 底色 + 黄 label），与 ov-chip.warn 同构
- [ ] step-nav .step-dot.done 补容器底色（ok-dim + 绿边框），与 ov-chip.done / card-step-status.done 同构
- [ ] refreshGenOverview 的 chips 循环里同步导航 dot 的 warn 类（done/current 仍由既有路径维护）
- [ ] 三处状态判定继续同源（stepDoneSet + genOverviewWarn），无新增状态源
- [ ] node --test tests/js/*.test.mjs 全绿；headless 截图目检
- [ ] 中文提交信息

## 真机项集中挂账（2026-09-09 在途盘点）

- 本单仍未勾的验收项属**真机工具链 / 浏览器 CDP / 真实 LLM 额度 / 人工取源 / 历史流程**类，
  已集中到 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md`（那里不写代码，
  验完一项回勾本单对应项即可）；后续盘点不再逐张重判这些项。
