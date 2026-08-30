# 02 — 模板级依赖覆盖机制

**要做什么：** PythonArtifactTemplate 增加可选 `dependencies`（None = 继承模块级依赖；非空 = 依赖展开时替换该模块的依赖），并在 resolve_selection 消费——选择/展开/骨架/生成四端点共用一个答案；digit 模板将依赖 digit_uart，blob/rect 缺省继承 coord_detect，且不选模板时行为逐字节不变。

**被谁阻塞：** 无——可立即开始（与 01、03 正交）。

**状态：** resolved

- [x] manifest.py：PythonArtifactTemplate 加 `dependencies: tuple[str, ...] | None`（序列化兼容——None 不落键，旧 manifest 逐字节不变）
- [x] 解析校验：manifest 解析时模板 dependencies 内 slug 合法非空（库级校验补漏，非法 = ManifestError）
- [x] resolve_selection 加 `python_templates` 参数：按模板 choices 构造依赖覆盖表 → resolve_dependencies 消费（缺省 None = 旧行为）
- [x] 依赖覆盖与环检测 / 未知 slug 报错语义一致（模板依赖未知 slug = UnknownModuleError，成环 = DependencyCycleError）
- [x] 探针测试：同一探针模块两模板各带/不带 dependencies → 选中不同模板依赖展开结果正确；缺省 = 模块级；webapp 展开端点透传 python_templates（与生成一致）
- [x] 旧行为回归：不传 python_templates 的所有既有测试保持绿

**实现备注（code-review 双轴驱动，2026-08-30）：**

- **库级校验补漏**：`validate_template_dep_slugs`（manifest.py）在 `list_modules` 调用——未选中模板里的悬空依赖也在库加载时大声失败（LibraryError，与 collect_exclusive_groups 同风格）；生成期 resolve_dependencies 只覆盖「选中」模板。未知 slug 由此提前到库层（spec 评审「only half met」→ 补齐）。
- **空数组拒绝**：`dependencies: []` → ManifestError——`[]` 会静默清空模块依赖（既非继承也非有效覆盖，语义黑洞）；「非空字符串数组」文案与行为一致（spec 评审 c2）。
- **非 Mapping 防御**：resolve_selection 对非 dict `python_templates` 视为无覆盖不崩（spec 评审 c1：generate 路径坏形状曾会 AttributeError→500 回归，现归 resolve_python_template_choices 抛 PythonArtifactError 400 中文）；webapp 展开/骨架端点去掉重复 coercion 直接透传（standards 评审 Duplicated Code + 三端点行为一致）。
- `deps_override` 未知 slug / 成环复用 UnknownModuleError / DependencyCycleError 同报错域（用户故事原样）。
- 测试 60 用例绿（新增：解析/序列化、非法 `[]`、覆盖/继承/缺省展开、悬空 Slug 库级校验、成环、generate_project 覆盖进产物、非 Mapping 400、webapp 展开端点透传）；k230 + webapp 355 用例绿；全量回归测试通过。
