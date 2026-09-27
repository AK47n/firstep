# 本机环境与当前状态（会变，改完就更新这里）

> **这份文件的存在意义**：有些事实只属于「这台机器 + 此刻」，既不该塞进 README（面向用户），
> 也不该只留在会话里（下次就没人记得）。凡是「下次接手需要知道」的环境事实写这里，**只写结论与位置**。
>
> 更新纪律：改动了这里描述的东西（删沙箱、发新版、换端口），**当场回来改这份文件**。

## 0. 交接区：main 上有什么还没到用户手上（2026-09-27 更新 · **已发布 v1.3.1，落差归零；涨落以 `git log` 为准**）

> ### ✅ 最新（2026-09-27，`release-v1.3.1` 会话）—— **`hwcheck-hygiene` 整批已随 v1.3.1 上线，落差归零**
>
> **发版动作走的是 `.scratch/release-v1.3.1/`**（spec + 三张单：`01` 版本同步与自检 / `02` 打包发布 /
> `03` 账本收口，全 resolved；读数与证据都在那个目录）。流程没变，见 `docs/agents/releasing.md`。
>
> | 项 | 值 |
> |---|---|
> | 线上最新 | **v1.3.1**（2026-09-27 发布），八件套齐全，`/releases/latest` 指向它 |
> | 远端 `main` | `1bea22a1`（= 本地 HEAD；`git rev-list --left-right --count origin/main...main` = `0 0`） |
> | tag | annotated `v1.3.1` → **`1bea22a1`**（打包那一刻的 CHANGELOG 提交；tag 对象 `e95be162`） |
> | Release | `https://github.com/AK47n/firstep/releases/tag/v1.3.1`；**八件资产服务端 size 与本地逐件相同（8/8、0 处不一致）** |
> | 联网自检 | `python tools\check-download-docs.py` **PASS**（三组全 `[OK]`；读数 `.scratch/release-v1.3.1/post-publish-check.txt`） |
> | 发版产物（本机留档） | `firstep-pack\firstep-{update,full}-v1.3.1.*` 全套 + `release-notes-v1.3.1.md`；**下一版基线 = 这两个清单**（update **`301,813,614`** B / sha256 `bb573332…`；full **`791,672,980`** B / sha256 `dcba7726…`） |
>
> **这一版带给用户的五条**（Release 说明与 `VERSIONS.md` 同口径）：
> ① 页面上的字面星号没了（JS 产品串 5 处 **＋ 库数据那一层**：配方说明 2434 处 / 模块简介与平台备注
> 1844 处的成对标记现在渲染成加粗）；② 母版配置读不出来 → 中文 400、检测记录读不出来 ≠
> 「记录坏了、删掉重填」；③ 板载 LED 脚以选型数据为源；④ 多实例件（LED / 按键）如实说「只验第一路」；
> ⑤ 勾选后焦点留在原地、器件卡键盘可达、编译/烧录状态可被读屏念出。
>
> **本轮量到的四条新本机事实**（下次发版直接照做，别再踩）：
> ① **钉 IP 的 git config 键与本节原来写的不一样**——`http.https://github.com/.resolve=…`
>    在 **git 2.54.0.windows.1 上不生效**（`ls-remote` 仍按 hosts 解析、约 21 秒后
>    `Failed to connect to github.com port 443`）。**有效的键是 `http.curloptResolve`**：
>
>    ```powershell
>    git -c http.curloptResolve=github.com:443:140.82.114.3 push origin main v1.3.1
>    ```
>
>    （v1.3.0 那次"钉了 IP 就通了"很可能是**巧合**：那个键一直没被 git 认。）
> ② **候选 IP 要按内容验，不能看 HTTP 码**：本机中间人对任意域名都可能答 200。
>    判据 = 拿回来的真是 git 智能 HTTP 广告（`001e# service=git-upload-pack…` + 真 ref）。
>    本轮实测通过的：`140.82.113.3` / `140.82.114.3` / `140.82.116.3` / `20.27.177.113` /
>    `20.200.245.247` / `4.208.26.197`；**同一个 IP 的成功率会变**（113.3 一会儿 OK 一会儿 `000`）。
> ③ **第一次推送仍被掐断**（`Recv failure: Connection was reset`，exit 128，一个字节没上去）——
>    不是"重试即好"：换验过的 IP **并加 `-c http.postBuffer=524288000`**（默认 1 MiB 之上走
>    chunked 编码，中间人更容易掐）之后一次过。
> ④ **新写的 `.ps1` 必须当场补 BOM**：本轮 `finish-publish.ps1` 由编辑工具写出来是**无 BOM** 的，
>    pre-push 闸门的 `tests/test_ps1_encoding.py` 当场红两条、**推送被拒一次**（白等 ~5 分钟）。
>    补 BOM 一条命令：
>    `[System.IO.File]::WriteAllBytes($p, [byte[]](0xEF,0xBB,0xBF) + [System.IO.File]::ReadAllBytes($p))`。
>
> **闸门读数（推送那一刻真跑的，与 13 号单的基线一致）**：pytest **5604 passed + 11 skipped**、
> 前端门禁 **1830 / 0**、浏览器门禁 **60 / 0**。
>
> **仍未做**：本版**没有任何板上行为被验证**——`hwcheck-acceptance/05` 保持 `ready-for-human`
> （本机没有板子），**不拿编译绿当板上证据**。
>
> ### 📌 上一轮（2026-09-27，`hwcheck-hygiene` 会话）—— **01–14 全部 resolved 并落 main，已随 v1.3.1 发布**
>
> **⚠ 交接口径（2026-09-27，13 号单收口后写全）**：
> **本批做完了，下一件事是发版 v1.3.1**（版本号已拍板；三处同步、`tools/preflight.ps1`、两个包、
> tag、Release 见 `docs/agents/releasing.md`；**本机推送要按本节「本机网络事实」钉 IP**）。
> 13 号单（收口）的读数与账在 `.scratch/hwcheck-hygiene/issues/13-closeout.md`；
> **另一条本机事实**：`git checkout` 之后工作树里的文本文件是 **CRLF**
> （`core.autocrlf=true`，blob 里仍是 LF）——写探针锚点**一律按文件实际换行换算**
> （`probe-10-red.py` / `probe-11-red.py` 的 `encode()` / `newline_of()` 是现成写法），别按 LF 写死。
>
> **这一批是什么**：`docs/improvement-review-hwcheck.md` 的 **P2 七项** + 前端守卫补洞 +
> 两个大文件按职责拆分，spec / 工单 / 反证读数全在 **`.scratch/hwcheck-hygiene/`**（**14 张工单**）。
>
> **已完成并各自提交（中文提交 + post-commit 自动补 CHANGELOG）**：
> `01` 全局桥守卫（`tests/js/window-bridge-guard.test.mjs` + 判据 ⑧）/ `02` 字面星号归零
> （`bold-marker-guard` + 判据 ⑨）/ `03` 检测记录写（唯一临时名 + 短临界区 + 按字段合并）/
> `04` 两处「失败」说真话（母版配置读不出来 → 400；记录读不出来 ≠ 损坏）/
> `05` 板级事实单源（LED 脚从 `selection` 取）/ `06` 焦点与可达性（+3 条真浏览器用例）/
> `07` 多实例只验首路（四格配方如实说 + 判据钉到渲染产物）/ `08` 账本收口 + 三条**判据侧**诊断
> （`[afterEach]` 告警 = 夹具在一拍里点掉一批 chip，产品没毛病；产物与页面里的内部工单号归零；
> `launcher-reload` 的 B2 **判据抢跑**——产品的重试预算是 300ms，而断言 322–372ms 就返回，
> 本机 8 轮红 5，已改成轮询等"那一发真的发出去了"）/
> **`09`+`10` 拆 fx**（1380 行 → 六件，barrel 只活一笔提交）/ **`11`+`12` 拆 ui**（1401 行 → 四件：
> 入口 / 核心渲染 / 我的器件 / 动作与请求；10 条源码串断言换成 11 条真浏览器用例）/
> **`14` 库数据里的 `**粗**` 改在渲染层转 `<strong>`**（12 号单当场抓到的既有缺陷：配方 note 2434 处 +
> 74 个 manifest 1844 处经 `esc()` 原样进页面）。
> **每单都跑过双轴 code-review 并整改，票尾有「结论（读数与账）」表。**
>
> **下一步是发版 v1.3.1**（本批不发版）：版本号三处同步、`tools/preflight.ps1`、两个包、tag、
> Release 见 `docs/agents/releasing.md`；本批要进发布说明的**用户可见行为变化**：
> ① 页面上的字面星号没了（JS 产品串 5 处 + **库数据那一层**：配方说明 / 模块简介 / 平台备注）；
> ② 母版配置读不出来与检测记录读不出来各说各的实话；③ 板载 LED 脚以选型数据为源；
> ④ 多实例件如实说"只验第一路"；⑤ 勾选后焦点留在原地、键盘可达、编译/烧录状态可被读屏念出。
>
> **接班要用的七条本机事实**（都是本轮新踩/新立的）：
> ① **读数落盘用 `.scratch/hwcheck-hygiene/readings.py`**（`python readings.py <名> -- <命令>`）——
>    PowerShell 的 `>` / `Tee-Object` 写 UTF-16LE（`read` 工具拒读）、`Select-Object -First N`
>    会掐断上游留下孤儿后端；它收全量、剥 ANSI、写 UTF-8 带命令/时间/退出码头。
> ② **反证探针的锚点要按文件实际换行编码**：本工作树 LF / CRLF 混装
>    （`webapp.py` / `hwcheck_board.py` / `index.html` / `ui/hwcheck*.js` 是 CRLF，
>    `hwcheck_triage.py` / `tests/**` / **`fx/*.js` 是 LF**）——按 LF 写死锚点会在 CRLF 文件上
>    **静默不中**（探针会打印"注入后 sha256 与前置相同"，本轮踩过两次，
>    `.scratch/hwcheck-hygiene/probe-0{4,5,6}-red.*` 里都有现成的 `encode_anchor` / `encode` 写法可抄；
>    07 起这份小工具提成了 `.scratch/hwcheck-hygiene/patch_bytes.py`）。
>    **2026-09-27 补充（10 号单实测）**：`git checkout` 之后文本文件是 **CRLF**（blob 仍是 LF），
>    所以「哪个文件是哪种换行」**跑一次 checkout 就会变**——最稳的写法是 `probe-10-red.py` /
>    `probe-11-red.py` 的 `newline_of()`（读文件现算，不写死），锚点一律按 `\n` 写给 `encode()` 换算。
>    另外：Python 的 `Path.read_text/write_text` 会把 CRLF 归一成 LF 再还原（平台相关），
>    **读数要报字节数就用 `read_bytes()`**——10 号单的迁移脚本第一版报的是"剥掉 CRLF 的字符数"，
>    从盘上复现不出来（双轴评审实测抓到）。
> ③ **浏览器门禁现在是 6 个 spec / 60 条**（11 号单 +11、14 号单 +1），
>    跑法仍是 `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"`（≈3.5 分钟）。
>    改 `static/js/**` 时**必须**跑它——ui 行为只由真浏览器作证（本批 spec 的测试决策）。
>    **只跑一条**用 `--test-name-pattern="<用例名>"`（真夹具照起，一条十几秒）——12/14 的反证探针
>    就是这么把四段/三段的运行时间压到分钟级的。
> ④ **会让配方文件变的探针不许与任何读数并行**（07 第二次踩到：浏览器门禁与注入探针同时跑，
>    读数红在"页面上没有那句话"——那不是产品红，是读到了注入态）。**探针跑完再跑门禁。**
> ⑤ **判据也会抢跑**（08 抓到，比产品缺陷更常见的一类假红）：`launcher-reload` 的 B2 断言
>    "登记重试发生了"，而产品的重试是 `setTimeout(…, 300)`、等待链 322–372ms 就返回——
>    **判据读的是一个还没发生的事**，本机 8 轮红 5。判据要么轮询等那个可观测事实，
>    要么把窗口设得**明显**大于被测的延迟；别用"刚好越过阈值"的数。
>    12 号单的补充：**反证要对着"当年那个 bug 的机制"注入**——把"blur 里的就地同步"换成整块重绘
>    不会红（blur 前状态已同步），真咬人的是**输入回调**那一路。
> ⑥ **探针崩了会留孤儿后端**（08 踩到：`--chips=2` 那支第一版在第 2 轮挂掉，留下两个
>    `contest_generator.webapp` 进程）。它们会抢端口、也会让后面门禁的读数不可信
>    ——**读数前先看一眼**：`Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
>    Where-Object { $_.CommandLine -like '*contest_generator*' }`。
> ⑦ **`tests/js` 不许从导出面判据的消费者集合里排除**（01 号单实测）：照评审 P2-12 字面做会当场红
>    **171 处**（消费者 169 → 只留 `tests/browser` 时剩 11）——判据 D 今天能成立，靠的正是那 150+ 条
>    测试侧 import 边。改写进 `.scratch/backlog.md` 与本批 spec 的「范围外」。
>
> **本轮读数基线**（会随提交变，**别写死**）：全套 pytest **5604 passed + 11 skipped**；
> 前端门禁 **1830 / 0**；浏览器门禁 **60 / 0**；两平台真编译矩阵 6 格全 PASS。
>
> **推之前**（⚠ **这一条已过期**：那二十余笔已随 v1.3.1 推上去了，见本节开头）：
> 推法见本节「本机网络事实」——**键名已更正为 `http.curloptResolve`**（原来写的
> `http.https://github.com/.resolve` 在 git 2.54 上**不生效**，见本节开头第 ① 条）。

