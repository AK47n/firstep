# spec — C5 剩余部分：ui 层的测试缝 + browser 用例接闸门

来源：架构评审报告 `%TEMP%\architecture-review-20260920-1745.html` 的 C5 卡「ui 层第一次有缝」，
以及复审结论里被明确「暂不做」的那一条。C5a（两条裸镜像）已由 `.scratch/cross-lang-mirror-c5a/`
落地（见 `.scratch/backlog.md` 第 12 节），**本条是 C5 卡里剩下的部分**。

> 报告副本已随本条入库（`.scratch/ui-dom-contract-gate/architecture-review-20260920-1745.html`）
> ——`%TEMP%` 会被清理，判据源不该只活在那里。
>
> **用例基数更正**：评审原文说「18 个真浏览器用例」，实测 `tests/browser/` 下走 `node --test`
> 的 spec 文件是**三个、共 21 条**（`module-intro` 9 + `code-tree-click` 2 + `hwcheck` 10；
> 评审的 18 应是把当时某个快照的 `hwcheck` 数少了）。本 spec 与工单里的判据一律以实测 21 条为准。

## 问题陈述

前端 `ui/` 层是这个仓库里唯一**没有任何测试缝**的地方，而它正是每次功能都要经过的地方：

- `static/js/ui/` 57 个模块 / 17,996 行 / **513 个 `addEventListener`**；`fx/` 另有 8 个。
- `tests/js/` 147 个文件里，**只有 2 个真的 import 并执行 ui 的代码**（`ui-cycle.test.mjs`
  只做 import 图无环的静态解析、`fix-center-core.test.mjs` 测一个纯流程件）；
  其余涉及 `ui/` 的断言**全部是「读源码字符串」**——`assert.match(ui.includes('from "/js/fx/hwcheck.js"'))`
  这一类。源码里写了什么它管得住，**接上去到底还灵不灵它一个字都不知道**。
- 会灵的证据只有一处：`tests/browser/` 里 21 个真浏览器用例（3 个 spec 文件）。但它们
  **没有任何自动触发点**——`tools/prepush.py` 的 `FRONTEND_PREFIXES` 与 `.github/workflows/ci.yml`
  都不认识 `tests/browser/`，只能靠人记得手敲。
- 于是「改了 `ui/` 某个 id 或监听器、页面点下去没反应」这类缺陷的发现时机，就是**有人顺手跑一次
  真机验收**——这正是 `docs/agents/local-environment.md:207` 记着「在 HEAD 上本就 6 绿 3 红」那条
  挂账的来源：没人跑，所以没人知道它红着。

**本轮实测更正了那条挂账的数字**：在 HEAD（`9b5d69b0`）上跑
`node --test tests/browser/{module-intro,code-tree-click,hwcheck}.spec.mjs` 是
**14 绿 7 红**（不是 6 绿 3 红）。7 条红里 4 条是同一个竞态的连锁（夹具的服务中途自杀，
后面 4 条全 `ERR_CONNECTION_REFUSED`），真红 3 条：

| 真红 | 现象 | 根因（已定位，**都不是产品缺陷**） |
|---|---|---|
| `hwcheck`「选上 MPU6050…冲突预警标 ⚠」 | `#hwcheck-conflicts` 里等不到 `PA22`，30s 超时 | **断言过期**：`hwcheck-pin-conflict-exit/01` 落地后默认脚撞脚在生成前就被求解器解开（OLED_SPI_RES 从 PA22 移到 PA2），页面上如实显示「✓ 没有两件模块抢同一个引脚」+ 一句「生成前自动移开了 2 处默认脚冲突」。用例还在等修前那个冲突 |
| `hwcheck`「专精小节：选上 led…」 | 30s 超时 | **用例间状态污染**：上一条超时中止时把 `ml_mpu6050` 留在了器件集里，本条再选 `led` → 两件都在 → 冲突被如实拦下 → 面板不渲染 |
| `module-intro`「需求清单灰注 + 已选清单行…」 | `#selected-list [data-mod-info="ir_beam"]` 计数 0 | **抢跑**：`#selected-list` 由推荐收尾的异步渲染写入，用例只等了 chip 可见、没等已选清单渲染完。单独跑该 spec 文件 9/9 全绿 |

