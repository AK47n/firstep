// launcher-reload.spec.mjs — 启动器模式下的 F5 竞态验收（工单 launcher-exit-race/04）。
//
// ## 为什么要这一条（它是本单最有说服力的一层）
//
// 这条竞态**就是真浏览器发现的**（docs/agents/local-environment.md 的现场：浏览器验收连跑
// 第 7 次 `goto` 时命中），所以验收也要按它被发现的方式做：**真 Chromium + 真后端 +
// 开启动器模式**（`FIRSTEP_LAUNCHER=1`，用户双击 `start-app.vbs` 的那条路）。
//
// 修前链路：`pagehide` 先发 `POST /api/tabs/bye` → 注册表空 → 服务端起 1.5 秒宽限
// （`webapp._EXIT_GRACE`）→ 新页面的 `POST /api/tabs/register` 要等 `index.html` +
// `boot.js` 整张模块图装载完才发（住在 `app.js` 里）→ 宽限内没到 → `os._exit(0)`
// → **应用把自己的服务关了**，后面每次请求都是 `ERR_CONNECTION_REFUSED`。
//
// ## 五条用例（各自钉一件事）
//
//   A. **连续 reload N ≥ 8**（覆盖现场"第 7 次命中"的量级）：服务始终活着 + 页面每次都能用。
//   B. **确定性用例**：把 `boot.js` 的响应拖到宽限之外（2s > 1.5s）—— 修复前 `register` 要等
//      它 ⇒ 服务自杀（**必红**）；修复后登记住在 `index.html` head 的内联脚本里，与模块图
//      无关 ⇒ 服务活着、页面最终仍装载可用。
//   C. **最后一个页面离开 → 服务自己停**：把"关浏览器 = 停服务"这个功能钉进闸门
//      ——修竞态最容易顺手弄丢的就是它。（必须是**最后一条**：它把服务关掉。）
//   D. **bfcache 回来补登记**（工单 bfcache-return-register/01）：冻结再恢复那一跳要补登记，
//      宽限过去后服务还活着、页面还能拿到数据。
//   E. **回来时服务已退出 → 可见态 + 自动接回**：中文说明与下一步要出现，服务回来（同一端口
//      重新起）后页面自己接回去。
//
// ## 一条实测出来的写法约束（别改成 `page.close()`）
//
// `.scratch/launcher-exit-race/probe-02-close-page.mjs` 量过三条收尾路径（`probe-02-close-page.txt`）：
//   · `page.close()` 与 `page.close({runBeforeUnload:true})` —— **服务端根本收不到
//     `POST /api/tabs/bye`**（playwright 走 CDP 关目标，渲染进程被直接拆掉，卸载流程与信标
//     都没跑）⇒ 拿它当"关标签"的替身只会得到一条永远红的用例；
//   · `page.goto("about:blank")`（**真导航离开**）—— 信标正常到达 ✓。
// 所以用例 C 用"导航离开"验"最后一个页面走了 = 停服务"这条**产品不变量**：它与真实关窗口
// 共用同一条 `pagehide` + `sendBeacon` 路径（`sendBeacon` 的设计用途正是在页面被关闭时也
// 把信标发出去——真实关窗口那一步由浏览器自己保证，夹具模拟不了，如实记账）。
//
// ## 运行
//
//     node --test --test-concurrency=1 tests/browser/launcher-reload.spec.mjs
//     （与其余 spec 一起：node --test --test-concurrency=1 "tests/browser/*.spec.mjs"）
//
// 依赖：`npm install` + `npx playwright install chromium`。零 LLM、零编译。
//
// ⚠ 只有本 spec 用 `startServer({ launcher: true })`：其余 **spec** 一律不设 `FIRSTEP_LAUNCHER`
// （服务生命周期归夹具；理由写在 `server.mjs` 头里）。本 spec 自己起、自己收。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { serverAlive, startServer } from "./server.mjs";

// 现场是"连跑第 7 次 goto 命中"；取 8 轮覆盖它，且留一轮余量。
const ROUNDS = 8;

