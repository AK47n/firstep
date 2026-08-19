README 引脚表：绑定生效引脚 + 多实例每实例一行（工单 `.scratch/project-readme/issues/03`）

## 改动

**机制**（`src/contest_generator/readme.py`）
- `render_readme` 增两个缺省参数：`resolved_bindings` / `instance_plans`（缺省 None = 工单 01/02 现状逐字节）
- 引脚表生效引脚 = 绑定载荷覆盖值，否则 `PinDeclaration.default`（两平台统一；绑定只改 pin 值，不新增行、不改行序）
- 多实例计划每实例追加一行：角色 = `ExpandedInstance.macro`（LED_RED / LED_1…）、引脚 = 实例 pin，追加在对应模块声明行之后；说明列 = 模块首个声明类型（仅类型，必接标记不随实例通道继承）

**装配**（`src/contest_generator/generator.py`）
- `generate()` README 落盘点透传 `resolved_bindings` + `instance_plans`（最小改动；两者空 = 缺省路径逐字节）

## 验收

- pytest 1801 passed + mypy src 47 文件干净
- 流程级（`generate_project()` seam）：同一选择无绑定 vs 带绑定各生成一例 → README 引脚表分别显示默认脚 / 绑定脚；带 led 多实例 → 每实例一行且引脚正确；缺省 vs 显式空载荷 → README 逐字节一致（回归护栏）
- 渲染器直测：双平台绑定覆盖 / 多实例行 + 行序 / 缺省参数逐字节等价

偏差留痕：spec/ticket 的「行内角色名 = 实例名」实施为 `ExpandedInstance.macro`（`ModuleInstance.name` 中文显示名在展开层已被 macro 取代，接线表给出代码里实际可用的通道宏名）。
