// 定位（工单 code-editor-cdp-hang/01）：smoke-04 结束后，第一个不返回的 CDP 命令是哪个？
// 逐命令打点（同步 stderr 直写，避免管道缓冲吞掉输出），每个命令 6s 超时。
//
// 用法：node .scratch/code-editor-cdp-hang/probe-first-hang.mjs [--after=smoke-04] [--timeout=6000]
import { spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeSync } from "node:fs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251, PAGE_URL = "http://127.0.0.1:8000/";
const argv = process.argv.slice(2);
const argOf = (n, d) => { const h = argv.find((a) => a.startsWith(`--${n}=`)); return h ? h.split("=")[1] : d; };
const AFTER = argOf("after", ".scratch/code-page-vscode-overhaul/smoke-04.mjs");
const TO = Number(argOf("timeout", "6000"));
const log = (s) => writeSync(2, s + "\n");   // stderr 无缓冲，直接可见

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const fetchT = async (url, ms = 5000, opts = {}) => {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal, ...opts }); } finally { clearTimeout(t); }
};
const listTargets = async () => { try { return await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch (e) { return []; } };
const pageTarget = async () => (await listTargets()).find((t) => t.type === "page" && t.url.startsWith(PAGE_URL));

if (AFTER && AFTER !== "none") {
  log(`前置：跑 ${AFTER}`);
  const r = spawnSync(process.execPath, [join(ROOT, AFTER)], { encoding: "utf8", timeout: 90000, cwd: ROOT });
  log(`  前置结果：exit=${r.status} 尾行=${(r.stdout || "").trim().split("\n").slice(-1)[0]}`);
}

const t = await pageTarget();
if (!t) { log("没有 page target"); process.exit(1); }
log(`目标：${t.id.slice(0, 8)} ${t.url}`);

const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
};
const cdp = (method, params = {}, timeout = TO) => new Promise((resolve, reject) => {
  const id = ++seq; const t0 = Date.now();
  const to = setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(Object.assign(new Error(`${method} 超时（${timeout}ms）`), { hung: true })); } }, timeout);
  pending.set(id, (m) => { clearTimeout(to); resolve({ m, ms: Date.now() - t0 }); });
  ws.send(JSON.stringify({ id, method, params }));
});
const step = async (label, method, params) => {
  try {
    const { m, ms } = await cdp(method, params);
    const val = m.result?.result?.value;
    log(`  OK   ${label.padEnd(46)} ${String(ms).padStart(5)}ms` + (val !== undefined ? ` → ${JSON.stringify(val).slice(0, 60)}` : m.error ? ` → error: ${m.error.message}` : ""));
    return { ok: true, ms, m };
  } catch (e) {
    log(`  HANG ${label.padEnd(46)} ${TO}ms —— ${e.message}`);
    return { ok: false, err: String(e) };
  }
};

log("逐命令探活（每个 6s 超时）：");
await step("Runtime.enable", "Runtime.enable");
await step("Page.enable", "Page.enable");
await step("Runtime.evaluate 1+1", "Runtime.evaluate", { expression: "1+1", returnByValue: true });
await step("Runtime.evaluate document.title", "Runtime.evaluate", { expression: "document.title", returnByValue: true });
await step("Runtime.evaluate 埋 marker", "Runtime.evaluate", { expression: "window.__probeMarker = 1; true", returnByValue: true });
await step("Page.reload(ignoreCache)", "Page.reload", { ignoreCache: true });
await sleep(1500);
await step("reload 后 Runtime.evaluate readyState", "Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
await step("DOM.getDocument", "DOM.getDocument", { depth: 1 });
await step("Page.navigate 同 URL", "Page.navigate", { url: PAGE_URL });
await sleep(1500);
await step("navigate 后 Runtime.evaluate readyState", "Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
await step("Input.dispatchKeyEvent keyDown x", "Input.dispatchKeyEvent", { type: "keyDown", key: "x", code: "KeyX", windowsVirtualKeyCode: 88, nativeVirtualKeyCode: 88, text: "x" });
await step("Page.handleJavaScriptDialog", "Page.handleJavaScriptDialog", { accept: true });
try { ws.close(); } catch {}
log("探活结束");
