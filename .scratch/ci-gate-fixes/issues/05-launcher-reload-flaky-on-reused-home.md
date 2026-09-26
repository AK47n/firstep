# 05 — `launcher-reload` 会偶发全红（**标题那个"复用 HOME"是误判**，真身是 ~1/3 的宽限竞态偶发）

**要做什么：** 让 `tests/browser/launcher-reload.spec.mjs` **不再偶发全红**：同一份代码、
同一个空 `HOME`，四次有效运行里红一次（5 条全红），而**红的那次后台是应用自己停掉了**
（"最后离开 → 停服务"那条不变量在 1.5 秒宽限内没等到新文档的 `register`）。

**被谁阻塞：** 无——可立即开始（但**先说清它不是 `ci-gate-fixes/02` 的回归**，见下）。

**状态：** resolved

- [x] 先按下面的「复现条件」把它稳定复现出来（**先能稳定复现再谈修**；复现不了就别动 spec）
- [x] 定性：是**产品侧**那条宽限竞态（`pagehide` → `bye` → `_EXIT_GRACE` 内 `register` 没到 ⇒
      `os._exit`）在慢盘 / 冷缓存下变宽，还是**夹具**侧（`test.after` 的 `server.stop()` 与
      下一轮 `before` 的端口 / 目录状态互相干扰）
      → **产品侧**（新文档那一发 `register` 丢在传输层；夹具与本单无关，见文末「定性」）
- [x] 修掉之后：`launcher-reload` 在「全新」与「复用」两种 HOME 下都要绿；且**不许**把
      「最后一个页面离开 → 服务自己停」这条产品不变量削弱（那是这个 spec 存在的理由）
      → **12/12 轮全绿**（冻结版读数 `probe-05-catch3.txt`；`_EXIT_GRACE` 一字未改，
      用例 C 照旧「离开 → 停服」实测 1.0–2.5 秒）
- [x] 若定性为"测试环境噪声"而非产品缺陷，就把判据改成对目录状态不敏感，并在文件中写清为什么
      → 不是环境噪声，是产品缺陷（见文末「定性」）
- [x] 中文提交

## Comments

### 现场（2026-09-25，`ci-gate-fixes/02` 排查时撞到）

**现象**：`node --test --test-concurrency=1 "tests/browser/launcher-reload.spec.mjs"`，空 HOME：

| 条件 | 读数 |
|---|---|
| `HOME=%TEMP%\empty-home-ci`（**复用过的目录**，第二轮） | 5 条全红。A = `page.reload: Timeout 30000ms exceeded`（`navigated to http://127.0.0.1:1411/`，卡在 `domcontentloaded`）；B–E = `net::ERR_CONNECTION_REFUSED`（秒级连红） |
| `HOME` 换成一个**全新**空目录 | 5 条全绿（退出码 0） |
| 本机正常 HOME | 5 条全绿 |

后端日志（夹具 `FIRSTEP_BROWSER_SERVER_LOG`）在**绿**那一轮的末尾是：
`GET /api/modules 200` → `POST /api/tabs/bye 200` → `[fixture] 后端进程退出 code=0 signal=null`
——产品按设计自杀了（那正是 spec C 要验的行为），绿的那轮是**后续 register 救回来了**。

> ⚠ **`02` 评审驳回过一个我先前写在这里的对照，别再引用它**：我曾拿"旧夹具 + 空 HOME 也 5 条红"
> 当"非本单引入"的证据——那是**错的**。空 HOME 没有 `config.json` 是**另一个已定性**的根因
> （哨兵判旧后端），它的红与这里的红**签名不同**（3.7 秒快速失败 vs `page.reload` 30s 超时），
> 两者不是一回事。**本单因此不做"是否回归"的判定**。

**本单没定性的部分**：这个签名（`page.reload` 超时 + `ERR_CONNECTION_REFUSED`）在本仓
`local-environment` 第 2 节记的几条老偶发里有前科（并行争用 / 残留服务那一类），
但也可能真是宽限竞态在慢环境下变宽——**先把它稳定复现出来再谈修**，别凭形态猜。

**为什么怀疑宽限竞态**：形态与 `local-environment` 第 2 节记的那条
「F5 重载慢过 1.5 秒会被应用自己关掉」（工单 `launcher-exit-race/01–05` 已修）**同形**——
都是 `pagehide` 的 `bye` 先到、新文档的 `register` 没在 `_EXIT_GRACE=1.5s` 内到达。
该轮修复的判据是「修复后 10/10 全程活着」，但那是**正常 HOME** 下测的；
本单要回答的是**空 / 复用 HOME 下是不是有另一条更慢的路径**（少了预热的目录 / 缓存，
首次请求更慢 ⇒ register 更晚）。

