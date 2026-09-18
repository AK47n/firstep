# 01 — 落后两版以上时升级：删除清单只覆盖「上一版 → 本版」，盘上留下孤儿文件

**Type:** task
**Status:** open
**发现于：** 沙箱真机演练 B1（`sandbox-drill/01`，2026-09-18），量具 `.scratch/verify-gate-drills/drill-01-upgrade.py` 的「升级后构成」一节

## 现象（逐文件量出来的）

沙箱 v1.1.1 ——（产品自己的小发版更新）→ v1.2.1 之后，把沙箱 tracked 树（打包器顶层白名单口径、排除 `sources/materials`）与**官方 v1.2.1 完整包清单**（`Desktop\firstep-pack\firstep-full-v1.2.1.manifest.json`，8142 条带 size+sha256）逐条比：

| 判据 | 数量 |
|---|---|
| 与官方**逐字节一致** | **3057** |
| 内容与官方不同 | **3**（全部是 `src/contest_generator.egg-info/{PKG-INFO,SOURCES.txt,requires.txt}`——更新器第 7 步 `pip install -e .` 重写了它们，见下方「附带发现」） |
| **官方已删、沙箱还在（孤儿）** | **1483**（`library/` 1482：`fix-backups/*`、`revise-backups/*`；`sources/` 1） |
| 官方有、沙箱缺 | **0** |

证据：`.scratch/verify-gate-drills/verify-01-upgrade-aftercare.txt`（含按顶层目录的分布与样例；主跑那份 `verify-01-upgrade.txt` 里同项的两个 0 字节文件曾被量具自己的 `or -1` 误判，已在复算里修掉）。

## 根因

- 小发版更新包**含全部 tracked 文件**（`tools/pack-update.ps1` 第 60-67 行：清单 = 本次 `git ls-files` 白名单快照），所以「覆盖」这一半是完整的；
- **删除这一半只覆盖一个版本区间**：`removed.txt = 基线 files.txt − 本次 files.txt`（同文件第 110-123 行），而发布时给的基线是**上一个版本**的包内清单（`local-environment.md` 第 3 节那张「下次发版可用的基线」表就是这么用的）；
- 更新器只按这一份清单删（`tools/update-app.py:503` `removed = full_manifest["removed"]`；小发版走 `remove_removed_list`）。

于是：**用户落后 N 版（N≥2）时，只有「上一版→本版」的删除被清理**，更早版本删掉的文件全部留在盘上——而界面/`__init__.py` 都会说「已是最新」。

## 影响评估（不夸大）

- 这些孤儿以**库备份目录**（`library/revise-backups/`、`library/fix-backups/`）为主，功能不受影响，工具正常起来（B1 善后复测：重起后 `/api/health` = 1.2.1）；
- 值得单独核一遍的是：这些孤儿落在 `library/**` 里，而 `library/` 是**库根**（模块 / 母版 / 赛题库 / 参考库 / 备份都在它下面）。要确认库扫描类功能（模块清单、资料库、参考库索引）**不会**把 `revise-backups/`、`fix-backups/` 这类残留当内容（若会，那就是用户可见的脏数据，严重度要上调）。
- 第二个后果是发布侧的口径问题：`-Baseline` 传的是「上一版的 files.txt」这个**隐含契约**（一个版本区间），一旦有人沿用更旧的基线或跳版发布，算出来的 `removed.txt` 与用户实际盘面就对不上。

## 建议修法（需 spec，二选一）

1. **发布侧累计**：每次发布除 `removed.txt`（上一版差集）外，再给一份「相对任意旧版的累计删除集合」——但累计到哪一版仍是拍的；
2. **更新器改用全量集合做差**（更彻底）：完整包清单本来就有 `files` 全量列表，更新器可在替换后按「工具根里存在、但既不在本次 `files` 也不在 `sources/materials`（包外内容）里的 tracked 白名单路径」清理——**风险**是包外文件与用户自建文件的边界，必须先 spec 清楚「什么算产品文件」。

倾向 2，但先把上面那条「库扫描会不会吃到孤儿」核掉，再定严重度。

## 附带发现（同一轮量出来的，属另一条线，不急）

`src/contest_generator.egg-info/*` **随发布包分发**（官方清单里就有这三件），而更新器每次替换后跑 `pip install -e .`（`tools/update-app.py:509-517`）会**重写它们的字节**——于是「同一次升级的两个产物（包 / 盘面）」必然有 3 个文件对不上，也给了「你有没有跑过 pip install」这类无用差异。是否该把 egg-info 从 git 与包里摘掉（并加守卫），另议。

## 验收

在任一修法落地后，同一台沙箱重跑 B1 并复算构成：

```
python .scratch/verify-gate-drills/drill-01-upgrade.py --aftercare
```

判据：`RESULTS.composition.not_in_official == 0`（现在 1483），且 `library/` 下不残留 `*-backups/` 孤儿。
