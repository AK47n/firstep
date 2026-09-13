# 10 — 「一次分卷下载」这件事只许有一处定义：两条链路的 `_download_one` 收成一个原语

**要做什么：** 让「**一次分卷下载**」在代码里有**一处**定义——两条任务链路
（完整包 / 资料库）不再各写一遍「判长度到点 / 判半成品可不可续 / 清来路不明的半成品 /
调下载器 / 异常时写边车 / 复用返回的哈希 / 校验失败清掉重下」这套**动作序列**与它承载的**规则**；
外部行为、状态面字段、既有判据一个字不改。

**被谁阻塞：** 无——可立即开始（工单 03 双轴评审留的账、工单 08 又在这套序列里改了两处、
工单 09 明文留作另立单）。

**状态：** resolved

- [x] **先量再动**：把两处正文逐行对过，写清「哪几行是真的同一件事、哪几行只是长得像」，
      并**从 git 历史取证**——这套序列被改过几次、有几次是「两边各改一次」。
      **量出来的账**（比原估的「约 40 行」更清楚）：55 / 47 行里**完全相同 37 行**，
      真正的差异只有 3 处；历史硬证据 = `22d0f643` 同一提交给两文件各加一遍**完全相同的分支**
      （取证过程与量具见验收记录第一、二节；量具从 `git show` 取改动前那份，故结论可复现）。
- [x] 抽出**一次下载尝试**的原语（新模块；`download_resume` 不许进——那里的边界纪律见备注）。
      入参须能接住两条链路**现成的** `_PartState`（两处字段名本来就同形：`name` / `url` /
      `size` / `sha256` / `dest` / `ok` / `downloaded_bytes`），**不引入一组回调参数**。
- [x] `_download_one` 各自只剩两件**真正不同**的事：**落盘路径怎么算**
      （完整包 `task_dir/full/<name>` vs 资料库 `task_dir/materials/<name>`）、
      **跟卷 / 批次有关的记账**（`_current_part_name`、重试观测复位、快照写在哪层）。
      若收完还剩「两个模块互相抄」的段落，说明缝划错了——**停下来改缝，不许把参数堆上去**。
- [x] `_resolve_download`（两处约 18 行同形）**不在本单**：它与「一次下载」不是同一件事
      （行为契约是 `monkeypatch.setattr(<Task>, "_download", …)` 这条注入缝），且它已由
      既有用例钉住；要收是**另一单**，见「先说清代价」第二节。
- [x] **零行为变化**：既有判据（工单 03/04/05/07/08/09 与探针）全程绿，**不许为迁就重排改断言**
      （工单 09 立的纪律照旧）；`git diff --stat` 里 `tests/` 既有文件须是 **0 deletions**。
- [x] 新增**一条**结构守卫（纯重排必须留守卫，否则「以后不会再漂」只是愿望，工单 09 的教训）：
      任务模块里再出现「调 `as_task_downloader` + `write_partial_marker` + `clear_partial` 的
      连续块」即转红；**并做反向注入验证它真的会红**（工单 08 的教训：守卫也可能只是装饰）。
- [x] 真机/探针复跑：`probe-01-resume.py`、`probe-03-corridor.py`、`probe-08-416.py` 总判 PASS
      （本单动的是异常与断点路径，必须有真 socket 证据，不能只靠单测）。
- [x] 双轴评审；判定记进「验收记录」。

## 先说清代价（为什么它必须单独一单）

### 一、这 40 行与工单 09 收的那 225 行**不是同一类重复**

| | 工单 09 收的 | 本单要收的 |
|---|---|---|
| 性质 | **同一件观测**被抄两遍（字段 + 规则 + 回调，逐字重复） | **同一段动作序列**被两条业务流程各写一遍 |
| 不同点在 | 没有不同点 | 卷怎么分组（扁平分卷 vs 按批次分组）、参数形状（`_download_one(part)` vs `_download_one(part, batch)`） |
| 合并的代价 | 低：换一个家，语义不动 | 高：缝划错就要参数化出一堆回调，或把「批次」概念塞进完整包 |
| 混在一单的后果 | — | 评审没法判断「合并是否值得」，只能一起否掉或一起放行 |

