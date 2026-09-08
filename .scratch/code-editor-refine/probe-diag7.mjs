// 复现 3：big.c 滚到深处 → 打开 beep.c（34 行）→ 检查窗口/可点击性
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
const waitFor = async (expr, ms = 10000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};
// 1) big.c 打开 + 滚到底
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('.scratch/code-editor-refine/sample-proj-11/big.c')).then(() => true).catch((e) => 'ERR:' + e.message)`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
// big.c 不在当前目录下——先打开它的目录
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer('C:\\\\Users\\\\luoji\\\\Desktop\\\\firstep\\\\.scratch\\\\code-editor-refine\\\\sample-proj-11'))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click(); true`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
console.log("big.c lines:", await Eval(`document.querySelector('#code-viewer .code-ta').value.split('\\n').length`));
await Eval(`(() => { const box = document.getElementById('code-viewer'); box.scrollTop = box.scrollHeight; box.dispatchEvent(new Event('scroll',{bubbles:true})); return true; })()`);
await new Promise((r) => setTimeout(r, 600));
console.log("big scrollTop:", await Eval(`document.getElementById('code-viewer').scrollTop`));
// 2) 打开 beep.c（同窗切换）
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('modules/beep/code/beep.c'), true).catch((e) => 'ERR:' + e.message)`);
await new Promise((r) => setTimeout(r, 1200));
// 注意：当前目录又被切到 sample-proj-11；先切回 2024H
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer('C:\\\\Users\\\\luoji\\\\Desktop\\\\2024H_Auto_Car_MSPM0'))`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.openEditorFile('modules/beep/code/beep.c')).then(() => true).catch((e) => 'ERR:' + e.message)`);
await new Promise((r) => setTimeout(r, 1200));
const d = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const gutter = document.querySelector('#code-viewer .code-gutter');
  const hl = document.querySelector('#code-viewer .code-hl');
  const box = document.getElementById('code-viewer');
  const nos = gutter ? Array.from(gutter.querySelectorAll('.code-gutter-line')).map(e => Number(e.dataset.codeLine)) : [];
  const br = box.getBoundingClientRect();
  const lineHits = [];
  if (hl) {
    for (const ln of Array.from(hl.querySelectorAll('.code-hl-line'))) {
      const r = ln.getBoundingClientRect();
      if (r.top >= br.top && r.top < br.bottom) {
        const el = document.elementFromPoint(br.right - 40, r.top + r.height / 2);
        lineHits.push({ no: Number(ln.dataset.codeLine), el: el ? (el.className || el.tagName) : null });
      }
    }
  }
  return {
    taLines: ta ? ta.value.split('\\n').length : 0,
    gutterCount: nos.length, gutterFirst: nos[0], gutterLast: nos[nos.length - 1],
    spacers: document.querySelectorAll('#code-viewer .code-window-spacer').length,
    scrollTop: box.scrollTop,
    lineHits: lineHits.slice(0, 6).concat(lineHits.slice(-4)),
  };
})()`);
console.log(JSON.stringify(d, null, 2));
const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(ROOT, ".scratch", "code-editor-refine", "diag-switch.png"), Buffer.from(shot.result.data, "base64"));
process.exit(0);