**为什么不并进 `02`**：`02` 的判据（空 HOME + 全新目录）是绿的，CI runner 每次也是全新环境；
这个红只在"同一目录反复用"时出现，成因未定，混在一起会让 `02` 的账读不准。

## Comments

### 复现与定性（2026-09-26 凌晨，本轮实测）

**① 本单的标题前提（"复用过的临时 HOME"）被推翻。** 逐轮读数（`launcher-reload.spec.mjs`，
`HOME`/`USERPROFILE` 指向临时目录）：

| 轮 | HOME | 读数 |
|---|---|---|
| 1 | `%TEMP%\empty-home-ci`（**新建**） | **5 passed / 0 fail** |
| 2 | 同一个目录（复用） | **0 passed / 5 fail**（复现本单现场） |
| 3 | `%TEMP%\empty-home-ci-b`（**新建**） | **5 passed / 0 fail** |
| 4 | `empty-home-ci-b`（复用） | **5 passed / 0 fail** ← 复用**也绿** |
| 5 | 不设 HOME（= 真身 profile） | 5 fail，但**是我的实验错了**：`USERPROFILE`/`HOME` 都删掉之后后端起不来（`Path.home()` → `RuntimeError: Could not determine home directory.`，exit code 1），**与产品无关** |

- 关键反证：**那个"复用过的"目录跑完是空的**（`Get-ChildItem -Force -Recurse` 计数 0）——
  目录里什么状态都没有，产品也一个字节都没往里写（`02` 之后配置走 `FIRSTEP_CONFIG_PATH`，
  种子配置在 `mkdtemp` 出来的临时目录里）。**"目录状态"这个变量不存在**。
- 于是真相是：**~30–40% 的偶发**（4 次有效运行里红 1 次；现场那次也是撞上了），
  与 HOME 的新旧无关。这也解释了为什么 CI 上四轮跑下来 `launcher-reload` **5 条始终全绿**。

**② 机制（红的那轮后端日志是逐字证据）**：进程**自己退出**（`code=0` = `os._exit(0)`，
即"最后一个页面离开 → 停服务"那条产品不变量真的开火了），随后的用例全部
`ERR_CONNECTION_REFUSED`（B–E 秒级连红），A 卡在 `page.reload` 超时（95 秒 = 三次 30 秒）。
日志里最后一轮的时序是：

```
GET / HTTP/1.1 200            ← 新文档的 HTML（reload）
…（同窗口内还有几十条旧文档的 GET /js/… 在飞）
[fixture] 后端进程退出（端口 3322；code=0 signal=null）   ← 宽限到点，register 始终没到
```

即：旧文档的 `bye` 把"在途退出"布防了（宽限 `_EXIT_GRACE = 1.5s`），而新文档那个
**住在 `index.html` head 内联脚本里的 `register`** 没能在 1.5 秒内到达 —— 页面当时**还在
装载模块图**（日志里那一屏 `GET /js/…`）。合理的成因：**浏览器的同源连接池被旧文档在途的
请求占满**，新文档的 `register` 排队排在它们后面；慢机器 / 冷缓存上更容易越过 1.5 秒。
这正是本单怀疑的那条宽限竞态（`launcher-exit-race/01–05` 修过的那条），只是**换了一条更慢的
到达路径**：修法把 `register` 从"等模块图"挪到了"HTML 解析即可发"，但它仍然要**抢到一个连接**。

### 下一步（未做完的部分，留给接手的人）

1. **做一个确定性红证**（本单要求的"先稳定复现"还没到确定性那一步）：用 `page.route`
   把几条模块请求**人为拖慢**（照用例 B 拖 `boot.js` 的既有先例），让新文档的 `register`
   必然排在后面 —— 若那时应用自杀，机制即被证明，且有了一个秒级可控的红回路。
2. 修法候选（**都要先拿上面的红证验一遍**）：
   - **夹具侧**：`reloadAndReady` 在 `page.reload()` 前等网络静默（`networkidle`）——
     真实用户不会在页面还在装载时按 F5；这不碰产品不变量。
   - **产品侧**：宽限窗口的判据从"固定 1.5 秒"换成"页面**真在装载中**就再等一轮"
     （例如把"最近一次页面请求"纳入判据）——动的是产品语义，得单独论证，别顺手改常量
     （`_EXIT_GRACE` 是刻意留的，关了浏览器实测 1.53–1.65 秒停服，用例 C 拿它当契约）。
3. 判据：修完之后**连续跑 ≥10 轮全绿**（本单的偶发率 ~1/3，跑 3 轮绿说明不了问题），
   且 `launcher-reload` 5 条与"最后离开 → 自停"那条不变量都还在。

## Comments

### 定性（2026-09-26，本轮：不再靠形态猜，改成"逮住红那一轮 + 三条独立通道同时记"）

