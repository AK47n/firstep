# 01 — bfcache 后退回来补登记：同标签导航走再后退，不再看到死页面

**要做什么：** 启动器模式（双击 `start-app.vbs`）下，同一个标签页导航离开应用再**按后退回来**时，
页面与服务都还活着——bfcache 恢复的文档自己补一次登记（撤销在途退出）；若回来时服务确实已经退出
（离开超过宽限窗口），页面给出中文说明与重启指引，而不是一片所有请求都连不上的死页面。

**被谁阻塞：** 无——可立即开始（前置 `launcher-exit-race/01-05` 已 resolved；本单是它账本
「未顺手做」段记下的**相邻洞①**，当时只记账没立单）。

**状态：** resolved（2026-09-24；红证 → 实施 → 三条判据进闸门，读数见下）

- [x] **红证先做**：真 Chrome + CDP 在启动器模式夹具上复现。
      **实际做法**：本机**没有独立安装的 Chrome**，用 playwright 的真 chromium（`channel: "chromium"`）
      + `ignoreDefaultArgs: ["--disable-back-forward-cache"]`——playwright **默认**就传这条 flag
      （`playwright-core/lib/coreBundle.js:34858`），不摘掉它 bfcache 根本不发生。
      四组 launch 配置逐组跑，读数 `.scratch/bfcache-return-register/probe-00-bfcache-red.{txt,json}`
      （base 钉 **`f3578691`**，在冻结的 base worktree 上跑）：

      | 配置 | 走了 bfcache？ | 后退后新 register | 宽限后退出码 | 判定 |
      |---|---|---|---|---|
      | playwright 默认（含 `--disable-back-forward-cache`） | 否（整页重载） | 1 | null | 复现不成立（门禁看不见它，红证要摘 flag） |
      | 摘 flag（默认 headless shell） | 否（整页重载） | 1 | null | 复现不成立 |
      | **摘 flag + `channel: "chromium"`** | **是**（`persisted=true`） | **0** | **0（~1.6s）** | **复现成立**：页面真请求 `FETCH_FAIL` = 死页面 |
      | **摘 flag + `headless: false`** | **是**（`persisted=true`） | **0** | **0（~1.6s）** | **复现成立** |

      **前后对读（同一支探针、同一 `--mode=bfcache-channel`，修完在主树复跑）**：

      | 跑法 | persisted | 恢复时补登记 | 宽限后退出码 | 页面请求 | 判定 |
      |---|---|---|---|---|---|
      | **修前**（base worktree @ `f3578691`） | `true` | **0** | **0**（~1.6s） | `FETCH_FAIL` | **复现成立（红）** |
      | **修后**（主树，本单落地后） | `true` | **1** | `null`（没退） | **`HTTP_200`** | **已修（绿）** |

      修后读数：`.scratch/bfcache-return-register/after-fix/probe-00-bfcache-red.{txt,json}`。探针本轮补了
      一档 `healed` 判定，同一支探针既能当红证、也能当修复后的对读（两条结论都在探针自己的输出里，
      不靠人再解读一遍）。
- [x] **恢复时补登记**：`pageshow` 且 `event.persisted === true` 时用**同一个 `tab_id` + 同一个 `epoch`**
      再发一次登记。**落在 `index.html` head 那段的同一个内联脚本里**（不是 `app.js`）——因为
      "登记的端点字面量只有一处、且必须在装载标签之前"是既有判据（`tab-register-guard` 一、
      `boot-contract` 判据⑥）；恢复时只有**已经注册过的监听器**还会被调用，模块图里的代码根本没机会跑。
      **服务端零改动**（`register()` 的「登记即撤防」语义已够）。
- [x] **真机轮数**：`tests/browser/launcher-reload.spec.mjs` 新增用例 **D**（合成 `pagehide(persisted)`
      → `pageshow(persisted)` 一对，忠实重演 bfcache 时序）：断言"补登记恰好发一次 + 宽限过去后
      服务仍活着 + 页面自己还能拿到数据（`/api/health` 200）"。**5/5 PASS / 24.3s**
      （读数 `.scratch/bfcache-return-register/browser-spec-run-02.txt`，含 A/B/D/E/C 五条）。
