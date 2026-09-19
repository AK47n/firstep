# 04 — 本机离线演练 + 账本收口：不发版也能证明「盘面与全新安装一致」

**要做什么：** 用一条可复跑的命令证明修复成立：把沙箱还原成真 v1.1.1 → 用**本机打出的修好的
小发版包**（不出网、不发版）走产品自带的更新器 → 复算构成，判据 = 盘上**不存在**完整包不会给的
产品文件（`not_in_official == 0`）。并把这一轮的更正写进账本。

**被谁阻塞：** 01、02、03。

**状态：** ready-for-agent

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
      - 隔离不变量：真身 `~/.contest_generator` mtime 未变、真身工作树未变、
        8020/8000 端口跑完释放、无残留 python 进程；
      - 原始输出落 `verify-offline-drill.{txt,json}`（进仓库，供复核）。
- [ ] 演练跑一次**判红对照**（可选但要记）：把谓词放宽（或跳过累计清单）后重跑，构成必须
      **不为 0**（证明判据不是恒真）
- [ ] 账本更新：
      - `.scratch/backlog.md` 第 8 节的 `update-orphan-files/01` 行按更正后的口径改写
        （1483 → 真实构成；级别与修法换成本轮拍板）；
      - `docs/agents/local-environment.md` 第 1 节记一笔：沙箱这次被本单的离线演练动过
        （起点/终点版本、有没有留残留），以及「线上资产本轮未动」；
      - 本目录工单里记下**这一轮没有发版**这件事，以及下次发版时要带上的判据
        （真机 drill-01 + `not_in_official == 0`）。
- [ ] 全仓测试跑一次绿（`python -m pytest -n auto -q`）