另有 4 条连锁红（服务被夹具自杀）来自**夹具自身的竞态**：`tests/browser/server.mjs` 设了
`FIRSTEP_LAUNCHER=1`，于是每张页面 `goto` 时的 `pagehide → POST /api/tabs/bye` 会让服务在
1.5s 宽限后 `os._exit`（产品侧 `webapp._schedule_exit_if_idle`）。夹具已用「常开 tab 占位」
打补丁，但**补丁只在那个固定 tab_id 留在注册表里时成立**——本次实测仍会中途死。

## 方案

两件事分开做，各自走仓库已有的先例，不新增第三套做法。

### 一、ui 层的测试缝 = **DOM 契约**，两层落地

`ui/` 模块的 interface 本来就是 DOM：它绑哪些选择器、绑上之后用户做某个动作会看到什么。
这条 interface 今天就存在，只是**没被写下来、也没被跑过一次**。本轮把它明确成两层：

- **第一层（静态健全性，进既有快速闸门）**：`ui/` 源码里写死的 id，必须在页面真正会出现的
  声明集合里找得到——`index.html` 的静态 `id="…"` ∪ 全前端源码里内联生成的 `id="…"` /
  `.id = "…"`。实测今天：541 + 38 = 579 个声明，ui 静态引用 510 个，**缺 0 个**（所以这条
  守卫落地即绿，它防的是明天）。同一层还钉「每个 `ui/` 模块都真的被装载」：导出 `initXxx` 的
  模块必须在 `index.html` 的 import 清单里被导入、且被调用；没有 `initXxx` 的模块必须以
  `import "/js/ui/x.js"`（只为加载）出现。两条都是**纯静态、零浏览器、跑在 `tests/js/` 面**。
- **第二层（行为契约，真浏览器）**：新建 `tests/browser/ui-contract.spec.mjs`——用真页面
  （`index.html` 就是夹具，不手搓 HTML 片段）+ 真后端，对**选定的几个 ui 模块**逐个断言它的
  DOM 契约：绑定生效（点下去真的变）、跨刷新保持（持久化真的写对键）、以及**模块被摘掉就会红**
  （红证逐条留档）。选谁按「监听器密度 × 交互是纯本地的（不依赖 LLM / 编译 / 生成）」定。

为什么第二层走浏览器而不是 `jsdom`：仓库 `package.json` 只有 `playwright` 一个依赖，
`tests/js/` 全部只吃 `node:` 内置模块（所以 CI 不装 npm 依赖也能跑）；引 `jsdom` 既会给那条
零依赖的快速闸门加安装前提，又会引入一份**假的** DOM——而这条缝要回答的恰恰是
「真页面 + 真事件」下还灵不灵。`tests/browser/` 已有真浏览器 + 真后端的夹具，用它。

### 二、21 个 browser 用例接进闸门（先修绿）

- **先修绿**：夹具去掉 `FIRSTEP_LAUNCHER=1`（夹具自己 `stop()` 收服务，根本不需要产品侧的
  自动退出；这一改让「服务中途自杀」这条整类假红消失），端口从固定的 8791 改成**每个 spec
  各向内核要一个空闲端口**（固定端口在「三个 spec 顺序跑」下必然自踩：上一个的服务还没死透、
  下一个 bind 失败，而端口上的旧服务照样答健康检查），补两条用例自身的缺陷（抢跑等待、
  用例间状态污染），并换掉一个已被配方覆盖的样本器件、更新那条过期断言（把「等 PA22 冲突」
  改成断言**新的正确行为**：冲突被求解器解开、线被移走且如实写在接线表与提示里）。
