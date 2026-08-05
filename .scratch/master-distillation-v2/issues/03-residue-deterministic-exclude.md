# 03 — 已知残留确定性剔除（报告可见 + 规则化原因）

**What to build:** 构建产物（.o / .axf / .hex / .map）、备份（.bak / *~）、临时文件按扩展名/模式机器识别、确定性剔除——不进 AI 判定、不读全文；但进报告 exclude 清单并带规则化原因（如"构建产物：.o 文件"），不做黑盒消失（ADR 0001）。与 template-fit-check.md 的"建议清理"清单一致。

**Blocked by:** 无（独立，可与 01 并行）

**Status:** resolved

## Answer

- [x] scan/compare 阶段规则化识别残留（保守名单：构建产物 + 备份 + 临时文件），确定性归入 exclude
- [x] 残留不进 AI 判定范围、不进两阶段摘要
- [x] 报告 exclude 清单含残留条目，reason 为规则化原因
- [x] 测试：带 .o/.bak 的旧工程 → 报告含残留条目且带规则化原因；扫描清单不含残留

实施要点：`master.py` 新增 `RESIDUE_RULES` 保守名单（.o/.axf/.hex/.map 构建产物、.bak/*~ 备份、.tmp/.temp 临时文件，后缀判定、大小写不敏感）与 `residue_reason()`；`scan_project` 把命中路径单独记录进 `ProjectStructure.residues`，不进 files/file_hashes、不读内容；`compare_projects` 汇总并集到 `ProjectComparison.residues`（不进公共 / 冲突 / 独有分类，也就进不了 AI 判定素材与两阶段摘要）。`assemble_report` 给每个残留路径自动生成 exclude 条目（reason 如"构建产物：.o 文件"），AI 判定残留路径是越界、直接拒绝；`_validate_report` 新增 `_validate_residue_disposition`：残留必须恰好剔除一次，用户确认改成 keep/merge 或删掉条目都拒绝（删掉 = 黑盒消失，违反 ADR 0001）。假旧工程已带 .o/.bak/.hex/~ 残留物，报告 / 落盘 / webapp 端到端断言全绿。
