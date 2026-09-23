# 本机环境与当前状态（会变，改完就更新这里）

> **这份文件的存在意义**：有些事实只属于「这台机器 + 此刻」，既不该塞进 README（面向用户），
> 也不该只留在会话里（下次就没人记得）。凡是「下次接手需要知道」的环境事实写这里，**只写结论与位置**。
>
> 更新纪律：改动了这里描述的东西（删沙箱、发新版、换端口），**当场回来改这份文件**。

## 0. 交接区：main 上有什么还没到用户手上（2026-09-22 夜更新 · 线上最新仍是 v1.2.2）

**当前状态：线上最新 = v1.2.2；但 main 上已比它多出三批未发布改动**（见下表最后一行）。
| 项 | 值 |
|---|---|
| 线上最新 | **v1.2.2**（2026-09-19 发布）八件套齐全，`/releases/latest` 指向本版 |
| 这次带上的三张单 | `update-orphan-files/01-03`（产品文件判据单源 + 删除清单累计化 + `revise-backups` 出索引）、`update-verify-failure-leftovers/01`（不可重试的校验失败不留半卷）、`update-content-mismatch-retry-cap/02`（连续 5 次内容不符转终态） |
| 顺手做掉的第四条 | `src/contest_generator.egg-info/**` 摘出产品文件（两个包都不再发 pip 构建产物） |
| **真机验收** | `drill-01`：沙箱真 v1.1.1 → 走产品端点升到 1.2.2，**判红 0 / 卡住 0 / PASS**；`not_in_official` 1482 → **6**，那 6 条经决定性实验证明是**更新器那一步 pip 现写的**（官方包里 0 个 → 跑完 pip 6 个齐），「官方缺失 0 / 内容不同 0」两条全绿 |
| 发版产物（本机留档） | `firstep-pack\firstep-{update,full}-v1.2.2.*` 全套 + `release-notes-v1.2.2.md`；**下一版的基线就是这两个清单** |
| **main 上还没到用户手上的（四批）** | ① **硬件检测栏目本身**（`module-hwcheck/01-09`，2026-09-20 起）＋ **检测页引脚出口**（`hwcheck-pin-conflict-exit/01`：默认脚撞脚提前解开）——v1.2.2 的用户看不到「硬件检测」这一栏；② **完整包会话态进 `AppContext` ＋ `_full_task_lock`**（`full-update-state-into-ctx/01-04`，2026-09-22，账见 `.scratch/backlog.md` §18：纯内部换归属 + 修「并发 apply 建出两个任务」的竞态，**前端零字节**）；③ **陌生器件（库外件）探测**（`hwcheck-unknown-device`，2026-09-22 起：规格 + 11 张工单已落 `.scratch/hwcheck-unknown-device/`，**工单 01–05 已落地**（支点模块 `i2c_probe` / 「我的器件」/ 探测小节渲染 + stm32 真编译 / mspm0 分支 + 两平台编译矩阵 / 检测页计划投影），06–10 未开工；**工单 11 已修**（mspm0 引脚符号重名：四条路都在生成前拦下，**但母版改名没做**——撞名的组合仍不能同选））。**四批都只在本机工作树 / main 上，任何发布包里都没有**——下次发版要一起带上 |

