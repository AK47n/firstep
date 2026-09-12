# 06 — 端到端冒烟 + 文档 + 回归

**要做什么：** 用本机临时 HTTP 服务模拟「Release + 完整包资产」，把「检查 → 下载 → 校验 → 应用落位 → 基线写回」整条链路真跑一遍，证明用户路径是通的（不是只有单测绿）；同时把发布流程、领域词表与用户文档补齐到与实际行为一致。

**被谁阻塞：** 05（前端入口与进度可用）

**状态：** resolved

- [x] 端到端冒烟脚本：临时目录造迷你完整包 → 本机 HTTP 资产服务（模拟 Release 列表 + 分卷 + 清单）→ 走 check → apply → status → 更新器落位 → 断言目标目录文件、基线清单、删除生效、备份生成
- [x] 断点续传真跑：中途杀掉下载再重试，断言只补未完成卷
- [x] 发布流程文档更新：完整包打包命令、资产命名与上传、tag 约定、校验步骤、以及「zip 完整包为推荐路线 / 7z 完整包保留」的口径
- [x] 领域词表更新：完整包 / 全量下载 / 基线 / 双轨 等术语与端点登记
- [x] 用户文档更新：README 获取方式与更新路径段落说明「一键下载完整 firstep」与「有基线只下变化部分」
- [x] 版本记录：若本次发布涉及版本号变动，同步工具版本号、打包元数据与对外版本声明（无变动则显式说明理由）
- [x] 全量回归：Python 测试全绿、前端 JS 测试全绿、类型检查干净、脚本编码与仓库语言规范检查通过
- [x] 真机项（需要真实 Release 才能验的那部分）登记到真机挂账单，不在本工单内假装完成

## 实施记录（2026-09-13）

**端到端演练**（`.scratch/full-download/e2e_full_download.py`，7 步全通过）

链路 = 发布侧真打包核心 → mock GitHub 资产服务（真实 HTTP）→ check → 真下载任务（真流式 + 每卷 SHA256）→ 更新器落位。断言覆盖：
- 分卷落盘与哈希逐卷一致；清单落盘与返回值一致；删除清单 = 基线有而当前无；
- 清单带资料库基线（落位后可直接转增量）；
- 落位：包内文件覆盖、资料库内容 v0 → v1、废弃文件被清、备份生成（旧内容还在）、已装标记 = v1.1.0、
  结果记录 `mode=full`、更新中锁释放；
- **不进包的第三方安装包原地不动**；收尾确认「全量完成后本地已有基线」。

**真机冒烟**（`.scratch/full-download/smoke-full-update.mjs`，9/9 PASS）——见工单 05 的实施记录；截图 `shot-full-update-window-dark.png`。

**文档**
- `docs/agents/releasing.md`：新增「完整包（zip 分卷）流程」（打包命令、四件套命名、上传到同一个软件 tag 的 Release、校验、把本版清单存为下次 `-Baseline`、与 7z 路线的关系）；「何时发 Release」加一条；快速发版段补完整包命令。
- `CONTEXT.md`：新增两条领域词条——「资料库基线」（有/无基线的判定与一次性状态）与「一键全量下载」（四端点 + 卷级断点 + 更新器链路 + 智能双轨 + 包内边界）。
- `README.md`：获取方式表补「已装用户不必再走 7z 完整包」；三级发布说明补「一键全量下载」；常见问题补「一键下载完整 firstep」操作路径与失败日志位置；第三方安装包不进包的口径写进说明。

**版本记录（显式说明为何不改 VERSIONS.md）**
- 本次**未发版**：仓库当前 `__version__` / `pyproject.toml` / README 声明的仍是 v1.0.0（已对齐），本特性随下一次发版一起走。
- `VERSIONS.md` 是**定稿区**（面向用户的版本要点，只在真发版时写），且本仓库既有先例明确「未发版 = 零真实条目」；`tests/test_repo_language.py::test_versions_entries_are_chinese` 也按「空通过」处理。故本次**不加**假版本区块（加了会在前台版本卡片里显示一个并不存在的版本）。
- 用户可见变更已进 `CHANGELOG.md` 草稿区（提交信息自动补录）；下次发版时由发布者归纳成 v1.1.0 要点。

**回归**
- Python 全量：**4269 passed / 1 skipped**（提交 04 时点；本工单新增用例后复跑见提交前结果）。
- 前端 JS：**1550 pass / 0 fail**。
- 类型检查：本次新增/改动的模块（`full_pack` / `full_update` / `full_task` / `full_apply` / `materials_pack`）**mypy 干净**；全库 `mypy src/contest_generator` 仍有 6 处**存量**错误，全部在 `pin_bindings.py`（本特性未触碰该文件）。
- 规范门禁：`test_ps1_encoding`（pack-full.ps1 带 BOM）/ `test_repo_language`（工单与 spec 中文）/ `test_onboarding_docs` 全绿。

**本轮修掉的真 bug（e2e 抓出来的）**
- **删除清单没进清单 JSON**：发布侧只写了 `removed.txt`，而更新器按 URL 只读 `manifest.json`——线上「废弃文件清理」会**静默不执行**。已修（`build_full_manifest(removed=...)` + `prepare_full_package` 落盘），并补两层回归：打包侧断言清单 `removed` 字段、更新器侧断言按清单 `removed` 真删（另测「清单无 removed 键 = 老资产 → 跳过删除不报错」）。

**真机项**
- 已登记 `.scratch/real-acceptance/issues/01-real-machine-acceptance.md` **G1**（真实 Release 发布演练：打包 → 上传 → 无基线环境一键全量 → 核对保留项与基线写回 → 弱网/失败演练），含命令、前置证据与本机 e2e/冒烟结果；缺的只是「真的发一次 Release」。
