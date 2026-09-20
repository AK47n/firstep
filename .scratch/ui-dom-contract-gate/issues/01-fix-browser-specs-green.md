# 01 — 浏览器用例先修绿（夹具不再自杀 + 两条用例自身缺陷 + 一条过期断言）

**要做什么：** 在 HEAD 上跑 `node --test tests/browser/{module-intro,code-tree-click,hwcheck}.spec.mjs`
时，**21 条**用例在一个进程里连跑**全绿且可重复**（`module-intro` 9 + `code-tree-click` 2 +
`hwcheck` 10；评审原文说的「18 个」与实测不符，见 spec 的来源注）。今天实测 14 绿 7 红，
其中 4 条红是夹具让服务中途自杀造成的连锁假红、3 条真红**全部不是产品缺陷**
（一条断言过期、一条抢跑、一条用例间状态污染），另有一条样本器件已被配方覆盖。
端到端行为：谁都可以用一条命令把这 21 个已写好的浏览器用例跑一遍，并且结果就是真实结论。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

- [x] `tests/browser/server.mjs` 起服务时**不再设 `FIRSTEP_LAUNCHER=1`**（保留 `FIRSTEP_LAUNCHER_PORT`）：
      夹具自己 `stop()` 收服务，产品侧的「关浏览器 = 停服务」在验收里只会制造假红。
      「常开 tab 占位」的 `holdTab()` 及其注释一并退场（它守的那件事随这个开关一起消失）。
      文件头把**为什么不再设它**写清楚（防下一个人"顺手补回去"）。
      **端口同时改为每个 spec 各向内核要一个空闲端口**（原固定 8791）——固定端口在
      「三个 spec 顺序跑」下必然自踩（下一个 bind 失败、端口上的旧服务却照样答健康检查）。
- [x] 三个 spec 连跑，**不再出现 `ERR_CONNECTION_REFUSED`**；`ℹ fail 0`。
- [x] `module-intro.spec.mjs`「需求清单灰注 + 已选清单行」：断言 `#selected-list [data-mod-info]`
      之前先**等它渲染出来**（`waitForFunction`），不再靠"机器慢"兜。判据 = 该 spec 文件单跑
      连绿 5 次 + 与另两个 spec 连跑仍绿。
- [x] `hwcheck.spec.mjs`「选上 MPU6050…」：把「等 `#hwcheck-conflicts` 里出现 PA22」改成断言
      **新的正确行为**——默认脚撞脚在生成前已被求解器解开，页面上如实显示：
      ① 冲突区明说"没有两件模块抢同一个引脚"；② 接线表里 `oled·OLED_SPI_RES` 的脚 = **PA2**
      （原 PA22）且带"已自动移开"的提示；③ `debug_uart·DEBUG_UART_RX` 仍在 PA22。
      断言点在**产品真输出**上，不是在测试自己算出来的期望上。
- [x] `hwcheck.spec.mjs` 各条**自清**：用例跑完（含中途失败）都把这一条选上的器件去掉，
      下一条从干净器件集开始。判据 = 故意让「选上 MPU6050」那条红一次，**后面的用例仍必须全绿**。
- [x] 三个 spec 连跑两轮，两轮都 `ℹ pass 21 / ℹ fail 0`（可重复性，不是撞运气）。
- [x] **零产品改动**：本工单只动 `tests/browser/`。
- [x] 证据（两轮读数 + 红证）留 `## Comments`；提交信息中文。

## Comments

### 一、实测基线（不是文档记的 6 绿 3 红）

在 HEAD（`9b5d69b0`）上 `node --test tests/browser/{module-intro,code-tree-click,hwcheck}.spec.mjs`
= **14 绿 7 红**（21 条）。7 条红分两类：

| 类 | 条数 | 现象 |
|---|---|---|
| **真红** | 3 | `hwcheck`「选上 MPU6050」30s 超时、`hwcheck`「专精小节」30s 超时、`module-intro`「已选清单行缺说明入口」 |
| 连锁假红 | 4 | 服务中途死掉 → 后面 4 条 `ERR_CONNECTION_REFUSED` |

### 二、根因（三条真红，**都不是产品缺陷**；另有一条是夹具的端口策略）

