# 本机环境与当前状态（会变，改完就更新这里）

> **这份文件的存在意义**：有些事实只属于「这台机器 + 此刻」，既不该塞进 README（面向用户），
> 也不该只留在会话里（下次就没人记得）。凡是「下次接手需要知道」的环境事实写这里，**只写结论与位置**。
>
> 更新纪律：改动了这里描述的东西（删沙箱、发新版、换端口），**当场回来改这份文件**。

## 0. 交接区：main 上有什么还没到用户手上（2026-09-16 晚更新）

**当前状态：没有挂账——`main` 与线上首发包同源**（v1.2.1 已发布，见第 3 节）。

上一轮那件「必须随下一个版本发出去」的事**已经发出去**：mspm0 母版 `.settings/`
（CCS 工程编码钉 `encoding/<project>=UTF-8`）随 **v1.2.1** 进包了。线上完整包与更新包里
都有 `library/masters/mspm0/.settings/org.eclipse.core.resources.prefs` 与
`org.eclipse.cdt.codan.core.prefs` 两件（第 7.1 节记着它们是怎么被误删又还原的）。

同时进包的还有仓库侧工具/配置（不影响用户功能，但会随包分发）：`scripts/make-purge-list.mjs`
的例外与闸门、`.gitignore` 的母版例外、`tests/test_master_template_config.py` 与
`tests/test_suite_timeout.py` 两个新守卫、`pyproject.toml` 的测试超时口径。

此前挂账的三处都已随 v1.2.0 出去：
`00-START-HERE.txt`（在完整包与清单里各查过一次，第 3 节）、`install.bat` 收尾话术、
`pack-full` 字节口径修复（那是打包器侧，不进包，**v1.2.0 就是第一次用修好的打包器发版**）。
另外 `ba32e95a`（小发版停服端口显式传 `FIRSTEP_LAUNCHER_PORT`）也在本版里了。

**下次发版前只需记住**：`pack-full` 的 `core.autocrlf=false` 那处修复是**打包器代码**，
不会随包分发——凡是换机器 / 换 clone 打包，先确认它还在（`tests/test_pack_update.py` 有跨包逐字节守卫）。


## 1. 沙箱「模拟用户机」（真机演练用的第二份安装）

| 项 | 值 |
|---|---|
| 工具根 | `C:\Users\luoji\Desktop\firstep-sim` |
| 数据目录 | `C:\Users\luoji\.contest_generator_sim`（与真身的 `~\.contest_generator` 隔离） |
| 端口 | **8020**（真身用 8000；`FIRSTEP_LAUNCHER_PORT=8020`） |
| 入口 | `sim-run.py`（沙箱专用，因为生产入口的配置路径写死在真身数据目录） |
| 构建脚本 | `.scratch/full-download/make_sim_sandbox.py`（删了可重建） |
| 当前状态 | 已用**线上真实包**更新到 v1.1.1（**尚未更新到 v1.2.0**）；资料库基线在场（12 批次 / 5087 文件） |

**已知故意为之的两处「不真实」**（复用时别被误导）：

1. **沙箱的 `src/contest_generator/__init__.py` 被钉在 `1.1.0`** —— 为的是下次还能重演「1.1.0 → 更新」。
   要恢复成真实版本，直接把它同步成与 `src/` 一致即可（其余文件是 v1.1.1）。
2. **沙箱没有 `.venv`** —— 所以包内自带的 `start-app.bat` 会在依赖检查分支弹窗退出；
   演练时改用 `sim-run.py` 直接起（这不代表用户机有问题，用户机都跑过 `install.bat`）。

## 2. 本机跑着的实例

| 端口 | 是什么 | 谁在用 |
|---|---|---|
| **8000** | 真身（`Desktop\firstep`，工作树即最新代码） | 你自己日常用；双击 `start-app.vbs` 启停。**2026-09-16 发 v1.2.1 时它没在跑**（重启后即是 v1.2.1） |
| **8020** | 沙箱 | 演练用，随时可停（发版时未在跑；沙箱仍是 v1.1.1） |

> **同机两个实例的坑**（已修，但知道一下）：更新器默认按 8000 停服。若在 8020 上点更新而没传端口，
> 会把 8000 上你正在用的那个停掉。两个更新路径（完整包 / 小发版）现在都从 `FIRSTEP_LAUNCHER_PORT`
> 取端口，正常不会再发生；停掉后重跑 `start-app.vbs` 即可恢复。

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
| 沙箱 | **还没补**（`Desktop\firstep-sim` 仍是 v1.1.1、无基线）；等发资料库增量包前一起补 |

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

