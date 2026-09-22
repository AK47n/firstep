# 04 — 真浏览器验收：启动器模式下的连续 F5（含确定性用例与"关页面 = 停服务"）

**要做什么：** 加一条**真浏览器 + 真后端 + 开启动器模式**的 spec，把这条竞态按它被发现的
方式验回来：连续 reload ≥ 8 次服务**始终活着**、页面每次都能用；再用一条**确定性**用例
（把 `boot.js` 的响应拖到宽限之外）把"修复前必红 / 修复后必绿"钉死；最后验"最后一个页面
离开 → 服务自己停"（"不许弄丢关浏览器 = 停服务"）。用例自己起服务自己收，不留残留进程。

**被谁阻塞：** 01（早注册）、02（文档实例令牌）—— 确定性用例在 02 之前会因乱序而偶发红。

**状态：** resolved

## 验收标准

- [x] `tests/browser/server.mjs` 增 `startServer({ launcher: true })`（给子进程置
      `FIRSTEP_LAUNCHER=1`）；**其余 spec 仍不设**（服务生命周期归夹具这条决策不变），
      并把文件头那段"为什么必须不设"改成新的口径（产品侧竞态已修，启动器模式由
      `launcher-reload.spec.mjs` 专门验）。另加 `PYTHONUNBUFFERED=1`（见 Comments ①.4）。
- [x] 新 spec `tests/browser/launcher-reload.spec.mjs`（自动进浏览器门禁 glob）：
      - [x] **用例 A**：连续 reload **N = 8**（覆盖现场第 7 次命中的量级），每轮断言
            "服务活着（`/api/health`）+ 页面可用（平台卡渲染出来）"，失败时打印服务端日志尾段。
      - [x] **用例 B（确定性）**：`page.route("**/js/boot.js")` 把装载根的响应拖到宽限之外
            （2s > `_EXIT_GRACE` 1.5s）再 reload —— 修复前旧 register 要等模块图 ⇒ 服务自杀
            ⇒ 必红；修复后 head 内联脚本的登记不受影响 ⇒ 必绿；页面最终仍装载可用。
      - [x] **用例 C**：最后一个页面离开 → **服务自己停**（上限 grace + 余量），且断言
            "是这一发告别关掉的"（防"服务早就死了"时假绿：判据含服务端确实收到 `bye`）。
      - [x] 用例自己起服务自己收：`after` 里 `browser.close()` + `server.stop()`（进程已死
            也能收干净、端口必须真空出来）。三条用例**各自成立**（单跑任一条都不空转）。
- [x] **真红证**：该 spec + 夹具选项放进 `eae57b43` 的 `git worktree` 里跑（playwright 经主仓库
      `node_modules` 解析）→ **3 条全红**（`probe-04-browser-red-proof.txt`）；**B 单独跑**
      也红，且服务端日志把死因钉住：`GET /` → `bye` →（**没有 `register`**）→ 进程 `exit 0`
      （`probe-04-b-only-server.log` / `probe-04-b-only.txt`）。跑完 `git worktree remove`，
      不留残留。
- [x] `node --test --test-concurrency=1 "tests/browser/*.spec.mjs"` 全绿（**29 passed / 0 fail**，
      基线 26 + 本单 3；81.9s）。
- [x] 修复后复跑现场探针 `.scratch/launcher-exit-race/probe-00-order.mjs`（同参数）：
      从"第 4 轮命中"变成"**10/10 全程活着**"（`probe-00-order-after.txt`）。
- [x] 未顺手做：不重议夹具"不设 `FIRSTEP_LAUNCHER`"的决策；不给其它 spec 开启动器模式；
      不碰 `launch-*.bat` / `launcher-stale.py`。

## Comments

### 2026-09-21 实现记录

#### ① 落点与四处取舍（都是量出来的，不是猜的）

1. **`launcher` 只给这一条 spec**：夹具默认仍**不设** `FIRSTEP_LAUNCHER`（服务生命周期归夹具
   ——那条决策与竞态无关）；本 spec 要的正是产品侧的自动退出行为。
