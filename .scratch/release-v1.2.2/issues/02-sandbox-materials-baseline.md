# 02 — 沙箱补资料库基线：沙箱的「资料库更新」不再报 baseline-missing

**要做什么：** 沙箱「模拟用户机」的 `sources/materials/.materials-manifest.json` 落位，
让沙箱的「设置 → 资料库更新」从 `error=baseline-missing`（「版本未知」）变成正常识别版本。

**被谁阻塞：** 无——可立即开始。**但执行时机排在工单 04 之后**（见下方 Comments 第 1 条）。

**状态：** ready-for-agent

- [ ] 基线的判据与真身同一套：与本机 `sources/materials` 逐文件 sha256 对比**全等才写**
      （`--write` 才落盘，缺省 dry-run 只对比）
- [ ] 工具根指向沙箱（`C:\Users\luoji\Desktop\firstep-sim`），**真身数据目录
      `~\.contest_generator` 与真身工具根零触碰**
- [ ] 写进去的版本号与沙箱**当时盘上的版本一致**（不制造「本地旧、基线新」的假差异）
- [ ] 复跑沙箱的 `GET /api/update/materials/check`，`error` 从 `baseline-missing` 变为
      预期值（无发布资料库更新包时为 `no-release`），原始输出落证据文件
- [ ] 沙箱 8020 演练收尾后释放；真身 8000 全程只读

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
