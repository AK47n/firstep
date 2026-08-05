# 04 — 模板 main.c：母版自带最小系统板空 main

**What to build:** 提炼落盘后母版写入**确定性模板 main.c**（非 AI 生成）：各平台一个空工程 main（时钟初始化 + while(1) 空循环 + TODO 区），能直接编译烧录；旧工程里的 main.c 一律不进母版（ADR 0002）。生成器仍会在生成时用按赛题的 AI 骨架覆盖它（generator.py 现状，不改）。

**Blocked by:** 无（独立，可与 01 并行）

**Status:** resolved

## Answer

- [x] stm32 / mspm0 各一份模板 main.c（最小系统板空工程，可编译）
- [x] apply_distillation 落盘后写模板 main.c；旧工程 main.c 不复制进母版
- [x] 母版候选含模板 main.c 后，analyze_structure 仍通过（IDE 可打开）
- [x] 测试：提炼出的母版含模板 main.c、不含任何旧 main.c；模板 main.c 与平台匹配

实施要点：`master.py` 新增模板机制——`TEMPLATES_DIR`（`templates/` 目录，与 webapp 的 `static/` 同一加载模式）+ `main_c_template(platform)`（按平台词表取 `main_stm32.c` / `main_mspm0.c`，未知平台拒绝）+ `main_c_reason()`（任意层级的 `main.c` 命中规则化原因，大小写不敏感——Windows 下 `MAIN.C` 也是 main 文件，与残留规则同一理由）+ `MAIN_C_TEMPLATE_REASON`。与残留同模式（ADR 0001 不做黑盒消失）：`scan_project` 把旧 main.c 单独记录进 `ProjectStructure.main_c_files`（不进 files/file_hashes、不读内容），`compare_projects` 并集到 `ProjectComparison.main_c_files`（不进公共 / 冲突 / 独有分类，也就进不了 AI 判定素材与两阶段摘要）；`assemble_report` 给每个旧 main.c 自动生成 exclude 条目（规则化原因），AI 判定 main.c 是越界、直接拒绝；`_validate_report` 新增 `_validate_main_c_disposition`（与 `_validate_residue_disposition` 共享抽取出的 `_validate_forced_exclusions`）：旧 main.c 必须恰好剔除一次，用户确认改成 keep/merge 或删掉条目都拒绝；`apply_distillation` 在 keep/merge 落盘后写平台模板 main.c（在 try 内，失败不留半成品）。模板内容：stm32 = Keil5 标准外设库风格（`stm32f10x_conf.h` + `SystemInit`），mspm0 = CCS SysConfig 风格（`ti_msp_dl_config.h` + `SYSCFG_DL_init`），都含时钟初始化 + while(1) 空循环 + TODO 区。假旧工程的两个 main.c 已改为内容不同（冲突场景也一律剔除），webapp 端到端（提炼报告 exclude 带 main.c 条目、确认入库后母版 main.c = 模板、用户把 main.c 改回保留被 400 拦截）全绿。

已知边界（代码评审确认，不属本工单范围）：模板 main.c 固定落位母版根 `main.c`（`MAIN_C_TEMPLATE_PATH`）；正点原子风格 `USER/main.c` 等子目录 main 同样被确定性剔除，但合并后的 .uvprojx 若仍引用子目录路径，其一致性归 AI 整合 uvprojx 的职责（AI 判定素材已不含 main.c，报告会向用户预览模板 main.c）。
