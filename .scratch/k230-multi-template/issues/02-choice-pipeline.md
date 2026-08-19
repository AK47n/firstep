# 02 — 模板选择请求管线

**要做什么：** 生成请求可携带模板选择 python_templates（{slug: template_id}）：webapp 解析并校验（slug 是已选模块且该模块声明多模板、id 在模板列表内，非法 = PythonArtifactError → 400 中文）；generator._write_python_artifacts 按选择渲染对应模板写 .py；缺省 = default（旧请求逐字节兼容）；跨模块同名 output 冲突校验照旧。

**被谁阻塞：** k230/01（python_artifact 多模板解析）。

**状态：** resolved

- [ ] webapp /api/generate 接受可选 python_templates 载荷，形状判决归域层（非法 slug / 非法 id / 非多模板模块带选择 → 400 中文）
- [ ] _write_python_artifacts 按选择渲染：选中模板文件读出 → render_python_artifact → 写 output；缺省 default
- [ ] 旧请求（不带 python_templates）行为逐字节不变（回归护栏）
- [ ] 模板缺失 / output 冲突错误文案照旧（PythonArtifactError → 400）
- [ ] 测试：带选择 / 缺省 / 非法 id / 非法 slug / 跨模块 output 冲突五条路径（照 test_webapp + test_k230_artifact 先例）
- [ ] 全量测试通过
