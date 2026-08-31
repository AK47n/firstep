// 基线/验收截图：打开 webapp → 「代码」tab → openCodeViewer(样本工程) → 点 main.c →
// 选第 1 行（当前行高亮）→ 视口 1600×1000 截图；顺带抓若干计算样式供改版对比。
// 用法：node .scratch/ccs-ref/shot-codeview.mjs <outPng> [theme:dark|light] [openFile]
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(process.cwd());
const SAMPLE = join(ROOT, ".scratch", "code-viewer", "sample-proj");
const [outPng, theme = "dark", openFile = "main.c"] = process.argv.slice(2);
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

const fetchT = async (url, ms = 5000, method = "GET") => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { method, signal: ctl.signal }); } finally { clearTimeout(t); }
};

// 找 webapp 页面；没有则 PUT /json/new 开一个
function findPage(list) {
  return list.find((t) => t.type === "page" && t.url.startsWith(pageUrl))
    || list.find((t) => t.type === "page" && !t.url.includes("3596") && t.url !== "about:blank")
    || null;
}
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
let page = findPage(targets);
if (!page) {
  const created = await (await fetchT(`http://127.0.0.1:${CDP}/json/new?${encodeURIComponent(pageUrl)}`, 10000, "PUT")).json();
  page = created;
  await new Promise((r) => setTimeout(r, 2000));
}
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
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

await Eval(`window.__shotMarker = 1`);
if (theme === "light") await Eval(`try { localStorage.setItem('firstep.theme', 'light'); } catch {}`);
else await Eval(`try { localStorage.removeItem('firstep.theme'); } catch {}`);
await Eval(`try { localStorage.removeItem('firstep.codeTreeWidth'); localStorage.removeItem('firstep.codeViewZoom'); } catch {}`);
await cdp("Page.reload", { ignoreCache: true });
if (!(await waitFor(`document.readyState === 'complete' && !window.__shotMarker && !!document.getElementById('code-viewer')`, 15000))) {
  console.error("页面未就绪"); process.exit(1);
}
await Eval(`document.querySelector('nav button[data-tab="code"]')?.click()`);
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length === 4`);
if (openFile !== "none") {
  await Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(openFile)}]')?.click()`);
  await waitFor(`!!document.querySelector('#code-viewer .code-gutter')`);
  await Eval(`document.querySelectorAll('#code-viewer .code-pre-line')[0]?.click()`);
}
const styles = await Eval(`(() => {
  const pick = (sel, props) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    const o = {};
    for (const p of props) o[p] = cs.getPropertyValue(p).trim() || cs[p];
    return o;
  };
  return {
    theme: (document.documentElement.getAttribute('data-theme') || 'dark'),
    page: pick('body', ['backgroundColor', 'color']),
    card: pick('#tab-code .card', ['backgroundColor', 'border', 'borderRadius', 'padding', 'boxShadow']),
    layout: pick('.code-layout', ['gridTemplateColumns', 'gap']),
    pane: pick('.code-pane', ['backgroundColor', 'border', 'borderRadius', 'padding']),
    paneMain: pick('.code-pane-main', ['backgroundColor']),
    view: pick('.code-view', ['backgroundColor', 'border', 'borderRadius']),
    gutter: pick('.code-gutter', ['backgroundColor']),
    gutterLine: pick('.code-gutter-line', ['color', 'fontSize', 'lineHeight']),
    pre: pick('.code-pre', ['fontFamily', 'fontSize', 'lineHeight', 'color']),
    tab: pick('.code-file-tab', ['backgroundColor', 'border', 'borderBottom', 'padding', 'fontSize']),
    treeItem: pick('.code-tree-file button', ['color', 'fontSize', 'padding']),
    paneTitle: pick('.code-pane-title', ['fontSize', 'color']),
    headH: pick('.site-header', ['height']),
    toolbar: pick('.code-toolbar', ['fontSize']),
  };
})()`);
console.log(JSON.stringify(styles, null, 1));
const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(outPng, Buffer.from(shot.result.data, "base64"));
console.log("shot -> " + outPng);
process.exit(0);