- [x] **晚回来的可见态**：用例 **E** —— 服务**真的**停掉之后派发 `pageshow(persisted)`：可见态亮起、
      文案含「应用服务已停止」与 `start-app.vbs`、「重新载入」按钮可见；随后**同一端口**重新起服务
      （= 用户双击启动器），页面**自动重新载入并接回**（判据用 `performance.timeOrigin` 变新文档，
      避免"旧文档里平台卡本来就在"那种假绿——第一版就是这么红的）。
- [x] **判据三处**（走既有缝，不新造一套）：
      ① 结构判据 `tests/js/boot-contract.mjs` **新增判据 ⑦ `restoreRegisterProblems`**
      （监听 `pageshow` + 判 `persisted` / 补登记落在监听体内 / 两处 payload 逐字同源 / 失败**在监听体内**
      广播且 UI 侧监听同一字面量 / 失败留可回读落地态且 UI 侧回读同一个键），守卫
      `tests/js/tab-register-guard.test.mjs` 加 **12 条**（1 条真源码 + 11 条合成反例，含"注释里的字样
      不许喂绿""UI 侧事件名分叉""落地态键分叉"三个假绿反例）→ **23/23 PASS**；
      ② 装载根契约相邻面：判据 ⑦ 复用判据 ⑥ 的同一套抽取件（`scriptBlocks` / `codeAnchorHolds` /
      `callArguments`），端点仍在**同一个内联块**里，`tab-register-guard` 那条"端点字面量只有一处"
      照旧为 1（补登记与初载共用同一份 payload，判据 ⑦③ 逐字比对防漂）；
      ③ 真浏览器行为契约：上面的 D / E。
      **整改后复跑（评审整改完那一版）**：前端门禁 **1780 passed / 0 fail**（读数 `js-gate-run-03.txt`）；
      浏览器门禁（五个 spec 全跑）**40 passed / 0 fail**（读数 `browser-gate-run-04.txt`；该 spec 单跑
      5/5 三次：`browser-spec-run-02/03/04.txt`）；全量 `python -m pytest -n auto -q`
      **5356 passed + 1 skipped / 166s**（读数 `pytest-run-03.txt`）。
      **两轮如实记账的偶发**：本单两次整支浏览器门禁首跑撞上已记档的并行争用偶发
      （`browser-gate-run-02.txt` 36/40、`-03.txt` 35/40：`launcher-reload` 的 A/B 在 `page.goto` /
      `page.reload` 上 30s 超时、后几条 5–40ms 速败），**同一工作树单跑该 spec 立刻 5/5 全绿**
      （A 6.5s / B 5.7s / D 3.7s / E 4.0s / C 1.2s）；形态与 `local-environment.md` 记的
      "A 30s 超时 + 后面速败 = 偶发，别去查产品"逐条对上。**整改前那一轮的前端/浏览器读数**：
      1775 / 40 passed（`js-gate-run-02.txt` / `browser-gate-run-01.txt`）；
      **整改前那一轮的全量 pytest** 5355 passed + 1 skipped + 1 failed / 214s——那条 failed 也是同一偶发
      （`tests/test_js_gate.py::test_full_mode_runs_js_gate_and_pytest` 在 `--full` 路径上真跑浏览器门禁），
      **同一工作树单跑该文件 29 passed / 125.67s**（`js-gate-pytest-isolated.txt`）。
- [x] **不动的三件**：`_EXIT_GRACE` 数值未改（`webapp.py` 零字节改动）、没做心跳/长轮询式存活重设计、
      `TabRegistry` 语义未动（`register()` 的撤防语义本来就够，服务端一行没改）。

## Comments

### 取证（2026-09-24，只读代码事实）

- **注销那一半不判 bfcache**：`static/js/app.js:131-135` 的 `pagehide` 监听器无条件
  `navigator.sendBeacon("/api/tabs/bye", {tab_id, epoch})`——没有 `event.persisted` 判断。
- **本页是 bfcache 合格页**：全仓只用 `pagehide` + `sendBeacon`，**没有 `unload` 处理器**
  （`unload` 才是 bfcache 的硬性排除项）⇒ 同标签导航离开时，页面通常正是**进 bfcache**（`persisted === true`），
  不是真卸载。
