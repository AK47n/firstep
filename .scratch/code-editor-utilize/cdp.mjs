// 冒烟共享 CDP 连接（code-editor-utilize）：零依赖——node 内置 fetch +
// WebSocket 直连 Chrome CDP；webapp 8000 提供真实 API。
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
export const SAMPLE = join(ROOT, ".scratch", "code-editor-utilize", "sample-proj");
export const CDP = 9231;

export async function connect() {
  const fetchT = async (url, ms = 5000) => {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), ms);
    try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
  };
  let targets = null;
  for (let i = 0; i < 50 && !targets; i++) {
    try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
    if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
  }
  if (!targets) { console.error("CDP 不可达"); process.exit(1); }
  const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
  let seq = 0;
  const pending = new Map();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  };
  const cdp = (method, params = {}) =>
    new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
  const Eval = async (expr) => {
    const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
    return r.result?.result?.value;
  };
  const waitFor = async (expr, ms = 8000) => {
    for (let i = 0; i < ms / 200; i++) {
      try { if (await Eval(expr)) return true; } catch {}
      await new Promise((r) => setTimeout(r, 200));
    }
    return false;
  };
  await Eval(`window.__smokeMarker = 1`);
  await cdp("Page.reload", { ignoreCache: true });
  let ready = false;
  for (let i = 0; i < 100 && !ready; i++) {
    try {
      ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
        && !!document.getElementById('code-viewer') && !!document.getElementById('btn-code-flash')`);
    } catch {}
    if (!ready) await new Promise((r) => setTimeout(r, 300));
  }
  if (!ready) { console.error("页面未就绪"); process.exit(1); }
  let failed = 0, passed = 0;
  const check = (name, ok, extra) => {
    console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
    if (ok) passed++; else failed++;
  };
  return { Eval, waitFor, check, cdp, summary: () => { console.log(`\n${passed} 项通过, ${failed} 项失败`); process.exit(failed ? 1 : 0); } };
}
