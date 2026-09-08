// 探针：smoke-05 fail5 排查——点击色点后发生了什么
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const SAMPLE = join(ROOT, ".scratch", "code-editor-refine", "sample-proj-05");
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
// 重建错误态
await Eval(`(() => {
  if (!window.__origFetch) window.__origFetch = window.fetch.bind(window);
  const payload = { passed: false, timed_out: false, parsed_errors: [
    { path: "bad.c", line: 3, message: "错误一" },
    { path: "..\\\\bad.c", line: 7, message: "错误二" },
  ] };
  window.fetch = (url, init) => {
    if (String(url).includes('/api/compile')) {
      return Promise.resolve(new Response('event: done\\ndata: ' + JSON.stringify(payload) + '\\n\\n', { status: 200, headers: { 'content-type': 'text/event-stream' } }));
    }
    return window.__origFetch(url, init);
  };
  return true;
})()`);
await Eval(`import('/js/ui/code-compile.js').then((m) => m.runCodeCompile()).then(() => true)`);
await new Promise((r) => setTimeout(r, 800));
const st1 = await Eval(`(() => ({
  dots: document.querySelectorAll('#code-viewer .code-gutter-line.code-err-line').length,
  active: document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath,
}))()`);
console.log("前置状态", JSON.stringify(st1));
// 直接调用 editJumpToLine(7) 看 flash 是否出现（隔离跳转层）
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.editJumpToLine(7)).then(() => true)`);
await new Promise((r) => setTimeout(r, 300));
console.log("editJumpToLine 后 flash:", await Eval(`document.querySelectorAll('#code-viewer .flash, #code-viewer [class*="flash"]').length`),
  await Eval(`Array.from(document.querySelectorAll('#code-viewer [class*="flash"]')).map((el) => el.className + '#' + (el.dataset.codeLine||'')).join(' | ')`));
// 点击色点 → 观察
await Eval(`document.querySelector('#code-viewer .code-gutter-line.code-err-line[data-code-line="7"]')?.click(); true`);
await new Promise((r) => setTimeout(r, 500));
console.log("点击后 flash:", await Eval(`Array.from(document.querySelectorAll('#code-viewer [class*="flash"]')).map((el) => el.className + '#' + (el.dataset.codeLine||'')).join(' | ') || '(none)'`));
console.log("点击后 err handler 是否收到:", await Eval(`(() => {
  const gn = document.querySelector('#code-viewer .code-gutter-line.code-err-line[data-code-line="7"]');
  return { found: !!gn, title: gn ? gn.title : '' };
})()`));
console.log("active 行:", await Eval(`document.querySelector('#code-viewer .code-gutter-line.active')?.dataset.codeLine`));
process.exit(0);
