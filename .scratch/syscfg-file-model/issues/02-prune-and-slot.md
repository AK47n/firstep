# 02 — prune 切到文件模型（contract）

**What to build:** `syscfg_prune.prune_syscfg` 委托给文件模型的 `SyscfgModel.prune`，删除 prune 自己的 addInstance / addModule 正则。**槽位校验不动**：`pin_bindings._check_slot_conflicts` / `_mspm0_same_slot` 是数据级前置检查（两绑定实例名交集），与写侧路径匹配 `syscfg_path_matches`（绑定→路径）是不同层的不同谓词，不在此工单收敛（真正收敛在写侧入模型的工单 03）。行为逐字节不变。

**Blocked by:** 01

**Status:** resolved

- [x] `prune_syscfg` 产出与迁移前逐字节一致（test_syscfg_prune 绿）
- [x] prune 不再持有自己的 addInstance / addModule 正则
- [x] 未选实例裁剪、模块全裁、映射表未登记实例防御（宁多勿裁）行为不变
- [x] 槽位校验零改动（test_pin_bindings / test_pin_unlock_mspm0_same 照常绿）

**Notes:** `prune_syscfg` 改为单行委托 `parse_syscfg(master_text).prune(selected_slugs).to_text()`，
删除 `_INSTANCE_DECL_RE` / `_MODULE_DECL_RE` 与 `import re`；`INSTANCE_CONSUMERS` re-export 保留
（test_syscfg_prune 仍从本模块导入，兼容期）。槽位校验零改动。

测试：test_syscfg_prune 5 passed（逐字节契约）+ test_syscfg_model 逐字节契约照常绿
（test_pipeline_byte_identical_prune_only 已断言 parse→prune 与旧 prune 等价）+
test_pin_bindings / test_pin_unlock_mspm0_same / _cross 照常绿 + 全量 1715 passed + mypy 45 文件干净。

PR #96 squash merged（ccdb3f3）。下一工单 03。
