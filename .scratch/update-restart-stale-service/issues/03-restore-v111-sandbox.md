# 03 — 还原一台真 v1.1.1 沙箱（否则验收验的是空气）

**要做什么：** 让真机验收有一个**真的会触发缺陷**的起点。修复的判据是「更新换完文件后，启动器
自己把僵着的旧进程踢掉」——而「僵着的旧进程」只有在**发起更新的那一代没传 `--port`** 时才会出现。
今天沙箱里跑的 webapp 已经带 `--port` 修复，**只把版本号改回 1.1.1 是验不出这条修复的**：
更新器会正确停掉端口，旧进程根本不存在，drill 会在「一行修复都没写」的情况下变绿。

**被谁阻塞：** 无——可与 01 并行。

**状态：** ready-for-agent

## 做法

本机那份**没下过线的全量包** `firstep-pack\firstep-full-v1.1.1.zip`（783 MB / 8777 文件 /
清单 `version=v1.1.1`）就是真旧树，其 `webapp.spawn_updater` 已逐行核实**没有** `--port`
（对照组：同一份备份里 `full_apply.py` 是传 `--port` 的）。

1. 把现沙箱里那两个 B2 演练标记先挪到旁边留档（`sources\materials\.b2-drill-marker.txt`、
   `.b2-drill-payload.bin`）——它们是 `sandbox-drill` 记账的一部分，不是垃圾；
2. 清空 `C:\Users\luoji\Desktop\firstep-sim` → 用 **Python zipfile** 解包（走长路径 API；
   资源管理器那条老 API 在 259 字符就截断，本包有 223 字符的深路径）→ 补回包内没有的沙箱专用入口
   `sim-run.py`（从旧沙箱拷）；
3. **脚本化**：写一个 `--write` 才落盘的可复跑重建脚本，把「下次还要重演」变成一条命令
   （现有的 `.scratch/full-download/make_sim_sandbox.py` 是从**当前工作树**拷的，还原不出旧版——
   `local-environment` 第 1 节那句「用它可以重建沙箱还原旧版」是错的，要当场改）。

## 验收标准

- [ ] 重建脚本落 `.scratch/update-restart-stale-service/`（默认 dry-run，`--write` 才动盘；自带前置断言）
- [ ] `firstep-sim\src\contest_generator\__init__.py` == `1.1.1`（盘上真旧版本）
- [ ] `firstep-sim\src\contest_generator\webapp.py` 的 `spawn_updater` **命令里没有 `--port`**
      （真旧代码的判据，脚本自己断言；同时断言 `full_apply.py` 里**有** `--port`——证明只缺那一条路）
- [ ] `start-app.bat` 的 sha256 **等于** v1.1.1 全量包清单里那一份 `88a9c45b9917…`
      （证明沙箱里的启动器也是真旧的那份，修复还没进沙箱）
- [ ] `sim-run.py` 在位；数据目录 `C:\Users\luoji\.contest_generator_sim` 的 `config.json` 未被破坏
      （库目录仍指沙箱 `library`）
- [ ] B2 两个标记已留档（位置写进 `local-environment` 第 1 节的痕迹表）
- [ ] 起一次沙箱（8020）自证：`/api/health`.version == `1.1.1`；收尾释放端口、无残留 python 进程
- [ ] `docs/agents/local-environment.md` 第 1 节当场改写：沙箱现在是什么、怎么重建、
      **更正「make_sim_sandbox.py 能还原旧版」那句错话**
