// 序列复现（工单 code-editor-cdp-hang/01）：第七轮实际中招的形态 = **两支脚本背靠背**
// 同一标签页（smoke-04 大量 trusted 按键 → smoke-05 开头 `Page.reload` 后挂死）。
// 本脚本用 spawnSync + 超时包装逐支跑，统计每支的退出码/耗时/挂死信号，挂死即抓现场。
//
// 用法：
//   node .scratch/code-editor-cdp-hang/repro-sequence.mjs [--rounds=5] [--scripts=a,b,c] [--timeout=60]
import { spawnSync } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const OUT = join(ROOT, ".scratch", "code-editor-cdp-hang");
mkdirSync(OUT, { recursive: true });
const argv = process.argv.slice(2);
const argOf = (n, d) => { const h = argv.find((a) => a.startsWith(`--${n}=`)); return h ? h.split("=")[1] : d; };
const ROUNDS = Number(argOf("rounds", "5"));
const TIMEOUT_S = Number(argOf("timeout", "90"));
const SCRIPTS = argOf("scripts",
  ".scratch/code-page-vscode-overhaul/smoke-04.mjs,.scratch/code-page-vscode-overhaul/smoke-05.mjs"
).split(",").map((s) => s.trim()).filter(Boolean);

const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function targets() {
  try { return await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch { return []; }
}
async function pageTarget() {
  return (await targets()).find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000/")) || null;
}
// 现场：对当前 page target 直接发 Runtime.evaluate，看是否响应
async function probeTarget(t, ms = 6000) {
  if (!t) return { alive: false, why: "无 page target" };
  return await new Promise((resolve) => {
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    let done = false;
    const finish = (v) => { if (!done) { done = true; try { ws.close(); } catch {} resolve(v); } };
    const to = setTimeout(() => finish({ alive: false, why: `Runtime.evaluate 超时（${ms}ms）—— 渲染进程无响应` }), ms);
    ws.onerror = () => { clearTimeout(to); finish({ alive: false, why: "ws error" }); };
    ws.onopen = () => {
      ws.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression: "1+1", returnByValue: true } }));
      ws.send(JSON.stringify({ id: 2, method: "Page.enable" }));
      ws.send(JSON.stringify({ id: 3, method: "Runtime.enable" }));
    };
    const replies = {};
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === 1) replies.eval = m.result?.result?.value ?? m.error?.message;
      if (m.id === 2) replies.pageEnable = m.error ? "error: " + m.error.message : "ok";
      if (m.id === 3) replies.runtimeEnable = m.error ? "error: " + m.error.message : "ok";
      if (replies.eval !== undefined && replies.pageEnable && replies.runtimeEnable) {
        clearTimeout(to);
        finish({ alive: true, ...replies });
      }
    };
  });
}
async function rebuildTab() {
  const t = await pageTarget();
  if (t) await fetchT(`http://127.0.0.1:${CDP}/json/close/${t.id}`).catch(() => {});
  await sleep(400);
  const r = await fetchT(`http://127.0.0.1:${CDP}/json/new?${encodeURIComponent("http://127.0.0.1:8000/")}`, 8000).catch(() => null);
  await sleep(1200);
  return (await pageTarget()) ? "已重建标签页" : "重建失败" + (r ? "" : "（json/new 无响应）");
}

const report = [];
let hangs = 0;
for (let round = 1; round <= ROUNDS; round++) {
  for (const script of SCRIPTS) {
    const t0 = Date.now();
    const r = spawnSync(process.execPath, [join(ROOT, script)], {
      encoding: "utf8", timeout: TIMEOUT_S * 1000, cwd: ROOT,
      env: { ...process.env, PYTHONIOENCODING: "utf8" },
    });
    const ms = Date.now() - t0;
    const tail = (r.stdout || "").trim().split("\n").slice(-1)[0] || "";
    const timedOut = r.error && r.error.code === "ETIMEDOUT";
    const hung = timedOut || /CDP 无响应/.test(r.stdout || "") || /CDP 无响应/.test(r.stderr || "");
    const rec = { round, script: script.split("/").slice(-2).join("/"), ms, exit: r.status, timedOut: !!timedOut, hung, tail };
    if (hung) {
      hangs++;
      rec.forensics = await probeTarget(await pageTarget());
      console.log(`\n!! 挂死：round ${round} / ${rec.script}（${ms}ms, exit=${r.status}, timedOut=${!!timedOut}）`);
      console.log("   现场：", JSON.stringify(rec.forensics));
      console.log("   尾行：", tail);
      rec.recovered = await rebuildTab();
      console.log("   恢复：", rec.recovered);
    } else {
      console.log(`round ${round} ${rec.script}: exit=${r.status} ${ms}ms | ${tail}`);
    }
    report.push(rec);
    await sleep(300);
  }
}
console.log(`\n结果：${ROUNDS} 轮 × ${SCRIPTS.length} 支，挂死 ${hangs} 次`);
writeFileSync(join(OUT, `repro-sequence-${Date.now()}.json`), JSON.stringify({ rounds: ROUNDS, scripts: SCRIPTS, hangs, report }, null, 2), "utf8");
process.exit(hangs ? 1 : 0);