**发版尚未启动（2026-09-22 22:0x 实测）**：这一轮只走到「决定要发」就停了——**版本号仍 `1.2.2`、
没打包、没打 tag、没建 Release**（用户要先继续改动再发，所以别把这份落差当成"发过了"）。
恢复发版的现成条件：`tools\preflight.ps1` 在 `1.2.2` 上**全绿**（改完版本号必须重跑）；上一版
基线都在本机 `Desktop\firstep-pack\`（`firstep-update-v1.2.2.files.txt` 给 `pack-update.ps1`、
`firstep-full-v1.2.2.manifest.json` 给 `pack-full.ps1`、`release-notes-v1.2.2.md` 当模板）；
`gh` 认证可用（当天撞过一次瞬时 TLS 握手超时，同一条命令重试即好）；线上 `latest` 仍是 v1.2.2。
**版本号未拍板**：建议 `v1.3.0`（硬件检测是整块新栏目 → SemVer 次版本 +1），若后面再塞新功能
还要往上走；流程与口径见 `docs/agents/releasing.md`。

**下一轮动手前必须知道的三件事（都是本轮实测踩出来的）**：

1. **跑 `drill-01`（起点 v1.1.1）会杀掉 8000 上的真身**——不是意外，是 v1.1.1 的已知缺陷：
   它的 `spawn_updater` **没有 `--port`**（`full_apply.py` 那条路有），于是更新器按缺省
   **8000** 停服，把真身那个进程杀掉。本轮实测：`updater.log` 记
   `停服：结束本应用进程 PID 43960`（43960 = 真身）。**跑之前先把真身挪到 drill 打不到的端口**
   （`$env:FIRSTEP_LAUNCHER_PORT=8021` 再起 `start-app.vbs`），跑完再挪回 8000。
   v1.2.1 起这条路已经修好（`--port` + 启动器 stale 判据），所以**沙箱升到 ≥1.2.1 之后就不再咬人**。
2. **重建沙箱前先收 8020**：`rebuild-sandbox-v111.py` 会整树删掉工具根，而上一轮 drill 结尾把
   沙箱又拉起来了 → `PermissionError [WinError 32] 另一个程序正在使用此文件`（本轮踩到一次）。
   顺序固定为：**收 8020 → 重建 → 跑 drill**。
3. **取证据时别让 drill 覆盖自己**：drill 的 `OUTPUT_STEM` 是模块级常量，**同一对
   `verify-01-upgrade.{txt,json}` 每次运行都覆盖**。本轮的目标版本与 drill 自带的不一致，
   包装层必须连它一起补（补在**模块级那一处**——`--aftercare` 分支里那句 `global OUTPUT_STEM`
   是函数内部声明，补它没用）。包装层见 `.scratch/release-v1.2.2/run-drill-01-v122.py`，
   它还把 drill 跳过的 `__main__` 收尾**代做了一遍**（漏掉它 = 演练跑完却一份证据都不落盘）。

**发版时踩到的工具坑**（都记在工单里，别再踩）：
① `tools/pack-update.ps1` 的 `.ps1` **BOM 会被编辑工具吞掉**——改完必须复核
`tests/test_ps1_encoding.py`；
② 判据强度探针**被强杀**时 `finally` 跑不到，源文件会停在注入态——探针的「前置干净性检查」
是为此而设，探针读写要**逐字节保真**（文本模式的 CRLF↔LF 归一会让「复原复核」假红）；
③ **打包要求工作树干净，包括工单文件的 `Status:` 标记**——`tools/pack-*.ps1` 默认拒绝脏工作树，
   而「标记已 claim/resolved」本身就是 tracked 变更。本轮的做法：打包前把标记还原到提交态，
   收尾时连同证据一次落 `resolved`。

**下次发版前只需记住**：`pack-full` 的 `core.autocrlf=false` 那处修复是**打包器代码**，
不会随包分发——凡是换机器 / 换 clone 打包，先确认它还在（`tests/test_pack_update.py` 有跨包逐字节守卫）。

**上一轮（`update-restart-stale-service`，2026-09-19 早）踩到的两个工具坑**（留档，别再踩）：
① `Select-Object -First N` 接在 `powershell -File tools\pack-update.ps1` 后面会**提前掐断上游**，
打包器跑不到写 `sha256.txt` 那一步（zip 生成了、校验和文件是上一版的）——上传前务必对一次
「zip 实算 vs `sha256.txt`」；② 更新器重启那一跳的日志重定向目标是**数据目录**，目录不存在时
cmd 整行不执行（真机上由 `install.bat` 的 bootstrap 配置保证存在，现已由启动器自己保证）。


## 1. 沙箱「模拟用户机」（真机演练用的第二份安装）

| 项 | 值 |
|---|---|
| 工具根 | `C:\Users\luoji\Desktop\firstep-sim` |
| 数据目录 | `C:\Users\luoji\.contest_generator_sim`（与真身的 `~\.contest_generator` 隔离） |
| 端口 | **8020**（真身用 8000；`FIRSTEP_LAUNCHER_PORT=8020`） |
| 入口 | `sim-run.py`（沙箱专用，因为生产入口的配置路径写死在真身数据目录）。**恢复副本在库里**：`.scratch/update-restart-stale-service/sandbox-entry-sim-run.py`（一次失败的重建把原件连目录删了，重建脚本会用它兜底） |
| 构建脚本 | `.scratch/full-download/make_sim_sandbox.py`（**从当前工作树拷**，只给「干净沙箱」用）；**要还原旧版用** `.scratch/update-restart-stale-service/rebuild-sandbox-v111.py --write`（从 `firstep-pack\firstep-full-v1.1.1.zip` 解真 v1.1.1） |
| 当前状态 | **2026-09-19 下午（v1.2.2 发版后）**：盘上 = **v1.2.2**，资料库基线 = `v1.2.2` / 12 批次 / 5081 文件（走完整包替换那一步由更新器写回，见 2.1）；8020 **已释放**。上一轮那次「本机修复包升到 1.2.1」的状态已被本轮的「重建 → 真升级」覆盖 |

**⚠ 重建沙箱前先收 8020**（2026-09-19 实测踩到）：`rebuild-sandbox-v111.py` 会整树删除工具根，
而 drill 结尾会把沙箱重新拉起来 → `PermissionError [WinError 32] 另一个程序正在使用此文件`。
固定顺序：**收 8020 → 重建 → 跑 drill**。

**⚠ 跑 drill-01（起点 v1.1.1）会杀掉真身**：v1.1.1 的 `spawn_updater` 没有 `--port`，更新器按缺省
8000 停服。跑之前把真身挪到 8021（`$env:FIRSTEP_LAUNCHER_PORT=8021` + `start-app.vbs`），
跑完挪回 8000。详见第 0 节第 1 条。

**要再重演一次「从旧版升上来」**（一条命令，约 1 分钟；**先收 8020**）：

```powershell
python .scratch\update-restart-stale-service\rebuild-sandbox-v111.py --write
```

它会：把 `sim-run.py` 暂存到临时目录 → 清空工具根 → 用 Python zipfile 解 v1.1.1 全量包
（8777 文件 / 长路径安全）→ 补回 `sim-run.py` → 按更新器同款口径写回资料库基线，
并逐条断言「这棵树真是会触发缺陷的那一代」（盘上 1.1.1 / `spawn_updater` 没有 `--port` /
`full_apply.py` 有 `--port` / 启动器 sha256 等于 v1.1.1 清单那份）。

**已知故意为之的一处「不真实」（2026-09-19 更新）**：**沙箱没有 `.venv`** —— 包内自带的
`start-app.bat` 会走「回退系统 python」那条路（系统 python 装齐了运行依赖，所以能起来；演练实测
首次启动要几十秒，`tries=1` 是缓存热了之后的结果）。演练时仍建议用 `sim-run.py` 直接起。
**附带后果**：没有 `.venv` 时更新器第 7 步的 `pip install -e .` 会装进**全局 site-packages**
（第 2.5 节记着怎么清）。

> **原「沙箱钉在旧版本号、可重演升级」那条前提现在由重建脚本承担**：沙箱跑完演练就变成新版了，
> 想再验升级就重跑上面那条命令——**不要**再靠「把 `__init__.py` 改回旧版本号」那一招：
> 只改版本号不会还原旧代码，更新器会正确停服、旧进程根本不存在，
> **这条修复会在「一行都没写」的情况下也变绿**（2026-09-19 实测确认）。

**2026-09-18 演练在沙箱上留下的痕迹（**已被 2026-09-19 的重建清掉**，留档在此）**：

| 痕迹 | 位置 / 说明 |
|---|---|
| B2 的两个演练标记 | `firstep-sim\sources\materials\.b2-drill-marker.txt`（84 B / sha256 `7e74566e6e633ee5…`）与 `.b2-drill-payload.bin`（3,961,289 B / sha256 `5fd0ac6359bd8fcd…`）——**重建时随工具根一起消失**；内容由 `drill-02-degraded.py` **确定性**造出（固定文本 + 固定重复字节），重跑那支演练即可复现，故不入库也不丢证据；记账在 `.scratch/update-restart-stale-service/b2-markers.json` |
| B1 的小发版包 | `~\.contest_generator_sim\updates\firstep-update-1.2.1.zip` + `.removed.txt` —— **数据目录没被重建动过**，所以还在（里面那份是重发前的包，演练会覆盖它） |
| 备份目录 | `~\.contest_generator_sim\updates\backup\` 现在有 6 份：`20260913-002004` / `-002734` / `20260918-224039`（B1）/ `20260919-104456` / `-110054` / `-113411`（本轮三次重跑各一份） |

## 1.5 沙箱真机演练结论（2026-09-18，第二梯队 B1–B5）

一次把「只差真机」的四件事跑完（spec `.scratch/sandbox-drill/spec.md`，脚本与原始证据
`.scratch/verify-gate-drills/`）。**结论一句话：判据 35 条里 33 条成立，暴露 4 条真问题（全部开单）。**

> **2026-09-19 复核：B1 那一格已经转绿。** 修复（`update-restart-stale-service/01`）落地后把
> v1.2.1 的资产**重发**（含修好的启动器），再把沙箱还原成真 v1.1.1 重跑同一支 drill：
> **判据成立** —— `served = 1.2.1` 且 `restarted_by_updater = true`，`launcher.log` 记
> `reason=started tries=1 port=8020 stale=1 served=1.1.1 disk=1.2.1`（走的正是「踢掉旧进程」那条路）。
> 判红 0 / 卡住 0，四条隔离判据与十三条保命项全成立。所以下表 B1 的结论按「已修 + 已复跑成立」读；
> 「暴露 4 条真问题」这句仍然成立（当时确实暴露了 4 条），只是其中这条已经关掉。

| 格 | 做什么 | 结果 | 证据 |
|---|---|---|---|
| **B1** 沙箱升级 | v1.1.1 → 走产品端点真下线上小发版包 → 替换 → 重启 | **2026-09-18 判据不成立**：盘上 1.2.1，**跑着的服务仍 1.1.1**（旧进程没被停；启动器判 `already_running`）→ 开缺陷单 `update-restart-stale-service/01`。**2026-09-19 修复 + 重发资产后复跑：PASS**（`restarted_by_updater=true` / `served=1.2.1`） | `verify-01-upgrade.{txt,json}`（最新一轮）、`-aftercare.*`、`-b1-failed.{txt,json}`（2026-09-18 那次失败证据另存） |
| **B2** 三极端场景 | 本地可控服务器造弱网/断线/坏字节，走产品端点 | 弱网取消 **10/10**、断线重试 **12/12**、校验失败（不可重试）**11/13**（两条不成立 = 失败后残留整卷半成品 + 边车 → `update-verify-failure-leftovers/01`）、持久内容不符 = 观察格（与 spec 一致 → 决策单 `update-content-mismatch-retry-cap/01`）。**2026-09-19 下午复核：两格都已转绿**——`verify-size` 的「半成品被清 / 边车被清」两条都成立（drill 判红 0），`content-mismatch` 出现终态 `failed` / `error_kind=verify` / 「重下不会有变化」文案、30.6 秒收敛、`retry_count=4`。复跑用**工作树的源码**当「用户机上那一代」（harness 偏离记账在 `.scratch/verify-gate-drills/run-drill-02-with-workspace-src.py`），drill 本身零改动 | `verify-02-degraded.{txt,json}` + `amend-02-corrections.py` + `.scratch/update-verify-failure-leftovers/verify-real-machine*` + `.scratch/update-content-mismatch-retry-cap/verify-real-machine*` |
| **B3** 编码钉落点 | 沙箱真调 `POST /api/generate`（mspm0 + servo） | **PASS**：产物 `.settings/` 两件都在、正文含 `encoding/<project>=UTF-8`、sha256 与**母版**与**官方包清单**三方相等。**只证落点，不证 CCS 读取行为**（写进证据） | `verify-03-encoding-pin.{txt,json}`、`artifacts-b3/` |
| **B4** 完整包换装 | 一次性根上**真下 801,873,335 B** → 校验 → 替换 → 重启 | **PASS**：服务 1.2.1（更新器自己带起来了）、基线写回（v1.2.1 / 12 批次）、包外与第三方安装包未动、隔离三判据成立 | `verify-04-full-pack.{txt,json}` + `-recheck.*` |
| **B5** 账本收口 | 本节 + 第 0/2/2.5 节 + `real-acceptance/01` G1 + `E2E-8020.md` + `backlog.md` | 已完成（B1–B5 五张工单全 resolved） | `.scratch/sandbox-drill/issues/05-ledger-closeout.md` |

**下次要复跑**：`python .scratch/verify-gate-drills/drill-0{1,2,3,4}-*.py`（B2 支持 `--only <场景>`；
B1/B4 各带 `--dry-run`（不下包）与 `--aftercare` / `--recheck`（对已跑完的一次性目录复算））。
**注意**：B1 要重演得先还原真 v1.1.1 起点——原沙箱跑完一轮就变成新版了（第 1 节），
一条命令：`python .scratch\update-restart-stale-service\rebuild-sandbox-v111.py --write`。
**别用「把 `__init__.py` 改回旧版本号」那一招**：版本号回去了、代码还是新的，更新器会正确停服，
旧进程根本不存在——这条修复会在「一行都没写」的情况下也变绿（2026-09-19 实测确认）。

## 2. 本机跑着的实例

| 端口 | 是什么 | 谁在用 |
|---|---|---|
| **8000** | 真身（`Desktop\firstep`，工作树即最新代码） | 你自己日常用；双击 `start-app.vbs` 启停。**2026-09-19 下午 v1.2.2 发版收尾后已在跑**（版本 1.2.2）——期间为躲开 drill-01 曾临时挪到 8021（见第 0 节第 1 条），收尾已挪回。**2026-09-19 16:16 实测：没在跑**（`GET /api/health` 连接被拒，见下条） |
| **8020** | 沙箱 | 演练用，随时可停。**2026-09-19 下午已释放**（drill 收尾自己收掉并验过） |
| **8021** | 一次性实例（B4 完整包换装用过；**2026-09-19 本轮又用它安置过真身**） | 只在该格 / 躲避 drill 时存在，用完即释放。`FIRSTEP_LAUNCHER_PORT=8021` 一路传到更新器的 `--port` |

> **同机两个实例的坑**（已修，但知道一下）：更新器默认按 8000 停服。若在 8020 上点更新而没传端口，
> 会把 8000 上你正在用的那个停掉。两个更新路径（完整包 / 小发版）现在都从 `FIRSTEP_LAUNCHER_PORT`
> 取端口，正常不会再发生；停掉后重跑 `start-app.vbs` 即可恢复。
>
> **2026-09-19 补充**：这条缺陷的射程在修复时被量准了——「更新后跑着的仍是旧进程」**只在端口 ≠ 8000
> 时才咬人**（更新器的默认端口与普通用户的端口都是 8000，两边一致就停对了），且只有**小发版**那条路
> 缺 `--port`（v1.1.1 的完整包路径本来就传）。详见 `.scratch/update-restart-stale-service/spec.md`
> 的「射程更正」。
>
> **2026-09-19 16:16 实测（module-hwcheck/02 会话）**：8000 上**没有实例在跑**（`GET /api/health`
> 连接被拒），8020/8021 也没起。该会话的验证全部走**进程内 TestClient**（`python -m pytest` +
> `.scratch/module-hwcheck/verify-02-real-machine.py`），一次服务器都没起——所以这一单不涉及端口纪律。
> **新栏目「硬件检测」的新端点与新静态文件要重启才在浏览器里可见**（Python 模块 + `static/js/`），
> 但库里**没有**任何常驻服务器需要你去重启。
>
> **2026-09-19 17:5x 复核（module-hwcheck/03 会话）**：8000 仍未起。该会话多起了一个**临时**
> 端口 **8791**——`tests/browser/hwcheck.spec.mjs` 的真浏览器验收用它（`tests/browser/server.mjs`
> 自带起停，跑完自己收）；其余验证走 TestClient 与 `python -m pytest`。跑完实测 8000/8020/8021/8791
> 都没在听。
>
> **2026-09-19 21:5x（module-hwcheck/04 会话）**：8000 仍未起。这一单新增三支**真编译**探针
> （本机有 Keil：`C:\Keil5\Core\UV4\UV4.exe`，`compile_runner.find_uv4()` 能探到），
> 用 `compile_runner.run_compile` 走产品那一路编了 7 次 stm32 工程（每次 3–5 秒）；
> 浏览器验收照旧用 8791。**跑完实测 8000/8020/8021/8791 都没在听。**
>
> ⚠ **8791 的一个坑（本轮踩了两次，白等两轮 30 秒超时）**：`tests/browser/server.mjs`
> 收服务是 `taskkill /T /F` + **5 秒兜底**；上一跑的 python 子进程若没被收干净，
> 下一跑的 `startServer` 会连上**那个旧服务**（健康检查与端点哨兵都过），
> 于是旧服务在下一跑中途被 taskkill 杀掉 → 后半截用例报 `ERR_CONNECTION_REFUSED`
> 或 `waitForSelector` 30s 超时。**症状看着像产品坏了，其实是端口上残留的旧服务。**
> 跑之前先清一遍：
> `Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -like '*contest_generator.webapp*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }`
>
> **同轮的一条工具事实（对以后任何"生成 C 代码"的功能都适用）**：**Keil ARMCC 5.06 按本地
> 多字节代码页（本机 GBK）解析源文件**——C 字符串字面量里直接写中文，会在某些字节收尾处把
> 收尾引号当尾字节吞掉，报 `#8: missing closing quote`，整份 main.c 编不过（本轮实测 22 error）。
> 两条出路都量过：工程加 `--locale=english`（要改母版编译开关，跨平台共享面）或
> **把非 ASCII 转义成 ASCII 转义序列**（不改母版、产出字节与原文逐字节相等）。检测程序取后者
> （`hwcheck_recipe.c_string`），量具在 `.scratch/module-hwcheck/probe-04-armcc-*.py`。
> **别在生成的 .c 里直接写中文串**；注释里可以（本机所有 `/* 中文 */` 都没问题）。
>
> ⚠ **2026-09-19 23:4x（module-hwcheck/05 会话）更正转义写法：`\xNN` → 三位八进制 `\NNN`**。
> `\x` 转义**贪婪吃十六进制数字**：`±2g` 的字节是 `C2 B1 32 67`，写成 `\xc2\xb12g`
> 会被编译器读成 `\xb12`（一个越界转义）——ARMCC 报 `#27-D: character value is out of range`
> 且字节不对（工单 05 的编译矩阵第一次跑就撞上，读数单位里的 `±2g` / `°1` 这类最容易中招）。
> 八进制转义最多三位数字、天然自终止，编译出的字节与原文仍逐字节相等。守卫用例
> `tests/test_hwcheck_recipe.py::test_escape_c_string_is_byte_exact_and_never_greedy`
> （判据 = 按 C 规则解码转义串后与原字符串逐字节相等）。
>
> ⚠ **同轮的另一条（对"生成 main.c 调模块函数"的功能适用）**：检测程序的框架 include
> 只覆盖通道与心跳（led / delay / oled / debug_uart），**器件模块的头必须由配方声明**
> （`hwcheck_recipes.json` 的 `include.headers`）——不然 ARMCC 报一串
> `#223-D function declared implicitly` + `#20 identifier undefined`（工单 05 实测 7 error）。
> 跨模块前置调用的头（如 `I2C_Init` 的 `ml_i2c.h`）也走这同一个段。
>
> **2026-09-20 01:0x（module-hwcheck/06 会话）**：8000 仍未起；这一单一次服务器都没起
> （全量套件 + 三支探针走进程内 TestClient / 子进程），浏览器验收照旧用 8791（夹具自带
> 起停）。跑完实测 8000/8020/8021/8791 都没在听、无残留 python。
>
> ⚠ **同轮钉到的一条既有竞态**（当时：产品侧，本单没修，另开单）——**✅ 2026-09-21～22 已修**
> （工单 `launcher-exit-race/01–05`，账见 `.scratch/backlog.md` §16）。原文留档（它是这条竞态
> 被发现的现场）：**F5 重载慢过 1.5 秒会被应用自己关掉**。链路：`app.js` 在每次页面加载时
> `POST /api/tabs/register`、在 `pagehide` 时 `sendBeacon("/api/tabs/bye")`；启动器模式
> （`FIRSTEP_LAUNCHER=1`）下 `webapp._schedule_exit_if_idle` 见"注册表空了"就起
> `_EXIT_GRACE = 1.5` 秒宽限然后 `os._exit(0)`。重载时旧页面的 bye 先到、新页面的 register
> 要等 `app.js` 求值才发出——**宽限内没到就自杀**（本机实测：浏览器验收连跑第 7 次 `goto`
> 时命中，现象是后端进程消失、后续请求 `ERR_CONNECTION_REFUSED`）。
> **当时判据**：`tests/browser/hwcheck.spec.mjs` 在 **HEAD（工单 05 状态）上同样 6 绿 3 红**
> ——与在跑的特性无关。夹具侧已修（`tests/browser/server.mjs` 起服务后替验收会话注册一个
> 固定 tab_id，注册表不再为空）；**产品侧那条竞态仍在**，要修得单独开单（候选：宽限放宽 /
> register 先于 bye 生效 / 只在真正"关窗口"时退出）。
> （**末句三条候选与"夹具侧那个补丁"都留档**：补丁后来在工单 04 里随"夹具不再替验收会话注册"
> 一起删掉了——它只在那个 tab_id 留在注册表里时成立，实测仍会中途死；夹具现行做法是**其余
> spec 一律不设 `FIRSTEP_LAUNCHER`**、启动器模式由 `launcher-reload.spec.mjs` 专门验。）
>
> **✅ 修法与现在的判据**（2026-09-21～22，本机重测：修复前 10 轮第 4 轮命中 → 修复后 10/10 全程
> 活着，探针读数 `.scratch/launcher-exit-race/probe-00-order-{before,after}.txt`）：
> ① 登记搬到 `index.html` **head 的内联脚本**（模块图之前——放 `boot.js` 没用，ESM 静态 import
> 会先把整张图取完才求值）；② `register`/`bye` 都带文档实例令牌 `epoch = performance.timeOrigin`
> （旧文档迟到的告别不许注销新文档的登记）；③ 退出调度显式化（布防 / 撤防 / 到点取走，同锁）。
> `_EXIT_GRACE` **仍是 1.5、未新增时间常量**；关浏览器那条路实测 **1.53–1.65 秒**停服
> （`probe-02-close-page.txt` 记 1638ms，本 spec 用例 C 各次 1525–1652ms）。
> 新判据三处：pytest（`tests/test_webapp.py` 的「标签会话」段 15 条）、结构判据
> （`tests/js/boot-contract.mjs` 判据⑥ + `tests/js/tab-register-guard.test.mjs`）、真浏览器
> `tests/browser/launcher-reload.spec.mjs`（**唯一**开 `FIRSTEP_LAUNCHER` 的 spec）。
>
> ⚠ **验收前先清 8791 的残留 python**（第 2 节那条老坑，本轮又踩）：本轮第一次跑
> 浏览器验收时端口上的旧服务把新起的挤掉，`startServer` 的健康检查与端点哨兵都过、
> 却答的是旧进程；跑之前按第 2 节那条 `Get-CimInstance … contest_generator.webapp`
> 清一遍即可。
> （**2026-09-20 21:xx 起这条已由夹具自己兜住**：端口改为内核分配，且加了"我起的进程
> 还活着吗"的判据——见下面那条 ✅。清残留仍是好习惯，但不再是必要条件。）
>
> **2026-09-20 14:2x（module-hwcheck/08 会话）**：8000/8020/8021/8791 都没在听、
> 无残留 python（实测命令见第 2 节那条 `Get-CimInstance`）。这一单一次服务器都没起：
> 验证全走进程内 TestClient（新端点的假 LLM 桩 / 真 DeepSeekLLM + 假传输）+ 前端
> `node --test "tests/js/*.test.mjs"`。跑过的读数：`tests/test_hwcheck*.py` +
> `test_llm.py` + `test_webapp.py` = **1004 passed**；前端门禁 **1678 passed**。
> **新端点（`POST /api/hwcheck/triage`、`POST /api/hwcheck/checklist`）与新静态文件
> 同样要重启才在浏览器里可见**——与上面那条老话同一件事。
>
> ⚠ **同轮钉到的一条前端纪律（本轮真踩）**：`index.html` 的卡片说明若**跨行折行**，
> 前端守卫里 `html.includes("整句话")` 这种判据会假红（HTML 里的换行 + 缩进空格把它
> 断成两截）。判据要写 `html.replace(/\s+/g, "").includes("整句话")`，或挑一段不跨行的
> 短语——本轮 `tests/js/hwcheck.test.mjs` 的"检测没过是正常结果"那一条就是这么修的。
>
> **2026-09-20 14:5x（module-hwcheck/09 会话）**：同样一次服务器都没起（全量套件 +
> 真编译矩阵走进程内 TestClient / 子进程）。这一单第一次**真编译 17 个检测工程**
> （stm32 走 `C:\Keil5\Core\UV4\UV4.exe`、mspm0 走 `C:\ti\ccs2050\ccs\utils\bin\gmake.exe`，
> 由 `compile_runner.find_uv4/find_make` 探测）——**16 种形态 0 error / 0 warning、
> 3 格生成前拦下**（读数在 `.scratch/module-hwcheck/probe-09-compile-matrix.txt`）。
> 相关面 pytest **1241 passed**、前端门禁 **1682 passed**。跑完实测
> 8000/8020/8021/8791 都没在听、无残留 python。
>
> ⚠ **同轮的一条工具纪律（本轮自己踩的）**：判据强度探针会**真的改库内文件**
> （`.scratch/module-hwcheck/probe-09-guard-strength.py` 删一格配方再复原）——
> **别和测试套件同时跑**。本轮并行跑了一次，套件读到"少了 beep"的中间态，
> 5 条无关用例假红（白排查一轮）。顺序固定：探针跑完 → 再跑套件。
>
> ⚠ **同轮量到的一条产品事实（不是本单引入，已开单）**：**mspm0 上"调试串口 + OLED"
> 是检测页的默认形态，而母版里 `OLED_SPI_RES = PA22 = DEBUG_UART RX`——mspm0 任何器件
> （含"一件都不选"）在默认双通道下生成必 400**，而检测页没有引脚配置入口
> （400 的出路文案指向赛题页的「自动配置」）。赛题链路同一条冲突有出口：
> `POST /api/bindings/auto` 会把 `debug_uart.DEBUG_UART_RX` 移到 PA24。
> 细节与候选修法：`.scratch/hwcheck-pin-conflict-exit/issues/01-*.md`；
> 复现：`.scratch/module-hwcheck/probe-09-contest-parity.py`。
>
> ✅ **2026-09-20 17:0x（hwcheck-pin-conflict-exit/01 会话）上面那条已修**：检测页在
> 预览与生成前跑**与赛题页「自动配置」同一个**求解器，把默认脚撞脚提前解开（仅 mspm0），
> 并把动过的线如实打进载荷 `wiring.pin_fixes`；同时把「孤儿 ADC 槽位」（母版 ADC12_0 里
> 属于**没选中**那几件的 MEM 脚）改成撞上就让位——两处判据都收敛到
> `syscfg_prune`（落盘同脚冲突报告已从生成门禁抽出、两页共用）。
> 最新读数：真编译矩阵 **18 种形态 0 error / 0 warning、生成前拦下 0 格、如实拦下 1 格**
> （全选 9 件在地猛星上物理装不下，页面点名了是哪几件、该怎么去掉）——见
> `.scratch/module-hwcheck/probe-09-compile-matrix.txt`；检测页验收读数
> `.scratch/hwcheck-pin-conflict-exit/verify-01-page-exit.txt`，判据强度反向验证
> `.scratch/hwcheck-pin-conflict-exit/probe-guard-strength.txt`。
>
> ⚠ **本轮的一处工具事实**（对"改配方数据"这类改动适用）：`probe-09-compile-matrix.py`
> 每次重跑都会**先清空 `probe-09-buildlogs/`**（防上一轮日志混进来），所以它删掉的是
> **已入库的上一轮日志**、留下的是未跟踪的新日志——跑它就会在工作树里造出 16 个 D + N 个
> `??`。别把那些删除当成"证据丢了"：证据在 `probe-09-compile-matrix.txt` 与当轮 buildlog 里。
>
> ✅ **2026-09-20 21:xx（ui-dom-contract-gate/01 会话）上面那条「8791 的坑」已经治本，端口事实变更**：
> `tests/browser/server.mjs` 不再用固定端口——**每个 spec 各向内核要一个空闲端口**
> （`requestedPort` 可指定钉死端口，排查时用）。原来的坑（端口上的旧服务把新起的挤掉、
> 健康检查与端点哨兵却都过、答的是旧进程）现在有三道判据兜住：① 起服务时先判
> 「**我起的这个进程**还活着吗」（它死了就是端口被占，当场指名失败，不再静默跑在旧服务上）；
> ② `stopServer` 等端口真的没有 LISTEN 才返回（`taskkill` 返回 ≠ 端口已释放，这正是
> 三个 spec 连跑时下一个 bind 失败 `[Errno 10048]` 的根因）；③ 收不干净就收掉它。
> `server.mjs` 同时**不再设 `FIRSTEP_LAUNCHER=1`**（拒绝产品侧"关浏览器 = 停服务"在验收中途开火；
> 服务生命周期归夹具自己）。**跑完不必再"先清 8791"**——但仍建议清一遍残留
> （第 2 节那条 `Get-CimInstance … contest_generator.webapp`），因为夹具现在不靠产品自杀兜底了。
> 详细读数与红证见 `.scratch/ui-dom-contract-gate/issues/01-fix-browser-specs-green.md`。
> 同一轮把「HEAD 上 6 绿 3 红」这个旧读数更正为 **14 绿 7 红**（根因与修法都变了，见同一份工单）。
>
> ✅ **2026-09-20 22:xx（ui-dom-contract-gate/04-05 会话）本机跑浏览器验收的口径与读数**：
> 现在是**四个 spec / 26 条用例**（`module-intro` 9 + `code-tree-click` 2 + `hwcheck` 10 +
> `ui-contract` 5，最后一个是本轮新增的 ui 行为契约）。前置一次性：
> `npm install` + `npx playwright install chromium`（本机已装齐，`%LOCALAPPDATA%\ms-playwright` 下有
> chromium-1234/1243）。跑法（**必须串行**：每个 spec 各起真后端 + 真 Chromium，跑同一份工作树与库）：
>
> ```powershell
> node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
> ```
>
> 本机读数（Node v24.15.0，2026-09-20）：`ui-contract` 单跑 **5 passed / 0 fail**；
> 四个 spec 串行全跑 **26 passed / 0 fail / 77.9s**；前端门禁 `node --test "tests/js/*.test.mjs"`
> **1715 passed / 0 fail**；`python -m pytest -n auto` **5042 passed + 1 skipped / 115s**。
> **这一支已经接进闸门**：改动落在 `tests/browser/`、`static/js/ui/`、`static/index.html`、
> `static/js/boot.js`（**装载根**，工单 frontend-boot-module/02 起——模块清单 / 接线 / 启动都在
> 这里，落点跟着搬家）、`static/js/app.js` 时本地 pre-push 会跑它（CI 另有 `browser-suite` job
> 跑同一条命令）；闸门自身缺能力（node / playwright / chromium 缺）时打印原因放行，用例真红才拒推。
> 红证工具留在 `.scratch/ui-dom-contract-gate/`：`probe-ui-contract-red-proof.mjs`（真源码注入 +
> 逐字节复原）、`probe-port-listening.mjs`（夹具端口判据自检）、`probe-guard-strength.mjs`（静态判据）。
>
> **2026-09-21 更新（工单 frontend-boot-module/05）**：装载根搬家后的本机读数 —— 前端门禁
> `node --test "tests/js/*.test.mjs"` **1679 passed / 0 fail**（退化删掉 57 条逐名用例、新增 11 条
> 结构判据后的条数）；四个 spec 串行 **26 passed / 0 fail / ≈113s**；`python -m pytest -n auto`
> **5049 passed + 1 skipped / ≈200s**。**一处已知的本地/CI 落差**：`tests/js/` 下的判据共享件
> （`boot-contract.mjs` / `import-usage.mjs` / `ui-dom-contract.mjs`）被浏览器夹具间接 import，
> 但**只改它们**时本地 pre-push 不带起浏览器门禁（CI 的 `browser-suite` 不受路径筛选影响，
> 照跑）——落点表要不要再扩，另立。
>
> **2026-09-21 追加（工单 export-surface-guard/01-03）**：新增导出面守卫 9 条用例后，前端门禁
> 本机读数是 **1688 passed / 0 fail**（1679 ＋ 9）；三门禁同一轮实测 `pytest` **5049 passed +
> 1 skipped / 101s**、浏览器门禁 **26 passed / 0 fail / 66s**。**一条与上面那份读数并列的环境事实**
> （工单 export-surface-guard/02 §⑥ 首次记账）：`tests/js/ai-action-refs.test.mjs` 与
> `tests/js/module-intro-detail.test.mjs` 按**字面 LF** 断言源码，本机 `core.autocrlf=true` 时
> **CRLF 检出**下这两条必红（1677 / 2 fail）——报读数前先看检出形态。
>
> **2026-09-21 追加（工单 module-import-usage/01-03）**：「零未使用具名 import」这条不变量的
> **判据面从装载根扩到全部 132 个模块**并进闸门。本单收尾读数（**LF 检出**下测得——`1691` 这个数
> 只在 LF 检出成立，见上面那条 CRLF 环境事实）：
> 前端门禁 **1691 passed / 0 fail / 6.4s**（1688 ＋ 本单 3 条）；浏览器门禁 **26 passed / 0 fail / 80.7s**；
> `python -m pytest -n auto -q` **5049 passed + 1 skipped / 138.9s**（另两次复跑 135.0s / 138.0s 同数）。
> **落点与口径三条**：① 本条判据的两个文件（`tests/js/import-usage.mjs` 与 `boot-contract.mjs` 的掩码）
> 属"判据共享件"——只改它们时本地 pre-push 不带起浏览器门禁（与上面那条已知落差同源）；
> ② 掩码件现在有**两种口径**：`maskCommentsAndStrings`（模板串整串掩掉，判据 D/T 与通用掩码用，
> **语义不得改动**）与 `maskNonCode`（`${…}` 表达式内部保留为代码，"未使用具名"判据用）。
> 混用就是假红（实测 33 处）——改判据前先看 `tests/js/import-usage.mjs` 的文件头；
> ③ 合成用例表 `tests/js/import-usage-cases.mjs` 被闸门与 `.scratch` 的红证脚本**共用**（判据单源那条纪律）。
> **判据强度自检**（会真改库内文件、跑完逐字节复原，**别和测试套件同时跑**）：
> `node .scratch/module-import-usage/probe-04-guard-strength.mjs`（3 条注入都让闸门变红，
> 且**首条红的用例名**与注入声明逐条对上）。
> 红证/证据都在 `.scratch/module-import-usage/`（base 钉 `f1c9e1c7`）。
>
> ⚠ **同轮量到的一条既有偶发（与本次改动无关，别误判成产品坏了）**：`python -m pytest -n auto -q`
> 偶发 1 failed —— `tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest`。根因是这条用例在
> `--full` 路径上**真的会跑整支浏览器门禁**（26 条真浏览器用例），并行争用下某个 spec 会超时；
> 证据：**同一工作树**里该文件单跑 **29 passed / 79s**、整支 `-n auto` 两次复跑 **5049 passed + 1 skipped**、
> 独立的浏览器门禁 **26 passed**，而评审那一轮 `-n auto` 报 5048 passed + **1 failed** + 1 skipped。
> 与工单 `export-surface-guard/02` §⑥ 记的两条"并行负载下假红"同源。
>
> **2026-09-21～22 追加（工单 launcher-exit-race/01-05：启动器模式下 F5 会把应用自己关掉）**：
> 第 2 节上面那条"产品侧竞态仍在"的现场记录**已结清**（修法见那段 ✅ 与 `.scratch/backlog.md` §16）。
> 本轮的**环境事实四条**：
> ① **浏览器门禁现在五个 spec / 29 条**（`module-intro` 9 + `code-tree-click` 2 + `hwcheck` 10 +
> `ui-contract` 5 + **新增 `launcher-reload` 3**），本机读数 **29 passed / 0 fail / 94.2s**；
> 前端门禁 **1702 passed / 0 fail / 10.1s**（1691 ＋ 判据⑥ 的 11 条）；
> `python -m pytest -n auto -q` **5060 passed + 1 skipped / 131.1s**（5049 ＋ 本单 11 条 tab 用例）。
> ② **`launcher-reload.spec.mjs` 是唯一**用 `startServer({ launcher: true })` 的 spec（给子进程加
> `FIRSTEP_LAUNCHER=1`）；其余 spec **仍然不设**（服务生命周期归夹具那条决策没变）。
> ③ **浏览器门禁模拟不了"真关窗口"**：playwright 的 `page.close()`（含 `runBeforeUnload:true`）
> 走 CDP 关目标，`pagehide` 与 `sendBeacon` **都不跑**——服务端一条 bye 都收不到（实测
> `.scratch/launcher-exit-race/probe-02-close-page.txt`）。所以用例 C 用**真导航离开**（`goto("about:blank")`）
> 验"最后一个页面走了 = 停服务"这条产品不变量。真关窗口那一跳由浏览器自己保证（`sendBeacon`
> 的设计用途），夹具证不了。
> ④ **夹具现在给子进程 `PYTHONUNBUFFERED=1`**：服务被自己关掉/崩掉时，uvicorn 的 access log
> 若压在块缓冲里就随进程一起没了——而那正是这套日志最要被读到的时候（实测只收到 8 行、零请求）。
> 另：**`reload` 之后别只看"平台卡在不在"**——`page.reload({waitUntil:"domcontentloaded"})` 返回时
> 平台卡是 0 个（要再等一次 ready，实测 `probe-03-timeorigin.txt`），而"读到上一个文档的 DOM"
> 会让用例抢跑（本单实测把正在装载的模块图拦腰掐断，看着像产品把自己关了）。判据用
> `performance.timeOrigin`（跨 reload 必不同，实测同份探针）。
>
> ⚠ **怎么会有"孤儿 python"**（本轮实测三次，别怀疑产品）：`node --test … | Select-Object -First N`
> 这种**截断输出管道**的跑法会在收到 SIGPIPE 时把 node 直接带走，`test.after` 里的
> `server.stop()` **来不及跑** ⇒ 夹具起的后端留在内核分配的那个端口上（形态：`python -m
> contest_generator.webapp` 起于某时刻、听着 `127.0.0.1:<高位端口>`；**不是** 8000）。
> 跑浏览器验收时想看前几十行就用 `Tee-Object` 落文件再读文件，别截断管道。清残留：
> 第 2 节那条 `Get-CimInstance … contest_generator.webapp`（按 PID `taskkill /PID … /T /F`）。
> 另：**临时 `git worktree` 用完必须 `git worktree remove`**——留在 `.scratch/<feature>/base-worktree/`
> 时 `tests/test_ps1_encoding.py` 会扫进它 `sources/**` 里第三方缺 BOM 的 `.ps1` 而报红（本轮踩到）。
>
> **2026-09-22（webapp-state-into-ctx/01–04 会话，C6 落地）**：这一单把三处进程级会话态搬进
> `AppContext`（账见 `.scratch/backlog.md` §17），**不改端口 / 工具根 / 快照路径 / 端点契约**，
> 前端只动了 `static/js/fx/task.js` 里一行注释的名字。**本单一次服务器都没起**
> （全走进程内 TestClient + 探针）；收尾实测 **2026-09-22 18:28**：8000/8020/8021/8791 都没在听、
> 无残留 `contest_generator.webapp` 进程。所以**第 0 节的发布落差表不动**（main-only 的仍是硬件
> 检测那两批）。
> ⚠ **别把套件的临时后端当残留**（本轮实测）：跑全套 `pytest -n auto` 时它会自己起真后端
> 子进程（**内核分配端口**，本轮在 11883 / 13157 上看到过，PID 起于 18:25–18:26、18:28 自己
> 消失）——那是夹具，不是孤儿；同节上文那条「孤儿 python」指的是**截断输出管道**把 node 带走
> 留下的那种。判据用上面那条 `Get-CimInstance … contest_generator.webapp`，并且**跑完再看一次**。
> 读数：`python -m pytest -n auto -q` **5070 passed + 1 skipped**、`node --test "tests/js/*.test.mjs"`
> **1702 passed / 0 fail**；判据强度与红证见 `.scratch/webapp-state-into-ctx/`。
> ⚠ **本单的判据强度探针会真改库内文件**（`probe-02-guard-strength.py` 往 `tests` 的守卫里追加
> stub 再逐字节复原）——**别和测试套件同时跑**（先例：`module-hwcheck/09` 那条纪律）。
> ⚠ **本轮量到的两条工具事实**（证据文件类工作适用）：
> ① **PowerShell 5.1 的 `>` / `Tee-Object` 写 UTF-16LE**——`read` 工具把它当二进制拒读，
> 证据文件让探针自己落盘（`python probe.py --out <file>`，UTF-8）。**这条的真源与判据早已在
> 仓库里**（`tests/js/windows-text-encoding.test.mjs` 的文件头 ②，工单 gen-chain-audit/04），
> 这里只记"本单又撞了一次、出路是 `--out`"。
> ② `git show <rev>:<path>` 的 path 要 **POSIX 正斜杠**，Windows 的 `str(Path)` 给反斜杠时
> 那条路会静默取不到文件（红证的测试侧两条腿曾凭空消失）。
>
> **2026-09-22（full-update-state-into-ctx/01–04 会话，C6 的尾巴结清）**：这一单把完整包链路的
> 模块级会话态搬进 `AppContext` 并补上 `_full_task_lock`（账见 `.scratch/backlog.md` §18）。
> 与环境有关的事实**只记与上一条不同的部分**：本轮**同样一次服务器都没起**（全走进程内
> TestClient + 探针；那条并发判据起的是同进程的两个线程，不是服务器）、**前端零字节改动**、
> 收尾实测 **2026-09-22 21:4x**：8000/8020/8021/8791 都没在听、无残留
> `contest_generator.webapp` 进程 —— 「不改端口 / 工具根 / 快照路径 / 端点契约」与
> 「第 0 节发布落差表不动」同上一条（不重抄）。**新增一条与本机有关的最小事实**：本轮把
> `tests/test_webapp_state_home.py` 的判据面扩到两条腿 + `src/` 全域，该文件单跑
> **15 passed / 6.6s**（扩面前 7 条 / 9s；中途因两腿反复解析涨到 34s，给 `_parse` 加
> `lru_cache` 后回落）。
> 读数：`python -m pytest -n auto -q` **5081 passed + 1 skipped**；`node --test "tests/js/*.test.mjs"`
> **1702 passed / 0 fail**。红证与判据强度见 `.scratch/full-update-state-into-ctx/`
> （另：C6 的红证探针复跑读数 `c6-pin-probe-recheck.txt`）。
> ⚠「强度探针会真改库内文件、别和套件同时跑」的纪律同上（本轮的 `probe-02-guard-strength.py`
> 仍是那一支，17 条腿；它住在 `.scratch/webapp-state-into-ctx/`，管的是**整个**守卫文件）。
> ⚠ **本轮量到的两条工具事实**（探针/证据文件类工作适用）：
> ① **本机控制台是 GBK + 探针「先 print 再写 `--out`」= 证据文件会连带丢**：报告里的
> `✗` / `✅` / `→` 在 `print` 上抛 `UnicodeEncodeError`，而写盘在 print 之后 → 整份证据没落盘
> （本轮两条探针各撞一次）。两条出路：给**不许改**的既有探针设 `PYTHONIOENCODING=utf-8`
> （C6 的红证探针就是这么复跑的），或把探针改成**先落盘再打印** +
> `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`（新写的与本轮维护过的那支已改）。
> ② **红证要按 base 的文件清单取源码**（`git ls-tree -r --name-only <rev> src`）：拿当前树的
> 清单去 `git show <rev>:<path>`，base 里有、今天已删的文件会**静默漏掉**（读数会缺一块）。
> 另：`pytest -n auto` 本轮又撞上一次 `tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest`
> 的并行争用偶发（该文件单跑 29 passed / 78s，复跑全绿）——与上文那条同源，不是产品问题。
>
> **2026-09-22（hwcheck-unknown-device/01 会话：库内新增总线原语模块 `i2c_probe`）**：
> 同样**一次服务器都没起**（真编译矩阵走子进程、端点用例走进程内 TestClient）；
> 收尾实测 8000/8020/8021 都没在听。读数：新增契约 `tests/test_module_i2c_probe.py`
> **19 passed**、全量 `pytest -n auto -q` **5101 passed + 1 skipped**、
> 前端门禁 **1702 passed / 0 fail**、两平台真编译 **2/2 PASS（0 error / 0 warning）**。
> 证据与红证：`.scratch/hwcheck-unknown-device/`（`compile_matrix.py` +
> `matrix-logs/`、`probe-01-c1-reverse.py{,.txt}`、`verify-01-readings.txt`；
> `matrix/` 是生成+编译产物，按惯例 gitignore）。
>
> ⚠ **本轮量到的一条工具事实（对任何「编译矩阵」探针适用）**：**别再按
> 「行里含 `warning`」数告警** —— Keil 的收尾汇总行 `0 Error(s), 0 Warning(s).`
> 自己就含这个子串，会把 0 告警读成 1 条（本单第一版就是这么误报的，被
> Standards 轴评审抓到）。排除掉 `... Warning(s).` 那种汇总行再数。
>
> ⚠ **同轮量到的一条产品事实（写 mspm0 硬件 I2C 代码时适用）**：SDK 的
> `DL_I2C_startControllerTransfer` 长度参数文档范围是 `[0x00, 0xFFF]`，但**全 SDK
> 没有 0 长度用法的示例**——0 长度突发到底发不发 START 没人能给准话。面对
> 「ping 静默永远无应答 = 把线/供电问题误报成真相」这种代价，本单选了**读 1 字节
> 丢弃**（有例可循），并把这一选择写进模块 notes。另外 `ADDR_ACK` 状态位是判地址
> 应答的正解——**库内先例 `ml_mpu6050/mpu_port.c` 并不读它**（只看 `ERROR`），
> 别把「双位判据」记成 mpu_port.c 的做法。
>
> ⚠ **上一轮那条「强度探针会真改库内文件、别和套件同时跑」的纪律本轮同样适用**
> （`probe-01-c1-reverse.py` 会临时注入 `syscfg_instances.py` 再逐字节复原；
> 本轮做法 = 探针跑完再跑套件，且探针自带「前置干净性检查 + sha256 复原复核」，
> 评审又补了「子进程崩溃不许被误读成反证成立」）。
>
> **第 0 节的发布落差表：本轮又添一批 main-only 改动**（工单
> `hwcheck-unknown-device/01`：库内新模块 `i2c_probe` ＋ 两平台实现 ＋ 四处登记；
> 后续 02–10 张工单仍未开工）——下次发版要连同上面那三批一起带上。
>
> **2026-09-23（hwcheck-unknown-device/02 会话：「我的器件」库外件落地）**：
> 这一单把「库外件」这条数据路打通（域模块 `my_devices.py` ＋ 三个端点 ＋
> 检测页卡片；**不生成任何代码**）。与环境有关的事实：
> ① **同样一次服务器都没起**（端点用例走进程内 TestClient，浏览器验收走夹具
> 自带的真后端 + 内核分配端口）；收尾实测 8000/8020/8021/8791 都没在听、
> 无残留 `contest_generator.webapp` 进程。
> ② **新落点 = `<配置目录>/hwcheck_devices/<id>/`**（真机上 =
> `~\.contest_generator\hwcheck_devices\`，与 `updates\` / `cache\` 同级）。
> 浏览器验收那几条自建件用例**会真的往这个目录写**（它们自己收尾时删掉），
> 跑完留一个**空目录**是正常的——本次会话收尾已手工删掉那个空目录。
> ③ 读数：`python -m pytest -n auto -q` **5183 passed + 1 skipped**、
> 前端门禁 **1739 passed / 0 fail**、浏览器门禁 **34 passed / 0 fail**；
> 反证（拿掉撞名守卫 → 两条撞名用例变红、逐字节复原）见
> `.scratch/hwcheck-unknown-device/probe-02-guard-strength.txt`。
>
> ⚠ **本机量到的一条门禁偶发（不是产品缺陷，别误判）**：浏览器门禁**连跑 34 条**时
> `launcher-reload.spec.mjs` 会偶发红（A 在 `page.reload` 上 30 秒超时 → B/C 跟着
> 9ms/37ms 速败）；**单跑这一支 3/3 全绿**（读数
> `.scratch/hwcheck-unknown-device/browser-02-launcher-isolated.txt`）。那支 spec
> 不碰检测页，与本次改动无交集——与第 2 节记的「并行争用下假红」同源。
>
> ⚠ **同轮量到的两条工具事实**（对后面 03–10 张工单同样适用）：
> ① **`TestClient` 会先把 URL 归一化**：想验「原始路径打进来」的判据
> （`DELETE /api/my-devices/%2e%2e` 这类编码穿越），必须用
> `httpx.ASGITransport` + `extensions={"path": ...}` 直接喂 ASGI——写成
> `client.delete("/api/my-devices/..")` 会假绿（请求被归一成 `/api/`，
> 根本到不了那个路由）。
> ② **`console.log` 在 `node --test`（真浏览器 spec）里可能整条不见**：
> 本次排查一个按钮态问题时，诊断输出一行都没进 tee 的日志文件，
> 最后是靠**断言消息**（assert 的第三个参数带 JSON 现场）拿到读数的。
> 排查这类问题优先用"会随失败打印的断言消息"，别指望 console.log。
>
> **第 0 节的发布落差表：本轮再添一批 main-only 改动**（工单
> `hwcheck-unknown-device/02`：新域模块 `my_devices.py` ＋ 前端 fx/ui ＋
> 检测页卡片 ＋ 三个新端点；**用户数据目录里多一个 `hwcheck_devices/`**——
> 那是运行时数据、不进发布包，但升级后第一次用会新建它）。
> 后续 03–10 张工单仍未开工。
>
> **2026-09-23（hwcheck-unknown-device/03 会话：自建件探测小节 + stm32 真编译）**：
> 库外件第一次真的产出 C 代码（`hwcheck_custom.py` 渲染三种形态的探测小节，
> 注入 `main.c` 的**唯一产地** `render_main_c`）。与环境有关的事实：
> ① **同样一次服务器都没起**（验证走进程内域函数 + 真 UV4 子进程 + 浏览器门禁）；
> 收尾实测 8000/8020/8021/8791 都没在听、无残留 `contest_generator.webapp` 进程。
> ② **本机 Keil 真编译 4 次**（`find_uv4()` 探到 `C:\Keil5\Core\UV4\UV4.exe`，
> 每次 3–5 秒）：四种形态（三档文案 ＋ 无输出通道）**全部 0 error / 0 warning**，
> 读数 `.scratch/hwcheck-unknown-device/probe-03-compile-stm32.txt`、逐格原始日志
> `matrix-logs/custom-*.log`。探针**不手写 main.c**（走 `hwcheck_view` +
> `render_main_c` 真路径），否则验的就不是要验的东西。
> ③ **新落点（探针用）**：`.scratch/hwcheck-unknown-device/probe-03-data/`
> ——编译探针自建的临时数据目录（探针每次自清，**已加 .gitignore**）；
> 它模拟的是真机的 `~\.contest_generator\hwcheck_devices\`，跑完不留东西。
> ④ 读数：`python -m pytest -n auto -q` **5222 passed + 1 skipped**、
> 前端门禁 **1739 passed / 0 fail**、浏览器门禁 **34 passed / 0 fail**；
> 反证（多插一个头里不存在的函数 → 守卫四条全红、逐字节复原）见
> `.scratch/hwcheck-unknown-device/probe-03-guard-strength.txt`。
>
> ⚠ **同轮量到的一条产品事实（自己踩的，已补用例钉住）**：**"从模块集里摘掉自建件"
> 必须摘"选中的全体"，不能只摘"出了小节的那几件"**。非 I2C 件与"没勾输出通道"
> 的形态不出小节，但它们**仍然不是模块**——漏摘一件就在 `resolve_dependencies`
> 报「库中没有这个模块」，端点是 400。判据：
> `tests/test_my_devices_endpoint.py::test_a_non_i2c_custom_device_still_does_not_render_a_probe`。
>
> **2026-09-23（hwcheck-unknown-device/04 会话：mspm0 探测分支 + 两平台编译矩阵）**：
> 环境事实与读数：
> ① **同样一次服务器都没起**（验证全走进程内域函数 + 真 UV4/gmake 子进程 +
> 真浏览器 spec、夹具自带后端）；收尾实测 8000/8020/8021/8791 都没在听、
> 无残留 `contest_generator.webapp` 进程。
> ② **本机真编译 23 次**：mspm0 走 `C:\ti\ccs2050\ccs\utils\bin\gmake.exe`
> （每格含 SysConfig CLI，约 15–40 秒）、stm32 走 `C:\Keil5\Core\UV4\UV4.exe`
> （3–5 秒）；**11 格 × 2 平台 0 error / 0 warning**
> （读数 `.scratch/hwcheck-unknown-device/probe-04-compile-matrix.txt`，
> 逐格原始日志 `matrix-logs/custom-<格>-<平台>.log`）。
> ③ **探针改名**：`probe-03-compile-stm32.py` → **`probe-03-compile-matrix.py`**
> （mspm0 那一轴并进来；旧的 `probe-03-compile-stm32.txt` 读数仍在，只是里面记的
> 命令名已过期）。04 之前那几个读数是 `probe-03-*.txt`、04 的是 `probe-04-*.txt`
> （同名不同轮，认文件名时注意）。
> ④ 读数：`python -m pytest -n auto -q` **5234 passed + 1 skipped / 153.3s**、
> 前端门禁 **1739 passed / 0 fail**、浏览器门禁 **35 passed / 0 fail / 123.3s**
> （新增一条真浏览器用例「自建件在地猛星上的接线」）；反证（三条注入各自变红 +
> 逐字节复原）见 `.scratch/hwcheck-unknown-device/probe-04-guard-strength.txt`。
>
> ⚠ **本轮量到的三条工具事实**（对后面任何"编译矩阵"或"渲染产物"改动都适用）：
> ① **探针必须走产品那条路**：自己 `resolve_dependencies()` + `generate()` 会漏掉
> `view.pin_bindings`（检测页生成前自动移开的脚）→ 产物撞 PA22、mspm0 全格 400。
> 产品端点在 webapp 里调的是 `generate_project(slugs=…, bindings=…)`；
> ② **`Debug/ti_msp_dl_config.h` 是编译期产物**（`Debug/makefile` 第一条规则跑
> SysConfig CLI）：判 `I2C_0_INST` 必须在 gmake **之后**，放在生成后判永远读到
> "文件不在"；
> ③ **"逐字节复原"的探针要用 bytes 读写**：文本模式会把 CRLF 归一成 LF，写回去
> 与原文差行尾 →「复原复核」假红（本轮 `probe-04-guard-strength.py` 第一版就是
> 这么红的，注入与守卫其实都对）。
>
> ⚠ **同轮量到的一条工具链事实（不是本仓库代码的告警）**：TI 链接器在**选了用堆的
> 模块**（`ml_mpu6050` 一族）时开一个默认 0x800 的 `.sysmem` 段并提示
> `warning #10210-D ... use the -heap option`。实测同一份配置**去掉 `ml_mpu6050`
> 就一条都没有**——编译矩阵要把它单列一栏，别混进"我们代码的告警数"（否则
> "0 warning"这条验收线永远红在一个改不动的点上：要改得动 mspm0 母版的链接选项，
> 属跨平台共享面，另议）。

