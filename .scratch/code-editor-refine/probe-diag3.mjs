// 复现：2026_Auto_Car_MSPM0/beep.c @ 140% + 行 24 —— 测窗口/高度/截图
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
const waitFor = async (expr, ms = 12000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};
const DIR = "C:\\Users\\luoji\\Desktop\\2024H_Auto_Car_MSPM0";
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer('${DIR.replace(/\\/g, "\\\\")}'))`);
await waitFor(`!!document.querySelector('#code-tree') && document.querySelector('#code-dir-label')?.textContent.includes('2024H')`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('modules/beep/code/beep.c'))`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await Eval(`(() => {
  const view = document.getElementById('code-viewer');
  view.style.setProperty('--code-zoom', '1.4');
  return true;
})()`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.codeWindowRefresh()); true`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.editJumpToLine(24)); true`);
await new Promise((r) => setTimeout(r, 800));
const d = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const edit = document.querySelector('#code-viewer .code-edit');
  const hl = document.querySelector('#code-viewer .code-hl');
  const gutter = document.querySelector('#code-viewer .code-gutter');
  const r = (el) => el ? { w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height) } : null;
  return {
    ta: r(ta), edit: r(edit), hl: r(hl), gutter: r(gutter),
    editH: edit ? edit.style.height : null,
    taLines: ta ? ta.value.split('\\n').length : 0,
    hlLines: hl ? hl.querySelectorAll('.code-hl-line').length : 0,
    gutterLines: gutter ? gutter.querySelectorAll('.code-gutter-line').length : 0,
    firstGutterNo: gutter ? gutter.querySelector('.code-gutter-line')?.dataset.codeLine : null,
    lastGutterNo: gutter ? Array.from(gutter.querySelectorAll('.code-gutter-line')).pop()?.dataset.codeLine : null,
    scrollTop: document.getElementById('code-viewer').scrollTop,
    lineH: ta ? parseFloat(getComputedStyle(document.querySelector('#code-viewer .code-hl-line')).lineHeight) : 0,
    editFont: edit ? getComputedStyle(edit).fontSize : '',
  };
})()`);
console.log(JSON.stringify(d, null, 2));
const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(ROOT, ".scratch", "code-editor-refine", "diag-beep-zoom.png"), Buffer.from(shot.result.data, "base64"));
console.log("截图 diag-beep-zoom.png");
process.exit(0);