所以工单 09 只做前者、把后者留在备注里（`.scratch/resumable-download/issues/09-retry-state-extraction.md`
第六节）——这是**记账**，本单是**还账**。

### 二、`_resolve_download` 要一起收吗？不要

两处 `_resolve_download` 同形约 18 行，但它的行为契约是
**`monkeypatch.setattr(FullDownloadTask, "_download", fake)` 这种类属性注入必须仍然生效**
（工单 03 备注里记着：接线时踩过，两条用例变红）。把这段收成基类方法之前，
得先回答「类属性注入点还认不认」——那是一个**判据问题**，与本单「动作序列收一处」不同性质。
硬塞进来，评审就得同时判两件事。

### 三、如果量出来的历史不支持「漏一边就出 bug」

本仓库的纪律是**先证明判据会红再用它判绿**，这一条同样适用于结构改动：
若 git 历史显示这套序列从未「两边各改一次」，本单就退化成纯洁癖——那就**不做**，
把结论写回本单并关掉（`wontfix`），别为了「对称好看」动 100 行热路径代码。

## 验收记录（2026-09-13）

### 一、先量再动：量出来的账比「约 40 行」更清楚

量具 = `.scratch/resumable-download/measure-10-duplication.py`（只读，按 AST 取函数全文、
不靠手数行号；判定「真重复」的口径是**去掉空白 / 注释 / docstring 后逐行比对**）。
**改动前那一列从 `git show <工单 09 收口提交>:<文件>` 取**，所以重排之后再跑仍然量得到同一组数
（第一版量具读的是工作区现状，重排后数字自己变了——评审指出，已修）：

| 函数 | 改动前 | 改动后 |
|---|---|---|
| `_download_one` · `full_task` | 55 行（`326-380`） | **16 行**（`322-337`） |
| `_download_one` · `materials_task` | 47 行（`341-387`） | **18 行**（`340-357`） |
| 两处**完全相同**的代码行（去噪后） | **37 行** | 7 行（只剩调用与说明） |
| 真正的差异 | 3 处 | 2 处 |
| `_resolve_download` | 18 / 13 行（**代码部分只相同 6 行，其余全是注释**） | 一行未动 |

`_download_one` 的三处真差异：**落盘路径**（`PARTS_DIRNAME` vs `"materials"`）、
**整文件哈希的取法**（`download_resume.file_sha256` vs 本地那份 `_file_sha256`）、
**跟批次有关的记账**（签名多一个 `batch`、`_current_part_name`、快照写在哪一层）。
第三处里哈希那半已经收到下载域单源，于是缝只剩两处——这就是本单的划法。
`_resolve_download` 的差异**全在注释**（materials 那份写着「与 full_task 同形」），
但它是「注入缝怎么解析」的**契约**问题、不是动作序列，故**不在本单**（见第七节）。

### 二、历史取证：这套序列真的「两边各改一次」过

| 证据 | 性质 | 说明 |
|---|---|---|
| `22d0f643`（工单 03） | **硬证据**：同一提交里给两个文件各加一遍**完全相同的分支** | `if part.size > 0 and have == part.size:` + `part.downloaded_bytes = have`，评审发现「判据把**完整卷**删掉重下」 |
| `2cad192c`（工单 07） | 软证据：两文件各同步一次边车口径的说明文字 | 1 行 / 1 行，说明这层连注释都要成对维护 |
| `daf0319d`（工单 08） | **反证也成立**：`git show --stat` 显示那次只改了 `download_resume.py`（+165）与其测试 | 三处「清了却没重下」修在下载域；任务层两侧仍在各自维护这套序列 → 同一类问题下次仍要两边各改一次 |
| 两个关键字 `_download_one` / `_resolve_download` | 全仓只有两处（两文件各一） | 没有任何既有判据直接注入这两个私有方法，改动半径清楚 |

`.scratch/resumable-download/probe-03-corridor.py` 的反证（`--negative-no-resume`）走的是
**`_download` 注入缝**（把「异常 → 保留半成品」换成 `unlink`），不碰 `_download_one` 的签名——
这也是本单敢动这两个私有方法的前提。

### 三、做了什么