// ⚠ 宽限**从产品源码里抠**，不手抄（工单 launcher-exit-race/04 评审指出：抄一份 1500 在产品
// 改值以后会让用例 B 静默变假绿——"拖慢超过宽限"这个前提就不成立了）。写法照
// `ui-contract.spec.mjs` 从产品源码抠存储键的先例。
const WEBAPP_PY = fileURLToPath(
  new URL("../../src/contest_generator/webapp.py", import.meta.url));
const graceMatch = /^_EXIT_GRACE\s*=\s*([0-9.]+)/m.exec(readFileSync(WEBAPP_PY, "utf8"));
assert.ok(graceMatch, "webapp.py 里找不到 `_EXIT_GRACE = <数字>`——产品那边改名/改写法了？");
const GRACE_MS = Number(graceMatch[1]) * 1000;
// 拖慢幅度必须**大于服务端宽限**——这条是把"宽限"当成**契约**用：它现在覆盖的只是
// "旧告别 → 新页面自报家门"的到达抖动，不是模块图装载时间。
const SLOW_MS = Math.max(2000, GRACE_MS + 500);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 服务端日志尾段（断言失败时要把它一起打出来：服务被自己关掉时，答案就在这几行里）。
 *  一处实现三处用（评审指出先前后抄了三遍）。 */
function logTail(server, lines = 12) {
  return server.log().split("\n").slice(-lines).join("\n");
}

/**
 * 等"页面可用"（平台卡渲染出来 ⟺ 装载根启动区跑过）。
 *
 * 为什么不用夹具的 `ready()`（30 秒上限）：本 spec 会**故意把模块图拖慢**，也会在重负载机器上
 * 跑（评审实测：并行 40+ 进程时这一支曾红在 ready 超时上，形态与修复前的红证一样，读的人会
 * 以为是产品又坏了）。超时要连**服务端日志尾段**一起抛——不然只剩一句 playwright 超时。
 */
async function waitReady(page, server, timeoutMs = 90000) {
  try {
    await page.waitForFunction(
      () => document.querySelectorAll("#platforms .platform-card").length > 0,
      undefined, { timeout: timeoutMs });
  } catch (e) {
    throw new Error(`等页面可用超时（${timeoutMs}ms）：${e.message}\n`
      + `（服务端日志尾段：\n${logTail(server)}\n）`);
  }
}

/** 把页面开到本应用并等它可用（三条用例各自成立的前提，一处实现）。 */
async function openApp(page, server) {
  await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
  await waitReady(page, server);
}

/** 轮询到 `fn()` 返回真值 → 返回那个值；超时返回 null。
 *  一处实现两处用（评审指出 `waitForLog` 与 `exitObservedAt` 各抄了一遍 deadline 轮询）。 */
async function pollUntil(fn, timeoutMs, every = 100) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await fn();
    if (value) return value;
    await sleep(every);
  }
  return null;
}

/** 等后端进程真的退出 → **观测到退出的时刻**（`Date.now()`）；超时返回 null。
 *  返回时刻而不是布尔：调用方要拿它算"离开 → 停服"用了多久（读数进 Comments）。 */
async function exitObservedAt(server, timeoutMs) {
  return pollUntil(() => (server.proc.exitCode !== null ? Date.now() : null), timeoutMs);
}

/** 本文档实例（`performance.timeOrigin`）：同一文档恒定、跨文档必不同。 */
function documentEpoch(page) {
  return page.evaluate(() => performance.timeOrigin);
}

/**
 * 等**新文档**出现（`performance.timeOrigin` 变了）——`reload` 与"服务回来后自动接回"共用。
 *
 * 判据用 `performance.timeOrigin`（与产品那个 `epoch` 同源）：**只有真换了文档它才会变**，
 * 所以"后面看到的 DOM 属于新文档"这件事是被证过的，不依赖对浏览器内部时序的推测。
 * 为什么需要它，两条**实测**事实：
 *   · `reload({waitUntil:"domcontentloaded"})` 返回 ≠ 页面可用 —— 那一刻平台卡还是 **0 个**
 *     （要再等一次 ready；`probe-03-timeorigin.txt`）；
 *   · 本机跑这一轮时踩到过**抢跑**：reload 之后紧接着的检查若在新文档就绪前通过，下一轮
 *     reload 会把正在装载的模块图拦腰掐断（服务端日志：那一轮只取到 `boot.js` + 两个模块就
 *     没了下一次 `GET /`），再下一轮 `DOMContentLoaded` 永远等不来（30s 超时）——现象与
 *     "产品把自己关了"一模一样（先例：`hwcheck.spec.mjs` 记过同族抢跑假红）。
 * 用例 E 里同一件事还有第二层理由：旧文档的 DOM 里平台卡**本来就在**（它"崩"之前是好的），
 * 拿"平台卡在不在"当重载判据会当场假绿（那一条第一版就是这么红的）。
 */
