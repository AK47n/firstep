# 02 — zigbee_uart ↔ zigbee_link 互斥组 + 生成门禁

**要做什么：** 推荐/UI 出现「Zigbee 无线链路（接收侧）」互斥组卡（zigbee_uart 与 zigbee_link 单选其一）；绕过 UI 直接 API 双选 → 生成 400 中文错误（同一路 ZIGBEE_UART 只能选一个接收驱动）；`zigbee_link` + `zigbee_uart_key` 双选放行；真库互斥组快照测试更新。防 L6200E multiply defined 双保险。

**被谁阻塞：** 01（zigbee_link 双平台驱动落地）

**状态：** resolved

**评审整改（2026-09-05）：** 双轴评审通过；补齐——① role 断言（真库 zigbee-rx 两成员 role 逐字）；② build_exclusive_groups 真库平台视图用例（mspm0/stm32 双视图出卡）；③ HARD_EXCLUSIVE_PAIRS 改三元组（left/right/reason，拦截消息数据派生，修 F541 与「vs」措辞）；④ 新增一致性测试：硬互斥对必须落在某 manifest 互斥组内（双源防漂移）；⑤ 门禁表注释同步（吃 manifests 类目）。

- [x] `zigbee_uart` 与 `zigbee_link` 的 manifest 各声明 `exclusive_group`（同 id/label、各自 role）
- [x] 生成/选择层门禁：`zigbee_uart` + `zigbee_link` 同选 → 400 中文；`zigbee_link` + `zigbee_uart_key` → 放行
- [x] `tests/test_module_universality.py` 真库互斥组快照更新（zigbee-rx 组标签/成员/role 断言 + 硬对一致性）
- [x] 组卡推荐链路测试（build_exclusive_groups 平台视图）覆盖新组
- [x] 相关测试全绿