| 文件 | 变化 |
|---|---|
| `src/contest_generator/task_download.py` | **新增 148 行**：`download_and_verify(part, dest, *, retry, lock, cancel, resolve)` + `PartLike` 协议 + 模块 docstring（量化账、历史代价、为什么不进下载域） |
| `src/contest_generator/full_task.py` | `_download_one` 55 → **16 行**（算 dest → 调原语 → 写快照） |
| `src/contest_generator/materials_task.py` | `_download_one` 47 → **18 行**（同上；**顺手删掉那个从没被用过的 `batch` 参数**） |
| `src/contest_generator/materials_task.py` | **删掉本地那份 `_file_sha256`**：整文件哈希原本有**三个住处**（下载域一份、materials 文件尾一份、full_task 从 materials 同层 import 一份）→ 收到 `download_resume.file_sha256` **一处** |
| `src/contest_generator/task_retry.py` | 新增 `TaskRetryState.callbacks(part)`（回调装配从「挂在 mixin 上」搬到「状态对象上」，共享路径拿到 `retry` 就能装）；**删掉 `TaskRetryMixin.retry_callbacks`**（成了零调用点的转发，见第八节） |
| `tests/test_download_sequence_home.py` | +2 用例（结构守卫 + 反向注入验证） |
| `tests/test_task_download.py` | +8 用例（**原语自己的行为契约**：长度到点 / 可续 / 来路不明 / 失败留半成品 / 取消不写边车 / 校验失败清干净 / 下载器返回 `None` / 真 socket 走缺省下载器） |
| `.scratch/resumable-download/measure-10-duplication.py` | 量具（第一节那张表的出处，可复跑） |

### 四、零行为变化：逐条对过（这是本单的硬验收线）

**`tests/` 既有文件一个字节没动**：改动前三个相关文件 **80 passed**，改动后仍 **80 passed**；
`git status --short tests/` 只多出**新增**的 `tests/test_download_sequence_home.py`。

等价性逐条核对（对照 `git show HEAD:` 的旧正文）：

| # | 关注点 | 结论 |
|---|---|---|
| 1 | 顺序：`dest` 赋值 → `downloaded_bytes = 0` → 长度判 → 可续判 / 清半成品 → 装配 → 调用 | 逐条相同（原语第一段就是这五步） |
| 2 | 「长度到点」短路 | 等价；记号从空串换成 `_NOT_DOWNLOADED`，且保留 `or not digest` 分支——空 sha（假件返回空串）仍读盘重算，与旧 `if not digest` 一致 |
| 3 | 失败路径 | 非取消失败 → `write_partial_marker` 后原样抛出；取消 → 不写边车、原样抛。异常类型与时机未变 |
| 4 | 校验失败 | `clear_partial` + `DownloadVerifyError("卷 {name} 校验失败（SHA256 不匹配）")`；`error_kind` 仍走下载域单源 |
| 5 | 注入缝语义 | `as_task_downloader(download, cancel=…, on_start=…, default=…, before_retry=…, before_attempt=…)` 的实参集合与顺序未变（`before_*` 改由 `TaskRetryState.callbacks` 产出，函数体逐字相同） |
| 6 | 快照时机 | 原语**只做卷内的事**，不写快照；`_write_snapshot(force=False)` 仍在成功之后、由各自模块调用（与旧代码同一位置） |
| 7 | **类属性注入 + 解析时机**（评审纠正过一次） | `_resolve_download` 一行未动；**解析改由原语在「真要下载」时才调用**（`resolve` 参数）。第一版把 `_resolve_download()` 提到长度判**之前**无条件调用——那会让「已下字节 == 卷大小 → 不发请求」这条路上**多解析一次**注入缝，是本次唯一的真实行为差异。现在与旧代码一致：那条短路根本不解析（旧代码的解析在 `else` 分支里） |
| 8 | `_file_sha256` 三处合一 | 调用 `download_resume.file_sha256` 逐字等价（同一实现；chunk 粒度由 256 KiB 变 64 KiB，**只影响读盘速度，不影响结果**） |
| 9 | 下载器返回**非 `DownloadResult` 的假值**（`None` / `""`） | 读盘自算哈希。第一版只认「没下载」记号，于是 `None` → `"None"` → 与真 sha 不等 → **把下好的整卷清掉并报校验失败**（评审实测复现）；现改 `str(actual or "")`，与旧 `if not digest` 逐字等价，并留了一条判据（`test_downloader_returning_nothing_falls_back_to_reading_the_disk`，反向注入 `str(actual)` 时如实转红） |