1. **夹具的固定端口 + 服务自杀**（最大的那条）。`server.mjs` 原先设 `FIRSTEP_LAUNCHER=1`
   并把端口固定为 8791。设了那个开关，前端每次 `page.goto` 的 `pagehide →
   POST /api/tabs/bye` 会让服务在 1.5s 宽限后 `os._exit`；而"常开 tab 占位"那个补丁只在
   该 tab_id 留在注册表里时成立。本轮抓到更狠的一条：**三个 spec 连跑时，上一个 spec 的
   `after` 收完服务、下一个的 `before` 立刻起新服务，而 `taskkill` 返回 ≠ 端口已释放** →
   新后端 bind 失败（`[Errno 10048]`，exit 3），**端口上那个还没死透的旧服务照样答健康检查
   与端点哨兵**（同一份代码）→ 夹具"起服务成功"、测试跑在不属于自己的服务上，等旧服务咽气
   就满屏 `ERR_CONNECTION_REFUSED`。服务日志实锤：

   ```
   INFO:     Started server process [57448]      ← spec 1 的服务，起来了
   INFO:     Started server process [64380]      ← spec 2 起的，随后 bind 失败
   ERROR:    [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8791)
   INFO:     Started server process [66192]      ← spec 3 起的，同样失败
   ERROR:    [Errno 10048] ...
   [fixture] 后端进程退出 code=3 / code=3 / code=1
   ```

2. **`hwcheck`「选上 MPU6050」的断言过期**：`hwcheck-pin-conflict-exit/01` 之后，检测页
   在生成前跑与赛题页「自动配置」同一个求解器，把默认脚撞脚解开（`OLED_SPI_RES`
   PA22 → PA2），页面上如实显示「✓ 没有两件模块抢同一个引脚」+「生成前自动移开了 2 处默认脚冲突」。
   用例还在等那个已经不存在的冲突。探针实测：`#hwcheck-conflicts` 的 `hasPA22 = false`。
3. **`module-intro` 抢跑**：`#selected-list` 由推荐收尾的异步渲染写入，用例只等了 chip 可见。
   单独跑该 spec 文件 **9/9 全绿**，与另两个 spec 连跑才红 —— 典型的抢跑。
4. **`hwcheck`「专精小节」样本被配方覆盖（第四条，本轮才挖出来）**：样本器件 `beep` 从工单
   `module-hwcheck/09`（扩齐 pilot 配方）起已经有 stm32 配方了，于是"未专精件"那条断言
   （`.hwcheck-generic`）永远等不到 —— **在 HEAD 上就是假红**。换样本为 `photoresistance`
   （stm32 有条目、库内无配方；探针实测专精小节 0 / 通用小节 1），并把"换样本的判据"写进注释。

### 三、改法

| 文件 | 改什么 |
|---|---|
| `tests/browser/server.mjs` | ① 不再设 `FIRSTEP_LAUNCHER`（夹具自己收服务；`holdTab` 退场）；② 端口改成**每个 spec 各向内核要一个空闲端口**（`freePort()`，`requestedPort` 可指定）——固定端口在"三个 spec 顺序跑"下必然自踩；③ `startServer` 的循环里新增**「我起的进程还活着吗」**判据（端口上答话的可能是旧服务）；④ `stopServer` 等到端口真的没有 LISTEN 才返回，收不干净就收掉它；⑤ 新增可选的 `FIRSTEP_BROWSER_SERVER_LOG=<路径>` 把后端 stdout/stderr 边跑边落盘（排查用，不设零影响） |
| `tests/browser/hwcheck.spec.mjs` | ① 过期断言改成断言新行为（冲突已被解开 + 移线如实写在表上）；② 新增 `clearDevices()` + `test.afterEach`（用例级隔离，红了也清）；③「未专精」样本 `beep` → `photoresistance`，并写清换样本判据 |
| `tests/browser/module-intro.spec.mjs` | 断言已选清单前先等它渲染出来 |

### 四、读数

| 轮次 | 结果 | 耗时 |
|---|---|---|
| 修前基线（HEAD） | **14 pass / 7 fail** | 50.8s |
| 修后 第 1 轮 | **21 pass / 0 fail** | 31.3s |
| 修后 第 2 轮 | **21 pass / 0 fail** | 31.5s |
| 修后 第 3 轮（复原红证注入后复跑） | **21 pass / 0 fail** | 36.2s |

跑完残留检查：**无残留 python 进程**；8791 / 8000 都 free。