> ### 📌 最新（2026-09-26 晚，`hwcheck-hardening` 会话）—— 硬件检测加固七单全落 main，**未发布**
>
> **一句话**：先把 `docs/improvement-review-hwcheck.md`（同日评审）的 **P0+P1 七项**做完了，
> spec / 工单 / 反证读数在 **`.scratch/hwcheck-hardening/`**（`01`–`07` resolved；
> `08` = OLED 分页，`ready-for-human`，**阻塞于真板子**——本机仍没有板子）。
> 收尾又跑了 `code-review` 双轴，立了 `09`–`11` 三张整改单（也已 resolved）：
> 同一条事实的三处副本收成"一句 + 双端断言"、六支探针加 timeout 与"真失败"判据、
> 读数行宽度守卫改成从渲染产物量、**把 03 越过自定硬边界这件事如实更正**（值优先改的是
> 板上可见输出——见下面第 ② 条，发布说明要点名）、读数行地板订正为 167、浏览器读数落盘。
> 每单一提交（中文），post-commit 照旧自动补 CHANGELOG。
>
> **下一版发布说明要带上的用户可见行为变化**（别漏）：
> ① **OLED 口径改成实话**——删掉"结果分屏显示 / 同样的分段内容 / 不接串口也能看"，
> 改成"屏上只留得住最后一行、超过屏宽 16 列会被截断，完整结果看串口"（勾选框文字、通道说明、
> 上板清单三处同口径）；② **读数行改成值优先**（`<值> <单位> (<表达式>)`）——原来横幅在数值之前，
> 实测 53% 的读数光横幅就超 16 列，数值进不了屏；③ **配方里那 5 条超 128 字节行缓冲的读数行修掉了**
> （长说明挪进平台说明）；④ **把库里专精件全勾上也能生成**了（命令池补齐 31 个字符，
> 页面另有"字符快用完"的事前提示）；⑤ **编译面板开始显示链接器形态的诊断**
> （`warning #10210-D: …` 这类此前被报成 0 warning）；⑥ **预览失败说真话**（"检测程序预览失败"，
> 且不再留着上一次的 main.c）；⑦ 每一格配方都如实自述「未上板」，页面顶部另有一句总口径，
> README 同步一句。
>
> **读数**（本机现跑）：全套 pytest **5579 passed + 11 skipped**；前端门禁 **1807 passed**；
> 浏览器门禁 **22/22**（新增一条"预览失败"）；真编译矩阵（`adc/beep/debug_uart` × 两平台）
> 6 格全 PASS（编译器 0 error / 0 warning）。
>
> **两条留给下一轮的**：`hwcheck-acceptance/05`（真机上板，需板子与人在场）与
> `hwcheck-hardening/08`（OLED 分页 / 逐件汇总，同样阻塞于真板子）；评审的 **P2 七项**（焦点与 aria、
> 记录写加锁、拆 `fx`/`ui` 大文件、`tests/js` 的 DOM 桩、多实例、`export-surface-guard` 的消费者集合、
> 账本收口）一条都没动。
>
> ⚠ **一条本轮踩到的工具事实**：`library/hwcheck_recipes.json` 在**盘上会被 checkout 成 CRLF**
> （`core.autocrlf=true`；blob 里仍是 LF）。改它的时候用 `rb`/`wb` 逐字节读写、改完把 CRLF 归一成 LF
> 再提交——本轮就这么处理过一次混合换行（见 `.scratch/hwcheck-hardening/apply-04-units.py` 的写法）。
>
> > ### 📌 上一轮（2026-09-26 凌晨，`ci-gate-fixes` 会话）—— **CI 已转绿**，保留作对照
>
> **结论：`6244e3ee` 推上去之后 CI 三个 job 全绿**（run `36219392088`：
> 浏览器门禁 / 全套 pytest / 快速守卫，逐个 success）。这一轮把「CI 全绿」从"推之前本机绿"
> 推进到"远端真绿"，代价是**四轮"修一层、露一层"**——读数如下（**别把数字写死**，
> 每次提交都在动；要看准就跑 `gh run list --limit 3`）：
>
> | run | head | 结论 | 红在哪 / 修掉它的单 |
> |---|---|---|---|
> | `36154463953` | `606494b1` | failure | 浏览器门禁连起都起不起来（哨兵误判旧后端）+ 前端门禁 step（两条 CRLF 锚点）→ `01–04` |
> | `36213107191` | `0deb8861` | failure | 浏览器门禁 **42 条真跑起来**（39/3）、前端门禁 1796 里只红 **1 条**（**时区**断言）→ `07` |
> | `36216009452` | `db169ed8` | failure | 前端门禁转绿；浏览器 39/2（编译那条按 `08` 显式 skip）；`全套测试` 第一次真跑，冒出 **1 条**（`10`） |
> | `36218384073` | `29d1ac35` | failure | pytest 腿**全绿**；浏览器 40/1/1——只剩一条**偶发**（清器件集的 10 秒等待）→ `11` |
> | **`36219392088`** | **`6244e3ee`** | **success** | **三腿全绿** |
>
> **`ci-gate-fixes` 工单面收口**：`01`–`04`（前一轮）+ `07`（时区断言）+ `08`（缺工具链时显式 skip +
> 夹具能造 CI 前提 + 两处预览等待带诊断）+ `09`（已删自建件自愈并如实报出）+ `10`（msp0 的
> `Debug/makefile` 断言缺 CCS 时 skip）+ `11`（清器件集改重试派发）+ `05`（`launcher-reload`
> 的 F5 偶发，2026-09-26 本轮定性并修掉：新文档那一发 `register` 丢在传输层 ⇒ 产品侧补重试 +
> 退出判据多一条"页面真在装载中就再等一轮"（`webapp.mark_page_request` / `exit_via`），
> 连跑 12 轮全绿）+ **`06`（2026-09-26 深夜补完，`9709587c` + CHANGELOG `bc1fd127`）：
> `masters_confirm` 的 AI 闸改成「按需 + 事务之前」——无归档动作走 04 那道「库在哪」闸
> （`_library_config`，不看 `api_key`）、有归档缺 key 在**调用事务之前**中文 400；
> 判据单源 = `report.parse_archive_section`（事务与闸门共用）+ `master.requests_archive`；
> 读数：全套 pytest **5564 passed + 11 skipped**（基线 5565 → 5575 collected，净增 10 条
> 用例）、`test_library_gate.py` 13 → **23 passed**、判据强度反证
> `.scratch/ci-gate-fixes/probe-06-gate-red-proof.py`（注入旧形态两条各红、复原逐字节相同）**。
> **至此本 spec 的 `01`–`11` 全部 resolved，没有单留在 frontier 上。**
> `main` 已比 `origin/main`（`efa819de`）多出若干笔，**未推**——**别把数量写死**
> （每笔后面还跟着一个 `chore: 自动更新 CHANGELOG`，写完就变），要看准就跑
> `git log --oneline origin/main..main`；推法见本节「本机网络事实」
> （⚠ 键名以本节开头的更正规为准：**`http.curloptResolve`**，不是 `.resolve`）。
> **这一段的状态已过期**：那些提交之后又攒了 `hwcheck-hygiene` 一整批，全部随 v1.3.1 上线了。
>
> **2026-09-26 追加（05 收尾之后：一句过期的账已订正）**：本节下面那张 v1.2.2 落差表里
> `bfcache-return-register/01` 那条第 ④ 项原写「**服务端 / 打包器 / 库零改动**」——
> 那句只对 **v1.3.0 那一刻**成立：`ci-gate-fixes/05` 那一轮已经动了服务端
> （`webapp.py` 的退出判据：`GET /` 记「页面正在来」+ `exit_via`），打包器与库仍未动。
> 该处已就地标注清楚（**别再按"服务端零改动"记账**，否则下次发版的版本清单会漏掉它）。
> **发版提醒（下一版要一起带上的两张行为单）**：`ci-gate-fixes/05`（F5 不再把服务自己关掉；
> 偶发 ~1/3 → 连续 12 轮全绿）与 `ci-gate-fixes/06`（没配 key 也能确认不归档的蒸馏；
> 有归档缺 key 在事务前中文 400）——两单都改了产品行为，发布说明里要点名。
>
> **本轮最值钱的一条方法论**（写进账本）：**本机复现不出来时，别靠形态猜**——
> `08` 加的那两处诊断（页面可见文本 + 末几次 `/api/hwcheck/preview` 的**状态码与响应体**）
> 第一次真跑就把 `:818`/`:914` 的真因逐字带回来了（`400 库中不存在模块：mine_probe692113`），
> 直接催生 `09`。另外：**没被看见触发过的诊断不算证据**——那次诊断的红证当场抓到诊断自己写错了
> （Node 侧变量写进了 `page.evaluate` 的闭包 → `ReferenceError`，三段诊断一行没打出来）。
>
> **读表必读**：`全套 pytest` 那一步此前一直被**前端门禁**挡着（`07` 修好之前它从没在 CI 上跑过），
> 所以 `10` 是"门一开就露出来的"。**新加一道门 / 修好一道门之后，必须再真推一次让它跑起来。**
>
> **本轮新增的三条本机事实**（都在下面第 2 节详记）：
> ① **本机 Node 认 `TZ`**（`TZ=UTC` 时 `new Date(0).getHours()` = 0）——表 0 节那两条
> "本机替 CI 兜底"的缺陷都靠它在本机造前提；
> ② **本工作树的换行是混的**：`tests/browser/hwcheck.spec.mjs` 是 **CRLF**、`tests/js/*.test.mjs` 是 **LF**，
> `core.autocrlf=true` 而两种形态同时在盘上——写锚点正则、写注入探针都得按**文件实际形态**走；
> ③ 浏览器夹具新增 `FIRSTEP_BROWSER_CONFIG_EXTRA`（JSON 并进种子配置）：本机唯一能造出
> "没有工具链"这个前提的口。
>
> **2026-09-26 追加（工单 `ci-gate-fixes/05` 收口轮）——第四条本机事实 + 两条读数口径**：
> ④ **`launcher-reload` 的偶发在本机**（不是 CI）：`node --test --test-concurrency=1
>    tests/browser/launcher-reload.spec.mjs` 连跑 10 轮会红 2–3 轮（A = `page.reload` 30 秒
>    超时、B–E 秒级 `ERR_CONNECTION_REFUSED`），CI 上（全新环境）5 条始终绿。红那几轮的
>    服务端日志与注入读数留在 `.scratch/ci-gate-fixes/probe-05-catch*-logs/`，
>    复跑回路是 `.scratch/ci-gate-fixes/probe-05-catch3.py`（连跑 + 红的轮留未筛日志）、
>    确定性红证是 `.scratch/ci-gate-fixes/probe-05-redproof.mjs`（约 7 秒）。
>    **故障根因**：多次连续 reload 之后，浏览器从连接池里取到旧文档留下的、已被服务端按
>    keep-alive 关掉的空闲连接，新文档那一发 `register` 当场失败（`status 0 / size 0`），
>    于是登记丢失 ⇒ 1.5 秒宽限到点自杀。**修法**：产品侧给登记补一次重试 +
>    退出判据多一条"页面真在装载中就再等一轮"（`GET /` 记一笔；`_EXIT_GRACE` 未改）。
>    ⚠ 这条偶发**与"复用过的 HOME"无关**（本单标题那个前提已推翻：那个目录跑完是空的）。
> ⑤ **`node --test` 的摘要行在 stderr 且带 ANSI**：用 PowerShell 的 `>` / `Tee-Object` 抓
>    stdout 会一行都拿不到（读到的是空），但**重定向 stderr 进同一文件**就有——本轮的
>    "留现场"脚本一律用 `subprocess.run(capture_output=True)` 再落盘 UTF-8 文件
>    （PowerShell 的 `>` 还会写 UTF-16LE，`read` 工具当二进制拒读）。
> ⑥ **注入探针要按文件实际换行换算锚点**：`webapp.py` / `index.html` 在这个检出里是
>    **CRLF**（`.gitattributes` 只声明 `.githooks/*` 与 `*.bat`）——锚点按 LF 写、注入前后换算，
>    否则 `old not in text` 当场失败（本轮踩到两次）。
>
> ### 📌 上一轮（2026-09-25 深夜，`ci-gate-fixes/04` 会话）—— 保留原样，作历史对照


