# 02 — sources/materials 塔克目录下架（分发面收口）

**要做什么：** 删除 `sources/materials/塔克R3两驱小车底盘资料/` 目录——完整包 next 版
自然不含；下一次 materials 增量包（diff 基线机制）自动产生该批次的 removed 清单，
已安装用户侧一键更新即自动删除塔克文件。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [ ] 删除目录（不在 git 内，直接文件系统删除）
- [ ] 确认下次打包 diff 机制覆盖整批删除（materials_pack L242-250 整批消失路径）——
      跑一次 diff 模式对当前基线做 dry 验证（若基线不可得则说明并跳过）

## Comments

- 2026-09-09 补标 resolved（代码事实盘点）：
  ① 目录已删——`Get-ChildItem sources\materials -Directory | Where-Object { $_.Name -match '塔克|xtark' }`
  → **零命中**（现存 11 个批次目录，无塔克）；
  ② diff 机制覆盖整批删除——`src/contest_generator/materials_pack.py:242-251
  diff_manifest` 的「整批目录删除」分支（旧清单有、新清单无 → `removed` 列全量文件、
  parts 为空），单测 `tests/test_materials_pack.py:164
  test_diff_whole_batch_removed_reported_as_removed` 钉死；
  打包入口 `tools/pack-materials.ps1`（diff 模式要求 `-Baseline`，第 45-48 行）。
  验收逐条对照：① 目录已删（grep 零命中）✓ ② 整批删除路径有实现 + 单测（dry 验证
  以单测覆盖替代，无需真基线——工单允许「基线不可得则说明并跳过」）✓。