> **同轮发现并开单的一条既有母版缺陷**：`library/masters/mspm0/mspm0.syscfg` 里
> **14 组重名引脚符号**（`SCL`/`SDA` 各 17 件、`CS` 5 件、`OUT` 6 件…）。SysConfig
> 对 `$name` 有全局唯一要求，于是**一个自建件都不选、只勾 OLED + JY61P 就是 4 个
> error**（`Duplicate name: 'SCL'`）；而既有的 `syscfg_pin_conflict_report` 只判
> "同一个脚被两个实例占用"，看不见这一轴。明细与最小复现：
> `.scratch/hwcheck-unknown-device/issues/11-mspm0-pin-name-collision.md`。
>
> **第 0 节的发布落差表：本轮再添一批 main-only 改动**（工单
> `hwcheck-unknown-device/04`：两平台编译矩阵探针重命名 ＋ 渲染器两条缺陷修
> （重复定义 / 死代码）＋ 平台代价进产物注释 ＋ 一条真浏览器用例。
> **外加工单 11**（mspm0 引脚符号重名 —— P0，见下）；后续 05–10 张工单仍未开工。
>
> **2026-09-23（hwcheck-unknown-device/11 会话：mspm0 引脚符号重名，P0）**：
> 这一单把"任选两件 I2C 器件就编不过"从**静默生成**改成**生成前大声拦下**。
> 与环境有关的事实：
> ① **同样一次服务器都没起**（验证走进程内域函数 + TestClient + 真 UV4/gmake
> 子进程 + 真浏览器 spec 自带后端）；收尾实测 8000/8020/8021/8791 都没在听、
> 无残留 `contest_generator.webapp` 进程。
> ② **本机真编译 24 次**（12 格 × 2 平台）：`probe-03-compile-matrix.py` 全绿
> （工单 04 的矩阵在 11 之后复跑仍 0 error / 0 warning），另有 `probe-11-contest-
> dupname.py` 的 4 组赛题主线组合。
> ③ 读数：`python -m pytest -n auto -q` **5259 passed + 1 skipped / 131.1s**、
> 前端门禁 **1748 passed / 0 fail**、浏览器门禁 **36 passed / 0 fail / 124.4s**；
> 反证（4 条注入 + 逐字节复原）见 `.scratch/hwcheck-unknown-device/
> probe-11-guard-strength.txt`，验收读数 `probe-11-contest-dupname.txt`。
>
> ⚠ **本轮量到的一条产品事实（对任何"新判据"都适用）**：**判据加在报告里不等于
> 所有入口都吃到**。新判据（`syscfg_prune` 的同名引脚轴）加进
> `syscfg_pin_conflict_report` 后，生成门禁与检测页自动有了——但赛题页的
> **`/api/bindings/auto`（自动配置）与 `/api/bindings/validate`（进生成前的校验）**
> 是另外两个入口，它们当时**不读**这份报告：于是"点自动配置回 ok:true、点生成
> 才 400"。本轮把这四条路（生成门禁 / 检测页 / auto / validate）全接上同一判据。
> **纪律：加判据时先问"谁都会读它"**，别只看那个最先想到的调用方。
>
> ⚠ **同轮量到的一条架构纪律**：**读盘那一步也算"装配"**。本轮第一版把
> `hwcheck_board.read_master_syscfg`（读母版 syscfg）import 回 `webapp.py` 给上面
> 两个端点用 —— `tests/test_hwcheck_assembly_home.py` 的 import 面守卫当场红
> （那是"检测页装配住在域层"的不变量）。出路是把读盘也收进域层
> （`syscfg_prune.syscfg_pin_name_conflict_for`），端点只调一个名字。
>
> **2026-09-23（hwcheck-unknown-device/05 会话：检测页的自建件计划）**：
> 这一单把「这一趟对自建件做什么」**显示到页面上**（接线那一行 / 建议顺序 /
> 标注词 / 上板清单三类），并补上"不出小节的件也要在计划里"（非 I2C、没勾输出
> 通道——如实说为什么没有它的探测程序）。与环境有关的事实：
> ① **同样一次服务器都没起**（验证走进程内 TestClient + 域层纯函数 + 前端门禁 +
> 真浏览器夹具自带的后端）；收尾实测 8000/8020/8021/8791 都没在听、
> 无残留 `contest_generator.webapp` 进程。
> ② 读数：`python -m pytest -n auto -q` **5253 passed + 1 skipped / 159.4s**、
> 前端门禁 **1748 passed / 0 fail**（改动前 1739）、浏览器门禁 **36 passed / 0 fail /
> 105.0s**（改动前 35；本单 +1 条「自建件的检测计划」用例，排在 `hwcheck.spec.mjs`
> **最后**——它会生成一个新工程，插在中间会打乱该 spec 后面几条的"上次生成目录"回读）。
> ③ 反证（**5 条后端注入 + 2 条前端注入**，逐字节复原 + sha256 复核）见
> `.scratch/hwcheck-unknown-device/probe-05-guard-strength.txt` 与
> `probe-05-guard-strength-front.txt`（探针 `.py` / `.mjs` 同名）。
>
> ⚠ **本轮两条与"探针"有关的工具事实**：
> ① **探针的指纹表要跟着注入面一起长**：`probe-05-guard-strength.py` 的收尾复核
> 用 `before[path]` 取前置指纹，新加一条注入（webapp.py）却忘了往 `files` 里加那个
> 文件 → `finally` 里 `KeyError`（**注入已逐个复原**，只是复核那一步炸了）。
> 加注入时同步加文件；「前置干净性检查」这一条纪律挡的是"被强杀留在注入态"，
> 挡不住这种"自己写漏一个文件"。
> ② **评审期间别改工作区**：本单的 Spec 轴评审是并发跑的，中途一次整改让它读到
> `NameError: _ANSWER_LABEL` 的中间态，并让已落盘的 `probe-05-*.txt` 里的 sha256
> 当场过期。**收尾必须在一份冻结的 revision 上重跑探针与三门禁**（本单照做，
> 工单里记的是重跑后的读数）。