>
> **`main` 上攒了一批还没推的提交**，`origin/main` 仍是 `606494b1`（= v1.3.0 发布那一刻）。
> **别把数量写死**（本节先前写过一次，当场就被自动提交作废）：每个实质提交后面都跟着一个
> post-commit 生成的 `chore: 自动更新 CHANGELOG`，所以计数每提交一次就变——要看准就跑
> `git log --oneline origin/main..main`。**实质提交**（按时间）：
>
> | 提交 | 是什么 |
> |---|---|
> | `af6e4b4f` | 发版 v1.3.0（二）：账本与工单按事实改写 |
> | `fbfa2357` / `46d5a748` | `ci-gate-fixes/01`（配置缺失回退随包库 + 配置路径覆盖口）、`02+03`（夹具种子配置 / CRLF 无关断言） |
> | `fd82f972` | **`ci-gate-fixes/04`**：库相关端点改用「库在哪」闸——没配 key 也能浏览库 |
> | `账本：…` 若干 | 本节按事实更新（含把计数改成"别写死"这一条） |
>
> **CI 现在是红的，而且只有推上去才会变绿**：`gh run list` 最新一条仍是
> `36154463953`（head `606494b1`，failure，2026-09-25T15:29Z），没有更新的 run——
> 修它的 `01–04` 全在本地。**推之前值得一读的**：`01` 修了夹具在干净机器上起不来的根因，
> `04` 顺手把「CI 夹具撞见 400」那个端点的闸门也拆了（`/api/bindings/matrix`）。
> 推法见本节「本机网络事实」（⚠ 键名已更正为 **`http.curloptResolve`**，见本节开头第 ① 条）。
>
> **`ci-gate-fixes` 工单面（`.scratch/ci-gate-fixes/`）**：`01`–`04` 已 resolved 并提交；
> **`05`（`launcher-reload` 在复用 HOME 下会红，现场记录未定性）与 `06`（`masters_confirm`
> 的闸门与它自己的 docstring 不一致，04 盘点时顺带量到）都是 `ready-for-agent`**。
> 04 的读数（本机 LF 检出）：pytest **5545 passed + 11 skipped**、前端门禁 **1796 / 0**、
> 浏览器门禁 **42 / 0**。
>
> ### ✅ v1.3.0 收尾轮（2026-09-25，当时 `main` 与发布包零落差）
>
> **`main` 与线上发布包没有落差了——v1.3.0 已真上线**：
>
> | 项 | 值 |
> |---|---|
> | 线上最新 | **v1.3.0**（2026-09-25 发布），八件套齐全，`/releases/latest` 指向它 |
> | 远端 `main` | `606494b1`（**发布那一刻**的 HEAD；此后本地又攒了 8 个提交，见上） |
> | tag | annotated `v1.3.0` → **`e47d9a8c`**（打包那一刻的 CHANGELOG 提交；**不是** `606494b1`——后者是 tag 之后由 post-commit 生成的 `chore: 自动更新 CHANGELOG`，见 `.scratch/release-v1.3.0/issues/02` 的更正） |
> | Release | `https://github.com/AK47n/firstep/releases/tag/v1.3.0`；八件资产服务端 size 与本地**逐件相同（8/8）** |
> | 联网自检 | `tools\check-download-docs.py` **PASS**（读数 `.scratch/release-v1.3.0/post-publish-check.txt`） |
> | 发版产物（本机留档） | `firstep-pack\firstep-{update,full}-v1.3.0.*` 全套 + `release-notes-v1.3.0.md`；**下一版基线 = 这两个清单**（update `301,635,963` B / full `791,495,348` B） |
>
> 收尾那一轮走的就是交接区留的那条命令（`powershell -File .scratch\release-v1.3.0\finish-publish.ps1`），
> 退出码 0：推 main + tag（带整套 pre-push 闸门）→ 建 Release → 传八件资产 → 联网自检。
> 闸门读数：前端门禁 **1796 passed / 0 fail**、浏览器门禁 **42 passed / 0 fail**、
> pytest **5523 passed + 11 skipped**。
>
> ### ⚠ 本机网络事实（2026-09-25 量准；2026-09-27 更正了「钉 IP」的键名；**每次发版都会再撞上**）
>
> **此前把推送失败记成「瞬时故障、重试即好」是错的。真凶是本机 hosts + 一个本地代理**：
>
> - `C:\Windows\System32\drivers\etc\hosts` 里有 **25+ 行 `127.0.0.1 <github 域名>`**
>   （`github.com` / `api.github.com` / `objects.githubusercontent.com` / `raw.githubusercontent.com` …），
>   本机 **Steam++ 加速器在 `0.0.0.0:443` 用自签证书（`Issuer=CN=SteamTools Certificate`）冒充这些域名**。
> - 后果：**`Test-NetConnection github.com -Port 443` 返回 True、`curl` 也能拿 200——但一次都没到真 GitHub**。
>   于是"网络通了"这个前提本身不可信（本轮的第一次探测就是这么被骗过去的）。
> - 上一次 `git push` 报 `RPC failed; curl 56 Recv failure: Connection was reset` 就出在这条中间人链路上
>   （小请求能过、大 body 被掐），不是 GitHub 挂了，也不是 gh 认证问题。
> - **可用的出路**（把真实 IP 钉给 git，**不动 hosts、不关加速器、不降 TLS 校验**）：
>
>   ⚠ **2026-09-27 更正——下面这个键名是错的**（当时"钉了就通"是巧合）：
>   `http.https://github.com/.resolve=…` 在 **git 2.54.0.windows.1 上不生效**，
>   `ls-remote` 照样按 hosts 解析到 127.0.0.1、约 21 秒后
>   `Failed to connect to github.com port 443`。**有效的键是 `http.curloptResolve`**
>   （v1.3.1 那一轮实测通过）：
>
>   ```powershell
>   git -c http.curloptResolve=github.com:443:140.82.114.3 -c http.postBuffer=524288000 push origin main v1.3.1
>   ```
>
>   （`postBuffer` 是顺手加的：默认 1 MiB 之上 git 走 chunked 编码，中间人更容易掐；
>   第一次推被掐成 `Recv failure: Connection was reset`，换 IP + 加它之后一次过。）
>   候选 IP **按内容验**（拿回来的得是 `001e# service=git-upload-pack…` + 真 ref，
>   不能看 HTTP 码）——本轮可用的有 `140.82.113.3` / `140.82.114.3` / `140.82.116.3` /
>   `20.27.177.113` / `20.200.245.247` / `4.208.26.197`，且**同一 IP 的成功率会变**。
>   也可以像 v1.3.0 那次一样写进**仓库级 `.git/config`** 再 `git config --unset` 清掉
>   （`gh` 走 `api.github.com` 照旧可用）。
> - **验收纪律**：真推上去没有，只能看 **git ref（`git ls-remote` / `gh api .../git/refs/...`）与
>   Release API**；TCP 可达、`curl` 200、浏览器能开页面**都不算数**——
>   `api.github.com` 也在 hosts 名单里，也可能由那个加速器作答。
>
> ### ⚠ 上板验收仍没做
>
> `hwcheck-acceptance/05` 保持 `ready-for-agent`（本机没有板子）。页面上凡涉及实测现象的地方都标着
> 「未上板」——**不拿编译绿当板上证据**。这一版是「硬件检测」整块能力的第一次发布，而它的
> **板上行为从未被真人验过**；下一轮若拿到板子，先做这单。

