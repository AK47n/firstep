# 工单 02：参数速调前端面板（param-tune/02）

Status: pending

## 目标

任务推进区「⚙️ 参数速调」卡片：识别 → 参数表（改值）→ 应用并验证 → 结果
（diff/编译/回滚/烧录）。

## 交付

- 新 `fx/params.js` 纯函数模块（import core.js esc/truncate + ./diff.js
  mainDiffHTML + ./flash.js flashPanelHTML）：paramListHTML(params,
  {running})（表：名称/含义/当前值输入框（value=old_value，id=
  params-input-<name>）/建议范围；valid=false 行禁用 + 「锚已失效」标记；
  running 全禁用；空参数表 → 引导文案 + scanEmpty 状态）；paramResultHTML(
  result, dir)（编译徽章 + mainDiffHTML + 备份回滚行（data-param-rollback）+
  flashPanelHTML(dir, "params")）；paramApplyButton? 无（按钮在 static
  html）；window 桥 + fx-guard 登记。
- 新 `ui/params.js`：paramsState{plan,busy,result,msg}；paramsScan()（SSE
  /api/tasks/params/scan handlers param_scanning/param_result/llm_telemetry/
  done；done → state.plan → 渲染 → toast）；paramsApply(name)（读输入框值 →
  SSE /api/tasks/params/apply；busy 守卫 toast；done → 渲染 result +
  paramsReload() 刷新 valid）；paramsReload()（/read 同步回填 plan）；
  paramsRollback()（/api/revise/rollback 复用——回滚后 reload）；委托
  #btn-params-scan / #btn-params-apply（data-param-name）/ #params-grid 上
  .btn-params-rollback；跨簇重置（revise-context-loaded / tasks-invalidated
  清 state）。
- `index.html`：tasks-box 内新 card-group「⚙️ 参数速调」（说明文字：识别
  main.c 可调参数 → 改值只改那一个常量 → 编译 → 可烧录；独立于任务清单）；
  btn-params-scan / params-status / params-grid / params-msg / params-result +
  CSS（.param-row/.param-input/.param-valid/.param-stale/.btn-params-*）。
- `tests/js/params.test.mjs`：paramListHTML（行渲染/输入默认值/失效禁用+标记/
  空态/转义）；paramResultHTML（diff 折叠/烧录行 uid="params"）；fx-guard
  DOMAINS 登记。
- JS 全量绿；探针（可选）实机验证识别→改值→应用→刷新。

## 验收

1. JS 全量绿 + fx-guard 过。
2. 面板与既有 tasks-box 布局协调（无重叠、暗色主题无色盲）。
3. 双轴评审通过后提交。
