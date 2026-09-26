// probe-05-diag3.mjs — 工单 ci-gate-fixes/05：**定性的最后一问** —— 页面挂住那 30 秒里，
// 后端到底是"死了"还是"没在答浏览器"？两个独立通道同时测：
//   ① Node 侧（浏览器之外、独立 socket）每 200ms 打一发 `GET /api/health`（1s 超时）；
//   ② 同刻打一发**裸 TCP connect** 到服务端口，量连接建立耗时。
// 浏览器那条通道（页面自己）另有读数：pagehide / register 发出 / 服务端 access log。
//
// 为什么要这么问：diag2 的现场是——第 7 个文档 document-start 后 17ms 就**发出**了 register，
// 但它**既没到服务端、也没拿到应答**，而 reload 30 秒超时；服务端 access log 的 register/bye
// 严格交替（register→bye ×5）说明前 6 个文档都正常。到底是服务端不答了，还是浏览器那条
// 连接坏了，二者指向完全不同的修法。
//
// 跑法：node .scratch/ci-gate-fixes/probe-05-diag3.mjs [--rounds=8] [--suite=10]
import { readFileSync } from "node:fs";
import { connect } from "node:net";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { serverAlive, startServer } from "../../tests/browser/server.mjs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const arg = (name, dflt) => {
  const hit = process.argv.find((a) => a.startsWith(`--${name}=`));
  return hit ? Number(hit.split("=")[1]) : dflt;
};
const ROUNDS = arg("rounds", 8);
const SUITE = arg("suite", 10);

const WEBAPP_PY = fileURLToPath(
  new URL("../../src/contest_generator/webapp.py", import.meta.url));
const GRACE_MS = Number(
  /^_EXIT_GRACE\s*=\s*([0-9.]+)/m.exec(readFileSync(WEBAPP_PY, "utf8"))[1]) * 1000;

/** 裸 TCP connect 耗时（毫秒）；连不上返回 null。 */
function tcpConnectMs(port, timeoutMs = 1000) {
  return new Promise((resolve) => {
    const t = Date.now();
    const sock = connect({ host: "127.0.0.1", port });
    const done = (v) => { try { sock.destroy(); } catch (e) { /* 忽略 */ } resolve(v); };
    sock.setTimeout(timeoutMs);
    sock.on("connect", () => done(Date.now() - t));
    sock.on("timeout", () => done(null));
    sock.on("error", () => done(null));
  });
}

/** Node 侧独立通道：健康检查 + 裸 TCP（1 秒预算，绝不与浏览器那条连接共用）。 */
async function probeServer(url, port) {
  const t0 = Date.now();
  let health = "?";
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 1000);
    const resp = await fetch(`${url}/api/health`, { signal: ctrl.signal });
    clearTimeout(timer);
    health = String(resp.status);
  } catch (e) { health = `ERR:${e.name}`; }
  const tcp = await tcpConnectMs(port);
  return { health, tcp, ms: Date.now() - t0 };
}

