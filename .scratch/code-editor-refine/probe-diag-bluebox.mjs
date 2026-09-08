// 诊断：代码编辑器淡蓝框——.code-edit/.code-ta 几何 vs 内容行数；截屏
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
await Eval(`window.__diag = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  try { if (await Eval(`document.readyState === 'complete' && !window.__diag && !!document.getElementById('code-viewer')`)) break; } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(join(ROOT, ".scratch", "code-editor-refine", "sample-proj-11"))}))`);
for (let i = 0; i < 40; i++) {
  try { if (await Eval(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`)) break; } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click(); true`);
for (let i = 0; i < 60; i++) {
  try { if (await Eval(`!!document.querySelector('#code-viewer .code-ta')`)) break; } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
const geo = await Eval(`(() => {
  const edit = document.querySelector('#code-viewer .code-edit');
  const ta = document.querySelector('#code-viewer .code-ta');
  const hl = document.querySelector('#code-viewer .code-hl');
  const box = document.querySelector('#code-viewer');
  const re = edit ? edit.getBoundingClientRect() : null;
  const rt = ta ? ta.getBoundingClientRect() : null;
  const rh = hl ? hl.getBoundingClientRect() : null;
  const rb = box ? box.getBoundingClientRect() : null;
  return {
    edit: re ? { w: re.width, h: re.height } : null,
    ta: rt ? { w: rt.width, h: rt.height } : null,
    hl: rh ? { w: rh.width, h: rh.height } : null,
    box: rb ? { w: rb.width, h: rb.height } : null,
    taStyle: ta ? { pos: getComputedStyle(ta).position, inset: getComputedStyle(ta).inset, w: getComputedStyle(ta).width, h: getComputedStyle(ta).height } : null,
    editStyle: edit ? { h: edit.style.height, w: edit.style.width } : null,
    taLines: ta ? ta.value.split('\\n').length : 0,
    lineH: ta ? (function(){ const l = document.querySelector('#code-viewer .code-hl-line'); return l ? parseFloat(getComputedStyle(l).lineHeight) : 0; })() : 0,
  };
})()`);
console.log(JSON.stringify(geo, null, 2));
const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(ROOT, ".scratch", "code-editor-refine", "diag-bluebox.png"), Buffer.from(shot.result.data, "base64"));
console.log("截图已存 diag-bluebox.png");
process.exit(0);
