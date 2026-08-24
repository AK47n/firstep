# 01 — manifest 组声明 + 库校验 + 摘要行标注（数据底座）

**要做什么：** 模块 manifest 能声明「我属于哪个功能组」（`exclusive_group: {id, label, role}`），
库加载时校验组一致性（同 id 的 label 逐字一致、role 非空），模块摘要行自动带
「同组互斥」标注（进推荐提示词与缓存指纹）；5 个模块登记首批两个功能组
（gray-track：huidu/pid/xunji；attitude-hold：imu_uart/ml_mpu6050）。旧 manifest
无该字段 = 不属任何组，加载与序列化逐字节不变。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `manifest.py` 的 `ModuleManifest` 增可选 `exclusive_group` 块（id/label/role 全为非空字符串），旧 manifest 无该字段解析为 None；`from_dict` 严格类型校验（错值大声失败），`to_dict` 缺省不落键（旧 manifest 序列化逐字节一致）
- [x] 库校验：同 id 的 label 逐字一致（不一致 = 库错误大声失败）；role 非空（缺 = 报错）
- [x] `ManifestSummary` 投影 `exclusive_group: (id, label, role) | None`；`to_line()` 追加 `（同组互斥：<label>，组内仅选其一）`
- [x] 组定义汇总纯函数：扫描库 → id → 成员清单（slug + role），平台过滤口子留好（单平台成员数 ≤1 的组标记无意义）
- [x] 5 个 manifest 登记：huidu/pid/xunji（gray-track，role 按 spec 表初稿写差异定位）+ imu_uart/ml_mpu6050（attitude-hold）
- [x] 结构测试：全库加载不破、组校验单测（label 不一致/类型错/缺省兼容）；pytest 全绿 + mypy src 干净

**Notes:**（2026-08-13 实现，7 文件 + 测试）
- manifest.py：`ExclusiveGroupSpec`（frozen：id/label/role + to_dict）/ `ExclusiveGroupMember`（slug/role）/ `ExclusiveGroup`（id/label/members + to_dict）；`ModuleManifest.exclusive_group` 缺省 None 不落键；`_parse_exclusive_group` 严格校验；`ManifestSummary` 投影 + `to_line()` 追加「同组互斥：<label>，组内仅选其一」；`collect_exclusive_groups(manifests, platform="")` 按 id 保序聚合，label 不一致抛 ManifestError，platform 非空时剔除该平台无条目成员 + 单成员组。
- library.py：`list_modules` 加载后调 `collect_exclusive_groups` 做库级一致性校验（不一致包 LibraryError「模块库功能组不一致：…」）。
- 测试：tests/test_manifest.py +8（roundtrip/缺省不落键/类型错拒/字段缺失拒/to_line 标注/聚合保序/平台过滤+单成员剔除/label 不一致拒/多组并存）；tests/test_module_universality.py +1 真库聚合（gray-track=[huidu,pid,xunji]、attitude-hold=[imu_uart,ml_mpu6050]、mspm0 完整、stm32 两组剔除为空）。
- 验证：pytest 全套 2267 passed（较基线 +9：test_manifest +8、真库聚合 +1；0 fail）；mypy src 0 错误（60 文件）；冒烟 26 模块加载正常，stm32 无意义组剔除。
- code-review 双轴无实质缺陷（Standards 判断项 3 条均接受；Spec 轻微点 4 条：真库聚合单测已补、ExclusiveGroup.to_dict() 面向 02 保留、role 措辞以 spec「初稿」为准、投影用完整 spec 对象功能等价）。
