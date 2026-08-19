# 03 — 绑定/多实例进引脚表

**What to build:** 引脚接线表从"只显示声明默认值"升级为"显示实际生效引脚"：绑定载荷覆盖的角色的生效引脚、多实例计划的每实例一行。未绑定 / 无多实例时与工单 01 产出逐字节一致（回归护栏）。

**Blocked by:** 01 — README 渲染器核心 + 生成落盘

**Status:** resolved

- [x] 引脚表生效引脚口径 = 绑定载荷覆盖值，否则 `PinDeclaration.default`（两平台统一；mspm0 与 stm32 同构）。
- [x] 多实例计划（ModuleInstance：name / variant / pin）在引脚表中每实例一行，行内角色名 = 实例名，引脚 = 实例 pin。
- [x] 未绑定、无多实例的生成：README 引脚表与工单 01 产出逐字节一致（回归用例锁住）。
- [x] 测试（走 `generate_project()` 流程级 seam）：同一选择生成两例——不带绑定 vs 带绑定覆盖某角色，断言 README 引脚表分别显示默认脚与绑定脚；带 led 多实例选择断言每实例一行且引脚正确；无绑定/无实例回归例断言与基线逐字节一致。
- [x] 全量测试绿 + mypy 干净（src 全部文件）。

## 实现

- `src/contest_generator/readme.py`：`render_readme` 增两个缺省参数 `resolved_bindings`（`Sequence[ResolvedBinding]`）/ `instance_plans`（`Mapping[str, Sequence[ExpandedInstance]]`），缺省 None = 工单 01/02 现状逐字节；`_pin_rows` 生效引脚 = `bindings.get((slug, decl.id), decl.default)`（绑定只改 pin 值，行序 = manifest 顺序 × pins 声明顺序不变）；`instance_plans[slug]` 每实例追加一行（角色 = `ExpandedInstance.macro`、引脚 = 实例 pin、说明 = 模块首个声明类型仅类型不带必接标记），追加在模块声明行之后；`_pin_remark` 提取声明行说明。
- `src/contest_generator/generator.py`：`generate()` README 落盘点透传 `resolved_bindings` + `instance_plans`（最小改动；两者空 = 缺省路径逐字节）。
- `tests/test_readme.py`：+6 例（流程级绑定覆盖 / 流程级 led 多实例 / 流程级缺省逐字节回归 / 渲染器双平台绑定覆盖 / 渲染器多实例行 + 行序 / 渲染器缺省逐字节）。

## 验收

- 全量 1801 绿 + mypy src 47 文件干净。
- 代码评审（双轴 sub-agent）：Standards 零硬违例（采纳三处 minor：generate docstring 同步 03 / 两个可选参改关键字透传 / 读码注释澄清 TYPE_CHECKING 边界）；Spec 两处处置——① 流程级缺省逐字节回归例补上（新流程测试），② 实例行说明改仅类型（必接标记是角色声明属性、不随实例通道继承）。
- 偏差留痕：spec/ticket 的「行内角色名 = 实例名」实施为 `ExpandedInstance.macro`（如 LED_RED / LED_1）——本工单实施提示词逐字规定；`ModuleInstance.name`（中文显示名）在 `expand_instances` 展开层已被 macro 取代、不回流 readme，接线表给出的是代码里实际可用的通道宏名。