### 2.1 「重启」与「全量更新」不是一回事（2026-09-13 实测）

**现象**：重启（`stop-firstep.vbs` + `start-app.vbs`）之后 `/api/health` 立刻是新版本，**一个字节都不用下**——
因为包里的文件与工作树逐字节同源（打的包就是这棵树）。但工具内「资料库更新」会报 `baseline-missing`
（前端话术「资料库版本未知…」）。

**根因**：`sources/materials/.materials-manifest.json`（本地基线清单，`materials_pack.MANIFEST_FILENAME`）
**不在完整包里**，只在走完整包替换那一步由 `tools/update-app.py:396 write_materials_baseline()`
从完整包清单的 `materials_manifest` 写回工具根。**直跑源码 / 普通重启永远不会写它**
（本次真身就是这种情况：文件不在，`/api/update/materials/check` → `error=baseline-missing`）。

**真身已就地补上（2026-09-13，不必下 770 MB）**：

| 项 | 值 |
|---|---|
| 脚本 | `.scratch/materials-baseline-writeback/init-baseline.py`（`--write` 才落盘；默认 dry-run 只对比） |
| 写了什么 | `sources/materials/.materials-manifest.json`（12 批次 / **5081 文件** / 1,473,311 字节，version=v1.2.0） |
| 判据 | 与 `firstep-pack\firstep-full-v1.2.0.manifest.json` 的 `materials_manifest` 做**逐文件 sha256 对比全等**才写 |
| 关键坑 | 扫描必须传 `full_pack.materials_excluded` 当排除规则——否则把 **36 个「故意不进包」的第三方安装包**（CCS_20.5 / VSCode / `*.img*` / `*.rar` / `tsp-xbhdcc`…）当成「本地多出」，5117 vs 5081 直接对不上 |
| 现状 | 检查已从 `error=baseline-missing` 变成 `error=no-release`（「还没有发布资料库更新包」）——基线读到了，当前版本识别为 v1.2.0 |
| 会不会污染仓库 | 不会：`sources/materials/` 整目录在 `.gitignore` 第 33 行，基线进不了 git / 发布包 |
| 沙箱 | **已补**（2026-09-19 实测：重建脚本会顺带把基线写回，见下） |

