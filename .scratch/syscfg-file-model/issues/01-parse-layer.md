# 01 — syscfg 文件模型：解析层 + 槽位原语落地（expand）

**What to build:** 新增 mspm0.syscfg 文件模型模块：独占两份文法（实例声明 addInstance、模块声明 addModule、`$assign` 赋值）、一次解析为结构化模型、一个槽位身份原语（binding → syscfg 实例/路径）、MSPM0_SYSCFG_FILENAME 常量。旧代码零改动，纯新增。

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] 新模块能解析母版 mspm0.syscfg，产出与 prune / rewrite 当前推导一致的实例集与 `$assign` 落点集
- [x] 槽位身份原语对 GPIO 组（associatedPins[n].pin）、外设（txPin/sclPin/ccp0Pin 等）两类路径返回与 `_mspm0_path_matches` 相同的判定
- [x] 新模块对母版 syscfg 的 parse+prune+rewrite 输出与旧 prune→rewrite 顺序逐字节一致（测试断言）
- [x] MSPM0_SYSCFG_FILENAME 在旧位置仍可导入（兼容期），新模块也导出

**Notes:** 新模块 `src/contest_generator/syscfg_model.py` 纯新增，旧代码零改动：
- `parse_syscfg` 独占 `_INSTANCE_DECL_RE` / `_MODULE_DECL_RE` / `_SYSCFG_ASSIGN_RE`
  三份文法，一次解析为 `SyscfgModel`（`lines` + `instances` + `assigns`）。
- `SyscfgModel.prune` / `.rewrite` 是对同一解析的两个操作（`to_text` 唯一 serialize
  出口），`syscfg_path_matches` 是槽位身份原语（与 `_mspm0_path_matches` 逐行等价）。
- `MSPM0_SYSCFG_FILENAME` 新模块导出，pinwriter 旧位置不动（兼容期，04 迁走）。
- `SyscfgModelError` 入错误映射白名单（模型内失败，03 由 pinwriter 翻译回
  PinBindingError）。

测试 `tests/test_syscfg_model.py` 8 用例：解析集与旧推导独立正则对照 / 槽位原语
全库角色×全母版路径穷举等价 / parse+prune+rewrite 与旧 prune→rewrite 逐字节一致
（无绑定 + 带绑定 9 组场景：gpio 组 / 默认重叠 / uart 换位 / i2c / pwm 同族跨族）/
文件名常量新旧并存。全量 1715 passed + mypy src 45 文件干净。

code-review 双轴：Spec 无 material finding（四验收项全中）；Standards 无 hard
violation，2 条 judgement call 已修——去掉解析产物死字段 `modules`（speculative
generality）、`rewrite` 空改返回原模型的 docstring 说明。其余（verbatim 复制
expand 契约豁免 / `SyscfgInstance.line` 解析节点自描述）为 expand–contract 或
模型自洽性，保留。

分支 `syscfg-file-model-01`（feat ecda 系 + auto-CHANGELOG），待 PR 合并 main。
