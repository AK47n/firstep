# 01 — 早注册：head 内联脚本在模块图之前报到

**要做什么：** 把"新页面自报家门"这件事从"132 个模块装载完（`app.js` 求值）"提前到
`index.html` head 的第一段脚本 —— **在装载标签之前**。修完这一张，F5 时新页面的
`POST /api/tabs/register` 在毫秒级到达（不再吃模块图那条 0.4–1.5s⁺ 的尾长），
并且这件事有**结构判据**钉住（含合成红证 + 真红证），下一轮谁把它挪走都推不上去。

**被谁阻塞：** 无——可立即开始。

**状态：** resolved

## 验收标准

- [x] `src/contest_generator/static/index.html` head 那段**已有的**内联脚本里，在主题防闪烁
      之后新增标签登记：读 / 建 `sessionStorage` 里的 tab_id（**与 `app.js` 同一个键**）→
      `POST /api/tabs/register`（fire-and-forget）→ 整段包 `try/catch`。
      **不新增脚本块**；内联脚本里**零顶层定义**（判据①②）、**零 import**（判据①）。
- [x] `src/contest_generator/static/js/app.js` 的标签会话块改为**只留注销一半**：
      读同一个 tab_id（保留"取不到就新建"兜底）+ `pagehide` 时照旧 `sendBeacon("/api/tabs/bye")`；
      **删掉那一处 `fetch("/api/tabs/register")`**（登记点单源 = head 内联脚本）。
- [x] 两处 payload 都带上文档实例令牌 `epoch: performance.timeOrigin`（**客户端那一半**——
      双轴评审指出这原写在 02 的清单里：它就在同一段代码里，拆成两张工单反而要改两遍同一行；
      **服务端的比对语义仍归 02**，见 Comments ①）。
- [x] `tests/js/boot-contract.mjs` 新增**判据⑥「早注册」**（纯函数，源码文本进 / 违规清单出），
      四条子判据：①内联脚本里**真有** register 调用（端点字面量拿原文匹配 + "标识符在掩码
      文本里还在"当锚点 ⇒ 注释里的不算）；②它在**装载标签之前**（字符偏移比较）；③两侧的
      `sessionStorage` 键**同源**；④两处 payload 都带 `epoch`（判在**该次调用的实参区间**里）。
- [x] 新守卫 `tests/js/tab-register-guard.test.mjs`（进前端门禁）：取数面体检 + **正向对照**
      （注入必须报出）+ 真源码判据为 0 + **合成红证**逐条：删登记 / 只把登记写进注释 /
      挪到装载标签之后 / 改内联脚本的键名 / 改 `app.js` 的键名 / 去掉 `epoch` /
      `epoch` 只出现在**别处**的同名字段里（假绿反例）—— 每条注入
      **自带自检**（断言注入真的落上了，防"静默空转"）。
- [x] **真红证** `.scratch/launcher-exit-race/probe-01-red-proof.mjs`（→ `red-proof.txt`）：
      `--base` **显式钉 `eae57b43`**（修复前那个提交，**绝不写 HEAD**）+ **base 自校验**
      （base 的内联脚本里没有 register、`app.js` 里有 register；不成立就大声失败、不许产出假绿）
      + base 上判据⑥必红 + 当前工作树必绿 + 判据非真空自检（内存注入）。
- [x] `node --test "tests/js/*.test.mjs"` 全绿（**1702 passed / 0 fail**，基线 1691 + 本单 11 条）。
- [x] 未顺手做（与 spec「范围外」一致）：不碰 C6 / C7 / 墓碑注释；不动 `_EXIT_GRACE`；
      不改夹具"不设 `FIRSTEP_LAUNCHER`"的决策。

## Comments

### 2026-09-21 实现记录

#### ① 落点与取舍

- **早注册放 head 那段已有的内联脚本**（零新增脚本块）。三条被否的路写进 spec「被否掉的候选」；
  这里只补一条实测性质的理由：**ESM 静态 import 会把整张图取完才开始求值**，所以写在
  `boot.js` 正文第一行也救不了（它仍在 132 个模块全部取完之后）。
