// 影响面 + 修复验证（工单 code-editor-cdp-hang/01）：
//
// 1) 逐支脚本跑一遍，跑完后测「残留状态」与「下一次 reload 是否挂死」
//    —— 判据 = 编辑器是否有未保存标签（tab.content !== tab.savedContent）。
// 2) 对挂死脚本验证两种修法：
//    fix1 每支前重建标签页（当前约定）
//    fix2 脚本末尾显式清脏（Ctrl+S 保存 / 关闭标签）
//    fix3 会话级注入「自动化下不挂 beforeunload」补丁（Page.addScriptToEvaluateOnNewDocument）
//
// 用法：node .scratch/code-editor-cdp-hang/probe-impact.mjs [--scripts=a,b] [--skip-reload]
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeSync } from "node:fs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const argv = process.argv.slice(2);
const argOf = (n, d) => { const h = argv.find((a) => a.startsWith(`--${n}=`)); return h ? h.split("=")[1] : d; };
const SCRIPTS = argOf("scripts", [
  ".scratch/code-page-vscode-overhaul/smoke-01.mjs",
  ".scratch/code-page-vscode-overhaul/smoke-02.mjs",
  ".scratch/code-page-vscode-overhaul/smoke-03.mjs",
  ".scratch/code-page-vscode-overhaul/smoke-04.mjs",
  ".scratch/code-page-vscode-overhaul/smoke-05.mjs",
  ".scratch/code-page-vscode-overhaul/smoke-06.mjs",
  ".scratch/code-page-vscode-overhaul/smoke-07.mjs",
  ".scratch/code-page-vscode-overhaul/smoke-08.mjs",
  ".scratch/code-page-vscode-overhaul/smoke-09.mjs",
  ".scratch/code-page-vscode-overhaul/smoke-10.mjs",
].join(",")).split(",").map((s) => s.trim()).filter(Boolean);
const log = (s) => writeSync(2, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fetchT = async (url, ms = 5000, opts = {}) => {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal, ...opts }); } finally { clearTimeout(t); }
};
const listTargets = async () => { try { return await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch { return []; } };
const pageTarget = async () => (await listTargets()).find((t) => t.type === "page" && t.url.startsWith(PAGE_URL));

async function rebuildTab() {
  const t = await pageTarget();
  if (t) { await fetchT(`http://127.0.0.1:${CDP}/json/close/${t.id}`).catch(() => {}); await sleep(400); }
  await fetchT(`http://127.0.0.1:${CDP}/json/new?${encodeURIComponent(PAGE_URL)}`, 8000, { method: "PUT" }).catch(() => {});
  await sleep(1500);
  return pageTarget();
}
function conn(t) {
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  let seq = 0; const pending = new Map(); const events = [];
  const open = new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    else if (m.method) events.push({ t: Date.now(), method: m.method, params: m.params });
  };
  const cdp = (method, params = {}, timeout = 6000) => new Promise((resolve, reject) => {
    const id = ++seq;
    const to = setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(Object.assign(new Error(method + " 超时"), { hung: true })); } }, timeout);
    pending.set(id, (m) => { clearTimeout(to); resolve(m); });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const Eval = async (expr, timeout = 6000) => (await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeout)).result?.result?.value;
  return { cdp, Eval, events, open, close: () => { try { ws.close(); } catch {} } };
}
// 脏标签判据 = 产品自身的 dirtyTabPaths()（单源，不自己比 content/savedContent）
const DIRTY_EXPR = `import('/js/ui/codeeditor.js').then((m) => {
  const paths = m.dirtyTabPaths() || [];
  const t = m.getActiveTab();
  return { dirty: paths.length, paths, active: t && t.path };
})`;

const results = [];
for (const script of SCRIPTS) {
  const name = script.split("/").slice(-2).join("/");
  await rebuildTab();                       // 每支前重建（既定约定）
  const t0 = Date.now();
  const r = spawnSync(process.execPath, [join(ROOT, script)], { encoding: "utf8", timeout: 90000, cwd: ROOT });
  const runMs = Date.now() - t0;
  const tail = (r.stdout || "").trim().split("\n").slice(-1)[0];
  const t = await pageTarget();
  let dirty = null, hung = false, dialogs = 0;
  if (t) {
    const c = conn(t); await c.open;
    // Page.enable 必须在 reload **之前**（否则收不到 reload 期间的 dialogOpening 事件）
    await c.cdp("Page.enable").catch(() => {});
    await c.cdp("Runtime.enable").catch(() => {});
    try { dirty = await c.Eval(DIRTY_EXPR, 5000); } catch (e) { dirty = "err:" + e.message; }
    if (!(argv.includes("--skip-reload"))) {
      try {
        await c.cdp("Page.reload", { ignoreCache: true }, 6000);
        await sleep(1500);
        const rs = await c.Eval("document.readyState", 5000);
        log(`  reload 探活：OK → ${rs}`);
      } catch (e) { hung = true; log(`  reload 探活：HANG（${e.message}）`); }
      dialogs = c.events.filter((e) => e.method === "Page.javascriptDialogOpening").length;
    }
    c.close();
  }
  const rec = { script: name, exit: r.status, runMs, tail, dirty, hung, dialogs };
  results.push(rec);
  log(`${name}: exit=${r.status} ${runMs}ms | 残留 ${JSON.stringify(dirty)} | 对话框 ${dialogs} | ${hung ? "挂死" : "未挂"} | ${tail}`);
  if (hung) await rebuildTab();
}
log("\n---- 汇总 ----");
const vuln = results.filter((x) => x.hung);
log(`跑过 ${results.length} 支，挂死 ${vuln.length} 支：${vuln.map((x) => x.script).join(", ") || "无"}`);
log(`残留未保存的：${results.filter((x) => x.dirty && x.dirty.dirty > 0).map((x) => `${x.script}(${x.dirty.dirty})`).join(", ") || "无"}`);