### 五、红证（`afterEach` 真的在防连锁假红）

把 `test.afterEach` 的清理停用、同时把「选上 MPU6050」的断言换成必定超时的一句
（`includes("这段文字不存在REDPROOF")`），跑 `hwcheck.spec.mjs`：

```
✖ 选上 MPU6050：…（32004.9181ms）      ← 注入的那条，如实红
✔ 本平台没有条目的器件：…
✔ 专精小节：选上 led …
✔ MPU6050 专精小节：…
✔ 同组互斥 = 单选交换：…
✔ 串口命令台：…
ℹ tests 10   ℹ pass 9   ℹ fail 1
```

**一条红就只红一条**——这正是不用 `afterEach` 时做不到的事（基线里那条超时把后面几条一起
拖红）。两处注入随后**逐字节复原**（`Select-String 'REDPROOF|停用'` 为空）。

### 六、工具事实（留给后来的人）

- 端口策略那条改动是必须的：`--test-concurrency=1` 只约束**单个文件内部**的用例并发，
  **文件之间仍会并行**（Node 24 实测），所以"三个 spec 抢一个固定端口"是真的会撞。
- 排查手段：`FIRSTEP_BROWSER_SERVER_LOG=%TEMP%\br-server.log` 跑一轮，就能看到
  `Started server process` / `[Errno 10048]` / `[fixture] 后端进程退出 code=…` 三行连起来
  的自杀链。**服务死掉时 `server.log()` 往往已经拿不到了**（异常先抛出来了），落盘才查得动。

### 八、code-review 双轴评审后的整改

**Standards 轴**（判据 = `CLAUDE.md` / `docs/agents/workflow.md` / `docs/agents/issue-tracker.md`
+ Fowler 第 3 章坏味道基线）：

| 发现 | 处理 |
|---|---|
| **端口事实换了、台账没当场改**（`CLAUDE.md` 明写"改了就当场回去改 `local-environment.md`"，而它还写着"固定 8791"、还教人"验收前先清 8791"） | **已改**：`local-environment.md` 第 2 节补那条 ✅（端口策略、三道判据、`FIRSTEP_LAUNCHER` 为什么不能再设），并在「验收前先清 8791」那条后面标注它已被夹具兜住 |
| **用例基数写错**：spec / 工单写「18 个」，实测是 **21**（9+2+10） | **已改**：spec 开头加「用例基数更正」注（并说明评审原文的 18 是怎么来的），工单标题与正文改 21 |
| `TEST_PORT = 8791` 的保留理由不成立（全仓零引用） | **已删**（连同"兼容探针脚本"的注释） |
| `stopServer` / `startServer` 用**模块级 `currentPort`** 双持有端口状态；同时起两个服务时第二个 `stop()` 的端口释放整段被跳过 | **已改**：端口改成入参（`stopServer(proc, port)`），闭包里捕获自己的端口；模块级状态删掉 |
| `freePort` 与 `spawnServer` 各做一遍端口占用诊断；`attempts = requestedPort ? 1 : 3` 让"重试兜住抢占窗口"在 `requestedPort` 路径失真 | **已改**：拆成 `startServer`（内核分配，重试三次）+ `spawnOn(port, opts.reclaim)`（钉死端口：先收残留、收不掉大声失败，**不静默换端口**） |
| `hwcheck.spec.mjs` 里"移除某 chip"三套写法并存 | **已澄清**：`afterEach` 的注释改成"**收尾兜底**"（只防中途失败），并说明正常路径由用例自己清——原来那句"件集由 afterEach 统一清"是错的 |
| `UNSPECIALIZED` 这名字没说出判据 | **已改名** `NO_RECIPE_DEVICE`（判据 = 该平台无配方，写在注释里也在名字里） |
| 来源指向 `%TEMP%` 的评审报告（会被清理，判据源不可复现） | **已改**：报告副本随本条入库 `.scratch/ui-dom-contract-gate/architecture-review-20260920-1745.html`，spec 里注明 |

**Spec 轴**（对账工单的 8 条验收项）：