### 历史：v1.2.2 那一轮的落差表（2026-09-24 口径，**v1.3.0 已把七批一起带走，2026-09-25 发布**）

**当时状态：线上最新 = v1.2.2；main 上已比它多出七批未发布改动**（下表最后一行）。
> 七批的内容 = ① 硬件检测栏目本身 + 检测页引脚出口 ② 完整包会话态进 `AppContext`（纯内部）
> ③ 陌生器件（库外件）探测 ④ bfcache 后退回来补登记 ⑤ 生成工程 README 的 mspm0 打开姿势
> ⑥ 母版 mspm0 引脚符号全局去重 ⑦ mspm0 生成链认下 SysConfig 构建期接口面；
> 本版另加 ⑧ 专精面扩张（30 件 / 57 格）与 ⑨ 三处库内驱动缺陷修复（`driver-defect-fixes/01-03`）。
> 下面这张表保留原样，只作历史对照——**别再当成待办清单读**。

| 项 | 值 |
|---|---|
| 线上最新 | **v1.2.2**（2026-09-19 发布）八件套齐全，`/releases/latest` 指向本版 |
| 这次带上的三张单 | `update-orphan-files/01-03`（产品文件判据单源 + 删除清单累计化 + `revise-backups` 出索引）、`update-verify-failure-leftovers/01`（不可重试的校验失败不留半卷）、`update-content-mismatch-retry-cap/02`（连续 5 次内容不符转终态） |
| 顺手做掉的第四条 | `src/contest_generator.egg-info/**` 摘出产品文件（两个包都不再发 pip 构建产物） |
| **真机验收** | `drill-01`：沙箱真 v1.1.1 → 走产品端点升到 1.2.2，**判红 0 / 卡住 0 / PASS**；`not_in_official` 1482 → **6**，那 6 条经决定性实验证明是**更新器那一步 pip 现写的**（官方包里 0 个 → 跑完 pip 6 个齐），「官方缺失 0 / 内容不同 0」两条全绿 |
| 发版产物（本机留档） | `firstep-pack\firstep-{update,full}-v1.2.2.*` 全套 + `release-notes-v1.2.2.md`；**下一版的基线就是这两个清单** |
| **main 上还没到用户手上的（七批）** | ① **硬件检测栏目本身**（`module-hwcheck/01-09`，2026-09-20 起）＋ **检测页引脚出口**（`hwcheck-pin-conflict-exit/01`：默认脚撞脚提前解开）——v1.2.2 的用户看不到「硬件检测」这一栏；② **完整包会话态进 `AppContext` ＋ `_full_task_lock`**（`full-update-state-into-ctx/01-04`，2026-09-22，账见 `.scratch/backlog.md` §18：纯内部换归属 + 修「并发 apply 建出两个任务」的竞态，**前端零字节**）；③ **陌生器件（库外件）探测**（`hwcheck-unknown-device`，2026-09-22 起：规格 + 12 张工单已落 `.scratch/hwcheck-unknown-device/`，**12 张全部 resolved**（支点模块 `i2c_probe` / 「我的器件」库外件定义与数据目录 / 探测小节渲染（stm32 真编译 + mspm0 分支 + 两平台编译矩阵）/ 检测页计划投影 / 串口复测命令台接入自建件 / mspm0 引脚符号重名拦下 / 自建件 id 文法收紧到 C 标识符 / 资料 → 事实草稿 / 工程内快照与回读 / 排障带自建件事实 / 闸门与真机验收收口）；④ **bfcache 后退回来补登记 + 「应用服务已停止」可见态**（`bfcache-return-register/01`，2026-09-24：前端三处——`index.html` 内联脚本 + 可见态标记 + CSS、新 `ui/service-stopped.js`、`boot.js` 接线；**服务端 / 打包器 / 库零改动**——⚠ **"服务端零改动"这句只对 v1.3.0 那一刻成立，已过期**：`ci-gate-fixes/05` 那一轮改了服务端（`webapp.py` 的退出判据：`GET /` 记「页面正在来」，`exit_via` 给「最后离开 → 自停」多一条"页面真在装载中就再等一轮"；同轮 `index.html` 的登记补了一次重试）——打包器与库仍然没动）。⑤ **生成工程 README 的 mspm0「打开姿势」修正**（`a0602718`，2026-09-24：CCS Theia 只把工作区的**子目录**认成工程，原话术「`File → Open Project` 选择工程目录」按字面做 `Build Project` 是灰的 → 改成实测姿势 + 「两份 mspm0 工程别放进同一个工作区」警告；账见 `.scratch/backlog.md` §20）。⑥ **母版 mspm0 引脚符号全局去重**（`hwcheck-acceptance/02`，2026-09-24：14 组同名符号 / 68 个符号 / 35 个实例全部改成 `<实例名>_<原符号>`，生成宏随之变成 `<实例>_<实例>_<符号>_<后缀>`；35 个模块的 mspm0 源码（36 个文件）+ 27 个 manifest 的 mspm0 段 notes 同批改，**stm32 零改动**；建了构建期守卫「母版引脚符号全局唯一」）——**这条对用户可见的影响是"OLED 屏 + I2C 器件"等 10 组此前必 400 的组合能生成、能编译了**。⑦ **mspm0 生成链认下 SysConfig 构建期接口面**（`hwcheck-acceptance/01`，2026-09-24：`SYSCFG_DL_init()` 那一行从**注释占位**变**活代码**——骨架 / 赛题 / 检测三条路都保证它在 main() 里、生成门禁按"恒有四个 + 裁剪后**外设**实例"精确放行（GPIO 实例不放行，实测 0/109）；检测页那条"上板前取消注释"清单项与两处配方文案随之删改）——**用户可见影响：地猛星上生成的工程烧进去外设真的初始化了**（此前"灯不闪、串口一个字没有"，最像板子坏）。**七批都只在本机工作树 / main 上，任何发布包里都没有**——下次发版要一起带上 |
| **硬件检测验收补齐（本批）进度** | `.scratch/hwcheck-acceptance/`：**01、02、03、04 已 resolved 并提交**（`e80d40d8` / `bb7c3816` / `91a4d270` / 见 `issues/04-*.md`）；**05（真机上板）未开工**——它要真板子，等用户在场。**发版动作（v1.3.0）未启动**，见下条。**2026-09-25 复测**（账 + 读数落 `.scratch/hwcheck-acceptance/报告-复测.md` 与 `recheck-*.txt`）：01–04 的产出**全部成立**（12/12 组合能生成、三路 mspm0 真编译 0 error、页面 11 场景无一被拦、浏览器 21 用例过）；复测另抓到两处**既有**问题——`library/hwcheck_recipes.json` 的 `key` 条目仍写着"上板前取消注释"（工单 01 漏改一处），以及 `parse_compile_errors` 看不见链接器形态告警（`warning #10210-D:`）导致面板对 `ml_mpu6050` 那格误报 0 warning |
| **硬件检测专精面扩张（新 spec，2026-09-25 立项）** | `.scratch/hwcheck-specialize/`：射程 = 首批 20 件从「未专精」升到「专精」（身份探头 + 读数 + 复测命令）；**01 命令字符让位、02 未专精样本解耦、03 批次 A（aht10/sht20/sht30）、04 批次 B（bh1750/bmp180/ms5611）、05 批次 C（hmc5883l/qmc5883l/tcs34725）、06 批次 D（mlx90614/sgp30/at24c02）、07 批次 E（ads1115/pca9685/dht11/ds18b20）七批已全部 resolved 并提交**（`cfa83607` / `f5072abd` / `01f6b066` / `a75b3279` / `2ed04caa` / 06 见 `git log` / 07 = `1e6bb9e5`，各带双轴评审整改）；**——**首批 20 件全部专精化完毕（30 件 / 57 格），本 spec 的收尾（发版动作 v1.3.0）**已于 2026-09-25 完成并上线**。**2026-09-25 用户已明确点头「从 04 一路推到 frontier」**（原「做完 03 停下汇报」的口径已被这条覆盖），后续批次不必再逐批等点头，做完一批接着下一批。每批判据 = 两平台真编译矩阵六/八格全 `[PASS]` + 扩张地板（`EXPANSION` 只追加 + `EXPANSION_CELL_COUNT` 是手写字面量）+ 未专精基线如实下调 + 反证（`probe-expansion-floor.py` 现已支持 `--victim/--platform/--out`，可只撤一格）。**五条量具纪律**：① 读数**按批分文件**（`probe-compile-matrix.txt` 属批次 A，B/C/D/E 起用 `--out …-04.txt` / `-05.txt` / `-06.txt` / `-07.txt`），别覆写前一批的证据；② 配方文件在盘上是 **LF**（**不是 CRLF——07 时按 CRLF 处理过一版是错的**：`.gitattributes` 只声明 `.githooks/*` 与 `*.bat`，这个 JSON 进 blob 是 LF、checkout 出来还是 LF）；反证探针改写与回滚按**原字节**走，编辑时用 `newline=""`，别让文本模式换行归一制造整档重写；③ **会让配方文件变的探针不许与任何"读配方"的验证并行**（05 踩过：矩阵与撤格反证同时跑，读到 `页面标记=未专精` 的假读数）；④ **每批都要穷举一遍"新件 + 既有件"的控制台字符组合**（06 踩过：新件的首选撞掉旧件的首选、而旧件的候选又都是别人的首选 ⇒ 一个四件组合直接 400；**07 起量具 = `probe-console-combos.py`——`|S| <= 6` 全子集穷举 + 容量天花板读数**，并给每条配方补了共享后备池 `n z i 0 1 2 3`；08 已复跑，两个平台全子集（39.8 万 / 76.8 万组）仍零撞车）；⑤ **声明了 `locals` 的格子必须有一条「locals 真被赋值」的判据**（08 踩过最险的一次：`hx711 × stm32` 的探头把采样存进了判定变量 `r` ⇒ **编译过、校验过、探头判 OK、读数恒 0**——守卫 `test_expansion_cells_that_declare_locals_actually_write_them` + 它自己的自检用例 + `probe-locals-guard.py` 反证就是为此立的）。**写配方时的三条新增口径（05/06 起）**：① **`console.candidates` 只从"既不是保留字、也不是任何一件首选"的字符里挑**（06 起再带数字尾巴当兜底）——挑了别人的首选，就会在勾到那一件时把它挤成构建期 400（05 实测 tcs34725 的 `e`/`f` 挤掉 sht30；06 实测 at24c02 的 `e` 撞 sht30 的首选、而 sht30 的候选 `f`/`c` 又都是别人的首选，**已把 sht30 候选改成 `n`/`z`**）；② **note 里不许写死复测字符**（字符是分配后的，勾件不同就不一样；写"敲复测字符"）；③ **recon 是二手来源**：把 recon 的结论写进学生可见文案前，回驱动源码核一遍（06 实测 recon-02 §4.1 把 stm32 头的一句话安到了 mspm0 头上，工单照抄、配方也照抄 ⇒ 已更正 recon 并改文案）。**跨批挂账（04 发现，未修）**：`debug_uart × stm32` 的那条读数行约 **247 字节**、超过板上 `hwcheck_line[128]`，会截成半个汉字——属 v1 pilot 的既有账，见 `.scratch/backlog.md` §21；同文件 §22 = 复测字符池的**容量天花板**（把 26/30 件全勾上必撞，部分已修）、§23 = 库里三处**模块头注释与 syscfg 不一致**（未修）。同批另立 `.scratch/driver-defect-fixes/`：侦察撞出来的三条驱动缺陷各一张 ready-for-agent 修复单（joystick × mspm0 自旋超时 → 读数恒 0、servo × mspm0 周期超 16 位量程、hx711 的 20ms 窗口短于 10SPS 的 100ms） |