> **2026-09-19 更正（发 v1.2.2 时量到）**：上面那行原本写「沙箱还没补」——
> **它已经补了**，而且判据比真身那次更直接：`rebuild-sandbox-v111.py` 第四节会按
> `tools/update-app.py:write_materials_baseline` 的同款口径，从**刚解开的 v1.1.1 全量包清单**
> 写回 `sources/materials/.materials-manifest.json`。实测（`measure-baseline.py`）：
> 沙箱基线 `version=v1.1.1` / 12 批次 / **5087 文件**，与 v1.1.1 包内清单**逐文件全等（零差集）**。
> 「5087 vs 真身 5081」的差不是缺陷，是资料库演进：v1.2.0 做过一次库治理回收了 6 个重复文件
> （v1.1.1 = 5087 → v1.2.0/v1.2.1/v1.2.2 = 5081）。沙箱升到 v1.2.2 之后，完整包那条路
> （或更新器的第 7 步）会把它带到 5081。

**顺手修掉的一处用例环境耦合**（这次补基线时暴露的）：`tests/test_materials_update.py::test_check_endpoint_baseline_missing`
原先**没有注入资料库目录**，读的是真身 `sources/materials/`，于是「真机上有没有基线」这个真机状态直接决定它的红绿
（我一写基线它就红了；同文件姊妹用例 `test_check_endpoint_has_new_version` 本来是注入的）。已改成注入空目录，
判据一个字没改。**这条不是产品缺陷，是用例把环境当夹具了。**

**版本号怎么看才准**：改完 `src/contest_generator/__init__.py` 后，**已经在跑的进程不会变**——
浏览器刷新、重新打开页面都没用（`/api/health` 与「检查更新」都吃进程内的模块）。必须重启进程。

**将来要发资料库增量包时**（`materials-v*` release，线上目前一个都没有）：发布侧基线用
`firstep-pack\firstep-full-v1.2.0.manifest.json` 里的 `materials_manifest` 即可，**不必**再单独留一份
`firstep-materials-*.manifest.json`——两者本来就是同一份东西（本次已实测逐文件相等）。