- **服务端随即自停**：`webapp.py:517-527 unregister` → 注册表空 → `:565 _schedule_exit_if_idle` →
  `:576 arm_exit` → `:579-581` 睡 `_EXIT_GRACE`（`:465` = 1.5s）→ `exit_if_due(_EXIT)` →
  `os._exit(0)`（仅启动器模式，判据 `:560-562`）。
- **回来时没人补登记**：文档从 bfcache 恢复**不执行任何脚本**（`static/index.html` head 的内联登记不重跑，
  `boot.js` / `app.js` 也不重跑），而全仓**没有 `pageshow` 监听**（`grep pageshow` 只命中注释与历史工单）
  ⇒ 注册表仍空 ⇒ 到点退出；**晚于 1.5 秒回来时服务已经退出了**。
- **用户看到什么**：页面还在浏览器内存里活着，但 `fetch` 全 `ERR_CONNECTION_REFUSED` = 死页面，
  只能重新双击启动器。

### 落地时改掉的一处口径（原验收 → 现状 + 理由）

原验收第 4 条写「至多**一次自动重试**」，落地改成了「**补登记只发一次，不重试**；失败即广播，
恢复靠可见态里每 2 秒探一次 `/api/health`、服务回来**自动重新载入一次**」。理由：
① 补登记失败只有一种成因——回来时已经晚于宽限、服务**已经退出**，几百毫秒后重试必然也失败，
重试是纯粹的空转；② 真正的"恢复"来源是用户重新双击启动器，所以有用的是**探活**（轮询到服务回来
再重载一次），而不是重试登记；③ 不重试也顺带避免在内联脚本里抄第二份 payload。
`reload` 只发生在新文档（服务已回来）之后，不构成"自动无限刷新"。

### 实施落点（4 个文件，前端三处 + 无服务端）

| 文件 | 改动 |
|---|---|
| `src/contest_generator/static/index.html` | ① head 内联脚本加 `pageshow` 补登记（与初载那次**逐字同源**的 payload）+ 失败广播 `service-stopped`；② `<body>` 末尾加 `#service-stopped` 可见态标记；③ CSS 加 `#service-stopped` / `.service-stopped-box`（令牌化：`--radius-*` / `--panel` / `--muted`，z-index 300 压过 `#toast-root`） |
| `src/contest_generator/static/js/ui/service-stopped.js` | 新增：收到广播显示说明 + 「重新载入」按钮 + 每 2 秒探活、服务回来自动重载一次（`initServiceStopped`，幂等） |
| `src/contest_generator/static/js/boot.js` | 具名 import + `initServiceStopped()` 调用（结构判据要求 init 必须有人导入且有人调用） |
| `tests/js/boot-contract.mjs`、`tests/js/tab-register-guard.test.mjs`、`tests/browser/launcher-reload.spec.mjs` | 判据 ⑦ + 7 条守卫用例 + 浏览器用例 D / E |

### 为什么浏览器门禁用**合成事件**而不是真 `goto → goBack`

playwright 默认关掉 bfcache（上面那条 flag），所以门禁里 `goBack` 只会得到**整页重载**：内联登记重跑、
服务活着、用例"绿"——**那是假绿，比红更坏**。所以 D / E 用同一条时序的合成事件
（`new PageTransitionEvent("pagehide"|"pageshow", {persisted: true})`）：产品的监听器、端点、
服务端退出调度全是真的，只有"浏览器替我派发这两个事件"这一步是合成的。
**真 bfcache 的读数**由上面那支探针负责（`--mode=bfcache-channel`），它也是这条红证的唯一出处。

### 未复现的历史记录（立单时的状态，保留以便对照）

立单那轮**没有真机复现**，全是代码事实取证；红证由本单实施前在 base worktree 上补做（见验收第 1 条）。

### 两条候选修法与取舍（立单时记下、落地时按此取舍）