**历史：发版尚未启动（2026-09-22 22:0x 实测）** ——**该状态已于 2026-09-25 结清：版本号按建议的
`v1.3.0` 拍板并三处同步、两件套已打、tag 已打、Release 已上线**（见本节开头）。下面只作历史对照保留：

> 这一轮只走到「决定要发」就停了——**版本号仍 `1.2.2`、没打包、没打 tag、没建 Release**。
> 恢复发版的现成条件：`tools\preflight.ps1` 在 `1.2.2` 上**全绿**（改完版本号必须重跑）；上一版
> 基线都在本机 `Desktop\firstep-pack\`（`firstep-update-v1.2.2.files.txt` 给 `pack-update.ps1`、
> `firstep-full-v1.2.2.manifest.json` 给 `pack-full.ps1`、`release-notes-v1.2.2.md` 当模板）；
> `gh` 认证可用；线上 `latest` 仍是 v1.2.2。**版本号当时未拍板**：建议 `v1.3.0`（硬件检测是整块
> 新栏目 → SemVer 次版本 +1）——**这条建议后来被采纳**；流程与口径见 `docs/agents/releasing.md`。

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
> ✅ **2026-09-25 更正（工单 ci-gate-fixes/03）：这两条已经修好，上面那条不再成立。**
> 两条锚点改成 `[^\n]*\r?\n[ \t]*`（吃 CRLF 的行尾 `\r`，只吃同行缩进），**两种检出都绿**：
> 干净 clone（`core.autocrlf=true`）改前 **1794 / 2 fail** → 改后 **1796 / 0 fail**；
> 本机 LF 检出同样 **1796 / 0 fail**。反向验证也做过（把旧 `\n` 锚点注入回去 ⇒ 又是那 2 条红）。
> **注意本机工作树是 LF、CI windows 腿是 CRLF**——这条差异曾经让「本机全绿」骗过一次发布
> （v1.3.0 推上去 CI 才第一次跑这两支闸门就红），报读数时仍要写清检出形态。
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
>
> **2026-09-23（hwcheck-unknown-device/06 会话：串口复测命令台接入自建件）**：
> 这一单让自建件也分到串口命令字符（板上敲该字符重跑它的探测小节，页面命令区照载荷
> 画出"这是自建件"）。本单经历一次会话中途交接：**实现/测试/两轴评审/整改由上一会话
> 完成，收尾（冻结版复跑三门禁 + 探针 + 编译矩阵 → 结论 → resolved）由新会话完成**。
> 与环境有关的事实：
> ① **同样一次服务器都没起**（验证走进程内 TestClient + 域层纯函数 + 前端门禁 +
> 真浏览器夹具自带的后端 + 真 UV4/gmake 子进程）；收尾实测 8000/8020/8021/8791
> 都没在听、无残留 `contest_generator.webapp` 进程。
> ② 读数（整改后的冻结版）：`python -m pytest -n auto -q` **5272 passed + 1 skipped /
> 131.5s**（js_gate 并行偶发本轮未出现）、前端门禁 **1752 passed / 0 fail**、
> 浏览器门禁 **37 passed / 0 fail / 102.8s**（05 轮 36 + 本单 1，新用例排在
> `hwcheck.spec.mjs` 最后）；两平台编译矩阵 **11 格 × 2 平台 0 error / 0 warning**
> （`probe-06-compile-matrix.txt`）；反证 6 条后端注入 + 2 条前端注入全红且逐字节复原
> （`probe-06-guard-strength{,-front}.txt`）。
> ③ **上一会话残留的两个 node 浏览器门禁进程**（`node --test --test-concurrency=1
> tests/browser/…` 及其 hwcheck.spec 子进程）在接手时还在跑——交接中断把浏览器门禁
> 半路撂下了。**接手第一件事先按第 2 节清残留**（node 的 `--test` 进程也一并查），
> 不然自家门禁与残兵抢同一份工作树。
>
> ⚠ **本单实施时定的一条产品口径**（对后面任何"生成产物里加文案"的改动适用）：
> 「这一趟一条命令都没有」那三句（板上帮助 / 检测页 hint / 产物文件头）在自建件
> 出现后**措辞不再统一，但判为不改**——自建件从不声明字符，那三句仍然为真；统一
> 措辞要动字节，与票面"零自建件时产物逐字不变"冲突时**以票面为准**。
> 下一单（12）注意：**自建件 id 的文法允许 `-`，而 id 会被拼进 C 函数名**——
> `mine_gyro-2` 产物编不过但三个端点全 200；量具
> `.scratch/hwcheck-unknown-device/probe-12-hyphen-id.py` 现在返回 0 = 缺陷复现。
> （**12 已修**，见下一条：量具现在返回 1 = 守卫在。）
>
> **2026-09-23（hwcheck-unknown-device/12 会话：自建件 id 文法收紧到 C 标识符）**：
> 同样**一次服务器都没起**（验证走进程内 TestClient + 域层纯函数 + 前端门禁 +
> 真浏览器夹具 + 真 UV4/gmake 子进程）。读数：`python -m pytest -n auto -q`
> **5285 passed + 1 skipped**、前端门禁 **1755 passed / 0 fail**、浏览器门禁
> **37 passed / 0 fail**（首跑 2 红为 `launcher-reload` 已知并行偶发，单跑 3/3 复证）；
> 编译矩阵 **12 格 × 2 平台全 PASS**（新 `hyphen-id-refused` 边界格两平台都在装载期
> 被拦下，读数 `probe-12-compile-matrix.txt`）；反证 3 后端 + 1 前端注入全红逐字节
> 复原（`probe-12-guard-strength{,-front}.txt`）。
> ⚠ **本轮量到的矩阵探针环境事实**：`save_device` 的原子改名在 Windows 上会被
> 实时扫描 / 索引器**瞬时占住句柄**（`PermissionError [WinError 5]`），矩阵连发
> 几十次落盘把概率放大（4 跑 3 中，且**每次废在不同的格**——别把它当成某一格的
> 产品缺陷）。探针已加"`save_device` 整调用重试"（每次重试仍是完整产品调用）；
> 产品侧单次保存要不要也加，另议。
> ⚠ **一条产品限制（评审抓的，如实记）**：盘上旧坏条目（带连字符 id）**在产品里
> 删不掉**——`delete_device` 与文法判据共用一条路径防线，旧 id 过不去；要手工删
> `hwcheck_devices/<id>/`。拆"路径安全 / C 标识符文法"两条判据的小票是候选。
>
> **2026-09-23（hwcheck-unknown-device/07 会话：资料 → 事实草稿）**：
> 同样**一次服务器都没起**（验证走进程内 TestClient + FakeLLM 桩 + 域层纯函数 +
> 前端门禁 + 真浏览器夹具）。读数：`python -m pytest -n auto -q`
> **5322 passed + 1 skipped**、前端门禁 **1764 passed / 0 fail**、浏览器门禁
> **38 passed / 0 fail**（首跑 2 红又是 launcher-reload 已知偶发，复跑全绿）；
> 反证 4 后端 + 1 前端注入全红逐字节复原（`probe-07-guard-strength{,-front}.txt`）。
> ⚠ **本轮一条与"浏览器夹具"有关的设计纪律**（对以后任何要调 LLM 的页面都适用）：
> 浏览器夹具**继承真机环境**起真后端——页面上真点一次"AI 抽取"就是真调一次
> LLM（花真额度）。所以 07 的浏览器用例刻意停在**零请求**（入口渲染 + 知情文案 +
> 空文本本地提示），抽取 / 降级路由 TestClient + FakeLLM 桩钉住。别学有的 spec
> 直接点按钮——先想清楚那个按钮背后是不是真模型。
> ⚠ **LLM 协议加新方法的完整清单**（07 实测漏了两处、评审抓回）：①
> `llm.py` 的 LLM 协议 + DeepSeekLLM + RoutingLLM 三处实现；② `tests/fakes.py`
> 的 FakeLLM 与 RecordingLLM 两个假件；③ **`tests/test_llm.py` 的
> `PROTOCOL_METHOD_NAMES` 覆盖清单 + `_call_all_protocol_methods` 扫描 +
> 派发测试的 remote 名单**——漏了它，"协议全量覆盖"那条不变量静默失效。
>
> **2026-09-23（hwcheck-unknown-device/08 会话：工程内快照 + 回读以快照为准）**：
> 同样**一次服务器都没起**。读数：`python -m pytest -n auto -q`
> **5338 passed + 1 skipped**、前端门禁 **1768 passed / 0 fail**、浏览器门禁
> **38 passed / 0 fail**；反证 4 后端 + 1 前端注入全红逐字节复原
> （`probe-08-guard-strength{,-front}.txt`）。
> ⚠ **本轮踩出来的一条门禁纪律（对"改 JS"的改动适用）**：改完 JS **必须先跑
> `node --test "tests/js/*.test.mjs"` 再跑浏览器门禁**——js 门禁 import 全部
> 模块，一个重名声明（`const saved` 撞既有声明）就会当场红；跳过它直接跑浏览器
> 门禁，代价是 38 条真浏览器用例**全部**在页面加载时超时（读数像"产品全坏"，
> 其实是一个语法错）。另：**别在浏览器门禁跑着时并发跑别的套件**（本轮实测：
> 并发的 pytest 自带的浏览器子套件与它抢同一棵工作树，38 条互相拖死、还留了
> 两个孤儿后端进程）。
> ⚠ **`tests/test_hwcheck_assembly_home.py` 的 import 白名单改法**：08 给 webapp
> 加了 `hwcheck_store.archive_custom_devices` import，守卫当场红——修法不是绕
> 守卫，是把名字加进白名单并在判据旁写明理由（它是**落盘原语**，与
> `write_hwcheck_record` 同族；守卫拦的是装配原语回 webapp）。
>
> **2026-09-23（hwcheck-unknown-device/09 会话：AI 排障带自建件事实）**：
> 同样**一次服务器都没起**（验证走进程内 TestClient + FakeLLM 桩 + 域层纯函数 +
> 真浏览器夹具自带后端）；收尾实测 8000/8020/8021/8791 都没在听、无残留
> （唯一命中的 node 进程是 DSH 自己的，不属于本仓库）。读数：
> `python -m pytest -n auto -q` **5356 passed + 1 skipped / 139.4s**（08 轮 5338），
> 前端门禁 **1768 passed / 0 fail**（本单零 JS 改动，与 08 轮同数），浏览器门禁
> **38 passed / 0 fail / 109.4s**；反证 8 条后端注入全红且逐字节复原
> （`probe-09-guard-strength{,.txt}`）。**编译矩阵本轮未重跑**（本单不碰 C 渲染：
> 改的是排障上下文、两条提示词与页面计划载荷的三个键）。
> ⚠ **本轮量到的一条工具事实（对"评审交给子代理"的会话适用）**：评审子代理会在
> 仓库里**建临时文件**（本轮 Standards 轴建了 `.scratch/_review-standards-09.md`
> 又自行删掉）——评审回来后先 `git status --short` 核一遍文件清单，别把它的残留
> 当自己的改动提交，也别把"多了个文件"误读成产品改动。
> ⚠ **同轮的一条判据事实（对"评审提了死分支"这类结论适用）**：评审把
> `if token in facts.customs: continue` 判成死分支（理由：所有 id 都以 `mine_`
> 开头）——**判错了**：没有它，**本次选中**的 `mine_gyro` 会被前缀判据判成
> "不在本次"。反证探针的注入 B 就是这条（拿掉专用判据 → 对应用例变红），
> 一次注入既证伪了结论、又给新判据留了强度证据：**"死代码"这类判断先用注入
> 试一下再下结论**。
>
> **第 0 节的发布落差表：本轮再添一批 main-only 改动**（工单
> `hwcheck-unknown-device/09`：排障上下文的自建器件事实段 + 两张白名单表 +
> 两条提示词 + 计划载荷三键）；**至此 01–09、11、12 全部 resolved，只剩工单 10
> （收口）**——本特性整批还没进任何发布包。
>
> **2026-09-23（hwcheck-unknown-device/10 会话：收口）**：本特性 12 张工单全部
> resolved。与环境/工具有关的四条：
> ① **同样一次服务器都没起**（收口只跑探针、套件与文档）；收尾实测
> 8000/8020/8021/8791 都没在听、无残留 `contest_generator.webapp` 进程。
> ② **收口驱动**：`.scratch/hwcheck-unknown-device/probe-10-guard-strength-all.py`
> 把 17 支强度探针（12 支 Python + 5 支 Node）**在一份冻结 revision 上逐支重跑**并
> 汇总成一张表（读数 `probe-10-guard-strength-all.txt`），顺带核 `src/` + `tests/`
> 646 个文件整轮前后逐字节未变。**跑它时别跑套件**（探针会真改源文件）。
> 本机读数：全 PASS、约 2 分钟。
> ③ **编译矩阵按交接单口径引用、没重跑**（`probe-12-compile-matrix.txt`：12 格 ×
> 2 平台 0 error / 0 warning）——09/10 两单都没碰 C 渲染。要复跑仍是一条命令：
> `python .scratch\hwcheck-unknown-device\probe-03-compile-matrix.py --out <证据.txt>`
> （约 4–6 分钟）。
> ④ **`tmp-matrix/` 的 gitignore 缺口已补**：`probe-11-contest-dupname.py` 的
> docstring 早写着"产物落 `tmp-matrix/contest-dupname/`（gitignore）"，但
> `.gitignore` 里一直没有这条规则——跑一次它就在工作树里留下 4 套生成工程
> （`?? tmp-matrix/`）。已补规则并删掉残留；**下次谁再写"（gitignore）"的注释，
> 顺手确认规则真的在**。
> 读数：`python -m pytest -n auto -q` **5356 passed + 1 skipped / 137.0s**、
> 前端门禁 **1768 passed / 0 fail**、浏览器门禁 **38 条里首跑 36 passed / 2 failed**
> ——那 2 条又是 `launcher-reload.spec.mjs`（A 在 `page.reload` 上 30s 超时 → B/C 速败），
> **单跑该 spec 3/3 全绿**（`browser-10-launcher-isolated.txt`）；同一工作树收口文档
> 改动前的整支跑是 **38 passed / 0 fail**（`browser-10-all-specs.txt` 是这一跑）。
> ⚠ **这条偶发的形态值得记死**：整支连跑时它每几轮中一次，**单跑必绿**，而且红的那两条
> 永远跟着 A 的超时走（B/C 是 7ms 级速败，不是真失败）——见到"B/C 瞬间红 + A 30s 超时"
> 就按它办，别去查产品。
>
> **2026-09-24（bfcache-return-register/01 会话：启动器模式「导航走后按后退」看到死页面）**：
> 本单把「被浏览器冻结进 bfcache 的文档回来时要补登记」做进产品（账见 `.scratch/backlog.md` §19）。
> 与环境/工具有关的事实四条：
> ① **真 bfcache 在本机要三件一起满足**：`chromium.launch({ ignoreDefaultArgs: ["--disable-back-forward-cache"] })`
> **＋** `channel: "chromium"`（完整 chromium；默认 headless 用的是 headless shell，**它不出 bfcache**）
> **或** `headless: false`。根因是 **playwright 默认就传 `--disable-back-forward-cache`**
> （实测 `node_modules/playwright-core/lib/coreBundle.js:34858`）——所以浏览器门禁里
> `goto → goBack` 只会得到**整页重载**，拿它写"bfcache 用例"是**假绿**（比红更坏）。
> 四组 launch 配置的实测矩阵 + 真复现读数：`.scratch/bfcache-return-register/probe-00-bfcache-red.{txt,json}`
> （base 钉 `f3578691`，在冻结的 base worktree 上跑；探针 `--mode=default|bfcache|bfcache-channel|bfcache-headed`）。
> ② 读数：**整改后那一版**（双轴评审改完）——全量 `python -m pytest -n auto -q`
> **5356 passed + 1 skipped / 166s**（读数 `.scratch/bfcache-return-register/pytest-run-03.txt`）、
> 前端门禁 **1780 passed / 0 fail**（`js-gate-run-03.txt`）、浏览器门禁 **40 passed / 0 fail**
> （`browser-gate-run-04.txt`；该 spec 单跑 **5/5 三次**：`browser-spec-run-02/03/04.txt`）。
> **整改前那一版**：前端 1775、浏览器 40 passed、全量 pytest 5355 passed + 1 skipped + **1 failed**
> （`tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest`——它在 `--full` 路径上真跑整支
> 浏览器门禁；**同一工作树单跑该文件 29 passed / 125.67s**，`js-gate-pytest-isolated.txt`）。
> **本单两次整支浏览器门禁首跑撞上偶发**（`browser-gate-run-02.txt` 36/40、`-03.txt` 35/40）：形态是
> `launcher-reload` 的 A/B 在 `page.goto` / `page.reload` 上 **30s 超时**、后面几条 **5–40ms 速败**；
> **紧接着单跑该 spec 立刻 5/5 全绿**（A 6.5s / B 5.7s / D 3.7s / E 4.0s / C 1.2s）。与本节上面那条
> "A 30s 超时 + B/C 速败 = 偶发，别去查产品"逐条对上——本单给它加了两条用例，撞上的概率只会更高，
> 见到这个形态**先单跑该 spec 复证**再谈产品。
> ③ **又踩了一次 PowerShell 文本往返的坑**（CLAUDE.md 那条硬性约定的实例）：`Get-Content -Raw` 把
> UTF-8 当 GBK 解码 → `Set-Content -Encoding utf8` 写回 = 文件彻底乱码，且**GBK 硬配对吞掉了行尾
> 换行符**（探针 .mjs 从 ~591 行掉到 543 行、多行并成一行）。**改文本一律用编辑工具**（write/edit），
> 别用 PowerShell 读写做替换；这类探针文件不在 git 里，坏了没有 `git checkout` 可回滚。
> ④ 本单没起常驻服务器（浏览器用例走夹具自带的真后端 + 内核分配端口）；探针另起过自己的实例，
> 收尾实测 8000/8020/8021/8791 都没在听、无残留 `contest_generator.webapp` 进程。
> 新落点两个：可见态标记 `#service-stopped` / `.service-stopped-box`（`index.html` 末尾 + CSS）与
> 新 ui 模块 `static/js/ui/service-stopped.js`（由 `boot.js` 显式 `initServiceStopped()` 接线）。

