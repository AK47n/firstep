# 01 — 步骤完成态修复（空推荐不标完成 + 默认布线双态）

**要做什么：** 走查发现的两处「向导信任伤」修复：AI 推荐返回空结果时步骤 5 不再被标成「已完成」；按默认布线生成工程后步骤 7 显示中性「默认布线」标记而非绿「✓ 已就绪」，同时完成计数不变（生成已走通仍如实反映）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

**实现记录：** fx/draft.js 新增 step7WireMode 纯函数（configured/default/none 三态）；
ui/step-state.js 维护 step7Wire 并广播 step7-wire-changed；generate-recommend.js 空结果分支
markStepUndone(5)、非空才 markStepDone(5)；generate-steps.js 总览 chip（▣ 青色）与卡徽章
（「▣ 默认布线」）按 wire 模式渲染；index.html 补 .wire 两处样式；单测 step7-done.test.mjs
新增 6 例 wireMode + fx-guard 登记；CDP 冒烟 probe-t01.mjs 全 PASS（无 JS 异常）。

- [ ] 推荐结果为空（无模块/无需求建议/无互斥组卡）时，步骤 5 保持未完成，步骤卡与总览不出现✓，空结果提示文案保留并指向模块库
- [ ] 推荐结果有可用命中时，步骤 5 仍正常标记完成（含手动加模块场景不反向补标步骤 5）
- [ ] 按默认布线生成（有引脚角色、未显式绑定、实例未配引脚）后，步骤 7 卡徽章与总览 chip 显示「默认布线」中性标记，而非「已就绪」✓
- [ ] 显式绑定引脚/实例配脚/无角色需配置三种情形仍显示「已就绪」✓，行为不变
- [ ] 新增纯函数与 node:test 单测覆盖上述四态判定
- [ ] 全量前端测试与既有 01-09 之外所有用例保持绿