- **接闸门**：`tools/prepush.py` 增加一支与现有前端门禁并列的**浏览器门禁**——改动落在
  `tests/browser/`、`static/js/ui/`、`static/index.html`、`static/js/app.js` 或 `server.mjs`
  时跑 `tests/browser/*.spec.mjs`；`.github/workflows/ci.yml` 增加一个 windows job 跑同一条命令。
  门禁自身故障（node 缺失 / playwright 未安装 / 清单为空）沿用既有政策：**打印原因并放行**；
  用例真红必须拒推。
- **并发纪律**：每个 spec 有自己的端口（互不抢），但三个 spec 仍以
  `--test-concurrency=1` **串行**跑——它们各自起真后端 + 真 Chromium，跑在同一个工作树与
  同一个库目录上，并行只会让失败更难归因，省下的时间不值。

## 用户故事

1. 作为维护者，我想要 `ui/` 里某个模块绑的选择器在页面上**根本不存在**时立刻变红，以便不用等
   人肉点页面才发现「点了没反应」。
2. 作为维护者，我想要新增一个 `ui/` 模块而忘了在 `index.html` 里装载时立刻变红，以便不出现
   「代码写了、从没生效」。
3. 作为维护者，我想要判定「ui 模块到底还灵不灵」不用手敲命令、不用记得起服务，以便这件事
   在合并前就发生。
4. 作为维护者，我想要浏览器门禁的失败**说得清是哪条用例、哪一处契约**，以便一眼知道是自己改
   坏了还是环境问题。
5. 作为维护者，我想要门禁自己在环境不齐时**明说原因并放行**（而不是把推送堵死，也不是静默
   当作通过），以便闸门坏了不阻塞日常。
6. 作为维护者，我想要前端改动的推送闸门**不因为多了这一支而变得难以忍受**，以便我还愿意开着它。
7. 作为使用者，我想要硬件检测页在默认配置下**不再显示一条已经不存在的引脚冲突**误导我改线，
   而如实显示「已经自动移开了哪几根」。
8. 作为使用者，我想要真机验收里那些「刷新后回显」之类已经写好的用例**每次改动都被跑到**，
   以便它们守住的行为真的被守住。
9. 作为下一个接手的人，我想要「ui 的缝在哪、谁守、怎么扩」写在领域词表里，以便不用读完
   `tests/js/` 147 个文件才知道。

## 实现决策

### 一、缝的形状（写进 `CONTEXT.md` 词表，作为领域事实）

- 新词条 **「ui 层测试缝」**：判据 = ① 静态健全性（id 存在性 + 装载可达性，在 `tests/js/` 面）；
  ② 行为契约（`tests/browser/ui-contract.spec.mjs`，真页面 + 真后端）。缝的位置 = **DOM**：
  模块绑的选择器与绑上之后的可观察结果，就是它的 interface；`initXxx()` 是唯一入口。
- 不在本轮把 57 个 ui 模块逐个补契约——**缝先立起来 + 覆盖密度最高的几处**，其余按同一形制
  增量添加（写进词表与 spec 的补充说明）。

### 二、第一层的落点与判据（静态健全性）

- 落点 `tests/js/ui-dom-contract.test.mjs`（新文件），判据来源单源在 `tests/js/ui-dom-contract.mjs`
  （照 `tests/js/import-usage.mjs` 的先例：判据与断言分文件，判据可被别的用例复用）。
- **id 存在性**：从 `ui/*.js` 抠静态 id 字面量（`$("x")` / `getElementById("x")` /
  `querySelector("#x"…)`），声明集合 = `index.html` 的 `id="…"` ∪ 全前端 JS 里内联的
  `id="…"` / `.id = "…"` / `id: "…"`。游离的 id（两边都没有）= 红，并点名文件与 id。
  **不判动态拼接**（模板串拼出来的选择器不进判据——那要靠第二层）。
