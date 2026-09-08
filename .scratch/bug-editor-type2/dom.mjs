// 检查逐键后 hl 层 innerHTML 的确切结构
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9252;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "bug-editor-type2", "sample2");
const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
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
const waitFor = async (expr, ms = 12000) => {
  for (let i = 0; i < ms / 200; i++) { try { if (await Eval(expr)) return true; } catch {} await new Promise((r) => setTimeout(r, 200)); }
  return false;
};
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) { try { if (await Eval(`document.readyState === 'complete' && !!document.getElementById('code-viewer')`)) break; } catch {} await new Promise((r) => setTimeout(r, 300)); }
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="empty2.c"]')`);
const out = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  await ce.openEditorFile('empty2.c');
  const box = document.getElementById('code-viewer');
  const ta = box.querySelector('.code-ta');
  const tab = ce.getActiveTab();
  ta.focus();
  const snap = (tag) => ({
    tag,
    model: tab.content,
    hlHTML: box.querySelector('.code-hl').innerHTML,
    hlLines: Array.from(box.querySelectorAll('.code-hl-line')).map((el) => ({ text: el.textContent, cls: el.className, html: el.outerHTML })),
  });
  const log = [];
  log.push(snap('初始'));
  const p = ta.value.indexOf('\\n') + 1;
  ta.setSelectionRange(p, p);
  for (const ch of ['a', 'b']) {
    const p2 = ta.selectionStart;
    ta.value = ta.value.slice(0, p2) + ch + ta.value.slice(p2);
    ta.setSelectionRange(p2 + 1, p2 + 1);
    ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
    log.push(snap('输入 ' + ch));
  }
  return log;
})()`);
console.log(JSON.stringify(out, null, 2));
process.exit(0);
