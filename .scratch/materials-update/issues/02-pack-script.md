# 02 — 发布侧：pack-materials.ps1 薄封装 + 发版流程

**要做什么：** 发布者一条 PowerShell 命令跑完资料库打包：扫描 → 调用 01 核心逻辑 → 产出规范命名的资产（清单 JSON + 批次 zip/part + 各卷 SHA256），并把发行步骤写进 `docs/agents/releasing.md`。

**被谁阻塞：** 01

**状态：** resolved

- [x] `tools/pack-materials.ps1`（UTF-8 with BOM 硬约定）：参数 `-Tag`（必填，`materials-vX.Y.Z` 文法校验）+ 模式 `-Diff`（默认，从 `-Baseline` 本地路径或 `-BaselineUrl` 拉上版清单）/ `-Init`（只出清单）/ `-Full`（全量批次分卷包）+ `-OutDir`
- [x] 资产命名规范：`firstep-materials-<tag>.manifest.json`、`firstep-materials-<tag>-<slug>.zip`（分卷 `.part<N>`）、每卷 `firstep-materials-<tag>-<slug>[.part<N>].sha256.txt`
- [x] 摘要输出（总增量大小 / 文件数 / 批次数 / part 数），非零退出码机器可判
- [x] `docs/agents/releasing.md`：资料库发版步骤（tag 命名 `materials-vX.Y.Z`、打包命令、资产上传清单、下版基线 = 本版清单）
- [x] 测试：`tests/test_ps1_encoding.py` 兜底（若仓库有该检查则断言新脚本通过）；脚本冒烟跑通 `-Init` 迷你目录

## Answer

`tools/pack-materials.ps1`（UTF-8 with BOM）：薄封装 Python CLI `contest_generator.materials_pack:main`——`-Tag`（仅打 `[A-Za-z0-9._-]` 防注入）+ `-Mode init|full|diff` + `-Baseline`（本地路径或 URL）+ `-Tree`/`-OutDir`/`-Python`/`-AllowDirty`；PYTHONPATH=src；非零退出码 throw。资产命名 `firstep-materials-<tag>[-<slug>].zip`（分卷 `.part<N>`）+ `<tag>.manifest.json`（下一版基线）。冒烟：init 与 diff（假基线）迷你目录均产出正确清单与 zip；BOM 已加（PS 5.1 安全）；`tests/test_ps1_encoding.py` / `test_repo_language.py` 全绿。`docs/agents/releasing.md` 大发版流程改写为「资料库增量包」并保留完整包路线。
