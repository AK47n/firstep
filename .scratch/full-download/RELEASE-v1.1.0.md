# v1.1.0 发布记录（2026-09-13）

**Release**：https://github.com/AK47n/firstep/releases/tag/v1.1.0
**tag**：`v1.1.0` → `d9d14e8b`（已推远端；`main` 与 `origin/main` 同步，此前落后 139 个提交已一并推上）
**标题**：firstep 电赛工程生成器 · v1.1.0（三段式更新：一键更新 / 资料库增量 / 一键全量）

## 上传的 8 件资产

| 资产 | 大小 | 用途 |
|---|---|---|
| `firstep-full-v1.1.0.zip` | 783.29 MB | 一键全量（整份 firstep，1 卷） |
| `firstep-full-v1.1.0.manifest.json` | 3.55 MB | 完整包清单（8774 文件 + 资料库基线 12 批次 / 5087 文件 + 删除清单） |
| `firstep-full-v1.1.0.removed.txt` | 注释行 | 删除清单（本次无删除项） |
| `firstep-full-v1.1.0.sha256.txt` | 小 | 分卷校验和 |
| `firstep-update-v1.1.0.zip` | 295.98 MB | 小发版一键更新（5036 文件） |
| `firstep-update-v1.1.0.files.txt` | 0.30 MB | 更新包文件清单（下次小发版的删除清单基线） |
| `firstep-update-v1.1.0.removed.txt` | 注释行 | 删除清单（首次发布 = 无基线） |
| `firstep-update-v1.1.0.sha256.txt` | 小 | 更新包校验和 |

## 发布前动作

1. 版本号三处同步 → `1.1.0`：`src/contest_generator/__init__.py`、`pyproject.toml`、`README.md`
2. `VERSIONS.md` 新增 v1.1.0 区块（主题 + 6 条用户可见要点；把 v1.0.0 之后累计的「应用内一键更新」「资料库增量更新」一并记为 1.1.0）
3. 打包：`tools\pack-update.ps1 -Tag v1.1.0`（296 MB）+ `tools\pack-full.ps1 -Tag v1.1.0`（783 MB）

## 验证证据（全部实跑）

| 验证 | 脚本 | 结果 |
|---|---|---|
| 四件套自洽（哈希可复算 / zip 与清单逐条一致 / 基线文件全在包内 / 不含安装包） | `.scratch/full-download/verify_release_assets.py` | **26 项全过** |
| 线上资产：从 Release 重新下载两个 zip 重算 SHA256 | `.scratch/full-download/verify_published_assets.py` | **两个 zip 与校验和一致**；线上清单 8774 文件 / 12 批次 |
| 真机端点（真实 GitHub API） | `.scratch/full-download/verify_live_endpoints.py` | **15 项全过**（health=1.1.0、完整包 v1.1.0 / 1 卷 / 清单地址就绪、小发版「已是最新」、资料库 `baseline-missing`） |
| 端到端链路（发布 → 检查 → 下载 → 应用落位） | `.scratch/full-download/e2e_full_download.py` | **7 步全通过** |
| 浏览器窗口（真点击） | `.scratch/full-download/smoke-full-update.mjs` | **9/9 PASS** + 截图 |
| 全量回归 | `pytest` / `node --test tests/js/*.test.mjs` | **4309 passed / 1 skipped**；**1550 pass** |

## 现场踩坑

- **空 `removed.txt` 被 GitHub 拒收**：0 字节资产 → `gh release upload` 报 `HTTP 400: Bad Content-Length`。改写为 `# 注释行`（更新器 `remove_removed_list` 跳过 `#` 行，语义不变）后上传成功。已开工单 `full-download/08`，要求发布侧生成时就写注释行。
- **两个打包器的换行符口径不一致**：`pack-update`（git archive，应用 `.gitattributes` + 本机 `autocrlf=true` → CRLF）与 `pack-full`（读工作树 → LF）对 3474 个共有文件有 926 个字节不同，**真实内容差异 0**。本次不影响（首个完整包、无上一版基线可比；两条路线各自自洽），但下次发布会让增量 diff 把文件判为「已修改」而近全量重下。已开工单 `full-download/08` 并附不变量测试要求。

## 遗留

- 工单 `full-download/07` / 真机挂账 **G1 后五步**：在**无基线的用户环境**演练客户端链路（下载 → 替换 → 重启 → 保留项核对 → 弱网 / 失败演练）。
- 工单 `full-download/08`：跨包字节一致性 + 空删除清单注释行（发布侧）。