## 2.5 本机 Python 与依赖现状（2026-09-13 实测，动过就回来改）

| 项 | 值 |
|---|---|
| 系统 Python | **3.14.6**（`py -0p` 只有这一个；满足工具的 ≥3.13） |
| 依赖 | fastapi / uvicorn / pypdf / pillow / pymupdf **已装在全局 site-packages** |
| 真身 `.venv` | **现在有了**（2026-09-13 11:09 由 `install.bat` 建，跑依赖自检通过）——`start-app.bat` 会优先用它；在那之前真身一直是走「回退系统 python」分支 |
| 沙箱 `.venv` | 不存在（第 1 节已记，属于故意不真实项） |

**已清理的隐患（2026-09-13）**：全局 site-packages 里曾有**两个**同名 editable 安装并存，
版本元数据指向**同一套源码的两个路径**——`0.1.0 → Desktop\firstep-sim\src`、
`1.1.1 → Desktop\firstep\src`（注意方向：版本号小的指向沙箱、大的指向工作区，我先前记反过）。
已用 `python -m pip uninstall -y contest-generator` 把 `0.1.0` 那份元数据清掉（pip 卸装输出留痕：
`Uninstalling contest-generator-0.1.0`）。**残留的那份 `1.1.1` 指向 `firstep-sim\src`**，
两份源码同源所以无害——但**再跑全局 `pip install -e .` 会重新制造重复元数据**，要装就用 `.venv`。

**2026-09-18 更新（B1 演练把它又搅了一次，现已归零）**：

| 时刻 | 全局 editable 安装 | 怎么来的 |
|---|---|---|
| B1 之前 | `1.1.1 → firstep-sim`（上面记的那份残留） | 历史遗留 |
| B1 更新器跑完 | `1.1.1` + **`1.2.1`** 两份并存（都 → `firstep-sim`） | 沙箱无 `.venv` → 更新器第 7 步 `pip install -e .` 装进**全局**（`pyproject.toml` 变了就装，这是产品设计） |
| 演练收尾（本次） | **零**（`python -m pip list` 里已无 `contest-generator`，site-packages 无 `contest_generator-*.dist-info`） | `python -m pip uninstall -y contest-generator` 两次 |

**副作用是好的**：裸 `pytest` 那个坑（被测对象变成沙箱源码，见下面那段）**因此消失**；
但**跑测试仍然用 `python -m pytest`**（`pyproject.toml` 的 `pythonpath=["src"]` 才是口径来源，
别依赖任何全局安装）。下次谁再在无 `.venv` 的根上跑更新，会重新装进全局——**那之后记得再卸一次**。

