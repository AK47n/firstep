# 交付集成：前端交付卡（delivery-suite/02）

## 状态
Status: resolved

## 目标
任务推进区（第 11 步）新增「🚀 交付」卡：打开工程 / 交付检查 / 一键打包。

## 实现
- 新 fx/delivery.js（import core.js esc/truncate；纯函数 + window 桥）：
  - `deliveryActionsHTML(busy)`：三个按钮（btn-delivery-open（打开工程）/
    btn-delivery-check（交付检查）/ btn-delivery-package（一键打包）），
    busy 禁用；按钮行说明文案一句。
  - `deliveryCheckHTML(result)`：ok → ✅ 全绿文案 + 统计行（已验证 N /
    已跳过 N / 未完成 N）；未完成 → ⚠ + 逐条 `.delivery-incomplete`
    （title + verifyStatusMarkup 徽章（fx/task.js 既有））；plan_present
    False → 「尚未拆解任务清单——可先拆解或直接打包」；全 esc。
  - `deliveryPackageHTML(result)`：zip 路径（.slug 样式）+ 大小
    （fmtDuration 不合适——formatSize from core.js）+ 文件数；空 → ""。
  - fx-guard 登记 3 导出。
- 新 ui/delivery.js：deliveryState{busy, result}；deliveryOpen /
  deliveryCheck / deliveryPackage（apiPost 同步；busy 守卫 tasksSetBusy 共享
  闸——与任务/参数流程互斥）+ rendering；交付结果渲染到 #delivery-result；
  跨簇重置（revise-context-loaded / tasks-invalidated）清结果；导出三个执行
  函数挂 window（供委托与探针）。
- index.html：tasks-box 内新 card-group「🚀 交付」（位置 = 参数速调卡之后、
  拆解按钮行之前——工具卡集群）；#delivery-actions / #delivery-result /
  #delivery-msg + CSS（.delivery-stat-row / .delivery-incomplete / zip 行样式
  ——变量色，零硬编码）。
- 委托：generate-tasks.js 网格委托区外挂 #tasks-box 上（delivery 卡在
  tasks-box 内、grid 外）——click 委托 .btn-delivery-*。
- tests/js/delivery.test.mjs：actionsHTML（busy 禁用/转义）/ checkHTML（ok
  绿 / 未完成列表 / 无清单 / 转义）/ packageHTML（空 / 正常 / 转义）；
  fx-guard 登记。

## 交付
- 双轴评审 → 整改 → JS 全量 → 提交。