- **装载可达性**：对每个 `ui/*.js`：有 `export function init*` → 必须在 `index.html` 的
  import 清单里被具名导入**且**在该文件的模块体里出现 `init…()` 调用；没有 `init*` 导出 →
  必须以 `import "/js/ui/<file>"` 出现（只为加载）。落空的模块 = 红并点名。
- 两条都要**反向验证**（把判据打回原状必须变红）——照本仓「判据强度探针」的惯例，证据留工单。

### 三、第二层的形状与取件（行为契约）

- 新文件 `tests/browser/ui-contract.spec.mjs`；夹具沿用 `tests/browser/server.mjs`（真后端 + 真页面），
  新增 `tests/browser/ui-contract-fixture.mjs` 放共用助手（开页、等启动完成、点页签、取存储、
  判定「契约红了」时的报错文案）。
- **选件口径**（写进文件头，作为下一个人扩展的判据）：① 监听器密度高的；② 交互是**纯本地**的
  （只有 DOM + localStorage，不起 LLM / 不编译 / 不生成）；③ 一个模块一条用例，断言的是
  「用户动作 → 可观察结果」，不是内部函数名。
- 本轮取件（4 条，全部满足上述三条）：
  1. `ui/guide.js` — 子页签切换：点页签 → `aria-selected` / `hidden` / `tabindex` 三态一致；
     方向键与 Home/End 循环；焦点跟随。
  2. `ui/step-state.js` — 卡片折叠：点卡头 → `.collapsed` 翻转 + `localStorage` 记忆键写入；
     刷新后记忆生效（**跨刷新的持久化契约**，纯本地）。
  3. `ui/resource-board.js` — 视图切换：点 `.res-view-btn` → `aria-pressed` 与 `#res-view-body`
     内容同步；非法值忽略。
  4. `ui/welcome.js` — 欢迎卡：首屏可见/可关闭，关闭后写 `WELCOME_DISMISS_KEY` 且刷新不再出现
     （**持久化契约**；不清 localStorage，避免影响别的用例）。
- 每条都要**红证**：临时摘掉该模块的绑定，用例必须变红且点名是哪条契约；恢复变绿，证据留工单。

### 四、闸门接线

- `tools/prepush.py`：新增 `BROWSER_PREFIXES` 与 `Selection.browser`（照 `Selection.js` 的形制）；
  新增 `browser_test_files()` / `run_browser_tests()`；命令 `node --test --test-concurrency=1 <展开的文件>`
  （**串行是刻意的**：每个 spec 各起真后端与真 Chromium，且跑在同一份工作树与库上；
  端口已经各用各的，串行是为了失败可归因）。失败语义三分层照 `run_js_tests()`：
  node 缺失 / 清单为空 / **playwright 浏览器不可用**→ 打印原因放行；用例红 → 拒推。
- `.github/workflows/ci.yml`：新增 job `browser-suite`（windows-latest）：checkout（`fetch-depth: 0`）
  → setup-python 3.13 → `pip install -e ".[dev]"` → setup-node 22 → `npm install` →
  `npx playwright install chromium` → 跑浏览器门禁。
- **顺带修一条已经失效的守卫**：`tests/test_ci_workflow.py::test_workflow_does_not_use_secrets_or_network_steps`
  的 action 白名单**只列了 checkout / setup-python**，而 CI 里早已有 `actions/setup-node@v4`
  （工单 module-hwcheck/01 加的）——它现在能绿只是因为没人再动那段。本轮把 setup-node 与
  `pip install` 明确纳入白名单，并把「不联网」那条约定的真实边界写进 docstring（测试不打网络；
  CI 装依赖要联网）。**这条守卫的改动必须在工单里说明，不许静默绕过。**

### 五、修绿的四处（全部是用例/夹具，无产品改动）