**结论一句话**：红的那一轮里，**新文档的 register 那一发"发出去即失败"**
（`net::ERR_CONNECTION_REFUSED` / `ERR_CONNECTION_RESET`，resource timing 记 `status 0 / size 0`），
服务端**从头到尾没收到它**；注册表停在空集 ⇒ 1.5 秒宽限到点 ⇒ `os._exit(0)`
⇒ 页面装载被拦腰掐断（`reload` 30 秒超时）⇒ 后面每条用例 `ERR_CONNECTION_REFUSED`。
所以"宽限太短"只是**表层**——宽限再长也没用：那一发登记**根本没到**。

**先纠正上一轮的一条推测**（「浏览器的同源连接池被旧文档在途的请求占满，新文档的 register
排队排在它们后面」）：**测不成立**。三支探针都量过（读数 `probe-05-{clock,load,sat2}.mjs`）：
旧文档挂着 **24 发**被拖慢 8 秒的在途请求时，新文档 `document-start` 仍在 reload 后 **15ms**、
register 仍走**新建连接**。

**本轮的取证方式**（照 `08` 的教训：本机复现不出来时别靠形态猜——这里反过来，**能复现就
必须逮住它**）：用**真 spec 命令**连跑（`node --test --test-concurrency=1 …launcher-reload.spec.mjs`），
红的那些轮把现场整份留档；同时记三条独立通道——
① 浏览器侧（`page.on("request"/"requestfailed"/"response")` + 页面侧 `PerformanceObserver` 的
resource timing）；② Node 侧独立通道（每 200ms 一发 `/api/health` **加**一发裸 TCP connect，
1 秒预算，绝不与浏览器共用连接）；③ 服务端 access log（夹具 `FIRSTEP_BROWSER_SERVER_LOG`，
**留档时不筛**）。另用 `probe-05-inject.py` 给 `webapp.py` 临时注入 `[P5]` 落点日志
（register / bye / 布防 / 宽限到点，逐字节复原）——服务端视角的第一次/第二次登记都看得见。

**红的现场读数**（`probe-05-catch2-logs/suite-05-red.txt` 与 `suite-08-red.txt`，本轮 10 套件红 2）：

| 通道 | 读数（红那一次 reload） |
|---|---|
| 浏览器 | `GET /` 发出 @4ms（服务端 200、日志最后一条正常请求）→ `register` 发出 @29ms → **@30ms `ERR_CONNECTION_REFUSED`**，同一刻 `GET /` 也 `ERR_CONNECTION_RESET` → `reload` 30 秒超时 |
| 独立通道 | +3ms `health=200` / 裸 TCP **1ms**；**+217ms 起 `health=ERR` 且裸 TCP 连不上**（此后再没起来）→ 进程 `code=0`（`os._exit(0)` 的签名） |
| 服务端 | access log 最后两条 = 新文档的 `GET / 200` 与**旧文档的** `POST /api/tabs/bye 200`；**没有**那一发 register |
| 注入日志（绿的轮） | 稳态时序是 `bye`（空=True）→ **8–9ms 后** `register 收到`（注册表 0→1）——两件事贴得极近，任何一发丢失就是 1.5 秒后的自杀 |

**机制（与 05 怀疑的"宽限竞态"同源，但到达路径不是连接池排队）**：`register` 那一发**失败即
被丢弃**——head 内联脚本写的是 `fetch(...).catch(() => {})`，**没有任何重试**；浏览器这一次
把它派发在一条**不可用的连接**上（多次连续 reload 之后，旧文档留下的空闲连接被服务端按
keep-alive 超时关掉，浏览器从池里取到它；`ERR_CONNECTION_REFUSED`/`RESET` 正是这个签名），
于是登记永远没发生。旧文档的 `bye` 照旧把注册表清空 ⇒ 宽限到点自杀。

**修法（两条一起上，缺一条都不够）**

1. **重试那一发**（`index.html` head 内联脚本）：丢了再发一次（延时 300ms，预算 < 宽限）。
   这一条是**修法实验**里读出来的：先只加重试 → 确定性红证（`probe-05-redproof.mjs`）
   立刻由红转绿，但**真 spec 连跑 10 轮里仍有 3 轮红**（读数 `probe-05-catch3.txt`），
   现场还是 A 用例（`page.reload` 30 秒超时 + 服务端 `code=0`，access log 里那一发 register 依旧没有）。
   也就是说：**丢了的那一发不是每次都能靠"再发一次"救回来**——新文档那 1.5 秒里要同时
   导航 + 解析 611KB 的 index.html + 取 133 个模块，重试也可能排在后面。
