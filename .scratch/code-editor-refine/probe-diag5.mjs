// 复现 2：滚动到 line 24 附近（scrollTop≈261）后窗口端是否正确
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { writeFileSync } from "node:fs";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT("http://127.0.0.1:9251/json/list")).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000/"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const msg = JSON.parse(ev.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  box.scrollTop = 261;
  box.dispatchEvent(new Event('scroll', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 800));
const d = await Eval(`(() => {
  const gutter = document.querySelector('#code-viewer .code-gutter');
  const hl = document.querySelector('#code-viewer .code-hl');
  const nos = Array.from(gutter.querySelectorAll('.code-gutter-line')).map((e) => Number(e.dataset.codeLine));
  const box = document.getElementById('code-viewer');
  return {
    scrollTop: box.scrollTop,
    gutterCount: nos.length,
    gutterFirst: nos[0], gutterLast: nos[nos.length - 1],
    hlCount: hl.querySelectorAll('.code-hl-line').length,
    hlFirst: hl.querySelector('.code-hl-line')?.dataset.codeLine,
    hlLast: Array.from(hl.querySelectorAll('.code-hl-line')).pop()?.dataset.codeLine,
    winSpacers: document.querySelectorAll('#code-viewer .code-window-spacer').length,
    spacerHeights: Array.from(document.querySelectorAll('#code-viewer .code-window-spacer')).map(s => s.style.height),
    taScrollTop: document.querySelector('#code-viewer .code-ta')?.scrollTop,
  };
})()`);
console.log(JSON.stringify(d, null, 2));
const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(ROOT, ".scratch", "code-editor-refine", "diag-beep-scroll.png"), Buffer.from(shot.result.data, "base64"));
process.exit(0);
