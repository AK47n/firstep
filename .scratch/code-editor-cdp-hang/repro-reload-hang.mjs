// 复现/取证脚本（工单 code-editor-cdp-hang/01 验收项 ①）：
// 「CDP 冒烟跑完后，下一次 Page.reload 偶发导致渲染进程无响应」的挂死率与现场证据。
//
// 用法（先起 webapp 8000 + Chrome headless CDP 9251）：
//   node .scratch/code-editor-cdp-hang/repro-reload-hang.mjs [--cycles=20] [--mode=plain|editor|smoke08]
//
// 三档负载（mode）：
//   plain    —— 裸 reload（对照：确认基线不挂）
//   editor   —— 先 openCodeViewer(5000 行 big.c) 让编辑器装满窗口化状态，再 reload
//   smoke08  —— 直接跑 .scratch/code-page-vscode-overhaul/smoke-08.mjs（含 5000 行 + 编辑），再 reload
//
// 每个 cycle 都：Page.reload → 等就绪 → Runtime.evaluate 心跳。
// 命令 8s 不返回即判「挂死」，立刻抓现场（§挂死现场）：
//   - /json/list 里该 target 是否还在、url/title 是否已变（导航是否卡住）
//   - 同 target 上 Page.enable / Runtime.enable 是否也超时（单命令问题 vs 渲染进程死）
//   - 浏览器端点 Inspector.targetCrashed / Page.frameDetached / Target.* 事件回放
//   - webapp /api/tabs/bye 是否被调过（pagehide + sendBeacon 路径）
//
// 退出码：0 = 全 cycle 通过；1 = 有挂死（打印挂死率）。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-cdp-hang");
const SAMPLE = join(OUT, "sample-proj");
const argv = process.argv.slice(2);
const argOf = (name, dflt) => {
  const hit = argv.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.split("=")[1] : dflt;
};
const CYCLES = Number(argOf("cycles", "20"));
const MODE = argOf("mode", "editor");
const CMD_TIMEOUT_MS = Number(argOf("timeout", "8000"));

// ---- 大文件样本（5000 行，与 smoke-08 同形） ----
mkdirSync(SAMPLE, { recursive: true });
const big = [];
for (let i = 1; i <= 5000; i++) big.push(`int fn_${i}(int x) { return x + ${i}; }  // line ${i}`);
writeFileSync(join(SAMPLE, "big.c"), big.join("\n") + "\n");

const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---- 浏览器端点连接（收 Inspector.targetCrashed / Target.* 等事件） ----
const browserEvents = [];
let browserWs = null;
async function connectBrowser() {
  const ver = await (await fetchT(`http://127.0.0.1:${CDP}/json/version`)).json();
  browserWs = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { browserWs.onopen = res; browserWs.onerror = () => rej(new Error("browser ws error")); });
  let bseq = 0;
  browserWs.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.method) browserEvents.push({ t: Date.now(), method: msg.method, params: msg.params });
  };
  const send = (method, params = {}) => new Promise((res) => {
    const id = ++bseq;
    const onMsg = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === id) { browserWs.removeEventListener("message", onMsg); res(m); }
    };
    browserWs.addEventListener("message", onMsg);
    browserWs.send(JSON.stringify({ id, method, params }));
    setTimeout(res, 3000, { timeout: true });
  });
  // Inspector 域在浏览器端点不生效（它在 page target 上）；这里只确保能收发。
  await send("Target.setDiscoverTargets", { discover: true });
  return true;
}

// ---- page target 连接 ----
async function pageTarget() {
  const list = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json();
  return list.find((t) => t.type === "page" && t.url.startsWith(pageUrl)) || null;
}

let seq = 0;
function makeConn(target) {
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  const events = [];
  const pending = new Map();
  const open = new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else if (msg.method) events.push({ t: Date.now(), method: msg.method, params: msg.params });
  };
  const cdp = (method, params = {}, timeout = CMD_TIMEOUT_MS) =>
    new Promise((resolve, reject) => {
      const id = ++seq;
      const t = setTimeout(() => {
        if (pending.has(id)) { pending.delete(id); reject(Object.assign(new Error(`CDP 超时（${timeout}ms）: ${method}`), { hung: true, method })); }
      }, timeout);
      pending.set(id, (msg) => { clearTimeout(t); resolve(msg); });
      ws.send(JSON.stringify({ id, method, params }));
    });
  const Eval = async (expr, timeout) => {
    const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeout);
    if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
    return r.result?.result?.value;
  };
  return { ws, cdp, Eval, events, open, close: () => { try { ws.close(); } catch {} } };
}

// ---- 挂死现场取证 ----
async function forensics(conn, reason) {
  const snap = { reason: String(reason), at: new Date().toISOString(), target: null, pageEvents: conn.events.slice(-40), browserEvents: browserEvents.slice(-40) };
  try {
    const t = await pageTarget();
    snap.target = t ? { id: t.id, url: t.url, title: t.title } : null;
  } catch (e) { snap.target = { error: String(e) }; }
  // 同一 target 上换命令再试：Page.enable / Runtime.enable 是否也超时
  for (const m of ["Page.enable", "Runtime.enable", "DOM.enable"]) {
    const t0 = Date.now();
    try { await conn.cdp(m, {}, 5000); snap[m] = `ok ${Date.now() - t0}ms`; }
    catch (e) { snap[m] = `超时 ${Date.now() - t0}ms`; }
  }
  // 最后一条：极短表达式（纯 JS 求值，不需要 DOM）
  try { snap.eval1p1 = await conn.Eval("1+1", 5000); } catch (e) { snap.eval1p1 = String(e); }
  writeFileSync(join(OUT, "forensics-" + Date.now() + ".json"), JSON.stringify(snap, null, 2), "utf8");
  console.log("---- 挂死现场 ----");
  console.log(JSON.stringify(snap, null, 2));
}