- **A —— `pagehide` 里 `persisted === true` 就不发 bye**（"bfcache 里的页面仍算开着"）。
  **单独用不成立**：用户导航走了不再回来、之后关标签时，被冻结的文档**不会再发 `pagehide`**
  （bfcache 逐出没有对应事件）⇒ 告别永久丢失、服务不再自停——违反「关最后一个页面 = 停服」，
  还留下一个没人管的常驻进程。**本单未采用。**
- **B —— 保留 bye，补 `pageshow` 补登记（已采用）**：epoch = `performance.timeOrigin` 是**每文档**的值，
  bfcache 恢复的是同一个文档 ⇒ 令牌天然不变，与注册表里记的对得上（`register()` 覆盖同键并撤防）。
  宽限内回来 ⇒ 退出作废；晚于宽限 ⇒ 服务已退出、补登记必然失败 ⇒ 靠可见态兜底。

### 与已记边界的关系（别混读）

`launcher-exit-race` 账本那条洞写的是「**1.5 秒内**后退回来会看到死页面」；本单把它拆成两个形态，
**两条都做了**：**① 宽限内回来**——补登记救回（用例 D）；**② 晚于宽限回来**——服务已经退出，
任何补登记都救不回来，给可见态 + 探活自动接回（用例 E）。

### 顺带记下的一条工具事实（本单真踩）

用 PowerShell 做文本读写（`Get-Content -Raw` → `.Replace` → `Set-Content -Encoding utf8`）改
**本单的探针文件**，把它的中文全变成乱码（UTF-8 按 GBK 解码再写回），并且
**GBK 硬配对吞掉了行尾换行符**（多行被并成一行、行数从 ~591 掉到 543）。这正是 CLAUDE.md
那条硬性约定警告的坑——**改文本一律用编辑工具，别用 PowerShell 文本往返**
（`docs/agents/local-environment.md` 也记了一笔）。文件已由原作者的 write 工具整份重写复原。

### 双轴评审与整改（2026-09-24，`code-review`：Spec + Standards 并行，只报告不修改）

评审跑在本单**未提交的工作树**上（fixed point = `f3578691`）。两轴共 11 条：**9 条改掉、1 条按有意
取舍保留并写明理由、1 条是"非违规记录"**。逐条处置（评审原文的编号保留）：

**Spec 轴**

| # | 发现 | 处置 |
|---|---|---|
| 1 | spec 本体未随口径同步（`:35` 仍写"至多一次自动重试"、`:44` 仍写判据"导航走 → 后退 → 服务仍在"） | **已改**：两处各加一行指针指向文末「落地回填」，并把 `范围外` 那条与本单 2 秒探活的关系写明（探活不参与"标签在不在"的判定） |
| 2 | 判据⑦子条款"第二处 register 落在监听体内"没有合成反例（违背守卫文件头"每条子判据各自的反例"） | **已改**：补 4 条反例——②"补登记整块没了"、②"补登记挪到监听体之外"、④"广播挪到监听体之外"、⑤"缺落地态 / 落地态键分叉"；守卫 18 → **23 条** |
| 3 | 闸门里没有真 bfcache（D/E 发合成事件，真 `goBack` 只在 .scratch 探针） | **保留（有意取舍）**：门禁里开 bfcache 要把整支 spec 的 launch 换成"完整 chromium + 摘 flag"，为一条用例把 40 条浏览器用例都押在浏览器版本行为上，红/绿的归因也更差；真 bfcache 已由探针覆盖且可复跑（`--mode=bfcache-channel`，修前红 / 修后绿的读数都在库）。写在 spec「落地回填」第 2 条 |
| 4 | 2 秒探活与 spec「不做心跳 / 长轮询式存活检测」字面冲突；工单里"避免抄第二份 payload"这条理由不成立 | **理由已删、边界已写明**：那条 `范围外` 指的是"用轮询重做标签在不在的判定"（判据⑥ 那套协议），可见态的探活只在可见态亮着时跑、用来把用户重启完的页面自动接回来；工单里那条不成立的理由已删（真理由只有两条：晚于宽限时重试必然失败 + 恢复来源是用户重启启动器） |
| 5 | 广播不判启动器模式，非启动器下也会亮并让用户"双击 start-app.vbs" | **已改**：文案改成「重新启动 firstep：双击 `start-app.vbs`（或你平时启动它的方式）」——两种启动方式下都成立（广播本身只在**服务真的连不上**时才发，非启动器模式下服务不会自停，正常路径根本走不到这里） |
| 6 | 广播是瞬时事件、无落地态：文档在 `boot.js`（132 模块）跑完前被冻结时没人接 ⇒ 可见态永不亮；判据⑦只验字面量同源、不验时序 | **已改（本单最实的一条）**：内联脚本失败时同时写 `documentElement.dataset.serviceStopped = "1"`，ui 模块 `initServiceStopped()` 装载时**回读同一个键**；判据 ⑦ 新增子条款 ⑤（两侧键对账）+ 反例；浏览器用例 E 直接断言这个属性 |
| 7 | `!r.ok` 也广播「服务已停止」，把非 2xx 一律断成"服务已退出" | **已改**：失败判据收窄为**网络错或 5xx**；4xx 明确排除（那是我方载荷问题，不是服务停了），并把同步抛错（存储被拒）经 `Promise.resolve().then(...)` 并进同一条失败路径 |

