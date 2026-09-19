# 02 — 沙箱补资料库基线：沙箱的「资料库更新」不再报 baseline-missing

**要做什么：** 沙箱「模拟用户机」的 `sources/materials/.materials-manifest.json` 落位，
让沙箱的「设置 → 资料库更新」从 `error=baseline-missing`（「版本未知」）变成正常识别版本。

**被谁阻塞：** 无——可立即开始。**但执行时机排在工单 04 之后**（见下方 Comments 第 1 条）。

**状态：** resolved（**判据被证伪——本单无事可做**）

- [x] 基线的判据与真身同一套：与本机 `sources/materials` 逐文件 sha256 对比**全等才写**
      （`--write` 才落盘，缺省 dry-run 只对比）
- [x] 工具根指向沙箱（`C:\Users\luoji\Desktop\firstep-sim`），**真身数据目录
      `~\.contest_generator` 与真身工具根零触碰**
- [x] 写进去的版本号与沙箱**当时盘上的版本一致**（不制造「本地旧、基线新」的假差异）
- [x] 复跑沙箱的 `GET /api/update/materials/check`，`error` 从 `baseline-missing` 变为
      预期值（无发布资料库更新包时为 `no-release`），原始输出落证据文件
- [x] 沙箱 8020 演练收尾后释放；真身 8000 全程只读

## Comments

### 结论：沙箱的基线**早就有了**，本单的前提是错的（2026-09-19）

本单是照 `docs/agents/local-environment.md` 第 2.1 节末那句「沙箱**还没补**」开的。
发 v1.2.2 时按它去准备，一量才发现**那句话不成立**：

| 项 | 实测（量具 `.scratch/release-v1.2.2/measure-baseline.py`） |
|---|---|
| 沙箱基线文件 | `firstep-sim\sources\materials\.materials-manifest.json` **在**（`version=v1.1.1` / 12 批次 / **5087 文件**） |
| 与 v1.1.1 完整包内清单比 | **逐文件全等：只在沙箱 0 / 只在包内 0 / 同名 sha256 不同 0** |
| 谁写的 | `rebuild-sandbox-v111.py` 第四节——按 `tools/update-app.py:write_materials_baseline` 同款口径，从**刚解开的 v1.1.1 全量包清单**写回 |
| 「5087 vs 真身 5081」 | **不是缺陷**：资料库演进（v1.2.0 做过一次库治理回收 6 个重复文件；v1.1.1 = 5087 → v1.2.0 起 = 5081） |

所以本单**没有可交付物**：沙箱不存在 `baseline-missing`，也无「本地旧、基线新」的假差异
（基线版本与盘上版本都是 v1.1.1）。已把 `local-environment` 第 2.1 节那句更正过来
（连同「重建脚本会顺带写回基线」这条事实）。

### 顺带确认的一件事（原验收项第 4 条）

drill-01 的保命项里有「资料库基线清单未变」一格——**成立**，且沙箱升到 v1.2.2 之后
基线会由更新器一路带到 v1.2.2 / 5081（与「全新安装该版本」一致）。本单因此**不需要**
单独跑一次基线写入，判据由 drill 的保命项覆盖。

## Comments

- **1. 为什么依赖边不连 04（用户在澄清里拍板）**：写进去的基线必须与沙箱盘上一致，
  而工单 04 会把沙箱从 v1.1.1 升到 v1.2.2。若在 04 之前写，写的是针对 v1.1.1 的基线；
  04 跑完更新器会自己写回 v1.2.2 的基线（`tools/update-app.py` 的 `write_materials_baseline`），
  本单就白做了。所以：**04 跑完再执行本单**，判据取 04 之后的事实。
  依赖边不连 04 的理由：04 不是本单的**技术前提**（判据、脚本、路径都不依赖它），
  连上去会让「沙箱升到 v1.2.2」看起来像是本单的阻塞源，而事实是**时序**关系。
- **2. 沙箱为什么需要这一步**：`docs/agents/local-environment.md` 第 2.1 节末——
  真身 2026-09-13 就地补过基线（脚本 `.scratch/materials-baseline-writeback/init-baseline.py`），
  沙箱当时「等发资料库增量包前一起补」，一直没补。沙箱走的是 v1.1.1 的完整包，
  那份包里没有基线文件（基线只在完整包替换那一步由 `write_materials_baseline()` 写回）。
- **3. 一条要复核的既有判据**：`init-baseline.py` 的判据是「与**线上 v1.2.0 包内**那份逐文件
  相等」。2026-09-14 重发之后线上包与本机资料库重新同源（12 批次 / 5081 文件），所以
  它现在应该仍然可用于沙箱；若报差异，按 `.scratch/path-budget/rebuild-materials-baseline.py`
  就地重算，并把「为什么不能直接用原判据」记进 Comments。