async function waitNewDocument(page, server, prevEpoch, what = "reload") {
  try {
    await page.waitForFunction(
      (prev) => performance.timeOrigin !== prev, prevEpoch, { timeout: 60000 });
  } catch (e) {
    throw new Error(`${what} 之后没看到新文档：${e.message}\n`
      + `（服务端日志尾段：\n${logTail(server)}\n）`);
  }
}

/** reload 一次，确认看到的是新文档，再等页面可用。 */
async function reloadAndReady(page, server) {
  const prevEpoch = await documentEpoch(page);
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitNewDocument(page, server, prevEpoch, "reload");
  await waitReady(page, server);
}

let server = null;
let browser = null;
let page = null;

test.before(async () => {
  server = await startServer({ launcher: true });     // ← 本 spec 的全部特殊之处
  browser = await chromium.launch();
  page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
});

test.after(async () => {
  if (browser) await browser.close();
  if (server) await server.stop();                    // 进程可能已被产品自己关掉：stop 照样收干净
});

test("A：启动器模式下连续 reload 8 次——服务始终活着、页面每次都能用", async () => {
  await openApp(page, server);
  for (let i = 1; i <= ROUNDS; i++) {
    await reloadAndReady(page, server);                // 每次都必须是**新文档**且真的可用
    assert.ok(await serverAlive(server.url),
      `第 ${i} 次 reload 之后服务没了——F5 竞态复现（服务端日志尾段：\n${logTail(server)}\n）`);
  }
  assert.equal(server.proc.exitCode, null, `跑完 ${ROUNDS} 轮后服务已经退出`);
});

test("B：模块图被拖到宽限之外，登记仍然早到——服务活着且页面最终可用", async () => {
  // 修复前：`register` 住在 `app.js`（要等 `boot.js` 的模块图）⇒ 拖慢 `boot.js` 就是拖慢登记
  // ⇒ 宽限（1.5s）内到不了 ⇒ 服务自杀。修复后：登记在 `index.html` head 的内联脚本里，
  // 与模块图无关 ⇒ 服务活着。
  //
  // 先把页面开到本应用（**每一条用例自己成立**：单跑这一条时页面还是 about:blank，
  // 那条 `reload` 只会重载空白页——本机实测踩到过，红得毫无意义）。
  await openApp(page, server);
  await page.route("**/js/boot.js", async (route) => {
    await sleep(SLOW_MS);
    await route.continue();
  });
  try {
    await reloadAndReady(page, server);                // 页面最终必须可用（慢归慢）
    await sleep(GRACE_MS + 1000);                      // 让整个宽限窗口过去
    assert.ok(await serverAlive(server.url),
      `boot.js 被拖慢 ${SLOW_MS}ms 之后服务没了——登记又回到"等模块图装载"那条路上去了`
      + `（服务端日志尾段：\n${logTail(server)}\n）`);
  } finally {
    await page.unroute("**/js/boot.js");
  }
});