2. **用例 C 用"真导航离开"而不是 `page.close()`**：`probe-02-close-page.mjs` 量了三条收尾路径
   （`probe-02-close-page.txt`）——`page.close()` 与 `page.close({runBeforeUnload:true})`
   **服务端一条 `bye` 都收不到**（playwright 走 CDP 关目标，卸载流程与信标都不跑），只有
   `goto("about:blank")`（真导航）信标正常到达。"最后一个页面离开"与真实关窗口共用同一条
   `pagehide` + `sendBeacon` 路径，是夹具能造出来的最接近形态；真关窗口那一跳由浏览器自己
   保证（`sendBeacon` 的设计用途），夹具证不了——如实记账。
3. **`reload` 之后先确认"看到的是新文档"**：`page.reload({waitUntil:"domcontentloaded"})` 返回时
   平台卡还是 **0 个**（要再等一次 ready，`probe-03-timeorigin.txt`），而"读到上一个文档的 DOM"
   会让用例抢跑——本机实测把正在装载的模块图拦腰掐断（服务端日志：那一轮只取到 `boot.js` +
   两个模块就没了下一次 `GET /`），下一轮 `DOMContentLoaded` 永远等不来（30s 超时），看着像
   "产品把自己关了"（先例：`hwcheck.spec.mjs` 记过同族抢跑假红）。判据用 `performance.timeOrigin`
   （跨 reload 必不同，同份探针实测），它与产品的 `epoch` 同源。
4. **夹具加 `PYTHONUNBUFFERED=1`**：服务被自己关掉时，uvicorn 的 access log 若压在块缓冲里就
   随进程一起没了——而那正是这套日志最要被读到的时候（实测只收到 8 行、零请求，失败信息里的
   `log()` 尾段是空的）。这条同时让"失败时打印服务端日志尾段"这个既有能力真正可用。

#### ② 读数（最终状态上）

| 项 | 读数 |
|---|---|
| 本 spec 单跑（当前树） | **3 passed / 0 fail / 11.9s**（A 5.2s、B 5.4s、C 1.6s）；复跑两次同绿 |
| 用例 C 实测 | 最后一个页面离开 → 服务自己退出 **1525–1640ms**（宽限 1500ms + 进程退出）——"关浏览器"这条路径的延迟**不变**，用户可接受上限 ≤ 2s |
| 浏览器门禁（五 spec） | **29 passed / 0 fail / 81.9s**（26 ＋ 本单 3） |
| 真红证（`eae57b43` worktree，全文件） | **3 failed**：A 33.0s 超时（服务在 reload 中途自杀）、B `ERR_CONNECTION_REFUSED`（级联）、C"没收到 bye"（服务早已死——强化后的判据当场抓住） |
| 真红证（同 worktree，**只跑 B**） | **1 failed**；服务端日志：`GET /` → `POST /api/tabs/bye` →（**没有 register**）→ `[fixture] 后端进程退出 code=0` = 产品自杀，页面再也回不来 |
| 现场探针 | 修复前 10 轮第 4 轮命中（`-before.txt`）→ 修复后 **10/10 全程活着**（`-after.txt`） |

#### ③ 双轴评审整改（`code-review`：Standards + Spec 并行，只报告不修改）

