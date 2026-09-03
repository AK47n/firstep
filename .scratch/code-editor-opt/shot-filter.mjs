// 聚焦截图（code-editor-opt）：浅色主题下，侧栏轮廓面板展开时的过滤框区域
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-opt");
const SAMPLE = join(ROOT, ".scratch", "code-editor-refine", "sample-proj-11");

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
const shotClip = async (name, clip) => {
  const shot = await cdp("Page.captureScreenshot", { format: "png", clip });
  writeFileSync(join(OUT, name), Buffer.from(shot.result.data, "base64"));
  console.log("saved", name);
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
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]').click(); true`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await Eval(`document.documentElement.setAttribute('data-theme','light'); localStorage.setItem('firstep.theme','light'); true`);
await new Promise((r) => setTimeout(r, 300));
// 展开大纲侧栏（先点 rail 按钮；若面板已开则再点一次非 rail 同步态）
await Eval(`(() => {
  const rail = document.querySelector('.code-side-rail-btn[data-code-side="outline"]');
  if (rail) { rail.click(); return 'rail'; }
  const tab = document.querySelector('[data-code-side="outline"]:not(.code-side-rail-btn)');
  if (tab) { tab.click(); return 'tab'; }
  return 'none';
})()`);
await new Promise((r) => setTimeout(r, 500));
const rect = await Eval(`(() => {
  const el = document.getElementById('code-outline-filter');
  const r = el.getBoundingClientRect();
  return { x: r.x, y: r.y, width: r.width, height: r.height, focused: document.activeElement === el };
})()`);
console.log("rect:", JSON.stringify(rect));
await shotClip("focus-filter-light.png", { x: rect.x - 20, y: rect.y - 20, width: rect.width + 40, height: rect.height + 80, scale: 2 });
process.exit(0);