// ## 两条 bfcache 用例（D / E，工单 bfcache-return-register/01）
//
// 用户从应用**导航走**时浏览器可能把本文档冻结进 bfcache：那一下同样触发 `pagehide`
//（`persisted === true`），产品照发告别 ⇒ 服务端开始 1.5 秒倒计时；而按**后退**回来时
// 文档恢复、**脚本一行都不重跑**，只有已经注册过的监听器还会被调用 ⇒ 没补登记就没人救。
//
// **为什么用合成事件而不是真导航 + goBack**：playwright 默认给 chromium 传了
// `--disable-back-forward-cache`（实测 `playwright-core/lib/coreBundle.js:34858`），
// **bfcache 在门禁里根本不会发生** —— 拿 `goto → goBack` 写用例只会得到"整页重载"，
// 看起来是绿的、其实什么都没验（那是假绿，比红更坏）。真 bfcache 的读数与"要不要
// `ignoreDefaultArgs` 才能打开"记在 `.scratch/bfcache-return-register/probe-00-bfcache-red.*`。
// 所以这里用**同一条时序的合成事件**（产品侧监听器、端点、服务端退出调度全是真的）：
//   ① `pagehide(persisted=true)` = 冻结那一下（产品真的会发告别）；
//   ② `pageshow(persisted=true)` = 恢复那一下（脚本不重跑，只有监听器被调用）。
// 两条用例分别钉住"宽限内回来 ⇒ 补登记救回"与"回来太晚 ⇒ 说清楚发生了什么"。

/** 等某段新日志出现（默认 5 秒）。返回是否等到，调用方决定断言。 */
async function waitForLog(server, from, needle, timeoutMs = 5000) {
  return Boolean(await pollUntil(
    () => (server.log().slice(from).includes(needle) ? true : null), timeoutMs));
}

/** 派发一次页面转移事件（`pagehide` / `pageshow`，带 `persisted`）——产品监听器照常被调用。 */
function dispatchTransition(page, type, persisted) {
  return page.evaluate(([t, p]) => window.dispatchEvent(
    new PageTransitionEvent(t, { persisted: p })), [type, persisted]);
}

test("D：文档被冻结（bfcache）后按后退回来——补登记救回服务与页面", async () => {
  await openApp(page, server);
  const logMark = server.log().length;

  // ① 冻结那一下：产品发告别（注册表空 ⇒ 服务端布防退出，宽限 GRACE_MS）。
  await dispatchTransition(page, "pagehide", true);
  assert.ok(await waitForLog(server, logMark, "POST /api/tabs/bye"),
    `合成的 pagehide(persisted) 之后服务端没收到告别——用例没有牙齿（后面红了也说明不了什么）`
    + `（服务端日志尾段：\n${logTail(server)}\n）`);
  const afterBye = server.log().length;
  const registerBefore = server.log().slice(logMark).split("POST /api/tabs/register").length - 1;

  // ② 恢复那一下：脚本不重跑 ⇒ 只有 pageshow 监听能补登记。
  await dispatchTransition(page, "pageshow", true);
  assert.ok(await waitForLog(server, afterBye, "POST /api/tabs/register"),
    `后退回来（pageshow persisted）之后没有补登记——修复前正是这条：宽限到点服务自杀`
    + `（服务端日志尾段：\n${logTail(server)}\n）`);
  assert.equal(server.log().slice(logMark).split("POST /api/tabs/register").length - 1,
    registerBefore + 1, "补登记应当恰好发一次（多发的每一条都是一次会漂的 payload）");

  // ③ 宽限过去之后：服务活着 + 页面自己还能拿到数据（产品不变量）。
  await sleep(GRACE_MS + 1500);
  assert.equal(server.proc.exitCode, null,
    `补登记之后服务仍然退出了（exit ${server.proc.exitCode}）——bfcache 回来还是死页面`
    + `（服务端日志尾段：\n${logTail(server)}\n）`);
  assert.ok(await serverAlive(server.url), "补登记之后服务不健康");
  const health = await page.evaluate(() => fetch("/api/health")
    .then((r) => r.status).catch((e) => "FETCH_FAIL:" + e.name));
  assert.equal(health, 200, `页面自己拿不到数据（${health}）——用户面前仍是死页面`);
});