> **2026-09-24（hwcheck-acceptance/02 会话：母版 mspm0 引脚符号全局去重）**：
> 本单把母版 14 组同名引脚符号（68 个符号 / 35 个实例）改成 `<实例名>_<原符号>`
> （账见 `.scratch/hwcheck-acceptance/issues/02-mspm0-pin-symbol-dedup.md`）。
> 与环境/工具有关的事实五条：
> ① **同样一次常驻服务器都没起**（判据走 pytest / 域层直调 / 真编译子进程）；收尾实测
> 8000/8020/8021/8791 都没在听。**本单的探针不真改库内文件**（除了反证探针，见下）
> ——重名现场是用 `tests/conftest.py` 的夹具（真母版文本 + 撤回一处改名）**在内存/临时目录**
> 造的，所以"探针别和套件同时跑"这条纪律在本单只对反证探针适用。
> ② 读数：全量 `python -m pytest -n auto -q` **5359 passed + 1 skipped / 147s**；
> 真编译矩阵 **50 格全绿**（47 格 mspm0 gmake + 3 格 stm32 UV4，0 error / 0 warning；
> `.scratch/hwcheck-acceptance/probe-02-compile-matrix.txt`）；既有 hwcheck 矩阵复跑
> **18 形态判红 0 / 如实拦下 1**（`.scratch/module-hwcheck/probe-09-compile-matrix.txt`，
> 该探针**会清掉上一轮 `probe-09-buildlogs/`**——跑完工作树里必然出现 18 D + N 个 `??`，
> 这是它设计如此，别当成证据丢了）。
> ③ **SysConfig 生成宏 = `<实例>_<符号>_<后缀>`**（`OLED_SPI_SCL_PORT`/`_PIN`/`_IOMUX`，
> 本机 `Debug/ti_msp_dl_config.h` 实测确认）——所以**改引脚符号名 = 改生成宏名**，
> 模块源码必须同批改；改名后的形态是 `<实例>_<实例>_<符号>_<后缀>`（`AHT10_AHT10_SCL_PIN`）。
> ④ **"真库上撞名"这条判据路线已经走到头**：02 之后母版不再有重名，"改回旧名再跑用例"
> 才造得出红（夹具/探针都是这么做的）。**造现场时借的符号必须是"今天仍在用的原名"**
> （`TRIG`），不能按改名前的心智挑（`SR04_TRIG` 在 02 之后**不撞**——探针第一版就栽在这，
> 见 `probe-02-reverse.txt`；`tests/test_syscfg_prune.py` 的阴性对照注入同理）。
> ⑤ 新增构建期守卫：`tests/test_syscfg_prune.py::test_master_pin_symbols_are_globally_unique`
> （母版全文 `name_count == 0`）——**以后往母版加实例，引脚符号撞名会当场红**。

