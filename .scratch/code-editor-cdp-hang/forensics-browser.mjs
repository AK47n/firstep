// 取证（工单 code-editor-cdp-hang/01 验收项 ②）：复现「smoke-04 → smoke-05 挂死」时
// 从**浏览器端点**抓 target 生命周期事件（targetCreated / targetDestroyed / targetCrashed /
// targetInfoChanged），并对 page target 轮询 /json/list 与 Runtime.evaluate，判定：
//   渲染进程崩溃（targetCrashed / RenderProcessGone）  vs
//   渲染进程无响应但存活（target 在、命令不返回）      vs
//   标签页真的被销毁（targetDestroyed → /json/list 空）
//
// 用法：node .scratch/code-editor-cdp-hang/forensics-browser.mjs [--seq=smoke-04,smoke-05] [--rounds=3]
import { spawnSync } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const PAGE_URL = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-cdp-hang");
mkdirSync(OUT, { recursive: true });
const argv = process.argv.slice(2);
const argOf = (n, d) => { const h = argv.find((a) => a.startsWith(`--${n}=`)); return h ? h.split("=")[1] : d; };
const ROUNDS = Number(argOf("rounds", "3"));
const SEQ = argOf("seq", ".scratch/code-page-vscode-overhaul/smoke-04.mjs,.scratch/code-page-vscode-overhaul/smoke-05.mjs")
  .split(",").map((s) => s.trim()).filter(Boolean);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fetchT = async (url, ms = 5000, opts = {}) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal, ...opts }); } finally { clearTimeout(t); }
};
async function listTargets() {
  try { return await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch (e) { return { error: String(e) }; }
}
async function ensureTab() {
  let list = await listTargets();
  if (!Array.isArray(list)) return null;
  let page = list.find((t) => t.type === "page" && t.url.startsWith(PAGE_URL));
  if (!page) {
    await fetchT(`http://127.0.0.1:${CDP}/json/new?${encodeURIComponent(PAGE_URL)}`, 8000, { method: "PUT" }).catch(() => {});
    await sleep(1500);
    list = await listTargets();
    page = Array.isArray(list) ? list.find((t) => t.type === "page" && t.url.startsWith(PAGE_URL)) : null;
  }
  return page || null;
}
// 单次探活：Runtime.evaluate("1+1") 是否在 5s 内返回
async function probe(t, ms = 5000) {
  if (!t) return { alive: false, why: "无 page target" };
  return await new Promise((resolve) => {
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    let done = false;
    const finish = (v) => { if (!done) { done = true; try { ws.close(); } catch {} resolve(v); } };
    const to = setTimeout(() => finish({ alive: false, why: `Runtime.evaluate 超时（${ms}ms）` }), ms);
    ws.onerror = () => { clearTimeout(to); finish({ alive: false, why: "ws error（target 可能已销毁）" }); };
    ws.onopen = () => ws.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression: "1+1", returnByValue: true } }));
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === 1) { clearTimeout(to); finish({ alive: true, value: m.result?.result?.value, error: m.error?.message }); }
    };
  });
}

// ---- 浏览器端点：收 target 生命周期事件 ----
const events = [];
let bseq = 0;
const browser = await (await fetchT(`http://127.0.0.1:${CDP}/json/version`)).json();
const bws = new WebSocket(browser.webSocketDebuggerUrl);
await new Promise((res, rej) => { bws.onopen = res; bws.onerror = () => rej(new Error("browser ws")); });
bws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.method) {
    const p = m.params || {};
    events.push({
      t: new Date().toISOString().slice(11, 23), method: m.method,
      targetId: (p.targetInfo && p.targetInfo.targetId) || p.targetId,
      type: (p.targetInfo && p.targetInfo.type) || p.type,
      url: (p.targetInfo && p.targetInfo.url) || p.url,
      status: p.status, errorCode: p.errorCode, reason: p.reason,
    });
  }
};
bws.send(JSON.stringify({ id: ++bseq, method: "Target.setDiscoverTargets", params: { discover: true } }));
await sleep(500);

const report = { rounds: ROUNDS, seq: SEQ, rounds_detail: [] };
let hangs = 0;
for (let round = 1; round <= ROUNDS; round++) {
  const startIdx = events.length;
  await ensureTab();
  const pre = await probe(await ensureTab());
  const detail = { round, pre_probe: pre, scripts: [] };
  for (const script of SEQ) {
    const t0 = Date.now();
    const r = spawnSync(process.execPath, [join(ROOT, script)], {
      encoding: "utf8", timeout: 70000, cwd: ROOT, env: { ...process.env, PYTHONIOENCODING: "utf8" },
    });
    const ms = Date.now() - t0;
    const timedOut = !!(r.error && r.error.code === "ETIMEDOUT");
    const listNow = await listTargets();
    const pageNow = Array.isArray(listNow) ? listNow.find((t) => t.type === "page") : null;
    const post = await probe(pageNow);
    const entry = {
      script: script.split("/").slice(-2).join("/"), ms, exit: r.status, timedOut,
      stdout_tail: (r.stdout || "").trim().split("\n").slice(-2).join(" | "),
      stderr_tail: (r.stderr || "").trim().split("\n").slice(-2).join(" | "),
      targets_after: Array.isArray(listNow) ? listNow.map((t) => `${t.type}:${t.url.slice(0, 40)}`) : listNow,
      post_probe: post,
    };
    if (timedOut || !post.alive) {
      hangs++;
      entry.hang = true;
      console.log(`\n!! round ${round} ${entry.script} 挂死/无响应（${ms}ms, timedOut=${timedOut}）`);
      console.log(`   target 列表：${JSON.stringify(entry.targets_after)}`);
      console.log(`   探活：${JSON.stringify(post)}`);
      console.log(`   事件（本轮）：`);
      for (const e of events.slice(startIdx)) console.log("     ", JSON.stringify(e));
      // 挂死后等 20s 看是否自愈（区分「渲染进程慢」与「真死」）
      await sleep(20000);
      const after = await probe(await ensureTab());
      entry.probe_after_20s = after;
      console.log(`   20s 后探活：${JSON.stringify(after)}`);
      // 重建标签页恢复
      const t = await ensureTab();
      if (t) { await fetchT(`http://127.0.0.1:${CDP}/json/close/${t.id}`).catch(() => {}); await sleep(500); }
      const nw = await ensureTab();
      entry.recovered = nw ? "已重建标签页" : "重建失败";
      console.log(`   恢复：${entry.recovered}`);
    } else {
      console.log(`round ${round} ${entry.script}: exit=${r.status} ${ms}ms | ${entry.stdout_tail}`);
    }
    detail.scripts.push(entry);
  }
  detail.events = events.slice(startIdx);
  report.rounds_detail.push(detail);
  await sleep(500);
}
console.log(`\n结果：${ROUNDS} 轮，挂死 ${hangs} 次`);
report.hangs = hangs;
report.all_events = events;
writeFileSync(join(OUT, `forensics-browser-${Date.now()}.json`), JSON.stringify(report, null, 2), "utf8");
try { bws.close(); } catch {}
process.exit(hangs ? 1 : 0);