| 发现 | 处理 |
|---|---|
| **断言偏松**：`wiring.includes("PA2")` —— `"PA24"` 里也含 `"PA2"`，脚漂到 PA24/PA20 照样绿 | **已改**：改成按**接线表的 DOM 契约**钉那一格——模块格 `.slug` = `oled`、角色格 = `OLED_SPI_RES` 的那一行，它的引脚格必须**等于** `PA2`（`allInnerTexts()[2] === "PA2"`）。改完第一次跑就**真的红了**（我第一版用 `innerText` 切 tab 拿到了整块文本，等于没钉住）——这正是评审说的那种松断言，实测有效 |
| **自清理由与实现不符**：注释说"由清空 → 落盘保证"，实际 `clearDevices` 不落盘 | **已改注释说实话**：真正让下一条从干净集开始的是**下一条 `openTab()` 的整页重载 + 服务端回读**（落盘由产品的防抖异步完成）；`afterEach` 只要"点掉"这一步发出去 |
| **缺一轮干净的第三轮读数**（原来第三轮是"复原注入后复跑"，不算干净） | **已补**：整改后干净复跑 21 pass / 0 fail / 35.8s（见下） |
| `afterEach` 吞异常应 rethrow | **保留并说明**：用例已经红着的时候，afterEach 再抛会把原始失败盖成"清场失败"。兜底清理不掩盖真红——打印一行，注释里写明 |
| **范围蔓延**：`local-environment.md` 有 24 行改动 | **已核实并拆分**：其中**9 行是别人（PDF 去重会话）的未提交改动**（`+15/-0` 是我的、`+9/-0` 是那批）——提交时只提交我那一段，PDF 那段留在工作树里不碰 |
| `portListening()` 用 `includes(":port ")` 会漏判 IPv6 行（`[::]:8791` 行尾无空格） | **已改**：改成 `new RegExp(":port(?![0-9])")` + 行内含 `LISTEN`。**改的过程里自检又抓到我自己写错的一版**（取"第一列"当本地地址——netstat 第一列是协议 `TCP`，那样会**恒判空闲**，等于把"收服务时等端口释放"整段废掉）——自检脚本 `probe-port-listening.mjs` 留档 |
| `freePort()` 只有 3 次重试、无 bind 后校验 | **保留并说明**：`freePort` 在 close 回调里才 resolve（窗口已收窄），抢输由 `startServer` 的三次重试兜住；实测 10+ 轮未复现 |

**两条经核实不成立**（如实记下，避免下次重复排查）：

- 评审说 `deep-audit.mjs` / `gen-chain-audit.mjs` / 两支 `repro-*.mjs` "起服务后从不收、
  删掉 `FIRSTEP_LAUNCHER=1` 后会留孤儿 python"：实测这 4 支**都**调了 `await server.stop()`
  （`deep-audit.mjs:646`、`gen-chain-audit.mjs:1062`、`repro-overwrite-confirm.mjs:88`、
  `repro-tree-click.mjs:98`）——它们的清理本来就不依赖产品自杀。
- Spec 轴说"台账一个字没提端口策略已变"：是它读的**快照**早于我的改动（同一轮里已改）。

### 九、整改后复跑（干净读数）

| 轮次 | 结果 | 耗时 |
|---|---|---|
| 修前基线（HEAD） | 14 pass / 7 fail | 50.8s |
| 01 修后 第 1 轮 | 21 pass / 0 fail | 31.3s |
| 01 修后 第 2 轮 | 21 pass / 0 fail | 31.5s |
| 红证轮（停用 afterEach + 注入必超时断言） | **9 pass / 1 fail**（一条红只红一条） | — |
| 双轴评审整改后（干净第 3 轮） | **21 pass / 0 fail** | 43.2s |
| 断言收紧 + `portListening` 修好后（干净第 4 轮） | **21 pass / 0 fail** | 35.8s |

`python -m pytest -n auto` **5024 passed + 1 skipped**（105.99s）；每轮跑完都实测**无残留 python**。

### 十、附带产出的排查工具（留在本条目录里）

| 工具 | 干什么 |
|---|---|
| `probe-port-listening.mjs` | 夹具自检：起一个真监听 → 必须判"有监听"，相邻端口 → "空闲"，关掉 → "空闲"。它抓出过两版 `portListening` 的错法（见上表） |
| `probe-compile-hang.mjs` | 复刻"生成检测工程 → 真 UV4 编译"，抓编译请求/响应与健康检查——排查服务中途死掉时用 |
| `probe-id-coverage.mjs` | 静态盘点 ui 引用的 id 与声明集合的差集（工单 02 的判据就是它的产品化） |
