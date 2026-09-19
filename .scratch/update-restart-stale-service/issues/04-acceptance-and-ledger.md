# 04 — 真机验收（跑既有 drill）+ 账本收口

**要做什么：** 用**一个字都不改**的既有演练脚本证明修复在真机上成立，并把这一轮产生的事实
（重发状态、沙箱新状态、缺陷射程更正）当场写回该记的地方，不留「下次就没人记得」的尾巴。

**被谁阻塞：** 02（线上含修复的包）、03（真 v1.1.1 起点）。

**状态：** resolved（2026-09-19）

**完成记录（验收）**：`python .scratch/verify-gate-drills/drill-01-upgrade.py`（**脚本零改动**）——
`served = 1.2.1`、`restarted_by_updater = true`、判红 0 / 卡住 0、保命项十三条与隔离四条全成立；
`launcher.log` = `reason=started tries=1 port=8020 stale=1 served=1.1.1 disk=1.2.1`。
B1 那次的失败证据另存为 `-b1-failed.{txt,json}`；中间两次「判据仍红」的原始输出也在
（`verify-01-upgrade.*` 被后一轮覆盖前各自提交过，见 `git log`）。

**完成记录（账本）**：`local-environment` 第 0/1/1.5/2/3 节、`.scratch/backlog.md` 第 8 节、
`sandbox-drill/01` 的判据勾选、`VERSIONS.md` 的 v1.2.1 区块（版本头未动）全部当场更新；
`tests/test_changelog.py` 32 passed；线上自检 `tools\check-download-docs.py` PASS。

## 验收命令与判据（判决只有这一条）

```
python .scratch/verify-gate-drills/drill-01-upgrade.py
```

判据：`RESULTS.endpoint.restarted_by_updater == true` **且** `RESULTS.endpoint.served == "1.2.1"`
（B1 当时分别是 `false` / `"1.1.1"`）。

**脚本零改动**——这正是选「重发 v1.2.1」而不是「给 drill 加本地包参数」的理由：drill 下的就是
线上真包，diff 为零，验收口径不掺水。原始输出照旧落
`.scratch/verify-gate-drills/verify-01-upgrade.{txt,json}`（会覆盖 B1 那次失败证据——
**先把 B1 原始证据另存一份**再跑，失败证据本身是这次修复的出处，不能丢）。

- [x] 跑之前先把 B1 的原始证据另存（`verify-01-upgrade.b1-failed.{txt,json}`），跑完两个文件都在
- [x] `restarted_by_updater == true`（更新器自己把服务带起来了，不需要演练脚本补起）
- [x] `served == "1.2.1"`
- [x] `launcher.log`（重定向 profile 里那份）出现 `reason=started`，且**带 `stale=1` 与
      `served=` / `disk=` 字段**——这是「走的是踢旧进程那条路」的机器可读证据（不是碰巧没旧进程）
- [x] 保命项十三条 + 隔离四条（真身 8000 / `~/.contest_generator` / 工作树 tree_stamp）全部成立
- [x] 收尾：8020 释放、无残留 python 进程
- [x] 脚本自身对「升级后构成」的复算结果如实记录（孤儿文件那条账的口径不变）

## 账本收口（当场写，别留尾巴）

- [x] `docs/agents/local-environment.md`：
  - 第 0 节交接区——重发之后的「main 与线上资产」落差（版本号相同、内容已换）
  - 第 1 节沙箱状态——现在是「跑过一轮升级的 1.2.1」+ 重建脚本在哪一条命令
  - 第 2 节端口现状（8000 / 8020 演练前后各查一次）
  - 第 3 节发布状态——v1.2.1 重发记录（新 sha256 / 字节数 / tag 未动 / **已装旧 v1.2.1 的用户
    收不到更新提示**这个缺口）
  - 第 1.5 节 B1 那一格的结论从「判据不成立」改成「成立（重发后复跑）」，
    并同步那句「判据 35 条里 33 条成立」的总账
- [x] `.scratch/backlog.md` 第 8 节：本单级别与口径更正（🔴「那批老用户都会中招」是推断过头，
      实际只有端口 ≠ 8000 中招；小发版这条路才有缺陷）+ 标已修
- [x] `.scratch/sandbox-drill/issues/01-sandbox-upgrade.md`：那条未勾的判据补上复跑结论
- [x] `VERSIONS.md` 的 v1.2.1 区块（**不动版本头那一行**，只加条目）记「本版资产于 X 重发，
      含启动器修复」；改完**必须**跑 `python -m pytest tests/test_changelog.py -q`
      （2026-09-14 那次事故就是改完 VERSIONS 没跑守卫）
- [x] 本目录四张工单 `Status: resolved`；spec 里被本轮推翻的判断保持原样不改（更正追加在工单）
- [x] 提交（中文提交信息；CHANGELOG 自动补录）