| 版本 | 线上状态 | 说明 |
|---|---|---|
| **v1.2.1（2026-09-16）** | ✅ 线上：八件套齐全（完整包 `801,873,335` B / 小发版 `304,729,724` B），`/releases/latest` 指向本版 | 补回 mspm0 母版 `.settings/`（CCS 编码钉）——**v1.2.0 的用户装的就是缺的**；顺带把 v1.2.0 那条漏掉的版本记录页区块补上。发版自检 `check-download-docs.py` 三处全 PASS（README 体积口径 770/296 MB 与线上 802/305 MB 同量级、clone 口径 291 MiB 与实际 pack 同步） |
| **v1.2.0（2026-09-14 重发，第二次重传）** | ✅ 线上：旧那版 Release + tag 已删，同一版号重打重传（完整包 `807,704,880` B / 小发版 `310,584,891` B），线上 tag 指向 `a5542cc2` | 重发两次的原因见下：第一次修「路径太长」，第二次修「版本更新记录页缺 1.2.0」。版本号**始终没动**（用户指定沿用 v1.2.0） |
| ~~v1.2.0（2026-09-13 首发）~~ | 🗑️ **已删除**（Release 与 tag 都删了） | 那一版完整包解压会静默丢文件；删前资产下载数：full.zip 2 次 / update.zip 0 次 / manifest 3 次 |
| **v1.1.1** | ✅ 已发布（8 件资产，完整包 821,352,026 B / 小发版 310,369,185 B） | 修复「一键全量白下载」与「全量后资料库仍报版本未知」 |
| **v1.1.0** | ⚠️ 有缺陷，已被 v1.1.1 / v1.2.0 取代 | 点「一键全量」不会真正替换；资料库检查永远报「无基线」。老用户点一次「检查更新 → 一键更新」即可升级 |

**⚠️ 重发留下的一个真实缺口**（下次动手前先读这段）：删掉旧 release 后，**已经下过旧
v1.2.0 并装好的用户不会收到任何更新提示**——「检查更新」比的是版本号，而新版仍是
v1.2.0。他们的工具能正常用（只是资料库那两族 LCD 例程还停在旧的长路径上），要修得
手动重下完整包。当时判断可接受（已装用户极少，用户明确要求「之前那版直接删了」），
但**下次再想「同版号重发」时，先想清楚这批人怎么触达**。

> **2026-09-16 更新：这个缺口被 v1.2.1 顺手关掉了**——版本号更高，那批人点「检查更新」就能
> 拿到修复，不必手动重下完整包。以后尽量避免同版号重发，真发生了就靠「下一版号把缺口带上」。

**⚠️ 同版号重发还踩了一个坑（2026-09-14，写下来别再犯）**：把 `VERSIONS.md` 的版本头
写成 `## v1.2.0 (2026-09-13，2026-09-14 重发)`——日期段混进中文后**整行不匹配**
`_VERSION_HEADER_RE`，解析器把它当普通 `##` 分区边界静默跳过，于是「版本更新记录」
页面最新只到 v1.1.1，而设置页版本号是对的（线上两个包里都带着这份坏文件，只能重打重传）。
两条教训：① **改完 `VERSIONS.md` 必须跑 `tests/test_changelog.py`**（它本来就有真文件
判据——这次是改完之后没跑就打包了）；② 现在多了一条绑 `__version__` 的守卫
（`test_real_versions_file_header_matches_tool_version`），版本块漏写/写坏当场红。

**下次发版可用的基线（v1.2.1 = 2026-09-16 首发，直接当 `-Baseline`）**：

| 文件 | 用途 |
|---|---|
| `firstep-pack\firstep-update-v1.2.1.files.txt` | 下次小发版的 `-Baseline` |
| `firstep-pack\firstep-full-v1.2.1.manifest.json` | 下次完整包的 `-Baseline` |
| `firstep-pack\firstep-full-v1.2.1.zip` | 想省流量复跑档③ e2e 时可直接复用 |
| `firstep-pack\release-notes-v1.2.1.md` | 本次 Release 说明原稿（已发到线上；下次照模板改） |

（v1.2.0 那一套基线仍在同目录，只作历史；**别再拿它当 `-Baseline`**。）

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
