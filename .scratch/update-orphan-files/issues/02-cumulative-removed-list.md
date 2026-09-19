# 02 — 删除清单改累计口径：跨版升级也能清掉被跳过版本的删除项

**要做什么：** 让每次发布写出的删除清单 = 「历史任一已发布版本发过、而本版不再发的产品文件」。
用户可观察的结果：跳版升级（例：v1.2.0 → v1.2.2）不再留下被跳过版本删掉的文件；
**老用户不需要换更新器**——删除清单是数据驱动的，旧版更新器照单执行。

**被谁阻塞：** 01（产品文件判据单源；累计口径的输入要靠它统一）。

**状态：** resolved（2026-09-19）

**完成记录。** 规则收进 `full_pack`：`cumulative_removed(shipped_before, current)`（唯一算法，
排序输出、跳过空行与 `#`）+ `previous_shipped_files(update_files=…, full_manifest=…, allow_missing_parts=…)`
（上一版**发行集合** = 小发版清单 ∪ 它的 `.removed.txt` ∪ 完整包清单的 `files` ∪ `removed`）
+ `read_release_file_list`。两个打包器都走它：

- 小发版：新增 `pack_update.write_removed_list`（**清单一律由 Python 核心写出**），
  `pack-update.ps1` 只负责找齐输入（`-Baseline` 与它旁边的 `.removed.txt`、OutDir 里同 tag 的
  完整包清单），并新增 `-AllowMissingBaselineParts`；
- 完整包：`prepare_full_package` 新增 `baseline_update_files` / `allow_missing_baseline_parts`，
  `pack-full.ps1` 自动找同 tag 的小发版清单传进去；
- **缺 `.removed.txt` 一律拒绝发版**（`ValueError` 里写明「少了它就写不出完整的累计清单」），
  首次发布等场景用显式开关放行。

| 判据 | 实测 |
|---|---|
| 累计语义（跳版） | 单测：上一版清单里的 `docs/old.md` **与**更早已删的 `docs/older.md` 同时在清单里 |
| 两条路径并集 | 单测：`.files.txt` ∪ `.removed.txt` ∪ manifest `files` ∪ `removed` 四条输入合成一份 |
| 缺兄弟文件 | 单测：抛 `ValueError`；`allow_missing_parts=True` 放行 |
| 空清单占位 | 单测：写一行 `#`（0 字节资产会被 gh 拒收），文件非空 |
| 完整包路径 | 单测：基线清单 `removed` 里的名字照旧被删（`docs/older-page.md`） |
| 更新器零改动 | 既有 `tests/test_update_app.py`（按清单删除 / 路径校验 / 已不存在跳过）全绿 |
| 聚焦测试 | `test_full_pack.py` + `test_pack_update.py` + `test_ps1_encoding.py` + `test_preflight.py` **70 passed** |

判据强度探针加到 **6/6 转红**（`.scratch/update-orphan-files/verify-01-guard-strength.{txt,json}`）：
新增 ⑤「上一版的删除清单不再参与」与 ⑥「只按小发版清单算（完整包发过的那些不再参与）」
两条注入，各自都能让累计口径的用例转红。

真仓库复算放在工单 04 的离线演练里（要跑真打包 + 真更新器）。

## 背景

现在两套删除清单都是「上一版 − 本版」：
小发版 `removed.txt = 基线 files.txt − 本版 files.txt`；完整包 `removed = 上一版清单 files − 本版`。
一个版本区间的洞（用户跳版）就永远清不到。另有一类更难看的：**完整包发过但未被 git 跟踪**的路径
（`sources/contest/**` 下的构建产物，实测 205 个）**从不出现在任何 `files.txt` 里**，
因此小发版路径永远清不到——完整包路径也只能在它们从工作树消失后的那一版清一次。

## 验收标准

- [ ] 发布侧有一个**单源函数**算累计删除清单（`(上一版发行集合) − (本版发行集合)`，
      排序输出、跳过空行与 `#` 注释）；两个打包器都调它，不再各写一段差集
- [ ] 「上一版发行集合」= 上一版小发版清单 ∪ 上一版小发版删除清单 ∪ 上一版完整包清单的 `files`
      （三项都由上一版发布产物提供；打包器按 `-Baseline` 的同名规则在旁边找）
- [ ] **找不到上一版产物就大声失败**（宁可不发版，也不写出比用户盘面短的清单），
      另有一个显式的「首次发布」开关绕过
- [ ] 小发版与完整包两条路径都走这条规则（各有一条单测）
- [ ] 单测覆盖：并集语义 / 跨版删除（上一版删过、上一版清单里没有） / 「删了又加回来不算删除」/
      空行与注释 / 缺产物时抛错
- [ ] 真仓库复算一次（工单 04 的离线演练里）：对 v1.1.1 → 本地的修复包，算出的删除清单
      **⊇** `files(v1.1.1) − files(本版)`，且包含 `library/revise-backups/**` 与那个 `*.exe`
      （它们是「上一版发过、本版不发」）
- [ ] 反向注入探针：把累计改回「只看上一版清单」**必须转红**
- [ ] 更新器（`tools/update-app.py`）**零改动**——它只按清单删，路径校验与「已不存在就跳过」
      照旧；既有 `tests/test_update_app.py` 全绿
