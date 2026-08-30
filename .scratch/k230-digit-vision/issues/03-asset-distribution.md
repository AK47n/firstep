# 03 — 静态资产分发机制

**要做什么：** PythonArtifactTemplate 增加可选 `assets`（{src, dst} 复制对，src 相对模块目录、dst 相对工程根），生成写盘阶段与 .py 副产物同阶段复制；src 缺失 / dst 跨模板冲突 / dst 撞既有文件 → 大声失败不留半成品；产物摘要「模块文件」行列出资产文件。

**被谁阻塞：** 无——可立即开始（与 01、02 正交）。

**状态：** resolved

- [x] manifest.py：PythonArtifactTemplate 加 `assets: tuple[AssetSpec, ...]`（AssetSpec = {src, dst} 字符串对；None/空缺省不落键，旧 manifest 逐字节不变）
- [x] manifest 解析校验：src/dst 非空、src 相对路径不越界（模块目录内）、dst 相对工程根不越界（非法 = ManifestError）
- [x] generator._write_python_artifacts：复制资产（shutil.copy2 逐字节）到工程根 dst；src 缺失 / dst 撞既有文件（含 Windows 大小写变体）→ PythonArtifactError；跨模板 dst 同名互斥（同 output 检查同款语义）
- [x] 摘要：describe_generation 模块文件行含资产文件（webapp done 载荷 + 前端展示同步，前端「模块文件」行显示 .py + mp_deployment_source 文件）
- [x] 探针测试：探针模块带 assets → 产物复制成功字节一致 + 摘要列出；src 缺失 / dst 冲突 / dst 撞母版文件 → 失败且 generate 不留半成品
- [x] 旧行为回归：无 assets 声明的所有既有测试保持绿（产物逐字节一致）

**实现备注（code-review 双轴驱动，2026-08-30）：**

- **顺手修复 02 潜伏洞**：PythonArtifactSpec.to_dict 的旧形状分支（单模板 id=default → {template, output}）会被「带增强字段的单模板」命中而丢字段——分支加 `dependencies is None and not assets` 守卫，增强单模板走新形状；补旧形状逐字节往返锁（test_legacy_single_template_serialization_byte_identical）。
- **摘要层改名**（standards 评审 Mysterious Name）：PythonArtifactSummary / webapp 载荷 / 前端统一 `asset_paths`（dst 路径列表——template.assets 是 AssetSpec 对，同名不同义误导）。
- **路径校验抽 helper** `_require_asset_path`（standards 评审 Duplicated Code：src/dst 非空+越界三连重复）；`.` 单点拒绝（与 template/output 同口径——is_unsafe_path 对 "." 放行，spec 评审 (a)3）。
- **同模块重复 dst 文案**独立（spec 评审 (c)2：不再报「模块 X 与模块 X」）；跨模板互斥大小写敏感与 output 检查同款（Windows 写时 exists() 兜底，spec 评审 (c)1 判定行为收敛、报错语义可接受）。
- README 产物清单行归属 04 工单（checkbox 已承）；二进制 kmodel 7,596,008 字节断言归 04。
- 测试 71 用例绿 + 前端 node:test 7 用例绿；k230 + webapp 371 用例绿；全量回归测试通过。
