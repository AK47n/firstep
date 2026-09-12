# 01 — 发布侧：完整包打包核心 + pack-full 脚本

**要做什么：** 发布者一条命令打出「完整 firstep 包」四件套：zip 分卷（单卷装不下自动拆、每卷独立 SHA256）+ 完整包清单（含包内全部文件清单与资料库基线清单）+ 相对上一版完整包的删除清单 + 校验和汇总。包里**只有会变的内容**：工具本体、五个库、资料库内容文件；第三方安装包与视觉 SDK 打包件、缓存、备份目录、日志都不进包。产物之间必须自洽（清单里的每个文件和分卷都能在 zip 里找到、SHA256 可复算），否则用户侧下载与更新器都会失准。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 打包核心逻辑为纯函数 + 薄 I/O：可对临时目录造的迷你仓库树单测，不碰网络
- [x] 排除规则单源登记，且对四类干扰件生效：资料库内的第三方安装包 / SDK 打包件（`*.exe`、`*.msi`、`*.rar`、`*.7z`、`*.img`、`*.img.gz`、`*.img.xz`、`*.z01`、`*.z02`、`*CCS_20.5*`、`*tsp-xbhdcc*`、`*ubuntu-20.04*`、`*dataset.zip*`、`*05_SPI*.zip`）、依赖与虚拟环境（`node_modules` / `.venv`）、缓存与工作区（`__pycache__` / `.pytest_cache` / `.mypy_cache` / `.scratch` / `.git` / `*.log`）、本地备份目录（`library/fix-backups`、`library/revise-backups`、`sources/.trash-pdf`）
- [x] 完整包清单契约落地：`{version, published_at, total_bytes, parts: [{zip_name, size, sha256}], files: [{path, size, sha256}], materials_manifest: {...}}`；`files` 覆盖包内全部文件（既是删除清单基线，也是资料库基线来源）
- [x] `materials_manifest` 与资料库扫描结果一致（批次 / 文件集 / 版本），落位后可直接写入 `sources/materials/.materials-manifest.json`
- [x] 分卷：单卷超 1.9 GB 自动拆 `firstep-full-<tag>.part<N>.zip`，未超则为 `firstep-full-<tag>.zip`；每卷独立 SHA256 且可复算
- [x] zip 内条目路径 = 仓库根相对 POSIX 路径（解压即覆盖）；中文文件名原样保留
- [x] 删除清单：以传入的上一版完整包清单为基线算「基线有、当前无」；无基线 = 空清单（更新器跳过删除），不报错
- [x] PowerShell 薄封装脚本（UTF-8 with BOM）：一条命令跑完扫描 → 打包 → 写清单 / 删除清单 / SHA256，并打印产物路径与总体积
- [x] 单测：临时目录迷你树（含中文目录名 + 一个 `.exe` + 一个 SDK 打包件 + 一个 `library/fix-backups` 干扰件）断言「干扰件不进包 + 清单与 zip 内容一一对应 + 排除件确实缺席」
- [x] 单测：分卷切分（含单文件超限单独成卷）与 SHA256 可复算
- [x] 单测：删除清单（有基线 / 无基线两态）
- [x] 脚本冒烟：迷你树上真跑一次，产出四件套且体积 / 卷数符合预期

## 实施记录（2026-09-13）

**实现面**
- 新增 `src/contest_generator/full_pack.py`：排除规则单源（`TOP_LEVEL_ENTRIES` / `SKIP_DIR_NAMES` / `SKIP_FILE_NAMES` / `SKIP_FILE_SUFFIXES` / `INSTALLER_GLOBS`）、`scan_tree`、`excluded_paths`（带原因，供体检与防回归）、`build_full_manifest`、`split_volumes`、`build_zip_volumes`、`prepare_full_package`、CLI `main`。
- 新增 `tools/pack-full.ps1`（UTF-8 **with BOM**，硬约定）：`-Tag` / `-Baseline` / `-Tree` / `-OutDir` / `-Python` / `-LimitMB` / `-AllowDirty`；含工作树脏检查与四件套确认。
- `materials_pack` 三处配套改动：`scan_materials` / `scan_as_manifest` 增加 `exclude` 谓词（清单与包同口径）、新增 `derive_slug` / `register_dir_slugs`（未登记中文目录的确定性补登记）。
- 测试 `tests/test_full_pack.py` 24 例（24 passed），另跑 `tests/test_materials_pack.py` 无回归。

**真机实测（本机仓库，2026-09-13）**
- 包内 **8764 个文件 / 原始 1069.9 MB**；资料库内容文件 **5087 个 / 688.3 MB**；最大单文件 51 MB（一个教程视频）；`scan_tree` 耗时约 6 s。
- 白名单内排除集合 4224 项，构成：备份目录 4182（`library/fix-backups` + `revise-backups`）、第三方安装包 33+、日志 6；**内容文件零误伤**（专项断言）。
- 迷你树冒烟：`pack-full.ps1 -Tag v0.0.2-smoke -LimitMB 1` 产出四件套（zip 1765 B / 清单 3036 B / removed 空 / sha256 汇总），zip 内条目与清单 `files` 一一对应。

**过程中修掉的两个真问题**
1. **清单与包不同口径**（真 bug）：资料库基线原先用不带排除的扫描，导致 SDK zip 被排除出包本体却仍列在基线清单里——用户侧基线会虚报文件、下载器按清单找不到文件。修法：排除谓词下沉到 `scan_materials`，两条路径同口径；补专项断言「基线文件集合 ⊆ 包内文件集合」。
2. **未登记中文目录阻断发版**：完整包要顺手写资料库基线，而基线走 slug 登记表，新资料目录会把整条打包链路打断。修法：`register_materials_dirs` 对未登记目录做确定性派生 slug（内容寻址，同名恒同 slug），已登记 slug 绝不被覆盖；补幂等与不覆盖两条测试。

**踩坑记录**
- 编辑工具会剥掉 `.ps1` 的 BOM → Windows PowerShell 5.1 按 GBK 解码中文注释 → 行解析错位、脚本报 `Missing closing '}'`。改完 `.ps1` 必须补 BOM（`tests/test_ps1_encoding.py` 兜底）。
- 夹具曾把 `spec.md` 写进临时树的 `.scratch/` 下，被仓库语言门禁扫到（门禁递归 `.scratch` 下所有 `spec.md` / `issues/*.md`）；改用 `notes.md`，且冒烟目录用完即删。
- `.ps1` 调用 Python 时需 `PYTHONIOENCODING=utf-8`，否则中文摘要按控制台 ANSI 编码在 UTF-8 控制台上显示为乱码（文件本体编码一直正确）。

## Comments

- 完整包实际体积比 spec 初稿（约 1.6 GB）小：排除规则定稿后原始 1.07 GB，zip 后约 1.0 GB、按 1.9 GB 单卷上限 = 1~2 卷。spec 内数字已按实测更新。