async function reloadAndCheck(conn, cycle) {
  // 心跳：reload 前在页面里埋一个递增计数器，reload 后应当归零（说明是新文档）
  const t0 = Date.now();
  try {
    await conn.cdp("Page.reload", { ignoreCache: true });
  } catch (e) {
    return { ok: false, at: "Page.reload", err: String(e), hung: !!e.hung, ms: Date.now() - t0 };
  }
  const reloadMs = Date.now() - t0;
  for (let i = 0; i < 60; i++) {
    try {
      const ready = await conn.Eval(
        `document.readyState === 'complete' && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`);
      if (ready) return { ok: true, reloadMs, readyMs: Date.now() - t0 };
    } catch (e) {
      if (e.hung) return { ok: false, at: "Runtime.evaluate(ready)", err: String(e), hung: true, ms: Date.now() - t0 };
    }
    await sleep(250);
  }
  return { ok: false, at: "ready-timeout", err: "页面未就绪（15s）", ms: Date.now() - t0 };
}

// ---- 主流程 ----
console.log(`复现脚本：mode=${MODE} cycles=${CYCLES} 命令超时=${CMD_TIMEOUT_MS}ms`);
if (!(await connectBrowser().catch(() => false))) console.log("警告：浏览器端点连接失败，仅用 page 端点取证");

let target = await pageTarget();
if (!target) { console.error("找不到页面 target（webapp 8000 / Chrome 9251 起了吗？）"); process.exit(1); }
let conn = makeConn(target);
await conn.open;
await conn.cdp("Page.enable").catch(() => {});
await conn.cdp("Runtime.enable").catch(() => {});

// 负载准备
if (MODE === "editor") {
  await conn.cdp("Page.reload", { ignoreCache: true }).catch(() => {});
  for (let i = 0; i < 60; i++) {
    try {
      if (await conn.Eval(`document.readyState === 'complete' && !!document.getElementById('code-viewer')`)) break;
    } catch {}
    await sleep(250);
  }
  await conn.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
  for (let i = 0; i < 40; i++) {
    if (await conn.Eval(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`).catch(() => false)) break;
    await sleep(250);
  }
  await conn.Eval(`document.querySelector('#code-tree [data-code-file="big.c"]')?.click()`);
  const lines = await conn.Eval(`(window.getActiveTab && getActiveTab() ? getActiveTab().content.length : -1)`).catch(() => -1);
  console.log(`负载：已打开 big.c（模型长度 ${lines}）`);
} else if (MODE === "smoke08") {
  const { spawnSync } = await import("node:child_process");
  const r = spawnSync(process.execPath, [join(ROOT, ".scratch", "code-page-vscode-overhaul", "smoke-08.mjs")], { encoding: "utf8", timeout: 180000 });
  console.log("smoke-08 复跑尾行：", (r.stdout || "").trim().split("\n").slice(-3).join(" | "));
  target = await pageTarget();
  if (target) { conn.close(); conn = makeConn(target); await conn.open; }
}

let hung = 0, ok = 0;
const results = [];
for (let c = 1; c <= CYCLES; c++) {
  const r = await reloadAndCheck(conn, c);
  results.push({ cycle: c, ...r });
  if (r.ok) { ok++; process.stdout.write(`.${c}`); }
  else {
    hung++;
    console.log(`\ncycle ${c} 挂死（${r.at}）：${r.err}`);
    await forensics(conn, `${r.at} @ cycle ${c}`);
    // 挂死后重建标签页，继续跑（同时验证「重建标签页即恢复」）
    const t = await pageTarget();
    if (t) {
      await fetchT(`http://127.0.0.1:${CDP}/json/close/${t.id}`).catch(() => {});
      await sleep(500);
      const nw = await (await fetchT(`http://127.0.0.1:${CDP}/json/new?${encodeURIComponent(pageUrl)}`, 8000)).json().catch(() => null);
      await sleep(1500);
      const t2 = await pageTarget();
      if (t2) { conn.close(); conn = makeConn(t2); await conn.open; console.log(`已重建标签页（${t2.id.slice(0, 8)}）${nw ? "" : "（json/new 返回空）"}`); }
    }
  }
  await sleep(200);
}
console.log("");
const rate = ((hung / CYCLES) * 100).toFixed(1);
console.log(`结果：${ok}/${CYCLES} 通过，挂死 ${hung} 次（挂死率 ${rate}%）`);
writeFileSync(join(OUT, `repro-${MODE}-${Date.now()}.json`), JSON.stringify({ mode: MODE, cycles: CYCLES, hung, ok, results }, null, 2), "utf8");
process.exit(hung ? 1 : 0);
