# 01 — jy61p 并入「航向保持 / 姿态传感器」功能组

**要做什么：** AI 推荐里「同一个功能出现两次」的现场不再发生——用户已经在功能组单选框里选了一个
姿态传感器（`imu_uart`）时，同一份推荐的其它需求句里不会再冒出一个**裸 chip** 的同类姿态件
（`jy61p`）；`jy61p` 改为出现在同一张功能组卡的成员行里（radio 可点、带 role、AI 推荐过就标
「同组互斥·未选中」），需求句里只留一条灰注。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `library/modules/jy61p/manifest.json` 补 `exclusive_group = attitude-hold`
      （label 与 `imu_uart` / `ml_mpu6050` 逐字一致：`航向保持 / 姿态传感器`；role 说清硬件差别）。
- [x] 判据不止「用户说的」：jy61p 自己的 `notes` 早就写着与 `imu_uart` **「姿态互替」**
      （且默认脚都是 PA28/PA31），属同一功能的第三种硬件——库内证据支持同组。
- [x] 真库收敛实测（探针）：同一份载荷同时推 `imu_uart` + `jy61p` → 顶层只留一个，
      另一个进 `dropped_exclusive_members`（载荷 `candidates` 可见），不再两个都进工程集。
- [x] 红证：把 jy61p 的组声明删掉再跑同一载荷 → `attitude-hold` 只剩 2 成员、`jy61p` 与
      `imu_uart` **同时**进顶层 modules（= 用户看到的现场形态）。
- [x] 回归守卫：`tests/test_module_jy61p.py::test_jy61p_declares_attitude_hold_group_with_imu_uart`
      （三件同组 + label 逐字 + role 齐备）；`tests/test_module_universality.py` 的真库基准
      同步为 `imu_uart/jy61p/ml_mpu6050`。
- [x] 全量回归：`pytest` 4014 passed / `node --test tests/js/*.test.mjs` 1444 passed。

## 实施记录（2026-09-12）

**现场（用户截图）**：功能组卡「功能组选择 · 航向保持 / 姿态传感器」里 `imu_uart` 是选中态，
而句子 12「无引导标记直线段航向保持」下挂着 `jy61p` 这个可移除 chip——**已经选了一个姿态件，
需求句里又出现另一个**。

**根因**（不是 UI 的问题）：`exclusive_group` 是模块级 manifest 声明，`jy61p` 没声明 ⇒
① 它不属任何组 ⇒ 需求句走 `recommendChip`（可移除 chip）而不是 `groupRequirementNote`（灰注）；
② 同组互斥收敛（`converge_exclusive_group_selection`）看不见它 ⇒ 两个姿态件同时进工程集。
库内当时的情况：`attitude-hold` = {imu_uart, ml_mpu6050}，`jy61p` 孤零零在组外。

**改动只有一个文件**（+ 两处测试基准）：`library/modules/jy61p/manifest.json` 加

```json
"exclusive_group": {
  "id": "attitude-hold",
  "label": "航向保持 / 姿态传感器",
  "role": "软 I2C + 器件内卡尔曼融合（roll/pitch/yaw 直出，接 PA28/PA31，JY61P 模块）"
}
```

**证据**：`.scratch/attitude-group-jy61p/verify-01-group-merge.txt`（探针
`probe-01-group-merge.py`，4/4 PASS；只读、零额度）：
- ① 真库聚合 → `attitude-hold = ['imu_uart', 'jy61p', 'ml_mpu6050']`；
- ② 三件的 role 并列（用户一眼看出「选它差在哪」）；jy61p 的 notes 自证「姿态互替」；
- ③ 同一载荷收敛 → 顶层 `['pid', 'jy61p']`、`dropped={'attitude-hold': ('imu_uart',)}`
      （收敛规则 = **保留模型清单里先出现的那个成员**，既有设计，本单未动）；
- ⑤ 红证 → 删掉声明即复现现场（`['pid', 'jy61p', 'imu_uart']`）。

**已知局限 / 留待用户拍板**：收敛后组卡默认选中的是「模型清单里先出现的那一个」。本现场里
「句子 12 先提 `jy61p`」⇒ 默认落在 `jy61p`，而 AI 把 `imu_uart` 列为组内首选（它在组卡上带
「AI 推荐」徽标）。两者都能用（点 radio 一键换），但**默认选中谁**是产品口径，已留作待拍板项。
