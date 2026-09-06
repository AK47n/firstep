# 04 — 收尾：影响面核对与常量注释回填

**要做什么：** 预筛落地后的收尾——既有「prompt 逐字」断言类测试逐一核对修正；预算常量按红证实测回填注释；仓库惯例（CONTEXT 平台行 / CHANGELOG）补录；code-review 双轴审查。

**被谁阻塞：** 03。

**状态：** ready-for-agent

- [ ] 全量 grep「模块库可用模块」相关断言，核对预筛注记契约对既有测试的影响（逐字断言允许「未截断零变化」），必要时修正测试或注释
- [ ] `budget.py` / `llm.py` 记账注释按红证实测数值回填（MODULE_SUMMARY_BYTES / REFERENCE_FULLTEXT_BYTES 最终值 + 推导链）；spec 更新参数定值
- [ ] CONTEXT.md 平台行 / 变更记录按仓库惯例补录
- [ ] code-review 双轴（Standards / Spec）审查通过并整改
- [ ] 全量测试（pytest + node）全绿；提交信息中文
