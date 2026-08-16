# 01 — manifest 能力声明 + 多实例数据形状（兼容解析）

**What to build:** 模块 manifest 能声明「我支持多实例」（`multi_instance: {max, variant}`），
选择与生成请求能携带实例清单（`{led: [{name, variant, pin}...]}`）；旧 manifest / 旧请求
缺这些字段时，整个库和生成流程照旧按「单默认实例」跑，产物与基线逐字节一致。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] `manifest.py` 的 `ModuleManifest` 增可选 `multi_instance` 块（`max` 正整数上限守卫、`variant` 非空字符串），旧 manifest JSON 无该字段解析为 `None`，严格类型校验（错值大声失败，不静默强转）
- [x] 选择域新增实例模型（name / variant / pin），`ModuleSelection` 或并行结构能携带 `instances` 清单；`resolve_selection` / `ResolvedSelection` 透传不丢
- [x] `to_dict` / `from_dict` 往返稳定，旧 manifest 序列化产物与基线逐字节一致
- [x] 结构测试：全库 manifest（含 led 之外所有模块）加载不破；新增 led 的 `multi_instance` 声明后旧测试仍绿
- [x] pytest 全绿 + mypy src 干净

**Notes:** 数据模型层落地。`to_dict` 在 `multi_instance is None` 时不落键（旧 manifest 序列化逐字节一致）；`_parse_multi_instance` 严格校验 max（布尔显式拒绝）/ variant。`ModuleInstance` 只有 `to_dict` 无 `from_dict`（请求解析归 04 前端 / 生成请求层，01 只建模型）；`resolve_selection` 纯透传不校验 instance slug ⊆ 选中 slug（展开 / 上限守卫归 02）。1638 passed + mypy src 干净。code-review 双轴：Spec 无 material finding；Standards 5 条 judgement call（variant 命名多义 / instances 类型重复 / 透传暂无消费方 / CONTEXT manifest 行未列新字段 / 拒绝测试缺 match）——前四为 spec 锁定的决策或垂直切片性质，仅把拒绝测试补齐 `match=`（精确到 max / variant）。CONTEXT.md「manifest」行未列新字段：留待后续（该行本就不枚举 pins 等字段，非本票边界）。