| 轴的发现 | 处理 |
|---|---|
| **硬**：工单未 claim/resolve、Comments 是占位（评审在改写前读到） | 已改（本文件：状态 + 勾选 + Comments） |
| **最重**：Spec 轴实测"同一命令跑 3 次 = 1 红 2 绿"，红的那次形态与修复前红证同形 ⇒ 全绿这条验收没站稳 | 见下面 ④：① 先在本机复现条件（`pytest -n auto` 全量并行负载 + spec 连跑 3 次 = **3/3 全绿**，A 8.7–13.8s）；② 把"机器慢"与"产品坏"分开：`waitReady` 超时上限 30s → **90s**，且**超时也打印服务端日志尾段**（原来最可能发生的那条红——`ready` 超时——一条服务端日志都看不到） |
| **口径**：`GRACE_MS = 1500` 是 spec 内字面量（产品一改值，用例 B 的前提就假绿） | 已改：**从 `webapp.py` 抠 `_EXIT_GRACE`**（先例：`ui-contract.spec.mjs` 从产品源码抠存储键），抠不到当场失败；`SLOW_MS` 由它推出来 |
| **口径**：用例 C 验的是"导航离开"，不是"关掉页面"（工单原文） | 实测后如实收窄（probe-02 两条 `page.close()` 都收不到 bye）＋ 文件头与 Comments 写明"真关窗口由浏览器保证，夹具证不了"；**不**把用例名写成"关掉页面" |
| **口径**：probe-02 第一版"③ 进程没退"是探针自己的状态没清（①② 不发 bye ⇒ 那两个 tab 还在册，③ 时"最后一个页面"不成立） | 已改：**每轮各起一个干净服务**，重跑读数 = ① 否/否、② 否/否、③ 是/**1638ms 自己退**（`probe-02-close-page.txt` 已重算） |
| 判断：夹具注释"默认不设"≠"保证不设"（`...process.env` 会透传） | 已改（措辞说准 + 点明探针正是靠这条透传进启动器模式） |
| 判断：注释称"只有本 spec 用它"，而 probe-02 也用了 | 已改（"其余 **spec** 一律不设；一次性探针可以自己开"） |
| 判断：`logTail`/`goto+ready` 各抄三遍、`alive()` 与夹具 `healthy()` 同形、`waitForExit` 返回时间戳当布尔、`before` 名不副实 | 已改：`logTail()` / `openApp()` / `exitObservedAt()` 各一处；夹具**导出 `serverAlive`**（用例不再抄第二份）；`logMark` 改名 |
| 判断：`PYTHONUNBUFFERED=1` 对所有 spec 生效、不在验收清单里 | 保留（理由写进 Comments ①.4：服务被自己关掉时日志最要被读到，而它原来正丢在那）；本文件第一条验收已把它写进清单 |
| 判断：用例 C"必须是最后一条"只在注释里 | 保留（node:test 在文件内按声明顺序串行；如实记不强制） |
| 判断：spec 里"读到上一个文档的 DOM"是推断不是读数 | 已改：注释改成两条**实测**事实（`domcontentloaded` ≠ 可用：那一刻平台卡 0 个；以及抢跑把模块图掐断的服务端日志形态），判据**不依赖**对浏览器内部时序的推测 |

#### ④ 极端负载下的残余（如实记账，不粉饰）

- **本机复现条件**：评审那一轮机器上并行 40+ python 进程时，这一支出现过 **1 红 2 绿**（红的那次
  3 条全红、形态与修复前红证逐条同形）。
- **本机可控负载下的复跑**：`python -m pytest -n auto -q` 全量并行负载**同时**跑本 spec，连跑
  **3 次 = 3/3 全绿**（A 8.7s / 13.8s / 8.8s，空闲时 5.2s）。⇒ 未能复现评审看到的形态。
- **残余风险的准确表述**：《宽限是**时限判据**》——浏览器渲染进程或服务端被饿到**超过 1.5 秒**
  仍可能命中自杀路径（修复前是"任何模块图装载 > 1.5 秒"，那是常态；现在要求"重载期间两端任一侧
  被饿 > 1.5 秒"，是极端态）。**没有**再加一层服务端信号来兜：唯一候选"刚服务过文档就不退"在本机
  实测的到达顺序（`GET /` 恒在 `bye` **之前**）下根本挡不住——到点时那个文档请求已经比宽限更旧了；
  再兜就得调宽限（spec 明确否掉了"只调宽限"这条）。要根治得换成"页面活着吗"的另一种机制
  （心跳 / 长轮询），那是另一件事，见 spec「被否掉的候选」。

#### ⑤ 未顺手做（与 spec「范围外」一致）

bfcache 相邻洞（`pageshow` 补登记）、心跳式重设计、`_EXIT_GRACE` 数值调整、启动器 `.bat` /
`launcher-stale.py` 一侧的改动、C6 / C7 / 墓碑注释清理。

#### ⑥ 收尾复跑的三条命令（原件读数）

```powershell
node --test --test-concurrency=1 tests/browser/launcher-reload.spec.mjs   # 3 passed / 0 fail
node --test --test-concurrency=1 "tests/browser/*.spec.mjs"              # 29 passed / 0 fail / 81.9s
node .scratch/launcher-exit-race/probe-00-order.mjs --rounds 10          # 10/10 全程活着（-after.txt）
```