> **2026-09-24（hwcheck-acceptance/01 会话：mspm0 生成链认下 SysConfig 构建期接口面）**：
> 本单把 `SYSCFG_DL_init()` 从**注释占位**变**活代码**（账见
> `.scratch/hwcheck-acceptance/issues/01-mspm0-sysconfig-init-injection.md`）。
> 与环境/工具有关的事实四条：
> ① **同样一次常驻服务器都没起**（判据走 pytest / 域层直调 / 真编译子进程）；收尾实测
> 8000/8020/8021/8791 都没在听。真编译两套工具链都用上了：mspm0
> `C:/ti/ccs2050/ccs/utils/bin/gmake.exe`、stm32 `C:\Keil5\Core\UV4\UV4.exe`。
> ② 读数：真编译矩阵 **4 格全绿**（骨架式 / 赛题式 / 检测程序 mspm0 + stm32 不回归，
> `.scratch/hwcheck-acceptance/probe-01-compile-matrix.txt`）；既有 hwcheck 矩阵复跑
> **18 形态判红 0**（含 **[stm32] adc / ml_mpu6050 / 全选**三格，补上"检测工程 stm32"这一格，
> `.scratch/module-hwcheck/probe-09-compile-matrix.txt`）；领单复核
> `.scratch/hwcheck-acceptance/verify-01-lead.txt`（另一条路线，14 条全过）；
> 全量 `python -m pytest -n auto -q` **5372 passed + 1 skipped / 154s**。
> ③ ⚠ **反证探针没扎中会"假绿"**（本轮连撞两次，都写进读数文件了）：注入点要选在**判据
> 单源**上（针扎在转调层 `syscfg_init_functions_for`，而门禁走的是语料文本入口 → 针下去
> 赛题路仍放行）；清缓存要**整包清**（`contest_generator*` 全删）——只清被改的那个文件时，
> `from .syscfg_model import …` 的模块仍握着**旧函数对象**，看着像"断言是摆设"。
> 这两条对以后任何"改一处、多处共用"的反证探针都适用。
> ④ ⚠ **`tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest` 在 `-n auto` 下会偶发失败**
> （本轮撞一次）：它真的调 `prepush.main(["--full"])`，而 `run_pytest(full=True)` 里写死
> `-n auto` → 嵌套并行，机器一忙就输。形态与既有的"并行争用假红"同源，**单跑该文件或换
> `-n 4` 即过**（本轮复跑 5372 passed）。别把它当成产品坏了。
> ⑤ **同一族偶发还有一条**（工单 03 会话实测一次）：`tests/test_launcher_stale_service.py::
> test_launcher_decision_leaves_the_normal_path_alone` 在 `-n auto` 下失败一次、单跑
> **18 passed / 17.6s** 全绿——形态是"刚向内核要到的空闲端口被另一个 worker 抢走"。
> 判据同上：单跑全绿就不是产品问题。

