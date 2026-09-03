// 探针（工单 code-editor-opt/06）：精确测量打开 6000 行 .c 的耗时
// （openEditorFile await 计时——含 fetch + renderPane + winBuild + 首帧窗口渲染）；
// 同时测打开后立即滚动到中部/底部并读窗口行高亮是否完整。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-opt");
const SAMPLE = join(ROOT, ".scratch", "code-editor-refine", "sample-proj-11");
mkdirSync(OUT, { recursive: true });

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
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await Eval(`window.__probe = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  try {
    if (await Eval(`document.readyState === 'complete' && !window.__probe && !!document.getElementById('code-viewer')`)) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);

const open = await Eval(`(async () => {
  // fetch 阶段单独计时（GET /api/code/file 同参）
  const tF = performance.now();
  const resp = await fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(SAMPLE)}) + '&path=' + encodeURIComponent('big.c'));
  const data = await resp.json();
  const fetchMs = performance.now() - tF;
  const t0 = performance.now();
  const ce = await import('/js/ui/codeeditor.js');
  await ce.openEditorFile('big.c');
  const t1 = performance.now();
  // 打开后：首帧窗口高亮行数 / 标记行数 / gutter 行数
  const box = document.getElementById('code-viewer');
  const hl = box.querySelectorAll('.code-hl-line').length;
  const marks = box.querySelectorAll('.code-marks-line').length;
  const gut = box.querySelectorAll('.code-gutter-line').length;
  // 滚到中部再滚到底读窗口（惰性补缺验证）
  box.scrollTop = Math.floor(box.scrollHeight * 0.6);
  const midHl = box.querySelectorAll('.code-hl-line').length;
  box.scrollTop = box.scrollHeight;
  const endHl = box.querySelectorAll('.code-hl-line').length;
  return { fetchMs: Math.round(fetchMs * 100) / 100,
    renderMs: Math.round((t1 - t0) * 100) / 100,
    openMs: Math.round((t1 - tF) * 100) / 100,
    chars: data.content ? data.content.length : 0,
    firstHl: hl, marks, gut, midHl, endHl };
})()`);
console.log(JSON.stringify(open, null, 2));
writeFileSync(join(OUT, "open-probe.json"), JSON.stringify(open, null, 2));
process.exit(0);