**Standards 轴**

| # | 发现 | 处置 |
|---|---|---|
| 硬 1 | `boot-contract.mjs` 加了判据⑦但文件头仍是「六类不变量」①–⑥ | **已改**：头部改「七类」并补 ⑦ 的索引行，另注明判据⑦ 的出处工单 |
| 硬 2 | `stringArgCallSites` 是"调用点→首实参转字符串"的**第二份实现**（同文件已有 `endpointCalls` / `sessionStorageKeys`），违背"判据单源" | **已改（评审点的最该修一条）**：`endpointCalls` 改为**委托** `stringArgCallSites`（只负责"哪些函数算端点调用 + 哪个端点"，并恢复位置序）；同型抽取器只剩一份 |
| 硬 3 | `index.html:3053/3055` 硬编码 `"JetBrains Mono", monospace` 与 `0 12px 40px rgba(0,0,0,.5)` | **已改**：改用 `var(--mono)` 与 `var(--shadow-pop)`（后者带亮色主题覆盖——新件在亮色下也不再是黑硬影） |
| 硬 4 | 两个测试文件头未同步（`launcher-reload` 仍写"三条用例 A/B/C"、`tab-register-guard` 仍写判据本体 = `earlyRegisterProblems`） | **已改**：两处文件头改写成"两条判据（⑥/⑦）"与"五条用例（A–E）"，并各自点明新增那条钉什么 |
| 判 1 | 用例 E 内联"等新文档 + waitReady + 日志尾段报错"= `reloadAndReady` 的复制；`waitForLog` ≈ `exitObservedAt` | **已改**：抽出 `pollUntil`（两处共用）与 `waitNewDocument`（`reloadAndReady` 与用例 E 共用）；E 里那段改成一行调用 |
| 判 2 | 内联两处 fetch payload 逐字重复 | **保留（标准背书）**：判据 ⑦② 要求同一内联块内 ≥2 处端点调用、⑦③ 要求两处 payload 逐字同源——抽 `registerBody()` 反而会把判据打红，这处重复是判据形状逼出来的 |
| 判 3 | 注释不实：ui 模块称"幂等"但按钮监听会叠；`#service-stopped-hint` 无 JS 引用；判据⑦④ 只查"块内存在 CustomEvent" | **已改**：`initServiceStopped()` 加 `inited` 守卫（真幂等）；删掉无引用的 hint id；判据 ④ 收紧为"广播必须**在 pageshow 监听体内**"（挪在块内别处不再算过）+ 反例 |
| 判 4 | 探针与读数仍 `??`，而同族 `.scratch/launcher-exit-race/probe-*` 是入库的 | **已改**：探针 + 全部读数随本单一并入 `git add`（入库清单见提交） |
| 判 5 | 非违规记录（`[hidden]` 属性 vs `.hidden` 类并存；`CustomEvent` 有 11 处先例） | 无需动作 |

**复跑读数（整改后）**：`tab-register-guard` **23 passed / 0 fail**；前端门禁见下方「整改后复跑」段。