> **2026-09-24（hwcheck-acceptance/03 会话：被拦下时的出路点名页面控件）**：
> 本单把 400 的出路从"SysConfig 实例名"改成"这一页上做得到的动作"（账见
> `.scratch/hwcheck-acceptance/issues/03-blocked-exit-names-page-action.md`）。环境/工具事实三条：
> ① 一次常驻服务器都没起（域层直调 + 夹具自带后端）；浏览器验收走
> `node --test --test-concurrency=1 "tests/browser/hwcheck.spec.mjs"`（本机 **20 passed / 0 fail / 76s**）。
> ② 读数：探针 `.scratch/hwcheck-acceptance/probe-03-exit-copy.txt`（两分支 400 原文 + 两条出路
> **都照着做过**）、全量 `python -m pytest -n auto -q` **5377 passed + 1 skipped**。
> ③ **页面上那两处栏位标题/勾选框文字现在是常量并有守卫**：`HWCHECK_CHANNEL_SECTION` /
> `HWCHECK_DEVICE_SECTION` / `HWCHECK_CHANNEL_LABELS`（`hwcheck.py`）与
> `static/index.html` 的 `<h3>2. 输出通道</h3>` / `<h3>3. 要测的器件` / 「OLED 屏」对账
> ——**改页面标题就得同步改这几个常量，反之亦然**（守卫会读 index.html 当场红）。

> **2026-09-25（hwcheck-acceptance/04 会话：检测页把验过的器件一键带进生成页）**：
> 本单在检测页「3. 要测的器件」下面加了一块带入区（`#hwcheck-handoff`）——点之前就说清
> "带哪几件 / 哪几件带不过去（为什么）/ 引脚不带"，点下去并进生成页已选清单并展开依赖再切页签；
> 页头副标题与导航 title 里那句陈旧假设一并改掉（账见 `.scratch/hwcheck-acceptance/issues/04-*.md`）。
> 与环境/工具有关的事实四条：
> ① **一次常驻服务器都没起**（验证走 `node --test` 前端门禁 + 真浏览器夹具自带后端）；收尾实测
> 8000/8020/8021/8791 都没在听、无残留 `contest_generator.webapp` 进程。
> ② 读数：前端门禁 **1796 passed / 0 fail**（本单 +15 条）；浏览器 hwcheck spec
> **21 passed / 0 fail / 85s**（读数 `.scratch/hwcheck-acceptance/probe-04-browser.txt`）；
> 反证探针 **7 条注入全按预期变红 + 源码逐字节复原**（`probe-04-guard-strength.txt`）。
> ③ ⚠ **`#toast-root` 里最多并存 3 条 toast**（`app.js` 的 `toast()` 保留最后三条）——浏览器用例
> 读整个容器会把两次点击的文案混在一起（本单实测：第二次点击读到了第一次的"已带进生成页"）。
> 判据要读 `#toast-root .toast:last-child`。
> ④ ⚠ **一条新的环境事实（对"往浏览器门禁加用例"这件事适用）**：
> `tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest` 在 `--full` 路径上**真的会跑整支
> 浏览器门禁**（42 条），而它的预算只有 `pyproject.toml` 的 **180s** 超时——本轮实测**单跑该用例
> 165.4s**（92% 预算），于是**并行套件里连续两次报红**（`-n auto`、`-n 4` 各一次；红的是
> `launcher-reload.spec.mjs` 的 A 超时 + B/C/D/E 速败 = §2 已记的老偶发）。**单跑该用例通过**
> （`1 passed / 165.36s`）、**单跑 `launcher-reload.spec.mjs` 连跑两次都 5 passed**。
> 浏览器门禁从 26 条长到 42 条之后这条就一直贴着临界线，**下次谁再往门禁加用例先量这个数**；
> 要治本得给小 js_gate 用例单独放宽超时或让它别真跑浏览器门禁（本轮未做，属另一张单）。
> ⑤ ⚠ **一条工具事实**：`node --test` 的失败详情里 `✖` 行**不一定**紧跟在 `failing tests:` 之后
> （并行/夹具输出会插进来），探针按"红名单里有宣称的那条守卫"判定比"首条红恰好是它"稳——
> 本单的强度探针照这个口径写的。

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

## 2.4 真机验收第十八轮（2026-09-24，A4/A5/A7）留下的东西

**结论：挂账单 A 组 11 项全部勾满**（本轮补齐 A4 Keil5 / A5 CCS / A7 CCS Theia）。
证据在 `.scratch/real-run/`：`verify-18-A4-keil-rebuild.txt`、`verify-18-A5-ccs-theia-build.txt`、
`verify-18-A7-ccs-theia-build.txt`、`regenerate-for-acceptance.py`（三份工程的重放脚本，
`--force` 可重跑）。挂账单剩下的未勾项：**D1**（6 器件人工取源）、**E1**（干净机器）、
**F 组**（按该单自己的定义不是待办，只是登记以免重判）。

**盘上多出来的东西**（要清就清这两个；`empty` 别碰）：

| 位置 | 是什么 |
|---|---|
| `~\workspace_ccstheia_a5\mspm0_project\` | A5 的 CCS 工作区（工程是它的**子目录**） |
| `~\workspace_ccstheia_a7\mspm0_project\` | A7 同上 |
| `~\workspace_ccstheia\empty\` | **TI 官方 empty 示例 = mspm0 母版源，只读，别删**（`architecture-deepening-v5/08` 定的） |

本轮还按 HEAD 重放了三份新树 `out_18_A4_stm32_2026C` / `out_18_A5_mspm0_2026H` /
`out_18_A7_mspm0_min`；**旧树没动**（`out_2026C_stm32` / `out_2026H_mspm0` / `out_16_mspm0_min` 留作对照）。
新旧树的实测差异：stm32 的 `pin_config.h` 多 28 行（HMC5883L / QMC5883L / I2C_PROBE，来自
`hwcheck-unknown-device/01`），mspm0 只多 12 行 `syscfg` 注释、**落点零变化**。

⚠ **CCS Theia 的工程模型（本轮卡住半小时，务必记住）**：**打开的文件夹 = workspace，工程 = 它的子目录**
（靠子目录里的 `.ccsproject` 注册）。**把工程目录本身当 workspace 打开时它扫不到** → `Build Project`
灰掉、`Build All` 点了没反应、Output 的 `ccs project-build` 一个字都没有。可行姿势 = 建工作区目录 +
把工程**拷成子目录** + `File → Open Folder` 打开那个目录（与 `architecture-deepening-v5/08` 记的
2026-08-09 首次 GUI 编译通过一致，那次也是「拷入工作区」）。完整步骤写在挂账单的「A 组附带」段。

⚠ **两份 mspm0 工程的 CCS 工程名都写死 `mspm0_project`**（母版 `library/masters/mspm0/.project`，
产品无改名机制）→ 同一 workspace 里导入两份必然重名冲突 → **各用各的 workspace**。
真实用户两道题各生成一份也会撞上（挂账单记为观察项 O-2，尚未开单）。

⚠ **交给 GUI 验收前必须清掉旧构建产物，且别提前用 CLI 预编同一棵树**（本轮实测踩到假绿）：
Keil 要清 `user/Objects/*` + `user/Listings/*`，CCS 要清工程下 `Debug/`。不清的话 IDE 判「无需重编」→
**空转 `Build Time 00:00:00`、一条 `compiling` 都没有**，只翻出上一版结果报 0/0——那只证到「IDE 能解析
工程文件」，**没证到「能编」**。判据必须带「这次真编了」的旁证（Build Time 非 0 / 有 compiling 行 /
产物 mtime 是本次）。本轮 A4 第一次就是这么假绿的，空转日志留档
`.scratch/real-run/verify-18-A4-keil-first-attempt-noop.htm`。

**顺带纠正的一处误读**：盘上 `out_2026H_mspm0` 的清单是 `slugs: ["motor","servo"]` +
`bindings: {"servo.SERVO_PWM_C0":"PA0"}`，**本来就是可解形态**；挂账单 A5 里那条「7 条 SysConfig
引脚冲突」说的是**12 模块**的 2026H 选中集，两者此前被混为一谈（已在挂账单补更正）。

**CCS 打开工程时会改写 `.cproject`**（补它自己的设置）：本轮实测模块 include 路径原样保住，
只抹掉了产品写的 `builtIn="false"` 属性 → 不影响产物可用性。


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

**同一条边界也管着探针（2026-09-25 硬件检测复测实测）**：`.venv` 里**连 `httpx` 都没有**，
所以任何 `from fastapi.testclient import TestClient` 的探针（走 `/api/...` 端点的那些）用
`.venv\Scripts\python.exe` 跑会直接抛 `RuntimeError: ... requires the httpx2 package`
（本机 `.venv` starlette 1.6.0、系统 python starlette 1.3.1）。用 `py -3` 跑就好；
纯域层的探针（不 import TestClient）两个解释器都能跑。

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