async function runSuite(n) {
  const server = await startServer({ launcher: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const lines = [];
  let mark = 0;
  const at = (what) => lines.push(`${String(Date.now() - mark).padStart(6)}ms  ${what}`);

  await page.addInitScript(() => {
    const origin = performance.timeOrigin;
    const key = "__probe_docs";
    const load = () => { try { return JSON.parse(sessionStorage.getItem(key) || "[]"); }
      catch (e) { return []; } };
    const save = (rows) => { try { sessionStorage.setItem(key, JSON.stringify(rows)); }
      catch (e) { /* 忽略 */ } };
    const rec = load();
    rec.push(["document-start", origin]);
    save(rec);
    addEventListener("pagehide", () => {
      const r = load();
      r.push(["pagehide", origin]);
      save(r);
    });
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        if (!e.name.includes("/api/tabs/")) continue;
        const r = load();
        r.push([`fetch ${e.name.split("/").pop()}`, origin,
          { start: Math.round(e.startTime), end: Math.round(e.startTime + e.duration),
            size: e.transferSize, status: e.responseStatus }]);
        save(r);
      }
    }).observe({ type: "resource", buffered: true });
  });

  page.on("request", (r) => {
    const p = new URL(r.url()).pathname;
    if (p === "/") at("GET / 发出");
    else if (p.endsWith("/register")) at("register 发出");
    else if (p.endsWith("/bye")) at("bye 发出");
  });
  page.on("requestfailed", (r) => {
    const p = new URL(r.url()).pathname;
    if (p.endsWith("/register") || p.endsWith("/bye") || p === "/") {
      at(`${p} 请求失败：${r.failure()?.errorText}`);
    }
  });
  page.on("domcontentloaded", () => at("domcontentloaded"));

  const ready = () => page.waitForFunction(
    () => document.querySelectorAll("#platforms .platform-card").length > 0,
    undefined, { timeout: 60000 });

  const rounds = [];
  try {
    await page.goto(server.url + "/", { waitUntil: "domcontentloaded" });
    await ready();
    for (let i = 1; i <= ROUNDS; i++) {
      mark = Date.now();
      lines.length = 0;
      at(`—— 第 ${i} 次 reload 开始 ——`);
      let err = null;
      // 独立通道：每 200ms 探一次（探测本身有 1s 预算，不会拖住主流程）
      const watch = [];
      let watching = true;
      const watcher = (async () => {
        while (watching) {
          const r = await probeServer(server.url, server.port);
          watch.push(`+${String(Date.now() - mark).padStart(6)}ms  health=${r.health}`
            + ` tcp=${r.tcp === null ? "连不上" : r.tcp + "ms"}（探测耗时 ${r.ms}ms）`);
          await sleep(200);
        }
      })();
      try {
        await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
        at("reload 返回");
        await ready();
        at("页面可用");
      } catch (e) {
        err = e.message.split("\n")[0];
        at(`reload 失败：${err}`);
      }
      watching = false;
      await watcher;
      const alive = await serverAlive(server.url);
      rounds.push({ i, err, alive, code: server.proc.exitCode, lines: [...lines],
        watch: [...watch] });
      if (err || !alive) break;
    }
    let docs = "(读不到)";
    try { docs = await page.evaluate(() => sessionStorage.getItem("__probe_docs")); }
    catch (e) { docs = `读不到：${e.message.split("\n")[0]}`; }
    const tabs = server.log().split("\n").filter((l) => l.includes("/api/tabs/"))
      .map((l) => (l.includes("/register") ? "register" : "bye"));
    return { n, rounds, docs, tabs, alive: await serverAlive(server.url),
      code: server.proc.exitCode, logTail: server.log().split("\n").slice(-8).join("\n") };
  } finally {
    await browser.close().catch(() => {});
    await server.stop().catch(() => {});
  }
}

const out = [];
for (let n = 1; n <= SUITE; n++) {
  const r = await runSuite(n);
  const red = r.rounds.some((x) => x.err || !x.alive);
  out.push(r);
  console.log(`\n=== 套件 ${n}：${r.rounds.length}/${ROUNDS} 次 reload，`
    + `${red ? "**红**" : "全绿"}（后端 ${r.alive ? "活着" : `已退出 code=${r.code}`}）===`);
  if (red) {
    const last = r.rounds[r.rounds.length - 1];
    console.log(`  末轮 Node 侧时间轴（宽限 ${GRACE_MS}ms）：\n    ${last.lines.join("\n    ")}`);
    console.log(`  末轮独立通道（health / 裸 TCP）：\n    ${last.watch.join("\n    ")}`);
    console.log(`  服务端 /api/tabs/* 顺序: ${r.tabs.join(" → ")}`);
    console.log(`  页面侧文档/请求记录: ${r.docs}`);
    console.log(`  后端日志尾段:\n${r.logTail}`);
  }
}
console.log(`\n=== 小结：${out.filter((r) => r.rounds.some((x) => x.err || !x.alive)).length}/${SUITE} 套件红 ===`);
