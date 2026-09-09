# 01 — manifest「Python 副产物」声明能力

**What to build:** 模块 manifest 能够声明「本模块除主控 C 代码外，还会额外生成一份 K230 侧 `.py` 脚本」。这是给后面工单铺路的纯数据模型改动——本工单结束时**没有任何模块实际使用该字段，生成行为也一字不变**。

**Blocked by:** None — can start immediately

**Status:** resolved

完成：3ca520c（manifest.py + test_manifest.py，166 行）——PythonArtifactSpec + ModuleManifest.python_artifact 可选字段；缺省不落键逐字节兼容、非法值大声失败；全量 1747 绿 + mypy 45 文件干净；code-review 双轴通过（template=="." 静默放行缺口已修）。

- [x] `ModuleManifest` 新增一个可选字段，表达「Python 副产物」声明（模板文件路径 + 输出文件名）；缺省 = 无（`None`/空）
- [x] `to_dict` 在缺省时**不落键**，存量 manifest 序列化产物与基线逐字节一致（照 `multi_instance` 先例）
- [x] `from_dict` 严格校验非法值（非对象 / 字段缺失 / 模板路径不安全或非相对）——错值大声失败，不静默强转
- [x] 新增单元测试：解析 / 序列化往返、缺省兼容（旧 manifest 无该键仍加载）、非法值报错
- [x] 全量测试绿 + mypy 干净（本工单不该让任何既有测试红）


## Comments

- 2026-09-09 在途盘点（第二轮）：本单未勾项经代码事实逐条核对，判定全部为「已实现（勾选没跟）」——证据见 `.scratch/tracker-audit/2026-09-09-在途盘点.md`（判定总表按批次给出 `文件:行号` / 测试文件名 / grep 否证）。本次只勾选 + 状态归一 resolved，未改任何验收项文字。
