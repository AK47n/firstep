# 01 — 引脚自动配置：一键解冲突（合法共享保留 + 标注）

**要做什么：** 生成第 7 步加「自动配置」按钮：点击后后端确定性算法把真冲突的角色（能力 / UART 成对 / mspm0 槽位互斥 / 类型级实例约束——resolve_bindings 校验面，与 validate 同源）重新分配到不冲突引脚，合法共享（I2C 总线多设备同挂、传感器共读等）保留并标注原因；结果回填板图可手动微调；只动冲突角色，用户合法绑定与默认脚不动；无冲突/无解给中文说明。TIM/EXTI/UART 实例级冲突属生成门禁（需 main_c 上下文），不在本功能范围。

**被谁阻塞：** 无——可立即开始

**状态：** resolved

- [x] pin_bindings 新增 `auto_assign_bindings` 求解器（逐角色修复：先试原值合法保留 → 非法换脚跳过已占用 → 无解中文报错）+ AutoAssignResult（增量 / fixed 说明 / shared 标注）+ `_shared_groups`（同脚多角色组，I2C 总线说明）
- [x] `/api/bindings/auto` 端点（resolve_selection + board_for_platform 同源，PinBindingError → ok:false）
- [x] 前端：第 7 步「自动配置」按钮 → 端点 → 应用增量重绘 + 说明条（✓ 已调整 / 🔗 保留共享）；生命周期与 pinBindings 一致（不落盘）
- [x] 测试：求解器 5 个（共享保留+标注 / 能力冲突重分 / UART 成对重分 / 合法绑定不动 / 全占无解报错）+ 路由集成 2 个（冲突重分+共享标注 / 无冲突空增量）+ 结构钉 1 个
- [x] 全量 pytest 绿（2028）+ JS 48 绿；CONTEXT.md「引脚绑定」词条补自动配置口径
