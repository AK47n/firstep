# 04 — 收尾：影响面核对与常量注释回填

**要做什么：** 预筛落地后的收尾——既有「prompt 逐字」断言类测试逐一核对修正；预算常量按红证实测回填注释；仓库惯例（CONTEXT 平台行 / CHANGELOG）补录；code-review 双轴审查。

**被谁阻塞：** 03。

**状态：** resolved

**实施记录：** code-review 双轴（独立子代理，diff = 8ff5f663...aaf98f3b）：

- **Spec 轴（2 项实质）**：① 模块侧「数字尾巴兼容」缺失——slug adc12 从未命中（测试靠描述独立 ADC 词假绿），修复 = slug 走 token 级规则（`_term_matches_token` 精确/前缀+纯数字尾巴）+ 描述文本走边界规则（`_preselect_score` 两层），补 zadc12 负例/描述无独立词钉死用例；② `_term_matches_topic` 对词表大写型号（BMP180/K230/ESP8266）无小写归一 → 纯型号题面漏召回（端到端原靠中文滑窗兜住，测试注释误述），修复 = 整体小写归一 + ascii 段边界 + 中文滑窗，补「采用 bmp180 芯片」3 组用例。spec 同步：截断机制为行边界变体（`_fit_summaries_by_wire`，不劈半行）、返回类型 `PreselectResult`、词源为同包私有互导（events._emit 先例）。
- **Standards 轴（判断性）**：截断器零文案契约以 docstring 明说（标注由调用方注记承担——模型侧不静默）；`scored_summaries` 重复提取；budget.py 占位日期 2026-09-xx → 2026-09-06；工单 01「零命中返回原全量」措辞对齐实现（slug 序零增量，超预算照截断）；测试函数内 import 集中到头部（test_selection / test_llm 两文件）；核心断言补消息。Shotgun Surgery（注记穿透 7+ 触点）判定为垂直切片必要形态，不整改。
- CONTEXT.md 补「推荐候选预筛」领域行（模块摘要行）。
- 整改后验证：2026 真题探测重跑（新件/常备件覆盖保持）、mypy 零新增、全量 3571 pytest + 1358 node 全绿。

- [x] 全量 grep「模块库可用模块」相关断言，核对预筛注记契约对既有测试的影响（逐字断言允许「未截断零变化」），必要时修正测试或注释
- [x] `budget.py` / `llm.py` 记账注释按红证实测数值回填（MODULE_SUMMARY_BYTES / REFERENCE_FULLTEXT_BYTES 最终值 + 推导链）；spec 更新参数定值
- [x] CONTEXT.md 平台行 / 变更记录按仓库惯例补录
- [x] code-review 双轴（Standards / Spec）审查通过并整改
- [x] 全量测试（pytest + node）全绿；提交信息中文
