# 06 — 身份字段强制收窄为仅硬件绑定条目

**What to build:** 工单 01 的身份字段强制（新录入必填 kit/source_url）收窄——只对 `hardware_bound=True` 的硬件绑定条目强制；纯逻辑条目（如 zone/pid/filter 这类区域判定、滤波、控制算法）免填身份字段，因为纯逻辑的身份由简介的专用性标注承担（判据第三要素），身份字段的本来职责是"确认哪块硬件"。但纯逻辑条目**提供**了身份值就必须合法（给了就要给对）。

**Blocked by:** 01 — 硬件身份字段 + 新录入强制（已完成）

**Status:** resolved

- [x] hardware_bound=False 的新录入不带身份字段 → 正常入库，字段为空串
- [x] hardware_bound=True 的新录入不带身份字段 → 拒绝（原强制保留）
- [x] 纯逻辑条目提供了非法 source_url → 仍拒绝（给了就要给对）
- [x] add_platform_files 新增平台条目同样按 hardware_bound 判定（补 hardware_bound 参数 + webapp 透传）
- [x] 全量测试 484 passed（另 1 例环境性失败见 Comments）+ mypy 干净

## Comments

- 2026-08-07 工单 06 完成（分支 ticket-module-desc-06，feat 90d2f02，已合 main）。
  实现：`_validate_identity_fields` 增 `required` 参数（required 时 kit/source_url
  必填 + 格式校验；否则提供值校验格式）；`add_module` / `add_platform_files`
  按 `hardware_bound` 传入；`add_platform_files` 新增 `hardware_bound` 参数并
  写入新条目；webapp platform-files 端点透传。新增测试 7 例（库层 5 + webapp 2），
  更新行为变化的旧测试 4 处。
- 环境性失败记录：`tests/test_master.py::test_real_projects_2026c_21f_distill_and_import`
  读取桌面真机工程，其真实 .uvprojx 被 Keil 改动后结构校验拒绝——与本次改动无关
  （stash 验证 pre-existing），是工单 07 遗留"用户 Keil 编译"的已知残留。
- 决策依据（grilling 定）：身份字段 = 硬件身份；纯逻辑身份靠简介专用性标注兜底。
