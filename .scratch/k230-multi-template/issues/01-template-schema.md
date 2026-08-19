# 01 — python_artifact 多模板解析

**要做什么：** manifest 的 python_artifact 支持多模板声明：旧形状（template/output 单模板）解析为 id="default" 单模板列表（存量 manifest 逐字节兼容）；新形状（templates 数组 + default id）校验通过；两种形状并存 / 非法声明大声失败（ManifestError）。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [ ] manifest.py PythonArtifactSpec 扩展：templates 列表（id/name/description/template/output）+ default id；旧形状解析为单模板列表（id="default"），序列化旧形状逐字节不变
- [ ] 新形状校验：id 唯一非空 / default 必须存在于列表 / template 相对无 .. / output 纯文件名（照现有口径）；旧+新形状并存 = ManifestError
- [ ] ManifestSummary / to_line 消费多模板（有模板时展示能力证据，旧模块不变）
- [ ] 结构测试：旧形状逐字节 / 新形状解析 / default 缺失 / id 重复 / 并存冲突 / 非法路径（照 test_manifest 先例）
- [ ] 全量测试通过
