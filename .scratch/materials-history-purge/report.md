# 仓库体积：`sources/materials/` 历史清理的测量报告（2026-09-16）

**状态：数字已测出，决策未拍板。** 本文件只记测量与代价，不含任何已执行的历史改动。

## 要回答的问题

用户 2026-09-15 起了个头（`probe-A.ps1` 写好但没跑）：**把 `sources/materials/` 从全部历史里
删掉，值多少 MB？** ——`sources/materials/` 现在**不在 HEAD**（`git ls-files sources/materials` = 0，
已进 `.gitignore:33`），但仍在 `main` 自己的历史里（2193 条对象）。

## 方法

`probe-A.ps1`：把原库**硬链接克隆**到 `%TEMP%\sm-probeA`（原库只读、零改动），
在克隆里 `filter-branch --index-filter 'git rm -r --cached --ignore-unmatch -- sources/materials/'`
（`-- --all` + `--tag-name-filter cat`），然后清 `refs/original` + reflog + `gc --prune=now --aggressive`。

## 结果

| 口径 | .git | 说明 |
|---|---|---|
| 现状（原库） | **591.1 MB** | `count-objects`：2 pack / `prune-packable 0` / 松散仅 6 个 → **不是"没 repack"**，`gc` 榨不出来 |
| 基线：克隆里只 repack、不删任何历史 | **292.3 MB** | 参见下面「关键发现」——克隆不含那 6 条旧远端分支 |
| A 级：repack + 删 `sources/materials/` | **123.4 MB** | 相对 repack 基线**净省 168.8 MB**；相对现状省 467.7 MB |

安全性：`src` 225 / `tests` 358 文件数前后相等（零源码损失）；提交 2780 → 2779（prune 掉一个空提交）；
重写耗时 **973 秒**；**四个 tag 的 hash 全被改写**（`v1.1.0` / `v1.1.1` / `v1.2.0` → 新 hash）。

## 关键发现：那 591 MB 里有一大块是「旧图」撑着的

- `git rev-list --all --count` = **5287**，而 `git rev-list main --count` = **2780**；
- 差额来自 **6 条远端跟踪分支**（`origin/coord-detect-rename`、`origin/feat/project-readme-03`、
  `origin/llm-observation-collector`、`origin/chore/deepseek-flash-model-id`、
  `origin/project-readme/02-build-flash-checklist`，2026-08-17～09-10）——它们指向
  **2026-09-15 历史重写之前**那套图，把改前全部对象（含已清掉的编译产物与 `sources/materials/`）
  继续钉在本地库里；
- `git clone` 只复制 heads/tags → 克隆里 `--all` 只有 2780 个提交 → 一 repack 就掉到 292.3 MB。

**所以这是两笔独立的账**：

| 动作 | 收益 | 代价 |
|---|---|---|
| **摘掉那 6 条旧引用** + repack（历史零改动） | **298.8 MB** | 低——但**线上那 6 条分支还在**（`git ls-remote --heads origin` 六条都在），先要决定这些 PR 分支是否废弃；否则下次谁 `fetch` 一把又会拉回来 |
| 再重写历史删 `sources/materials/` | **168.8 MB**（292.3 → 123.4） | 高——force push、四个 tag hash 改写、**所有既有 clone 与本地沙箱作废** |

**结论倾向**：免费的 298.8 MB 比重写挣来的 168.8 MB 更大，且风险低一个数量级。
「先摘引用、重写单独拍板」比「直接重写」合算——但**两件都还没做**，等用户拍板。

## 复跑与注意

- 复跑：`pwsh -File .scratch/materials-history-purge/probe-A.ps1`（约 20 分钟，全在 `%TEMP%`）。
- 它会导出 `probe-A-after-revlist.txt`（**4.16 MB**）——2026-09-16 已删，**别入库**
  （这条线本身就在讲仓库体积）。
- 探针里 `filter-branch` 的坑（绝对路径、`-f`、index-filter 而非 tree-filter）在
  `scripts/purge-generated.sh` 顶部注释里已经趟平；真要重写就照那套走（清单先给人看）。
