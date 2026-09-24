# 01 — bfcache 后退回来补登记：同标签导航走再后退，不再看到死页面

**要做什么：** 启动器模式（双击 `start-app.vbs`）下，同一个标签页导航离开应用再**按后退回来**时，
页面与服务都还活着——bfcache 恢复的文档自己补一次登记（撤销在途退出）；若回来时服务确实已经退出
（离开超过宽限窗口），页面给出中文说明与重启指引，而不是一片所有请求都连不上的死页面。

**被谁阻塞：** 无——可立即开始（前置 `launcher-exit-race/01-05` 已 resolved；本单是它账本
「未顺手做」段记下的**相邻洞①**，当时只记账没立单）。

**状态：** ready-for-agent

- [ ] **红证先做**：真 Chrome + CDP（`.scratch/cdp-harness.mjs`）在启动器模式夹具上复现——
      同标签导航到站外页 → 后退 → 观测到服务已退出 / 页面请求全失败。读数落 `.scratch/bfcache-return-register/`
      （含 `launcher.log` 的退出行、页面请求失败证据、探针前后对读）。
- [ ] **恢复时补登记**：`pageshow` 且 `event.persisted === true` 时，用**同一个 `tab_id` + 同一个 `epoch`**
      再发一次登记；宽限内回来 → 在途退出被撤销。**服务端零改动**（`register()` 的「登记即撤防」语义已够）。
- [ ] **真机轮数**：连续 N 次「导航走 → 后退回来」服务始终活着、页面可用（N 与读数照
      `launcher-exit-race` 现场探针的先例：修复前/后对读，而不是只跑一次）。
- [ ] **晚回来的可见态**：页内中文提示「服务已停止（应用已随最后一个页面关闭），请双击 start-app.vbs 重新启动」
      + 至多**一次**自动重试，**不自动无限刷新**；验证方式 = 真机把后退推迟到宽限之后。
- [ ] **判据三处**（走既有缝，不新造一套）：① 结构判据 `tests/js/tab-register-guard.test.mjs` 同族补两条腿
      （恢复时补登记 / 令牌同源），含「端点字样只出现在注释里」这类假绿反例；② `tests/js/boot-contract.mjs`
      的登记↔注销同源判据相邻补口；③ 真浏览器 `tests/browser/launcher-reload.spec.mjs` 加一条
      （启动器模式夹具上：导航走 → 后退 → 服务仍在），并**如实记账 headless 到底走不走 bfcache**。
- [ ] **不动的三件**：`_EXIT_GRACE` 数值（`launcher-exit-race` 明定保持 1.5s）、心跳/长轮询式存活重设计、
      服务端 `TabRegistry` 语义（必要时只补一条「同一 epoch 重登记」用例，不改行为）。

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
- **回来时没人补登记**：文档从 bfcache 恢复**不执行任何脚本**（`static/index.html:24-33` 的内联登记不重跑，
  `boot.js` / `app.js` 也不重跑），而全仓**没有 `pageshow` 监听**（`grep pageshow` 只命中注释与历史工单）
  ⇒ 注册表仍空 ⇒ 到点退出；**晚于 1.5 秒回来时服务已经退出了**。
- **用户看到什么**：页面还在浏览器内存里活着，但 `fetch` 全 `ERR_CONNECTION_REFUSED` = 死页面，
  只能重新双击启动器。

### 未复现（如实记）

本轮**没有真机复现**，上面全是代码事实取证。红证配方 = 启动器模式起服务（先例：
`tests/browser/launcher-reload.spec.mjs` 的夹具）→ 真 Chrome 打开 → 同标签导航到站外页 → 后退 →
看 `%USERPROFILE%\.contest_generator\launcher.log` 的退出行与页面请求失败。
**注意**：headless 与真 Chrome 的 bfcache 行为可能不同（`launcher-exit-race/05` ② 已记「浏览器门禁
模拟不了真关窗口」），所以红证优先真 Chrome + CDP，并把 headless 那一侧如实记账、不拿它当判据。

### 两条候选修法与取舍

- **A —— `pagehide` 里 `persisted === true` 就不发 bye**（"bfcache 里的页面仍算开着"）。
  **单独用不成立**：用户导航走了不再回来、之后关标签时，被冻结的文档**不会再发 `pagehide`**
  （bfcache 逐出没有对应事件）⇒ 告别永久丢失、服务不再自停——违反「关最后一个页面 = 停服」，
  还留下一个没人管的常驻进程。
- **B —— 保留 bye，补 `pageshow` 补登记（推荐）**：`persisted === true` 时用同一个 `tab_id` + `epoch`
  重登记。epoch = `performance.timeOrigin` 是**每文档**的值，bfcache 恢复的是同一个文档 ⇒ 令牌天然不变，
  与注册表里记的能对上（`register()` 覆盖同键并撤防）。宽限内回来 ⇒ 退出作废；晚于宽限 ⇒ 服务已退出、
  补登记必然失败 ⇒ 靠上面验收第 4 条那层可见态兜底。

### 与已记边界的关系（别混读）

`launcher-exit-race` 账本那条洞写的是「**1.5 秒内**后退回来会看到死页面」；本单把它拆成两个形态：
**① 宽限内回来**——补登记就能救（验收第 2/3 条）；**② 晚于宽限回来**——服务已经退出，任何补登记都救不回来，
只能给可见态（验收第 4 条）。两条都要，别只做一条就翻牌。
