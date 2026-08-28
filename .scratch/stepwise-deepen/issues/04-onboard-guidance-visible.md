# 04 — 修复：compile 任务「已验证」后卡片上板指引消失（实机反馈）

**要做什么：** 用户实机跑 2024H，点「做这一步」完成后卡片显示「已验证」，但看不到「接下来你要做什么」的上板指引，不知道该怎么上板。根因：`taskNextActionHTML` 旧规则 `status===verified` 一律隐藏——而 `verify=compile` 任务的 verified 只代表编译通过，用户仍需烧录上板，指引恰在最需要的时刻消失（实测数据 `user_action` 字段其实是好的，纯前端显示条件问题）。

**被谁阻塞：** 无（纯前端 bugfix，承接 stepwise-deepen/02）。

**状态：** resolved

- [x] `fx/task.js` `taskNextActionHTML` 显示条件修正：隐藏仅限 ① doing（执行中旧指引过期）② `verify=manual` 且 verified（用户已上板人工确认）；compile 任务 verified（编译绿）**常驻显示**。文档注释同步更新（工单 04 修正）。
- [x] tests/js：`taskNextActionHTML` 测试改为「未上板 / 编译通过待上板显示；人工已确认 / 执行中 / 无指引 = 空串」；`taskCardHTML` 补 compile-verified 卡「下一步要做」断言。全量 530 passed。
- [x] 无需后端改动（`user_action` 已正确落盘）；现有 2024H 工程数据无需迁移，刷新页面即生效。

**实机证据（2024H 首步 t1，verify=compile, status=verified）**：
- `user_action` = "将编译好的固件烧录到 MSPM0 开发板。上电后应看到 LED（PA15）闪烁一次、蜂鸣器响一声（初始化声光提示）。然后将小车置于黑线上，当灰度传感器检测到黑线时，小车应自动启动并再次声光提示。若未出现，请检查供电和接线：LED 接 PA15，电机按 motor.h 注释接线，灰度模块按 xunji.c 中 P1~P8 对应的引脚连接。"（后端工单 01 产出正常）
- 修复前：卡片不渲染 `taskNextActionHTML` → 用户看不到指引；修复后：卡上「下一步要做」常驻。

**提交：** 见 git 历史（工单 04 提交）。