### 五、新守卫真的会红（防「守卫只是装饰」）

`tests/test_download_sequence_home.py` 两条用例：

1. `test_download_sequence_has_a_single_home`——查三件事：任务模块的函数体里不再出现
   「装配缝 / 写边车 / 可续判据 / 清掉重下」这四个动作；`task_download` 确实是它们的家；
   两条链路**确实**还在调 `download_and_verify`（防绕过）。
2. `test_guard_turns_red_on_reinlined_sequence`——取**磁盘上那个真守卫函数**的源码，
   拼上抄回来的序列，写进 `%TEMP%` 副本再执行：守卫必须指名道姓转红
   （`_reinlined` + 「抄回来」），真身源码一个字节不碰。

**判据口径被评审加宽过一次**：第一版只守 `as_task_downloader` / `write_partial_marker` /
`is_resumable_partial`，于是「只把**清掉重下**那一半抄回来」不会红（工单原文写的正是
「调 `as_task_downloader` + `write_partial_marker` + `clear_partial` 的连续块」）。
现已把 `clear_partial` 一并纳入，四个动作合起来才算那段序列的形状。

另做了一次**面向真实代码形状**的反向验证（把重排前的旧正文当字符串喂给判据本体）：

```
干净的现码     -> []
抄回去的旧形状 -> ['_download_one（第 3 行：as_task_downloader、is_resumable_partial、
                   write_partial_marker）']
```

### 六、回归与真 socket 复跑

- 全套：**4444 passed / 1 skipped**（改动前 4434 / 1；+10 = 本单新增的 2 条守卫用例
  + 8 条原语契约用例，后者含那条 `None` 回归）。
  *口径更正*：跑测试要用 `python -m pytest`（`pyproject.toml` 的 `pythonpath = ["src"]` 才对
  本仓库源码生效）——本机全局那份 editable 安装指向的是沙箱 `firstep-sim`，直接调 `pytest`
  会把**沙箱的源码**当被测对象（本单实测：同一批用例在沙箱源码上 41 failed）。这条已写进
  `docs/agents/local-environment.md`。
- 探针（真 socket，跑在本仓库源码上）：`.scratch/resumable-download/verify-10-after-refactor.txt`
  是**本单重排之后**的原始输出（含日期）——`probe-01-resume.py` 五用例总判 **PASS**
  （起始偏移序列 `[0, 838860, 1342176, 1644166]` 与工单 02/03 逐字节相同）；
  `probe-03-corridor.py`（走廊 / 忽略 Range / 失败态跨进程续传）总判 **PASS**；
  `probe-08-416.py`（恒 416 / 一次性 416 / 本地比远端大 / 分类）四格 **PASS**。
  *评审提过一句「仓内没有新证据」——第一版只跑了探针没落文件，现在落了。*

### 七、本单没做的事（别读大）

- **没动 `_resolve_download`**（两处同形，但代码部分只有 6 行、其余是注释）：它的行为契约是
  **类属性注入缝**（`monkeypatch.setattr(<Task>, "_download", fake)` 必须仍生效），
  要收得先回答「类属性注入点还认不认」——那是**判据问题**，与本单不同性质。
  （本单只改了**何时调用它**：从「无条件先解析」改成「真要下载时才解析」，见第四节第 7 条。）
- **没动 `_restore_snapshot`**（两处同形，但卷的组织方式不同：扁平 vs 按批次）——
  与 `download_resume` 无关，属另一单。
- **没清兼容别名**（工单 09 第五节那笔账，仍是独立一步）。
- **没改状态面字段、词表、重试策略、半成品保留 / 删除的分界**。
- 顺手发现、**未处理**：`materials_task.download_part`（256 KB 分块那支）自工单 03 起
  缺省值已换成 `resumable_download`，它是否还有活口没查——属另一单。

### 八、双轴评审结论（2026-09-13）

两条轴各自独立跑（评审对象 = 本单未提交改动 + 新增文件），**四条硬问题都当场修了并复跑**：

