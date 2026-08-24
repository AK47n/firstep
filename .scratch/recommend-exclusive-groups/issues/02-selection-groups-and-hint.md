# 02 — 推荐链路组派生 + done 载荷 + hint 兜底

**要做什么：** AI 推荐完成后，推荐结果载荷带「功能组选择卡」数据：命中组（组内
成员被推荐）与 hint 组（赛题 manifest 声明疑似需要、AI 未命中）都出卡；AI 输出
契约不变（组为机器侧派生）。2024H topic manifest 声明 `hint_module_groups:
["attitude-hold"]`——即使 AI 漏了姿态模块，前端也能拿到「AI 未推荐，题面疑似
需要」的航向保持选择卡。

**被谁阻塞：** 01（组定义来自摘要投影）

**状态：** ready-for-agent

- [ ] `build_exclusive_groups` 纯函数：`(selection_modules, group_defs, platform)` → 命中组列表（{id, label, members:[{slug, role}], recommended:[命中 slug], hint: false}）；平台成员过滤；单成员组不出卡
- [ ] `run_recommendation` done 载荷增 `exclusive_groups`（仅命中组或 hint 组非空时落键；旧载荷逐字节兼容）
- [ ] topic manifest 可选 `hint_module_groups`（组 id 清单）解析进 `TopicEntry`（缺省空）；done 载荷对 hint 组无条件出卡（hint: true，recommended 可空）；hint id 库内无对应组 → 静默忽略不炸推荐
- [ ] 2024H topic manifest 登记 `hint_module_groups: ["attitude-hold"]`
- [ ] 单测：命中派生 / 平台过滤 / 单成员组不出卡 / hint 触发 / hint 未知 id 忽略 / 无组库不落键；pytest 全绿 + mypy src 干净

**Notes:**（实现后填）
