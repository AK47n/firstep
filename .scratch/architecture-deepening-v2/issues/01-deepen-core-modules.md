# 01 — 架构深化 v2：报告模型收口 + 确认事务化 + 生成流程接缝 + 工程文件读写底座

**What to build:** 第二轮架构深化（improve-codebase-architecture 驱动，2026-08-05 报告四个可落地候选，全实施）：
1. 提炼报告模型收口：FileDecision 六键形状从 llm/master/webapp/tests 五处手抄归一处（新模块 report.py，动作词表与"merge 必须带整合产物全文与说明"不变量唯一所有者）；补上"报告平台 × 工程平台"交叉校验（此前缺失）。
2. 提炼确认事务化：/api/masters/confirm 的六步编排（重扫 → 重比 → 重建报告 → 暂存 → 落盘 → 入库）从 webapp 壳下沉为 master.confirm_distillation 一个函数。
3. 生成流程接缝成真：选模块 → 母版定位 → 生成 → 摘要的组合操作从 webapp 下沉为 generator.generate_project；母版库布局（masters_dir/<platform>）归母版模块（master_project_dir，带平台名合法性校验）。
4. 工程文件读写底座：keil/ccs 孪生适配器的 _parse/_write/头部回注重复收进 projectfile.py（字节级行为不变）。

**Status:** resolved

## Answer

- [x] report.py：FileDecision + ACTION_* 词表 + ReportError；from_dict 形状校验唯一实现；llm.parse_distillation_report 委托给它（AI 专属检查保留）；master.DistillationReport.from_dict 捕获 ReportError → MasterError；test_llm 的 from_dict 失败断言改为 ReportError
- [x] 平台交叉校验：distill_master 与 _validate_report 都校验报告平台 = 工程平台（_validate_platform_match），确认路径与 AI 路径各一条测试
- [x] confirm_distillation：事务（重扫/重比/from_dict/暂存/apply/import/清理）一个函数，webapp 只剩校验 + 调用 + 转 JSON；test_master 新增事务成功与失败无痕两条直测
- [x] generate_project：组合流程（resolve_selection → master_project_dir → generate → describe_generation）一个入口；master_project_dir 带 _validate_store_key（借平台名逃出母版库从此 400 而非静默穿越）；webapp /api/generate 瘦身
- [x] projectfile.py：parse_project_file / write_project_file（声明行 + head_extra + restore 回注），keil/ccs 各留格式结构知识；ccs 头部与 xmlns 回注字节级不变（test_keil_patcher / test_ccs_patcher 原断言直接过）
- [x] 清理：test_master.py 两对内容相同的重复测试函数（469/480 与 492/503，worktree 合并残留，第二个 def 覆盖第一个）删掉先出现的死副本
- [x] 全量 347 pytest 绿 + mypy 干净；CONTEXT.md 词表补"报告模型"、接缝描述改 generate_project、修改器行补 projectfile 底座