| # | 轴 | 问题 | 修法 |
|---|---|---|---|
| 1 | Spec | **唯一真实行为差异**：`_resolve_download()` 被提到长度判之前无条件调用 → 「长度到点」那条短路上多解析一次注入缝 | 改为把解析器传进原语、**真要下载时才调**（第四条第 7 行） |
| 2 | Standards | **哨兵值改了「下载器返回 `None`」的行为**：非 `DownloadResult` 一律 `str(...)` → `"None"` → 清盘 + 报校验失败 | `str(actual or "")`（与旧 `if not digest` 等价）＋补一条判据，反向注入验证会红 |
| 3 | Standards | `full_task` 三个**死导入**（`DownloadResult` / `DownloadVerifyError` / `part_progress_callbacks`） | 删掉 |
| 4 | Spec | 守卫口径比工单窄：漏了 `clear_partial`（只抄「清掉重下」那一半不会红） | 纳入 `clear_partial`，按工单原口径四个动作一起守 |
| 5 | Standards | 量具退化：读工作区现状，重排后 55/47 那组数**不可复现**，与 docstring 自相矛盾 | 量具改成两个时刻（`git show` + 现状），并输出「相同 / 独有」逐行差 |
| 6 | Standards | `TaskRetryMixin.retry_callbacks` 成了**零调用点的转发**（兼容别名的账被顺手扩大） | 删掉转发，装配只留 `TaskRetryState.callbacks`；注释里写明「兼容别名只留既有判据真在用的那些」 |
| 7 | Spec | 验收记录称探针 PASS 但**仓内没有新证据** | 复跑输出落到 `verify-10-after-refactor.txt` |
| 8 | Standards | `Data Clumps`：`download` / `is_default` 恒成对取自 `_resolve_download()` | 由第 1 条的修法一并消掉：改成传 `resolve` 一个解析器（参数少一个，也不再重复解析） |
| 9 | Standards | 流程：工单还挂着 `ready-for-agent` 就动手了 | 本节之后置 `resolved`；开工先 claim 这条记在 `docs/agents/workflow.md`，下次照做 |

两轴另各有一条**判定为无需改**：`download_and_verify` 这个名字只说了「下载 + 校验」，
但它确实还记账（`part.ok` / 半成品 / 摘要）——改名会变成 `download_verify_and_record…`，
收益不抵名字变长，故保留名字、在 docstring 里把副作用逐条列出（已有的四条规则就是它）；
`is_default` 相关的一处中转发已随第 8 条消失。

**这轮评审值在哪**：第 2 条是**「极端输入下把好文件删掉」**这一类——既有判据全绿、
探针全 PASS，只有把旧正文逐行摆在一起才看得出来；第 1 条是「差异小到没人会注意」
（多一次属性查找），但它正好落在 spec 明写的断点契约那条路上。

## 备注

- **同层依赖方向不许破**：原语放**新模块**，不进 `download_resume`——下载域不许知道
  任务层的记账（`part.ok` / 重试摘要 / 快照），工单 04 立的守卫
  `test_download_resume_module_has_no_status_knowledge` 就是钉这个方向的。
  依赖方向：新模块 → `download_resume`（策略函数），反向不许。
- **半成品保留/删除的分界是任务层策略、下载域只给判据**（工单 03 立的规矩）。
  收动作序列时这条不许被顺手抹平：`is_resumable_partial` 仍是判据，删不删仍由调用点决定。
- **教训来源**（本单的地基，别当背景噪声）：
  - 工单 08 一次在这套序列里改了**三处**「清了却没重下」，并翻出「清掉就地做、旗标已删」那个坑；
  - 工单 03 评审改了「长度到点 → 跳过下载直接校验」与「校验失败用哪个异常」；
  - 整文件哈希**其实有三个住处**（取证过的现状，别照抄旧账）：
    `download_resume.file_sha256`（下载域的那份）、`materials_task._file_sha256`（在
    `materials_task` 文件尾自己又实现一遍，chunk 粒度都不同——256 KiB vs 下载域的 64 KiB）、
    以及 `full_task` 从 `materials_task` **同层 import** 复用的那一份。
    本单顺手把它收到 `download_resume.file_sha256` 一处，但**不许把它当成主目标**。
- 与工单 09 兼容别名的清理是**两件事**：那条是「名字有两个住处」，本单是「动作有两份抄写」。