**本机不该丢的环境变量**：`LOCALAPPDATA` / `USERPROFILE` 这类被清空或改错时，pip 找不到缓存目录
就会在当前目录建 `pip\cache\`（实测在仓库根落了 111 个文件）。演练脚本改环境变量请**逐项增删**，
别整段替换 `PATH`/`USERPROFILE`。

**跑测试的命令有讲究（2026-09-13 实测，工单 10 撞上）**：用 **`python -m pytest`**。
`pyproject.toml` 里 `pythonpath = ["src"]` 只保证 pytest 把本仓库 `src/` 排在最前；
而**裸 `pytest` 命令**会先走全局 site-packages 那份 editable 安装——它指向的是
**沙箱 `Desktop\firstep-sim\src`**，于是被测对象变成沙箱源码而不是你正在改的源码
（工单 10 实测：同一批用例在沙箱源码上 41 failed，在自己源码上全绿，白排查一轮）。
`.venv` 里**没有 pytest**（只有运行依赖），所以要跑测试就用系统 python +
`python -m pytest`（`-p no:cacheprovider` 可选）。

**全套会间歇性卡死（2026-09-13 工单 11 实测两次）**：一条 `python -m pytest` 跑全套有时会
**十分钟以上不返回、CPU 只烧 120s**（一次整支探针无输出被我按中断杀掉，一次后台跑 40 分钟
没完）。逐文件跑就正常：**196 个文件 / 335 秒 / 4457 passed + 1 skipped**（同一批用例）。
定位脚本 = `.scratch/resumable-download/run-11-suite.py`（逐文件 + 每文件 120s 超时，
卡住与转红分开记，原始输出落 `verify-11-suite.txt`）。**卡住不算判据**，要单独复跑。

**补充（2026-09-13 工单 12 实测，把「间歇」钉到一个具体触发点）**：卡死不只出现在整支全套——
`python .scratch/resumable-download/run-11-suite.py 120` 这一轮里
`tests/test_download_status_surface.py` 连续三次 >120s 不返回（另一次跑到 >600s 也没完），
逐用例隔离后落在 `test_message_cleared_when_backoff_window_closes`：
它的 spy 在每次进度回调里调一次 status，**只要「速度窗口记账」那一句没被推进
（`task._last_ts` / `_last_bytes` 不更新，或 status 本身抛错被重试路径吞掉），退避循环就空转**。
所以：① 「多文件一起跑会卡、单文件跑十几秒完事」是**同一批用例的两种结果**，别当成产品问题；
② 遇到某一格卡住要定位时，用 `-o faulthandler_timeout=25 -v -s` 让 pytest 自己转储栈
（本单就是这么钉到第 355 行的），别猜；③ 测量类脚本给每格配超时、把「卡住」与「红」分开记
（工单 12 的探针已按逐文件跑 + 每格 120s 落地）。同一批用例的通过数：本轮全套
**196 文件 / 绿 196 / 红 0 / 卡住 0**（耗时 550s 上下，随机器负载浮动）。

### 2.5c 口径更新：卡住 = 红 + 并行 opt-in（2026-09-16，工单 `test-speedup/01-03`）

**上面那两段「卡住不算判据」的旧口径已作废。** 现在：

| 项 | 值 / 口径 |
|---|---|
| 全库默认超时 | `pyproject.toml` 的 `timeout = 180` + `timeout_method = "thread"`（`pytest-timeout`） |
| 阈值依据 | 最慢的**正当**用例是 `tests/test_full_pack.py::test_repo_start_here_ships_in_package`，并行争用下 **47.3s**（串行时整个文件才 16.8s）→ 180s ≈ 3.8 倍余量，避免把「机器忙」误判成卡死 |
| **触发时的语义** | Windows 上只有 `thread` 方法（`signal` 直接 INTERNALERROR，已实测）——它会打印所有线程的栈并**中止整场**，不是只废掉那一格。所以阈值宁可给宽：假红的代价是一整轮白跑 |
| 并行 | `pytest-xdist` 已装，**opt-in**：命令里 `-n auto`。**不写进 addopts**——全仓共享配置会改掉所有既有跑法（文档 / 探针 / `.scratch` 批跑器），并行引入的偶发也更难归因 |
| 守卫 | `tests/test_suite_timeout.py`（配置在不在、值在不在区间、**仪器真的会响**——造一个会睡的用例跑子进程 pytest） |

**本轮实测数字**（2026-09-16，同一套用例 4472 passed + 1 skipped）：

| 跑法 | 耗时 |
|---|---|
| 逐文件（`.scratch/resumable-download/run-11-suite.py 120`，196 文件） | **315.1s**（卡住 0） |
| 整支单进程 `python -m pytest` | **155～172s**（9 轮） |
| 整支并行 `python -m pytest -n auto` | **79.85s**（**2.0×**，通过数一致） |

**卡死复现结论：9 轮整支 pytest 全部没卡**（3 轮 + 6 轮，`probe-hang.py`，
带 `-o faulthandler_timeout=30` 自动倒栈，逐轮输出在 `.scratch/test-speedup/run-*.txt`）。
所以那件「间歇性卡十分钟」**至今未定性**——现在至少有了上限：卡住最多等 180s 就变红并倒栈，
不会再无声地耗掉一小时。**别把这条写成「已解决」**。

**逐文件跑法保留**（不取代）：它的分工是「卡住与红分开记」，与整支超时互补。

### 2.5d 三道闸门（2026-09-16 起，工单 `commit-gate/01-04`）

推之前、合并之前、发版之前各有一道自动闸门——**细节见 `docs/agents/workflow.md`
「闸门」一节**，这里只记「这台机器上要做的动作」：

| 事项 | 这台机器上的做法 |
|---|---|
| 本地 pre-push 闸门 | **要手动配一次**：`git config core.hooksPath .githooks`（新 clone 默认没有；本机已配） |
| 远端 CI | `.github/workflows/ci.yml` 已在跑：push 与 PR 上，windows 全套 + ubuntu 快速面。**不联网、不吃 secret** |
| 发版前自检 | `powershell -File tools\preflight.ps1`（四项：三处版本号 / 母版编码钉 / 下载文档 / README 版本行） |
| 想知道「这次 push 会跑什么」 | `python tools/prepush.py --dry-run`（或 `FIRSTEP_PREPUSH=select-only`） |
| 前端用例（`tests/js/`） | **2026-09-20 起接进闸门**（工单 `module-hwcheck/01`）：改动落在 `src/contest_generator/static/` 或 `tests/js/` 时，本地闸门与 CI 都会跑 `node --test "tests/js/*.test.mjs"`（本地由 `tools/prepush.py` 在 Python 侧展开文件清单后传给 node——**Node 20 不认 glob 位置参数**，故不把 glob 交给 node；CI 另用 `setup-node` 钉在 22） |

**本机前端测试口径**（2026-09-20 实测，Node v24.15.0）：`node --test tests/js`
（目录形式）**跑不起来**——node 会把目录当模块解析并报
`Cannot find module '...\tests\js'`。要么写 glob、要么列文件：`node --test
"tests/js/*.test.mjs"`（≥21）或 `node --test tests/js/*.test.mjs`（由 shell 展开）。
仓库里 30+ 个前端用例文件头注释仍写着目录形式，属于**过期注释**（不影响执行，
改到哪个顺手改哪个）。

**两条硬约束**（都是 2026-09-16 实测踩出来的）：
1. **钩子文件必须 LF + 无 BOM** —— 带 BOM 时 git 报 `cannot spawn ...: No such file or
   directory` 且**成功 push 时 stderr 静默**，表现为"钩子存在却从不生效"；
2. **CI 的 checkout 必须 `fetch-depth: 0`** —— 浅克隆里 CHANGELOG 锚点守卫查不到提交
   （连 `HEAD~1` 都没有），会在最需要它的地方假红。

**本机测试夹具的一条新纪律**（CI 首轮抓出来的）：**测试读的文件必须在 git 索引里**。
2026-09-16 之前 `.scratch/real-run/` 下的真机 buildlog 与推荐缓存没入库，
于是「本机全绿、CI 12 条红」。判断标准就一句：**测试读它 → 就要入库**（`.gitignore`
加例外，注意 git 的规矩：父目录被排除时里面的 `!` 不生效，要逐层放行）。

**顺带发现（同一轮）：main 上本来就有一条红**——`tests/test_readme.py` 的母版同步守卫，
根因是 2026-09-15 的清理误删 mspm0 母版 `.settings/`（含 CCS 编码钉）。已修，见第 7 节。

## 2.5b 演练脚本的两条铁律（2026-09-13 用血换的）

1. **真身文件只读**：任何"改写一份再跑"的演练，改写目标必须是 `%TEMP%` 下的副本。
   当天我给验证脚本算错了仓库根层数（`.scratch/<slug>/` 下 `parents[2]` 才对），
   于是测试每跑一次就把「测试版 `install.bat`」覆盖到真身文件上一次——排查花了很久，
   而且它伪装成"产品坏了"。**写这类脚本时先断言 `真身文件字节未变`。**
2. **模拟外部命令别用 `.cmd`/`.bat` 垫片**：批处理里调用 `.cmd` 会**转移控制权**（缺 `call`），
   父脚本直接终止——看起来就像"脚本自己提前退了"。要模拟版本不符，只改脚本里那一行判断。

## 2.6 新用户下载体验的演练口径（2026-09-13 起，`newuser-download` 特性）

要当一次「新用户」把完整包走通，**不必动沙箱**——用这套更干净的口径（`.scratch/newuser-download/E2E-8020.md` 有细节）：

1. 从**真实包**解压到一个一次性工具根（`%TEMP%\firstep-l2\tool`），而不是拼装沙箱；
2. **重定向 `USERPROFILE`** 到同一目录下的 `profile`（实测 `Path.home()` 跟随它）→
   配置 / 日志 / updates 全被关进演练目录，真身 `~\.contest_generator` **零触碰**；
3. `FIRSTEP_LAUNCHER_PORT=8020` 起服务；
4. 依赖靠 `venv --system-site-packages` 就地满足（`PYTHONNOUSERSITE=1`），**别让 pip 写全局 user-site**；
   也别把 `LOCALAPPDATA` 清掉（pip 缓存会落到当前目录，见 2.5）；
5. 跑完查三件事：8000/8020 是否已释放、有无残留 python 进程、真身数据目录 mtime 是否未变；
6. **本次会话的 PowerShell 教训**：`PATH`/`USERPROFILE` 一旦在本会话改坏，后续每次调用都受影响，
   会造出"产品坏了"的假象。改坏了就从注册表重建：
   `HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment` + `HKCU:\Environment`。

## 3. 发布状态：main 与线上包的落差

**2026-09-19 下午（发版提交 `ccab2d7a`，13:54）：`main` 与线上资产同步（v1.2.2 已发）。**
下面这张表是「线上现在有什么」。（本节与第 0/1/1.5 节原记「晚」，2026-09-19 按提交时间与
drill 证据时间戳更正为**下午**——发版链 12:58 起、drill 13:07–13:49、发版提交 13:54。）

| 版本 | 线上状态 | 说明 |
|---|---|---|
| **v1.2.2（2026-09-19）** | ✅ 线上：八件套齐全，`/releases/latest` 指向本版 | **内容 = B1–B5 三张单的修复**（小发版不再多发本机库备份 / 不再漏发 `00-START-HERE.txt`；不可重试的校验失败不留半卷；连续 5 次内容不符转终态）+ `egg-info` 摘出产品文件。实测：完整包 `801,949,226` B（sha256 `3be2f0d6cd00…`）/ 小发版 `300,820,891` B（sha256 `866416309ab1…`）；小发版 **2858** 个产品文件（v1.2.1 是 4339——差的 1481 正是那批本机库备份）、删除清单 **2215** 条（累计口径）。真机 `drill-01` 判红 0 / PASS（第 0 节） |
| **v1.2.1（2026-09-16 首发；2026-09-19 重发一次）** | ✅ 线上（已被 v1.2.2 取代） | 首发内容：补回 mspm0 母版 `.settings/`（CCS 编码钉）。**重发内容**：启动器两处修复（旧进程判据 + 起服务前建数据目录）+ 提交期闸门工具进包。版本号没动、tag 仍指 `3263fa79`，资产内容 = `main@7784fe8d` |
| **v1.2.0（2026-09-14 重发，第二次重传）** | ✅ 线上 | 重发两次的原因见下：第一次修「路径太长」，第二次修「版本更新记录页缺 1.2.0」。版本号**始终没动** |
| ~~v1.2.0（2026-09-13 首发）~~ | 🗑️ **已删除**（Release 与 tag 都删了） | 那一版完整包解压会静默丢文件；删前资产下载数：full.zip 2 次 / update.zip 0 次 / manifest 3 次 |
| **v1.1.1** | ✅ 已发布（8 件资产，完整包 821,352,026 B / 小发版 310,369,185 B） | 修复「一键全量白下载」与「全量后资料库仍报版本未知」 |
| **v1.1.0** | ⚠️ 有缺陷，已被 v1.1.1 / v1.2.0 取代 | 点「一键全量」不会真正替换；资料库检查永远报「无基线」。老用户点一次「检查更新 → 一键更新」即可升级 |

> **2026-09-19 更新：那条「同版号重发触达不到」的缺口已经关掉。** 重发过的 v1.2.1 用户
> 现在点「检查更新」就能拿到 v1.2.2（版本号更高）。**以后尽量避免同版号重发**，真发生了就靠
> 「下一版号把缺口带上」——这条经验已经用过两次（v1.2.0、v1.2.1），两次都成立。

**⚠️ 重发留下的一个真实缺口**（下次动手前先读这段）：删掉旧 release 后，**已经下过旧
v1.2.0 并装好的用户不会收到任何更新提示**——「检查更新」比的是版本号，而新版仍是
v1.2.0。他们的工具能正常用（只是资料库那两族 LCD 例程还停在旧的长路径上），要修得
手动重下完整包。当时判断可接受（已装用户极少，用户明确要求「之前那版直接删了」），
但**下次再想「同版号重发」时，先想清楚这批人怎么触达**。

> **2026-09-16 更新：这个缺口被 v1.2.1 顺手关掉了**——版本号更高，那批人点「检查更新」就能
> 拿到修复，不必手动重下完整包。以后尽量避免同版号重发，真发生了就靠「下一版号把缺口带上」。

> **2026-09-19 再记一次同版号重发（这次是刻意的）**：v1.2.1 的启动器修复只能靠「被替换进去的那个包」
> 生效，而线上只有 v1.2.1 —— 不重发就永远到不了用户手上（`pack-update` 打出来的包内容取自
> `git archive HEAD`，修复在 HEAD 里）。所以**原地重发了 v1.2.1 的 8 个附件**，代价与上次同源：
> **已经装了旧 v1.2.1 的用户不会收到更新提示**（检查更新比版本号）。用户明确要求「就把这个发到
> v1.2.1 里」，已接受。**下次要触达那批人，只能靠下一个版本号。**
> 重发用的是 `pack-update.ps1 -Baseline firstep-update-v1.1.1.files.txt` 与
> `pack-full.ps1 -Baseline firstep-full-v1.2.0.manifest.json`（与原版同基线：两套 `removed.txt`
> 与线上原版**逐字节相同**，这就是基线选对了的判据）。

**⚠️ 同版号重发还踩了一个坑（2026-09-14，写下来别再犯）**：把 `VERSIONS.md` 的版本头
写成 `## v1.2.0 (2026-09-13，2026-09-14 重发)`——日期段混进中文后**整行不匹配**
`_VERSION_HEADER_RE`，解析器把它当普通 `##` 分区边界静默跳过，于是「版本更新记录」
页面最新只到 v1.1.1，而设置页版本号是对的（线上两个包里都带着这份坏文件，只能重打重传）。
两条教训：① **改完 `VERSIONS.md` 必须跑 `tests/test_changelog.py`**（它本来就有真文件
判据——这次是改完之后没跑就打包了）；② 现在多了一条绑 `__version__` 的守卫
（`test_real_versions_file_header_matches_tool_version`），版本块漏写/写坏当场红。

**下次发版可用的基线（v1.2.2 = 2026-09-19，直接当 `-Baseline`）**：

| 文件 | 用途 |
|---|---|
| `firstep-pack\firstep-update-v1.2.2.files.txt` | 下次小发版的 `-Baseline` |
| `firstep-pack\firstep-full-v1.2.2.manifest.json` | 下次完整包的 `-Baseline` |
| `firstep-pack\firstep-full-v1.2.2.zip` | 想省流量复跑档③ e2e 时可直接复用 |
| `firstep-pack\release-notes-v1.2.2.md` | 本次 Release 说明原稿（已发到线上；下次照模板改） |

（v1.2.1 / v1.2.0 那两套基线仍在同目录，只作历史；**别再拿它们当 `-Baseline`**。）

**发布仓库**：`AK47n/firstep`（= `git remote origin`）。
档② 的线上复核脚本 `verify-06-online.py` 按这个 slug 取 release 元数据（`gh` CLI 已认证）。

## 3.5 「下载抗断」特性的产物与**用户可见的新事实**（2026-09-13，`resumable-download`）

| 项 | 位置 / 值 |
|---|---|
| 可续下载域模块 | `src/contest_generator/download_resume.py` |
| 任务层共享件（工单 10/11） | `src/contest_generator/task_download.py`——**四件**：「一次分卷下载」原语（`download_and_verify`）、注入缝解析（`resolve_task_download`，工单 11）、卷级断点恢复（`restore_snapshot_parts`，工单 11）；`src/contest_generator/task_retry.py`（重试观测）——两条链路（完整包 / 资料库）的任务模块里只剩「路径 + 卷级记账」与一行壳 |
| 12 键状态契约的单源 | `tests/test_download_status_surface.py` 的 `STATUS_KEYS`（= `EXISTING_KEYS` 8 键 \| `NEW_KEYS` 4 键）：**要加字段就改这一处**——产品两侧的载荷改了而契约没改会红（键 / 侧 / 态六格实测），契约改了则两处测试一并跟上（工单 15 的两版实测：基线 1 failed / 现状 65 passed） |
| 结构守卫（钉「重复有没有回来」） | `tests/test_download_status_surface.py::test_retry_observation_has_a_single_home`（工单 09）、`::test_part_state_shape_has_a_single_contract`（工单 12：两条链路的 `_PartState` 字段/默认值/方法正文/`to_dict` 键序四轴同形，两条链路的 `from_dict` 已被删——零调用点）、`tests/test_download_sequence_home.py::test_download_sequence_has_a_single_home`（工单 10）与 `::test_shared_task_helpers_have_a_single_home`（工单 11）、`test_download_status_surface.py::test_status_contract_has_a_single_home`（工单 15：12 键契约只许有一个家；判据 = 字面量**或其 `\|` 联合**枚举 ≥8 个契约键——只认字面量的话连契约本体都认不出），五条都带反向注入验证；后一条另配**真身实测**（`run-15-evidence.py real-tree`：往 `tests/` 放一份副本 → 红并指名 → 删 → 绿） |
| 朴素下载器（保留的对照实现） | `materials_task.download_part`（256 KB 分块那支）：**生产侧零调用点**（炸弹注入实测三文件全绿 + 阳性对照转红），全仓活口只剩证据工具——本特性探针的红基线/反证（`probe-01-resume.py` 两处取值引用、`probe-01-negative.py` 一处模板 import）与完整包 e2e 脚本的一处真调用（`full-download/e2e_full_download.py`）；工单 14 量清后**按 `wontfix` 保留**（理由 = 那批工具要一份冻结的「改之前」实现）；注意它**不判截断**，别拿它当下载器 |
| 本地可控服务器 | `.scratch/resumable-download/sim-server.py`（六种行为；`--port 0` 由内核分配；默认 8031，**当前没有常驻实例**） |
| 探针（真 socket） | `probe-01-resume.py`（下载函数层，五用例）、`probe-03-corridor.py`（任务层走廊 + 忽略 Range + 跨进程续传）、`probe-01-negative.py`（反证）、`probe-07-stage-preflight.py`（工具根预检，零下载）、`probe-07-review-claims.py`（评审断言的独立复现） |
| 单测用桩服务器 | `tests/_byte_server.py`（进程内线程，只切流；**与探针那支强度不同**，别混） |
| 证据 | `verify-01-baseline.*`、`verify-01-negative.txt`（反证）、`verify-02-probe.*`、`verify-03-corridor.*`、`verify-03-negative.*`、`verify-05-*`、`verify-06-local.json`、`verify-06-online.txt`、`verify-07-tier3-e2e.*`、`verify-12-{duplication,guard-strength,suite}.txt`（工单 12：量具输出 / 判据强度探针 / 逐文件全套）、`verify-14-{callers,guard-strength,suite}.txt`（工单 14：`download_part` 逐处活口 / 判据强度探针 / 逐文件全套）、`verify-15-{duplication,guard-strength,guard-strength-before}.txt`（工单 15：契约副本盘点 / 判据强度探针现状与**基线版**两版）、`verify-15-{together,guard-real-tree,suite}.txt`（工单 15：按手续加字段的两版实测 / 守卫真身实测 / 逐文件全套；全在 `.scratch/resumable-download/`） |
| **半成品落点（用户可见）** | 下载未完成的卷留在 `updates/full/`（完整包）与 `updates/materials/`（资料库），旁边带 `<卷名>.partial.json` 边车。**用户点取消或下载失败，这些文件不会被删**（它们就是断点）；成功或校验失败才清。**边车「开跑就写」**（原口径「只在取消 / 失败时写」已被真机实测推翻：硬杀进程两条路都不走 → 白下 210 MB，见工单 06 档③） |
| 断点粒度 | **卷内**（字节级 `Range` 续传）。卷级断点（快照记 `ok`）是上一轮就有的，两者叠加 |
| **档③ 真实完整包端到端** | ✅ **已跑通**（工单 `resumable-download/07`，2026-09-13 15:56）：真检查 → 真下载 783 MB → **真替换（`tools/update-app.py`）→ 真重启** → `/api/health` 版本 `1.1.0` → **`1.1.1`**；隔离边界三条判据全「未变」。脚本 `verify-07-tier3-e2e.py`（可复跑，约 3 分钟，复用 `Desktop\firstep-pack\firstep-full-v1.1.1.zip` 省流量） |

**下次要验证/复现「抗断」时**：跑 `python .scratch/resumable-download/probe-03-corridor.py`
（秒级、自带反证）；它起的是子进程端口，用完即停。想手工看弱网效果就用
`sim-server.py --port 8031` 再配合 `?mode=cut|stall|slow`。
要复核「一键全量能不能真把工具换掉」就跑 `verify-07-tier3-e2e.py`（它会自己收掉 8020）。

**v1.2.0 发版留下的可复用基线**（都在 `C:\Users\luoji\Desktop\firstep-pack\`，下次发版直接当基线用）：

| 文件 | 用途 |
|---|---|
| `firstep-update-v1.2.0.files.txt` | **下次小发版的 `-Baseline`** |
| `firstep-full-v1.2.0.manifest.json` | **下次完整包的 `-Baseline`** |
| `firstep-full-v1.2.0.zip`（770.3 MiB） | 想省流量复跑档③ e2e 时可直接复用这个包 |
| `release-notes-v1.2.0.md` | 本次 Release 说明原稿（已发到线上；下次照模板改） |

发版时的实测口径留个印象（省得下次重新推）：**打小发版包约 7 分钟、完整包约 4 分钟、
8 件资产上传约 4 分钟**；`pack-update` 无基线差异时写出的 `removed.txt` 是 0 字节——
**上传前必须补一行 `# …` 注释**（GitHub 拒收 0 字节资产，`HTTP 400`）。

**发布要点（已在 v1.2.0 落地，见 VERSIONS.md 顶部与 Release 说明）**：

- 修复：下载断线后**从断点接着下**（以前一次网络抖动就从头再来；完整包 770 MB 尤其明显）；
- 修复：**被截断的下载不再当成「下完了」**（以前进度 100% → 报校验失败 → 从 0 重来）；
- 修复：断线**自动重试**（退避 2→4→8→…→60 秒封顶，**无次数上限**，随时可取消）；
- 新增：中途取消或失败**不再丢掉已下载的部分**（`updates/` 下会留着半成品与
  `.partial.json` 边车，**下一次点重试时从那里接着下**；成功或校验失败才清）；
- 修复：**强制结束工具（任务管理器 / 崩溃 / 断电）后重开，也不再从 0 重下**
  （边车改「开跑就写」；以前硬杀不写边车，下个进程把半成品当来路不明的文件清掉——
  真机实测白下 210 MB）；
- 界面：剩余时间改说人话（「约 12 分钟」），弱网明写「网络较慢」，重试明写
  「正在自动重试（第 N 次），从 X% 接着下」，失败分两类话术（网络 / 校验，后者明说
  「重新下载也不会有变化」）。

**发布侧（打包器）修复已随 v1.2.0 用上**（2026-09-13，工单 `full-download/08`，提交 `56ce0e74`）：

- 两个打包器字节口径不一致：`git archive` 会被本机 `core.autocrlf=true` 转成 CRLF，完整包读工作树
  → v1.1.0 的 3474 个共有文件里 **926 个字节不同**（v1.1.1 是 929 个，内容差异都是 0）。
  修法：`git archive` 钉 `-c core.autocrlf=false`（实测 `.gitattributes` 的 `-text` 压不住它）。
- **v1.2.0 是第一次用修好的打包器发版**——本次两包同源，用户增量更新不会把 900 多个文件误判成「已修改」。
  这条修复本身在打包器代码里，不进包；换机器 / 换 clone 打包前先确认它还在。

## 4. 发布流程的两个坑（已写进 `docs/agents/releasing.md`）

1. **`gh release create` 是在服务端建 tag**，本地 `git tag` 不会自动有 → 想本地按 tag 引基线，
   先 `git tag -a vX.Y.Z -m ...` + `git push origin vX.Y.Z`，或事后 `git fetch origin --tags` 补齐。
2. **空 `removed.txt`（0 字节）会被 GitHub 拒收**（`HTTP 400: Bad Content-Length`）→ 首次发布
   （无基线）上传前写一行 `# 本次无被删除的文件`；更新器本就跳过 `#` 行，语义不变。
   **2026-09-13 起已内建**：`tools/pack-update.ps1` 无基线时直接写注释行占位，不必再手工改。

## 5. 发 v1.1.1 时踩到的三个真缺陷（都已修，留个印象）

诱因都是**源码方式启动**（`start-app.bat` 的 `PYTHONPATH=src`，也正是用户机的标准启动方式）：

1. 工具根被算成 `<根>\src` → 更新器路径拼错、进程秒退，而编排只看「进程起没起来」**误报成功**
   → 用户点「一键全量」白下 783 MB。修法：`tool_root.find_tool_root` 单源判定 + 拉起前预检。
2. 同样的推导让资料库目录算成 `<根>\src\sources\materials` → **永远报「无基线」**
   → 「全量一次后只下增量」的核心收益失效。修法：同单源。
3. 停服端口没传 → 更新器按 8000 停，**把同机上另一个实例停掉**（演练中真实发生过两次）。
   修法：两条更新路径都显式 `--port`（取自 `FIRSTEP_LAUNCHER_PORT`）。

细节与证据：`.scratch/full-download/issues/09-tool-root-resolution.md`（工单区，需要时再翻）。

## 6. 包内路径长度上限（2026-09-14，用户报障后的根治）

**现象**：用户另一台电脑解压 `firstep-full-v1.2.0.zip` 报 `0x80010135: 路径太长`
（`touch_screen_calibration.ino`），点「跳过」= 静默丢文件。

**根因（实测口径，别再过一遍）**：

| 项 | 值 |
|---|---|
| 资源管理器「全部解压缩」上限 | **259 字符**（含解压根目录；老 API，改注册表 `LongPathsEnabled` 也救不了已运行的旧包） |
| 工具自身解压（Python `zipfile`） | 走长路径 API，实测写到 290+ 字符成功——**下载链路本来就没问题** |
| `tar.exe`（Windows 10/11 自带 bsdtar） | 走长路径 API，实测 267 字符落地成功——**旧包的即时解药** |
| 病灶位置 | 包内最深路径 223 字符，**100% 在 `lckfb-地阔星移植手册/网盘下载/{ili9341,ili9488}` 两族**；非资料库内容最长才 137 |

**已做的两半**（缺一不可）：

1. **把路径压回安全区**：三族规则（去 `1-Demo` 外壳层 / `Install libraries`→`libs` /
   仅在示例子树内折叠相邻同名层）改 747 层目录名，**只改目录名、不动文件名**；
   5172 个文件 (size, sha256) 多重集逐项不变 → 最长 **223 → 194**；
2. **让以后发不出这种包**：`full_pack.MAX_ENTRY_PATH_CHARS = 200` +
   `ensure_paths_fit()`——`prepare_full_package` 扫完树即校验，超限**拒绝发版**
   并给出修法脚本名。

**工具与量具**（都在 `.scratch/path-budget/`，可复跑）：

| 文件 | 用途 |
|---|---|
| `slim_materials_paths.py` | 改名脚本；默认 dry-run，`--write` 才落盘（清单自动备份、成功即清）；自带路径冲突/越界护栏与逐字节自校验 |
| `measure-extract-budget.py` | 把「解压后最深总长」按 5 种真实解压姿势算出来（含报障机的用户名长度与「多套一层」姿势）——**发版前跑它**，全绿才算过 |
| `rebuild-materials-baseline.py` | 就地重算 `.materials-manifest.json`（版本写成 `v1.2.0+pathbudget` 明示非发布态） |
| `spec.md` / `slim-report.json` | 决策与实测记录 |

**注意**：`.scratch/materials-baseline-writeback/init-baseline.py` 的判据是「与线上
v1.2.0 包内那份逐文件相等」——本机改造后它**必然报差异**（改名就是要让路径变）。
它的用途是「证明本机与线上一致」，不是「就地重算」；要重算用上表第三支。
**2026-09-14 重发之后，线上包与本机资料库重新同源**（资料库基线 12 批次 / 5081 文件），
那份对比脚本又可以用了。

**⚠ 2026-09-20 起，「同源」只对发布侧基线成立、对盘不再成立（PDF 去重，用户裁决）**：
`sources/materials` 的 lckfb-地阔星移植手册两族模块包（`ili9341` / `ili9488`）**各带一份同名
通用文档**，全量 SHA256 证实 **15 组逐字节相同**（0 组假重复）→ 回收 `ili9488` 侧
**15 件 / 10.85 MiB** 到 `sources/.trash-pdf/2026-09-20/`（可手动恢复）；PDF 97 → 82，
库内**内容层面零重复**。`.materials-manifest.json` **没跟着删**（仍是 12 批次 / 5081 文件），
所以拿**本机盘**扫基线 / 打完整包时，`full_pack.scan_as_manifest`、`materials_pack`
会把这 15 条算成 `removed`——**= 下一版会把它们从用户库里一并删掉**。想让删除进下一版就这么发；
不想就先把回收目录那 15 件挪回原位。明细 / 复跑脚本见 `.scratch/pdf-dup-verify/report.md`。

## 7. 清理线的三笔账（2026-09-16）

### 7.1 误删：mspm0 母版 `.settings/`（含 CCS 编码钉）——已修

**现象**：`tests/test_readme.py::test_directory_structure_syncs_with_master_templates` 红
（「mspm0/.settings/ 不在母版模板中——目录结构章与模板不同步」）。它在 main 上**挂了整整一天**
（2026-09-15 → 09-16）没人发现，因为**没人跑全套**。

**根因链（三处叠加，缺一条都不会出事）**：

1. 2026-09-15 的 `5ea37e97` 加了一批忽略规则，其中 `.settings/` 是照着「IDE 工程设置」写的
   ——但**母版**的 `.settings/` 不是 IDE 状态，是随母版分发给生成工程的工程配置：
   `org.eclipse.core.resources.prefs` 里钉着 CCS 工程编码 `encoding/<project>=UTF-8`；
2. 同一天的 `c0f33697` 用 `filter-branch` 把清单里的文件从**全部历史**删掉（清单 93 条
   `.settings` 命中，其中就有母版这两件）；
3. 清理器 `scripts/make-purge-list.mjs` 本来有「命中里像源码的要人工确认」这道闸，
   但判据是**扩展名白名单**，`.prefs` 不在其中 → 静默照删，没有任何东西叫停。

**修了四处**（都带反向验证）：

| 修法 | 判据 / 验证 |
|---|---|
| 还原两个文件 | 内容取自**两处独立来源**（线上 `firstep-full-v1.2.0.zip` + 沙箱 `firstep-sim`），sha256 逐字节相同（`6c355f2f86ad…` / `1a5b17d8a429…`，含 CRLF） |
| `.gitignore` 加母版例外 | 不修这条 = 文件在盘上、git 看不见、发布包也不会带（`git add` 直接被拒：`paths are ignored`） |
| `make-purge-list.mjs` 加 `KEEP` 例外 + `.prefs` 进闸门 | 反证：把例外清空后重跑 → **退出码 1 + 点名那两个文件**「请人工确认后再删」，正是当初该发生的动作 |
| 新增 `tests/test_master_template_config.py` | 反证：搬走编码钉 → 红；搬回 → 绿（sha256 复核） |

**顺带修掉的连带**：`test_readme.py` 那条红转绿 → 全套 4472 passed / 0 failed。

**⚠ 未了**：线上 v1.2.0 的完整包里**仍然缺这两个文件**——**v1.2.1 已补上**（第 0 节）。

### 7.2 免费的三百兆：那 5 条重写前的旧分支（2026-09-16 已做完，省 299.2 MB）

**症状**：`.git` = 591 MB，而 `git count-objects` 显示无松散垃圾（2 个 pack，`prune-packable 0`）。

**根因**：`--all` 有 **5287** 个提交，`main` 只有 **2780**——差额来自 5 条远端跟踪分支
（`origin/coord-detect-rename`、`origin/feat/project-readme-03`、`origin/llm-observation-collector`
等，都是 2026-08-17～09-10 的 PR 分支）。它们指向 **2026-09-15 历史重写之前**那套图，
把改前的全部对象（含被清掉的编译产物与 `sources/materials/`）继续钉在本地库里。

| 口径 | .git |
|---|---|
| 清理前 | 591.1 MB |
| **清理后（2026-09-16 已做，本机实测）** | **292.3 MB**（省 **299.2 MB**；`count-objects`：1 pack / `prune-packable 0` / 乱码 0） |
| 若再重写历史删 `sources/materials/` | 123.4 MB（再省 168.8 MB，耗时 973s，见 7.4 的拍板） |

**2026-09-16 做了什么**（远端 + 本地两侧）：

1. **先确认这 5 条 PR 分支可废弃**：`coord-detect-rename`(#105) / `project-readme/02-build-flash-checklist`(#107)
   / `feat/project-readme-03`(#108) / `llm-observation-collector`(#109) / `chore/deepseek-flash-model-id`(#110)
   ——`gh pr view` 全是 **MERGED**，且各分支 tip 的提交时间**都早于各自合并时间**（合并后再无新提交）；
   main 里还能搜到它们的**后续**提交（例：`LOCAL_LLM_METHODS` 已是六方法，那条工单在合并后继续演进过），
   说明这些分支的成果早已进 main。（`git cherry` 报的「唯一提交」是 09-15 历史重写的假象——它按 patch-id
   比对，重写后 hash 全变；判断依据要用**提交时间 vs 合并时间**，别用 cherry。）
2. **删远端**：`git push origin --delete` 逐条，现线上只剩 `refs/heads/main`。
3. **本机回收**：`git remote prune origin` + `reflog expire --expire-unreachable=now --all` +
   `git gc --prune=now --aggressive` → **591.5 → 292.3 MB**，与探针预测（292.3 MB）逐位吻合。

**注意**：那 5 条分支线上已删，**引用没了不等于 GitHub 服务端对象立刻消失**（服务端 GC 由 GitHub 择机做；
真要核对远端体积用仓库 Settings 里的体积数据，别拿本地数字当远端数字）。**决策已定**——不必再挂账。

### 7.3 历史重写还把 CHANGELOG 自动补录打断了（静默静止，已修）

**症状**：2026-09-15 20:57 那次重写之后的提交**全都没进 CHANGELOG**，而 `post-commit`
钩子每次只打印一句 `CHANGELOG up-to-date`——本轮连做三笔提交、三次都看到这句话才发现。

**根因**：CHANGELOG 头部的锚点 `<!-- changelog-auto: last-commit=2bdead56… -->` 指向
**重写前**的提交，而 `filter-branch -- --all` 换掉了**所有** commit hash → 该 sha 不复存在；
`update_changelog` 拿它算 `git log <sha>..HEAD` → git 报错 → 被当成「无新提交」直接返回。
根子在于那句「尽力而为、绝不抛」的兜底**分不开「没有新提交」与「我根本查不了」**，
所以机制一旦失效就永远不会自己好。

**修法**：新增 `changelog._commit_exists`（锚点还作不作数）；失效则按文件内最新日期兜底扫、
把锚点换成当前 HEAD（自愈），并**往 stderr 说一句**。兜底不写重复（`_merge_commits` 按
(时间, 文本) 去重，已核实）。守卫三条在 `tests/test_changelog.py`：失效兜底 / 有效区间反向 /
**真文件锚点必须在本仓库存在**（无 `.git` 的发布包副本跳过）。

**当场自愈结果**：09-15 那笔重写提交（`20:57`）与 09-16 三笔全部补进记录；锚点更新为 `35b98e35`。
**下次再重写历史，记得跑一次** `PYTHONPATH=src python -m contest_generator.changelog`
（忘了也不致命——真文件守卫会红，且失效锚点现在会出声）。

### 7.4 另一笔账的拍板：**不做**历史重写（2026-09-16 决定）

第二笔账是「重写全部历史删掉 `sources/materials/` 的痕迹」（再省 168.8 MB，`.git` 会到 123.4 MB）。
**决定：不做。** 理由四条，按分量：

1. **性价比掉了**：7.2 做完之后它从「省 467.7 MB」缩水成「292.3 → 123.4 MB」。为 168.8 MB 付
   「force push + **四个 tag hash 全改** + 所有既有 clone / 本地沙箱作废」，不划算；
2. **它会打断所有 clone 用户的 `git pull`**。README 把 `git clone` 列为一条并列的正规获取路线
   （第 35 行），重写后那批人的 `git pull` 全部报 non-fast-forward，得教他们 `fetch` + `reset --hard`
   （或重新 clone）——**为了仓库体积去给用户发一次人工操作通知**，方向不对；
3. **它删掉的正是「本机离线备份」**：`sources/materials/` 那 2193 条对象不在 HEAD、只在 main 历史里，
   是这套资料库唯一的版本化快照。真要哪天需要回溯（资料被误删 / 想比对历史版本），重写后就没了；
4. **不做也有出路**：GitHub 侧体积不是瓶颈（本机 292.3 MB 在正常 clone 量级），真要再瘦，
   下一批对象清理（像 09-15 清编译产物那样）还有别的目标可挑，代价比全量重写低。

**什么情况下再翻这笔账**：远端仓库体积逼近 GitHub 告警线、或 clone 慢到影响新用户（届时先测
远端体积，见 7.2 末尾的「别拿本地数字当远端数字」）。真做的话照 `scripts/purge-generated.sh`
顶部注释那套走（`filter-branch` 的绝对路径 / `-f` / index-filter 三个坑已趟平），
清单先给人看，做完**必须**跑一次 `PYTHONPATH=src python -m contest_generator.changelog`。