2. **产品侧判据换成"页面真在装载中就再等一轮"**（工单「下一步」里那条候选，本轮落地）：
   `GET /`（导航本身）记一笔「页面正在来」（`TabRegistry.mark_page_request`），退出那一步
   多一条判据：**最近一次页面导航请求落在本次退出这一段里**（不是"布防之后"——见下）
   且离现在不到 `_EXIT_PAGE_GRACE`（3 秒）⇒ 不出手，睡到"那次页面 + 3 秒"再判一次。
   **一发页面至多换一轮等待**（`_page_deferred_at` 记着"这一发等过了"；用户又刷一次可以再换
   一轮，但那本来就是新的一次导航）⇒ 「最后一个页面离开 → 服务自己停」这条不变量**没被削弱**：
   真关浏览器那条路根本没有新页面请求，停服时刻与从前一样（1.5 秒宽限）。
   **`_EXIT_GRACE` 一字未改**（那条是刻意的契约，改大是拿所有关窗场景陪绑）。

**这一步踩了三个坑，都留在这里**（每个都是"本机实测红"逼出来的，下一轮别再踩）：

- **判据不能写成"布防之后"**：`bye` 与新文档的 `GET /` 是**同一个导航的两侧**，谁先到不由
  我们定——`[P5D]` 注入读数量到 `page_at` 比布防时刻**早 10ms**（`probe-05-inject-p5.txt`）。
  写成"之后"就把最常见的情形漏掉，等于没修。所以窗口下界取"布防时刻 − `_EXIT_GRACE`"。
- **不能只取"最近"**：那样"用户就停在这一页上、几秒后关浏览器"会被无端推迟——
  实测用例 C 的停服从 1.3 秒变成 6.5 秒超时（`probe-05-pytest-full.txt` 那一轮红）。
  两侧都得卡。
- **判据与"睡到几点"必须是同一次判定**：拆成两个方法时，第一次调用会把"这一发等过了"记上，
  第二次再问就得到"不用等" ⇒ 循环当场返回、**应用根本不退**（用例 C/D 卡住）。现在
  `exit_via()` 一次调用给全两个答案（正数 = 睡到那一刻；0.0 = 退了），
  `exit_if_due()` 保留原布尔契约给注册表级用例用。

**为什么"发行页面"这一笔是可靠的信号**：导航请求是浏览器自己发的，它**不会**像 fetch 那样
被派发在坏连接上还失败（现场里新文档的 `GET /` 永远到得了服务端，丢的只有那一发 fetch）。

**夹具侧那条候选（等 `networkidle`）不采纳**：它治不了这一条——红那一次旧文档本来就是
**空闲**的（`GET /` @4ms 就回来了、`document-start` @41ms），等待网络静默不会改变
"新文档那一发 register 丢在传输层"这件事。它另有价值（真实用户不会在装载中按 F5），
若将来要加，按"压偶发"记账，**别记成治本**。

### 收口读数（2026-09-26，冻结版；**LF 检出**）

| 项 | 读数 |
|---|---|
| **验收（本单的硬指标）** | `launcher-reload.spec.mjs` **连续 12 轮 6/6 全绿**（`probe-05-catch3.txt`；`probe-05-catch3.py` 就是"连跑并留现场"的回路） |
| 修复前的同一回路 | 10 轮里红 2–3 轮、14 轮里红 2 轮（`probe-05-spec-loop{,2}.txt`、`probe-05-catch{,2}.txt`）；**去掉修法后 A 仍 2/10 红**（同一支回路量过，所以这不是"环境忽然变好了"） |
| 确定性红证 | `node .scratch/ci-gate-fixes/probe-05-redproof.mjs`：**修前红（服务 `code=0` 自杀）/ 修后绿**，秒级回路 |
| 全套 pytest | **5554 passed + 11 skipped**（`probe-05-pytest-full3.txt`） |
| 前端门禁 | **1800 passed / 0 fail**（含本单新增的 3 条结构判据） |
| 浏览器门禁（全部 spec） | **43 passed / 0 fail**（`probe-05-browser-full.txt`；`launcher-reload` 6 条 + 其余 37 条） |
| 「最后离开 → 自停」 | 用例 C 照旧（sweep 读数 1.0–2.5 秒；`_EXIT_GRACE` 未改） |

**改了哪些文件**：`index.html`（内联登记加一次重试）、`webapp.py`（`mark_page_request` /
`exit_via` / `page_defer_until*` + `GET /` 记那一笔 + `_EXIT_PAGE_GRACE`）、
`launcher-reload.spec.mjs`（新增 B2 用例 + 文件头补一条）、
`tab-register-guard.test.mjs`（判据⑧：重试在不在、等待是否压得比宽限短）、
`test_webapp.py`（+5 条：判据两侧 / 一发一轮 / `GET /` 记那一笔 / 跨语言重试预算）。