- **`epoch` 的客户端一半落在本单**（双轴评审抓出清单与代码不一致）：它就是同一个
  `JSON.stringify` 里的一个字段，拆去 02 意味着同一行要改两遍；**服务端的比对语义**（本单
  不做）在 02。两处 payload 的**形状**由判据⑥ 的第 ④ 条子判据钉住，语义由 02 的 pytest 钉住。
- **判据 ④ 判"该次调用的实参区间"**（评审实测的假绿：第一时间写的是"调用点之后 400 字符
  窗口"，紧跟调用的一句 `window.x = { epoch: 1 }` 就能把它喂绿）。现在在**掩码文本**上数
  圆括号找配对（字符串/注释/正则内容已掩成空格，括号不会捣乱），区间外的一律不算——
  守卫里那条 `__probeDecoy` 反例钉住它，且**不再有窗口魔数**。

#### ② 双轴评审整改（`code-review`：Standards + Spec 并行，只报告不修改）

| 轴的发现 | 处理 |
|---|---|
| **硬**：`boot-contract.mjs` 头部仍写"五类不变量"、消费者清单没加新守卫/红证 | 已改（头部改「六类」+ 列 ⑥ + 补两个红证脚本） |
| **硬**：越过工单边界（epoch 客户端一半在本单，而工单写"由 02 补"），且注释声称的"服务端忽略旧告别"当时**不存在** | 两向都修：清单改口径（见 ①）+ **02 的服务端语义当场落地**（本单提交前） |
| **硬（最严重）**：`index.html` / `app.js` 引"连跑第 4 次 reload 命中"，而盘上的 `probe-00-order.txt` 已被修复后的复跑**覆盖成全绿**——红侧证据在树内对不上 | 证据拆成两份并各自重跑：`probe-00-order-before.txt`（base worktree `eae57b43`，**第 4 轮命中**）/ `probe-00-order-after.txt`（当前树，**10/10 全程活着**）；注释与 spec 都点名是哪一份 |
| 判断：判据 ④ 太松（`/\bepoch\s*:/` anywhere 即可喂绿） | 已改（见 ① 第三条） |
| 判断：⑥ 头写"判在掩码文本上"与实现（原文匹配 + 掩码锚点）不符 | 已改（头的四条子判据逐条写明"原文匹配 + 标识符锚点"的理由） |
| 判断：`probe-01` 的 `earlyRegisterSummary` 重算偏移、又手抄 fx-guard ③ | 保留读取数（打印"登记偏移 < 装载标签偏移"要给人看），但**写明它不是第二条判据**，并删掉手抄的"脚本块恰好两处"措辞 |
| 判断：死代码（`probe-00` 的 `sleep` / `died`、`hasField` 改完后无人用） | 已删 |
| 判断：`tab-register-guard` 硬编码键名当注入锚点 | 已改（锚点从真源码里抠：`sessionStorageKeys(inlineBlock.text)`，抠不到就大声失败） |
| 判断：`index.html` 同一个键读两次 | 保留并**写明原因**（判据②禁止本段有顶层定义 ⇒ 没有局部变量可存） |
| 判断：`tee.mjs` 与 `.scratch/frontend-boot-module/tee.mjs` 重复 | 保留（一次性证据助手 / 20 行；探针要能独立跑，不跨 feature 目录互相 import） |

#### ③ 读数（最终状态上）

| 项 | 读数 |
|---|---|
| `node --test "tests/js/*.test.mjs"` | **1702 passed / 0 fail**（基线 1691 ＋ 本单 11 条；5.2s） |
| `probe-01-red-proof.mjs` | exit 0：base 上必红（判据⑥ 报 3 条，其中"内联脚本里没有 register 调用"是 ① 的直接结论）／当前树 0 条／非真空自检报出 |
| `probe-00-order-before.txt`（base worktree） | **第 4 轮命中**（服务 exit 0、`page.reload` 抛 `ERR_CONNECTION_REFUSED`），跑完 4/10 |
| `probe-00-order-after.txt`（当前树） | **10 / 10 全程活着**（逐轮 `GET /` → `bye` → `register`，reload → 页面可用 539–884ms） |
| 浏览器门禁 | **26 passed / 0 fail**（96.7s，改动落在 `static/` ⇒ 必跑） |
