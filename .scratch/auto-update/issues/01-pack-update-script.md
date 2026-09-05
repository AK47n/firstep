# 01 — 发布侧：更新包打包脚本 + 发版流程文档

**要做什么：** 发布者（开发者）能一条命令生成小发版更新包四件套（zip / 文件清单 / 删除清单 / SHA256），并让 releasing.md 的「小发版」流程可照做：跑脚本 → 传更新包附件 → 提交版本号与 README 同步。

**被谁阻塞：** 无——可立即开始（本工单全部为新增文件：`tools/pack-update.ps1` 与文档改动，与代码查看器优化零文件交集）。

**状态：** resolved

- [x] `tools/pack-update.ps1`：必填 `-Tag`（如 v1.1.0），可选 `-Baseline`（上次发布的 files.txt）与 `-OutDir`；用 `git archive` 打仓库 tracked 快照（顶层白名单 = src/library/sources/tests/docs/assets/tools/.githooks + 根级配置与启动/安装脚本，**含 VERSIONS.md**——评审发现原白名单遗漏，已补），zip 内顶层 = 仓库根；**不含** `.scratch`、`.venv`、`sources/materials`、`.git`、日志
- [x] 脚本产出四件套：`firstep-update-<Tag>.zip`、`.files.txt`（zip 内相对路径清单，每行一个）、`.removed.txt`（有 `-Baseline` 时 = 基线中已不在当前清单的文件；无基线 = 空）、`.sha256.txt`（zip 的 SHA256）
- [x] 脚本默认拒绝在工作树有 tracked 未提交变更时打包（`git status --porcelain --untracked-files=no` 非空即退出，中文提示；`-AllowDirty` 可豁免）；`.ps1` 存成 UTF-8 with BOM
- [x] 实跑一次（临时 OutDir）：四件套齐全；抽查 zip 内容与 files.txt 一致（4370 文件双向零差异）、无 `.scratch` / `sources/materials` / `.venv` 条目、含 `VERSIONS.md`；无基线 removed 为空
- [x] `docs/agents/releasing.md` 写入「小发版」流程：跑脚本 → 上传四件套 → 发版前同步 `__version__` / pyproject version / README / VERSIONS.md；「大发版（资料库）」流程保留

## Answer

脚本（`tools/pack-update.ps1`，UTF-8 with BOM）在先前会话已随本工单实现，本次收尾补齐：① 顶层白名单补入 `VERSIONS.md`（原遗漏会导致更新包丢失用户可见版本记录）；② 实跑验证 v1.1.0 四件套（293.4 MB / 4370 文件，zip 与 files.txt 双向零差异，无 .scratch / sources/materials，含 VERSIONS.md）；③ `docs/agents/releasing.md` 重写为两级发布流程（小发版更新包 / 大发版完整包）+ 发版前三处版本号同步清单。注意：edit 工具重写 .ps1 会丢 BOM，改后必须恢复（`test_ps1_encoding.py` 兜底）。