| # | 修什么 | 判据 |
|---|---|---|
| 1 | 夹具不再让服务自动退出（去掉 `FIRSTEP_LAUNCHER=1`，保留 `FIRSTEP_LAUNCHER_PORT`） | 三个 spec 连跑不再出现 `ERR_CONNECTION_REFUSED`；「常开 tab 占位」的补丁与注释一并退场 |
| 2 | `module-intro` 第 5 条等 `#selected-list` 渲染完成再断言 | 单文件连跑 5 次全绿；不靠「机器慢」兜 |
| 3 | `hwcheck`「选上 MPU6050」改成断言**新的正确行为**（冲突被求解器解开、原脚与新脚都如实写在页面上） | 断言点在产品真输出上（接线表 + 「自动移开」提示），不再等一个已不存在的冲突 |
| 4 | `hwcheck` 各条**自清**（用例结束/失败都不把器件留给下一条） | 故意让第 7 条红一次，后面的用例仍必须全绿 |

## 测试决策

- **只测外部行为**：
  - 第一层断言的是「id 有没有声明」「模块有没有被装载」——都是事实，不是实现细节；
    不钉函数名以外的写法（改名变量 / 两步走都算通过）。
  - 第二层断言的是「用户动作 → 可观察结果」，**不断言** ui 内部函数名、DOM 结构细节、
    也不断言文案全文（用关键短语）。`pin-share` 那条先例（文案不进对拍）同理适用。
- **测试缝（沿用既有，不新造）**：
  - `tests/js/*.test.mjs`（既有前端门禁，`node --test`）；
  - `tests/browser/*.spec.mjs`（既有真机验收夹具，真后端 + 真 Chromium；端口由夹具向内核要）；
  - 闸门选择器自身的用例 `tests/test_prepush.py`（新增一支就要在这里钉住）；
  - CI 契约 `tests/test_ci_workflow.py`（新 job 要在这里钉住）。
- **既有先例**：`tests/js/import-usage.mjs` + `import-usage-guard.test.mjs`（判据/断言分文件）、
  `tests/browser/code-tree-click.spec.mjs`（真鼠标 + 真页面 + 真后端）、
  `tests/test_prepush.py`（选择器纯函数 + 钩子契约）、本仓「判据强度探针」的红证惯例。
- **不许把 browser 用例塞进 pytest 面**（pytest 不该为前端 shell 出 node + 浏览器），
  也不许把浏览器用例混进 `tests/js/*.test.mjs` 的 glob（那会让零依赖的快速门禁多一个浏览器前提）。

## 范围外

- 把 57 个 ui 模块全部补上行为契约（本轮立缝 + 取 4 件；其余按同一形制增量添加）。
- `index.html` 的 555 个 id 耦合**改造**（评审 C5 卡里提到的那条）——本轮只把它变成**可测的**
  事实（第一层守卫），不动标记结构。这与 `.scratch/backlog.md` 第 10 节「把接线搬出 HTML」是
  两件事，后者仍未立项。
- ui 模块之间 import 环（已有 `ui-cycle.test.mjs`）、`ui/delivery.js` 的 window 挂桥
  （backlog 第 10 节已记账）——都不在本条。
- 产品侧的「F5 重载慢过 1.5 秒会被应用自己关掉」竞态（`local-environment.md:200` 记着的那条）：
  本轮只在**夹具侧**绕开（夹具不需要自动退出），**产品侧不动**——要修另开单。
- 把 `deep-audit.mjs` / `gen-chain-audit.mjs` 这两支审计脚本（不是 `node --test` 用例）
  接进闸门。

## 补充说明

- **为什么不把 `tests/browser/` 直接塞进现有前端门禁的 glob**：那支 glob 的前提是
  「只吃 `node:` 内置模块、零 npm 依赖、几秒钟跑完」，浏览器用例三条都不满足。两支并列、
  各自独立开关，改动落在哪一支就付哪一支的成本。
- **闸门成本口径**（本机实测，写进 README/文档时不写死）：三个 spec 串行 ≈ 50s（含起停服务与
  Chromium 启动），只有改动落在上面那几类落点时才付。
- 本轮**不**把 C5 卡之外的同向候选顺手带上。
