# 04 — 本机离线演练 + 账本收口：不发版也能证明「盘面与全新安装一致」

**要做什么：** 用一条可复跑的命令证明修复成立：把沙箱还原成真 v1.1.1 → 用**本机打出的修好的
小发版包**（不出网、不发版）走产品自带的更新器 → 复算构成，判据 = 盘上**不存在**完整包不会给的
产品文件（`not_in_official == 0`）。并把这一轮的更正写进账本。

**被谁阻塞：** 01、02、03。

**状态：** resolved（2026-09-19）

**完成记录。** 演练脚本 `.scratch/update-orphan-files/drill-offline.py`（`--write` 才动沙箱；
`--skip-pack` 可复用已有包），一次跑完七步：前置事实 → 重建真 v1.1.1（8.7s）→ **植入旧版残留**
（从 v1.1.1 发行集合里确定性取 5 条「本版不再发」的真实路径，否则删除清单这一步没东西可删）
→ 本地打修复包（`pack-update.ps1 -Baseline firstep-pack\firstep-update-v1.1.1.files.txt`，
11.1s）→ 产品自带更新器应用（`--no-stop --no-restart --skip-pip`，10.6s）→ 构成复算 → 收尾检查。

**判据全绿（`verify-offline-drill.{txt,json}`）**：

| 判据 | 实测 |
|---|---|
| **`not_in_official == 0`** | **0**（改动前同一口径是 1482） |
| 盘面 vs 完整包文件集 | 盘上 3071 / 完整包 3071：逐字节一致 3068、不同 3（`egg-info` 三件，由 `pip install -e .` 重写，本次 `--skip-pip` 未动）、盘上多出 **0**、盘上缺 **0** |
| 植入的旧版残留 | **全清**（5 条：`library/revise-backups/**` 三条 + `sources/car/**/.settings/*.prefs` + 一个 `.vscode` 文件） |
| 包内容 | 产品文件 **2858** 条（0 条 `revise-backups` / 0 条 `*.exe`）；累计删除清单 **4599** 条 |
| 应用后版本 | 盘上 `__init__.py` = `1.2.1` |
| 隔离 | 8020 无监听、真身数据目录 mtime 未变、8000 上用户自己的实例全程未被碰（演练一律 `--no-stop`） |
| 总判 | **判红 0 / PASS** |

**演练逮到的两个真问题**（都已修，这类「判据看着成立、盘上却少了东西」只有端到端跑才看得见）：

1. **删除清单差点删掉本版仍在发的文件**：第一跑拿**小发版清单**当「本版发行集合」的基准，
   而完整包会发一批**未被 git 跟踪**的产品文件（`library/masters/**/Project.uvguix.luoji`、
   `sources/contest/**` 下的构建产物与 `*.pdf`）——它们被写进了删除清单、应用时**真被删掉**
   （那一跑 `not_in_official == 0` 成立、而盘上少了那些文件）。修法：新增
   `full_pack.product_paths`（扫树取路径、不算哈希）+ `pack_update.current_release_files`
   （小发版清单 ∪ 工作树产品文件），删除基准取**两者并集**。修后删除清单从 7509 条降到
   4599 条（差的就是那批不该删的）。
2. **打包脚本按 tag 找基线找错了**：PS 的 `GetFileNameWithoutExtension` 只削一层扩展名，
   `firstep-update-v1.1.1.files.txt` 被切成 `v1.1.1.files` → 去找一个不存在的兄弟名 →
   **拒绝发版**（拒绝得对，但原因是我自己的 bug）。修法：tag 推导与两向定位收进 Python
   （`full_pack.release_tag_of` / `find_baseline_parts` / `find_update_files_for`），
   有单测钉住（`test_release_tag_of_handles_dotted_tags`）。

**账本已更新**：`.scratch/backlog.md` 第 8 节三行按更正后的口径重写（并写明本轮不发版）；
`docs/agents/local-environment.md` 第 0 节（挂账 6 笔 + 两个工具坑）、第 1 节（沙箱现状 =
v1.1.1 起点 + **本机**修复包）、第 1.5 节（B2 两格已转绿）、第 2 节（8000 现在在跑 = 用户自己的
实例）、第 3 节（main 领先线上资产）。

## 为什么不是重跑 drill-01

`drill-01-upgrade.py` 从**线上 release 真下载**更新包，所以它的判据要成立就必须先换线上资产。
本轮拍板：**不发版**（真机 drill-01 留给下一个版本号，见 spec「范围外」）。因此本单用离线口径
拿同样的证据：包在本地打、更新器是产品自带的那支、沙箱是真 v1.1.1、构成复算沿用 drill-01 的
同一套口径（顶层白名单 + 排除 `sources/materials`）。

## 验收标准

- [ ] 新增 `.scratch/update-orphan-files/drill-offline.py`（`--write` 才落盘/动沙箱）：
      - 前置断言：沙箱起点是真 v1.1.1（复用 `.scratch/update-restart-stale-service/rebuild-sandbox-v111.py --write`，
        并把它的结论逐条记进证据）；
      - 用 `tools/pack-update.ps1 -Baseline firstep-pack\firstep-update-v1.1.1.files.txt`
        在本机打一份修复后的包到**一次性输出目录**（不覆盖 `firstep-pack/` 里的线上资产）；
      - 用产品自带的 `tools/update-app.py` 把它应用上去（`--no-stop --no-restart --skip-pip
        --data-dir <一次性目录>`，`--skip-pip` 是硬要求：沙箱没有 `.venv`，全局
        `pip install -e .` 会污染全局 site-packages，见 `local-environment` 第 2.5 节）；
      - 复算构成：沙箱盘面（顶层白名单 / 排除 `sources/materials`）vs **本机**按
        `full_pack.scan_tree` 算出的完整包文件集；
      - 判据：`not_in_official == 0`；`official_missing_on_disk` 只允许
        `src/contest_generator.egg-info/*` 与 `sources/materials/*`（前者由 pip 重写、
        后者由资料库增量包负责，且本次 `--skip-pip` 未重装）；把这两个例外**逐条写进判据**，
        不许用模糊的「忽略若干」；
      - 隔离不变量：真身 `~/.contest_generator` mtime 未变、8020 跑完释放
        （8000 上是用户自己的实例，本演练一律 `--no-stop`，不碰它、也不拿它当判据）；
      - 原始输出落 `verify-offline-drill.{txt,json}`（进仓库，供复核）；
      - 额外一步（不在原计划里，但**必须**）：**植入旧版残留**再验删除清单——
        v1.1.1 的完整包本来就不含 `revise-backups`/`*.exe`，不植入的话「删除清单」这一步
        等于没验。
- [x] 判红对照：**第一跑就是判红对照**——产品侧的 `not_in_official == 0` 成立，但盘上少了
      本版仍在发的文件（`Project.uvguix.luoji` 等），证明这条判据不是恒真；修掉后复跑 PASS
      （细节记在完成记录里）
- [x] 账本更新：
      - `.scratch/backlog.md` 第 8 节三张单按更正后的口径重写（并写明本轮不发版）；
      - `docs/agents/local-environment.md` 第 0/1/1.5/2/3 节按本轮事实更新；
      - 本目录工单里记下**这一轮没有发版**，以及下次发版时要带上的判据
        （真机 drill-01 + `not_in_official == 0` + B2 两格）
- [x] 全仓测试跑一次绿（`python -m pytest -n auto -q`）→ 见本轮提交记录
