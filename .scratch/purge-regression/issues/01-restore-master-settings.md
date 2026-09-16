# 01 — 还原被误删的 mspm0 母版 `.settings/`（含 CCS 编码钉）

**要做什么：** 生成出来的 CCS 工程重新带上 UTF-8 工程编码；清理器再遇到这类「看着像 IDE 状态、
其实是工程配置」的文件时**停下来要求人工确认**，而不是静默删掉。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] 还原 `library/masters/mspm0/.settings/org.eclipse.core.resources.prefs`
      （`encoding/<project>=UTF-8`）与 `org.eclipse.cdt.codan.core.prefs`
- [x] 还原判据 = **两处独立来源逐字节同源**：线上 `firstep-full-v1.2.0.zip` 与沙箱
      `firstep-sim`，sha256 `1a5b17d8a429…` / `6c355f2f86ad…`（含 CRLF）
- [x] `.gitignore` 加母版例外（`!library/masters/*/.settings/` + `*.prefs`）——
      不加则 `git add` 直接被拒（`paths are ignored`），文件在盘上也不进包
- [x] `scripts/make-purge-list.mjs`：新增 `KEEP` 例外（母版 `.settings/` 不算 IDE 状态）+
      `.prefs`/`.ccsproject`/`.cproject`/`.project` 进「命中即要人工确认」闸门 +
      报告里显式打印「例外保留 N 个」
- [x] **反证（闸门）**：把 `KEEP` 临时清空重跑工具 → **退出码 1** + 点名那两个文件
      「⚠ 有 2 个命中不是"已知的生成文件"，请人工确认后再删」——正是当初该发生的动作
- [x] **反证（守卫）**：搬走编码钉 → `test_master_template_config.py` 红；搬回 → 绿（sha256 复核）
- [x] 连带修复确认：`tests/test_readme.py::test_directory_structure_syncs_with_master_templates`
      由红转绿 → 全套 **4472 passed / 1 skipped / 0 failed**

## Comments

- 忽略规则的注释原本写着「规则只写**确认过**的……确认全是产物才写进来」——这一条恰恰违反了
  自己的规矩：`.settings/` 是按目录名一刀切的，没按内容确认。**教训**：按目录名/扩展名扫的规则
  必须有「例外 + 人工确认闸门」两件配套，光靠注释里的自我要求不管用。
- 这条回归在 main 上活了一天没人发现，直接说明「跑全套太慢/太可怕」是真成本——
  同一轮的 `test-speedup` 工单就是冲这个去的。
- **未了**：线上 v1.2.0 的完整包仍缺这两个文件，必须随下一个版本发出去
  （`docs/agents/local-environment.md` 第 0 节）。
