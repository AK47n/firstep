# 本机环境与当前状态（会变，改完就更新这里）

> **这份文件的存在意义**：有些事实只属于「这台机器 + 此刻」，既不该塞进 README（面向用户），
> 也不该只留在会话里（下次就没人记得）。凡是「下次接手需要知道」的环境事实写这里，**只写结论与位置**。
>
> 更新纪律：改动了这里描述的东西（删沙箱、发新版、换端口），**当场回来改这份文件**。

## 0. 交接区：main 上有什么还没到用户手上（2026-09-13 夜，v1.2.0 发完）

**当前状态：清零。** v1.2.0 已发布（8 件资产），此前挂账的三处都已随包出去：
`00-START-HERE.txt`（在完整包与清单里各查过一次，第 3 节）、`install.bat` 收尾话术、
`pack-full` 字节口径修复（那是打包器侧，不进包，**本次就是第一次用修好的打包器发版**）。
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
| **8000** | 真身（`Desktop\firstep`，**v1.2.0**，2026-09-13 23:28:47 重启后生效——没走下载，直接吃了工作树里的新版） | 你自己日常用；双击 `start-app.vbs` 启停 |
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
| **v1.2.0** | ✅ 已发布（2026-09-13 夜，8 件资产；完整包 `807,732,870` B = 770.3 MiB / 小发版 `310,576,737` B = 296.2 MiB） | 主题「下载断了能接着下 + 第一次装完就知道双击哪个」；包体比 v1.1.1 小约 50 MB（库治理回收重名重复文件，README 口径已同步） |
| **v1.1.1** | ✅ 已发布（8 件资产，完整包 821,352,026 B / 小发版 310,369,185 B） | 修复「一键全量白下载」与「全量后资料库仍报版本未知」 |
| **v1.1.0** | ⚠️ 有缺陷，已被 v1.1.1 / v1.2.0 取代 | 点「一键全量」不会真正替换；资料库检查永远报「无基线」。老用户点一次「检查更新 → 一键更新」即可升级 |

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
