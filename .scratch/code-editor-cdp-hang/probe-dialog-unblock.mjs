// 决定性实验（工单 code-editor-cdp-hang/01 验收项 ②）：挂死时渲染进程是否卡在
// **导航前的 JS 对话框**（beforeunload 确认框）？
//
// 判据：挂死现场调 Page.handleJavaScriptDialog —— 若随后 Runtime.evaluate 立刻恢复
//       → 根因 = 对话框阻塞导航（渲染进程在等对话框应答）。
//       若仍不恢复 → 不是对话框，另找。
//
// 同时打印「挂死前页面是否 dirty」（tab.content !== tab.savedContent）与
// Page.javascriptDialogOpening 事件（挂死期间由另一个 page-target 连接监听）。
//
// 用法：node .scratch/code-editor-cdp-hang/probe-dialog-unblock.mjs [--after=<script>] [--no-after]
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeSync } from "node:fs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const argv = process.argv.slice(2);
const argOf = (n, d) => { const h = argv.find((a) => a.startsWith(`--${n}=`)); return h ? h.split("=")[1] : d; };
const AFTER = argOf("after", ".scratch/code-page-vscode-overhaul/smoke-04.mjs");
const log = (s) => writeSync(2, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fetchT = async (url, ms = 5000, opts = {}) => {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal, ...opts }); } finally { clearTimeout(t); }
};
const listTargets = async () => { try { return await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch { return []; } };
const pageTarget = async () => (await listTargets()).find((t) => t.type === "page" && t.url.startsWith(PAGE_URL));

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
    const to = setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(Object.assign(new Error(method + " 超时（" + timeout + "ms）"), { hung: true })); } }, timeout);
    pending.set(id, (m) => { clearTimeout(to); resolve(m); });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const Eval = async (expr, timeout = 6000) => (await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }, timeout)).result?.result?.value;
  return { cdp, Eval, events, open, close: () => { try { ws.close(); } catch {} } };
}

if (AFTER && AFTER !== "none") {
  log(`前置：跑 ${AFTER}`);
  const r = spawnSync(process.execPath, [join(ROOT, AFTER)], { encoding: "utf8", timeout: 90000, cwd: ROOT });
  log(`  前置结果：exit=${r.status} 尾行=${(r.stdout || "").trim().split("\n").slice(-1)[0]}`);
}
let t = await pageTarget();
if (!t) { log("无 page target"); process.exit(1); }
let c = conn(t); await c.open;
await c.cdp("Page.enable"); await c.cdp("Runtime.enable");

// 挂死前状态：dirty？焦点在哪？对话框事件？
const pre = await c.Eval(`import('/js/ui/codeeditor.js').then((m) => {
  const t = m.getActiveTab();
  return { path: t && t.path, dirty: !!(t && t.content !== t.savedContent), len: t ? t.content.length : -1,
    active: document.activeElement && (document.activeElement.tagName + (document.activeElement.className ? '.' + String(document.activeElement.className).split(' ')[0] : '')), tabs: (m.getTabs ? m.getTabs().length : -1) };
})`).catch((e) => "err:" + e);
log(`挂死前状态：${JSON.stringify(pre)}`);

log("发 Page.reload…");
try { await c.cdp("Page.reload", { ignoreCache: true }, 6000); log("  Page.reload 返回 OK"); } catch (e) { log("  Page.reload " + e.message); }
await sleep(1500);

// 挂死判定
let hung = false;
try { log(`  reload 后 Runtime.evaluate：OK → ${await c.Eval("document.readyState", 5000)}`); }
catch (e) { hung = true; log(`  reload 后 Runtime.evaluate：HANG（${e.message}）`); }
log(`  本连接收到的页面事件（reload 后）：${JSON.stringify(c.events.filter((x) => x.t > Date.now() - 8000).map((x) => x.method))}`);

if (hung) {
  // 另一条 page-target 连接：监听对话框事件 + 尝试应答
  const t2 = await pageTarget();
  const c2 = conn(t2); await c2.open;
  await c2.cdp("Page.enable").catch(() => log("  c2 Page.enable 超时"));
  log("  实验 A：Page.handleJavaScriptDialog{accept:true}");
  try { const r = await c2.cdp("Page.handleJavaScriptDialog", { accept: true }, 5000); log(`    → ${JSON.stringify(r).slice(0, 120)}`); }
  catch (e) { log(`    → ${e.message}`); }
  await sleep(1200);
  try { log(`  实验 A 后 Runtime.evaluate：OK → ${await c.Eval("document.readyState", 5000)}`); hung = false; }
  catch (e) { log(`  实验 A 后 Runtime.evaluate：仍 HANG（${e.message}）`); }
  if (hung) {
    log("  实验 B：Page.stopLoading / Page.navigate 换 URL 试解卡");
    try { await c2.cdp("Page.stopLoading", {}, 4000); log("    Page.stopLoading OK"); } catch (e) { log("    " + e.message); }
    await sleep(1000);
    try { log(`  实验 B 后 Runtime.evaluate：OK → ${await c.Eval("document.readyState", 5000)}`); }
    catch (e) { log(`  实验 B 后仍 HANG（${e.message}）`); }
  }
  log(`  c2 事件：${JSON.stringify(c2.events.map((x) => x.method + (x.params && x.params.type ? ':' + x.params.type : '')))}`);
  c2.close();
}
c.close();
log("结束");