test("E：回来时服务已经退出——给中文可见态，服务回来后自动接回", async () => {
  // 这一条把"晚于宽限回来"那条路走完：服务**真的**停掉（不是模拟的），补登记必然失败
  // ⇒ 广播 ⇒ 可见态；然后用户重启启动器（= 同一端口重新起服务）⇒ 轮询发现 ⇒ 自动重新载入。
  const port = server.port;
  await openApp(page, server);
  await dispatchTransition(page, "pagehide", true);
  const exitedAt = await exitObservedAt(server, GRACE_MS + 5000);
  assert.ok(exitedAt !== null,
    `告别之后服务没有按宽限退出——这一条要验的"服务已经停了"前提不成立`
    + `（服务端日志尾段：\n${logTail(server)}\n）`);

  await dispatchTransition(page, "pageshow", true);
  await page.waitForSelector("#service-stopped:not([hidden])", { timeout: 15000 });
  const box = await page.textContent("#service-stopped");
  assert.ok(box.includes("应用服务已停止"), `可见态没说清发生了什么：${box}`);
  assert.ok(box.includes("start-app.vbs"), `可见态没给下一步（双击启动器）：${box}`);
  assert.ok(await page.isVisible("#btn-service-reload"), "可见态缺「重新载入」按钮");
  // 落地态：广播是一次性的，模块图还没装载时事件会丢 —— 所以恢复那一刻还要在 DOM 上留下
  // 可回读的状态（`documentElement.dataset.serviceStopped`），ui 层装载时按它补显示。
  assert.equal(await page.evaluate(
    () => document.documentElement.dataset.serviceStopped), "1",
  "补登记失败没留下可回读的落地态（模块图装载途中被冻结再恢复时，可见态就永远不会亮）");

  // 用户重新双击启动器 = 同一端口重新起服务；页面每 2 秒探一次健康端点，回来就自动接上。
  const prevEpoch = await documentEpoch(page);
  server = await startServer({ launcher: true, requestedPort: port });
  await waitNewDocument(page, server, prevEpoch, "服务回来后自动接回");
  await waitReady(page, server);
  assert.equal(await page.$eval("#service-stopped", (el) => el.hidden), true,
    "接回之后可见态没有收起来（新文档应当是隐藏态）");
});

test("C：最后一个页面离开 → 服务自己停（关浏览器 = 停服务没被弄丢）", async () => {
  // 这一条**必须是最后一条**（它把服务关掉；node:test 在文件内按声明顺序串行跑）。
  // 判据是**进程真的退出了**，不是"端口空了"——后者夹具自己也会做（那是夹具收服务，
  // 不是产品行为）。
  //
  // 为什么是"导航离开"而不是 `page.close()`：见文件头那条实测约束（`page.close()` 走 CDP
  // 关目标，`pagehide`/信标都不跑，服务端压根收不到 bye ⇒ 拿它当"关标签"的替身只会得到
  // 一条永远红的用例）。"最后一个页面离开"与真实关窗口共用同一条 `pagehide` + `sendBeacon`
  // 路径，是夹具能造出来的最接近的形态。
  // 同样**自己成立**：单跑这一条时页面上还没有本应用，先开出来（这条用例要验的正是
  // "页面上是本应用 → 它离开 → 服务停"）。
  if (!page.url().startsWith(server.url)) await openApp(page, server);
  const t0 = Date.now();
  const logMark = server.log().length;               // 日志字符下标：只看这一轮新加的行
  await page.goto("about:blank");
  const exitedAt = await exitObservedAt(server, GRACE_MS + 5000);
  assert.ok(exitedAt !== null,
    `最后一个页面离开 ${Date.now() - t0}ms 后服务仍活着——"关浏览器 = 停服务"没生效`
    + `（服务端日志尾段：\n${logTail(server)}\n）`);
  // 先证明"是这一发告别把它关掉的"：不然服务**早就死了**时这条用例会假绿
  // （进程已退出 ⇒ `exitCode === 0` ⇒ 看着像"产品自己停的"）。
  assert.ok(server.log().slice(logMark).includes("POST /api/tabs/bye"),
    "这一轮服务端没收到 /api/tabs/bye——服务不是被这次的告别关掉的（多半是前面已经死了）");
  console.log(`[读数] 最后一个页面离开 → 服务自己退出用时 ${exitedAt - t0}ms`
    + `（宽限 ${GRACE_MS}ms + 进程退出）`);
  assert.equal(server.proc.exitCode, 0, "退出码应当是 0（os._exit(0)）");
});
