# 01 — 配置扩展：AppConfig 增可选本地 LLM 端点字段

**What to build:** 用户手改 config.json 增加两个可选字段（`local_llm_base_url` /
`local_llm_model`）后，工具能正常加载不报错；不配置这两个字段时，行为与现状
逐字节一致（零回归）。本工单是路由层（02）与设置页（03）的地基——字段存在且
可持久化，路由才有配置源。

**Blocked by:** 无（可立即开始）

**Status:** resolved

## 验收

- [x] `AppConfig` 新增可选字段 `local_llm_base_url` / `local_llm_model`
      （缺省空串 = 本地路由关闭）。
- [x] `load_config`：字段缺失 → 缺省空串；字段存在但非字符串 → 大声失败
      （与其余字段同严格度）；空串合法（= 关闭，不报错）。
- [x] `save_config`：roundtrip 写回两个字段，行为与既有 save 风格一致。
- [x] 既有 config（无这两个字段）加载 / 保存 roundtrip 后字段值与缺省完全
      一致；`test_config.py` 增覆盖（roundtrip / 缺省空串 / 类型校验大声失败）。
- [x] 全量 pytest + mypy 保持绿；无这两个字段的默认路径逐字节不回归。

## 文件边界

- 配置模块：`AppConfig` / `load_config` / `save_config`（config.py 一处）。
- 测试：test_config.py。
- 不动路由、不动 webapp、不动前端。

## 实施留痕（2026-08-17）

- TDD：先写 `test_local_llm_fields_default_blank_and_roundtrip`（缺省空串 /
  非空 roundtrip / 两字段各一次类型非法大声失败）→ red → config.py 三处实现
  （dataclass 字段 / load 校验 / save 写回）→ green。
- `test_saved_file_is_plain_json` 期望形状同步补两键（save 输出新增字段，断言
  精确形状必然更新）。
- 全量 pytest 1802 绿（原 1801 + 新增 1）；mypy src 47 文件干净。
- code-review 双轴：Standards 零硬违例、Spec 验收全过、无 scope creep。唯一
  baseline 观感 = load_config 内 `data.get+isinstance+raise` 块已重复 7 次
  （含既有 uv4/gmake/ccs 5 处），可抽 `_require_str_field` 助手——判定延后：
  文件既有 idiom 即此形态，抽助手波及既有代码超出本工单边界。
