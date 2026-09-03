// 守卫探针（工单 code-editor-opt/03）：编辑器三层几何对齐矩阵
// ——gutter 行号 / 高亮层行 / 标记层行 / 当前行高亮 在 缩放 × 折叠 × 主题
// 组合下逐行 top 对齐（容差 1px）。历史三次线上错位（行号截止/窗口错位/
// 折叠行号漂移）均为此矩阵边缘组合漏测。
// 用法：node .scratch/code-editor-opt/probe-align.mjs；CDP 9251 + webapp 8000。
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
const shot = async (name) => {
  const r = await cdp("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
  writeFileSync(join(OUT, name), Buffer.from(r.result.data, "base64"));
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
await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0, 0); return true; })()`);
await new Promise((r) => setTimeout(r, 300));

// 每次单元格重设：缩放（--code-zoom + codeWindowRefresh）+ 主题 + 光标行 1；
// 折叠通过编辑器 keydown 管线（Ctrl+Shift+[ 在第一行折叠 f0 区）
const setCell = (theme, pct, fold) => Eval(`(async () => {
  document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)});
  try { localStorage.setItem('firstep.theme', ${JSON.stringify(theme)}); } catch (e) {}
  const view = document.getElementById('code-viewer');
  view.style.setProperty('--code-zoom', String(${pct} / 100));
  const ce = await import('/js/ui/codeeditor.js');
  ce.codeWindowRefresh();
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(0, 0);
  const key = (k) => ta.dispatchEvent(new KeyboardEvent('keydown', {
    key: k, code: k === '[' ? 'BracketLeft' : 'BracketRight',
    ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }));
  key(']');   // 先展开（若 f0 区已折叠）
  ${fold ? "key('[');" : ""}  // 目标折叠态
  return true;
})()`);

const collect = () => Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const tops = (sel) => Array.from(box.querySelectorAll(sel))
    .map((el) => Math.round(el.getBoundingClientRect().top * 2) / 2)
    .sort((a, b) => a - b);
  const gutTops = tops('.code-gutter-line');
  const hlTops = tops('.code-hl-line');
  const marksTops = tops('.code-marks-line');
  const near = (a, b) => Math.abs(a - b) <= 1;
  const bad = [];
  // 三层行 top 集合两两互有对应（折叠态 gutter 用模型行号、hl 用视图行号，
  // 编号不同但每行 top 必须 1:1——历史错位正是 top 集合不齐/偏移）
  for (const t of hlTops) if (!gutTops.some((g) => near(g, t))) bad.push({ kind: 'hl-orphan', top: t });
  for (const t of gutTops) if (!hlTops.some((h) => near(h, t))) bad.push({ kind: 'gut-orphan', top: t });
  for (const t of marksTops) if (!hlTops.some((h) => near(h, t))) bad.push({ kind: 'marks-orphan', top: t });
  // 当前行：gutter active 与 hl active 顶部对齐
  const ga = box.querySelector('.code-gutter-line.active');
  const ha = box.querySelector('.code-hl-line.active');
  if (ga && ha && !near(ga.getBoundingClientRect().top, ha.getBoundingClientRect().top)) {
    bad.push({ kind: 'active', g: Math.round(ga.getBoundingClientRect().top * 100) / 100, h: Math.round(ha.getBoundingClientRect().top * 100) / 100 });
  }
  return { gutterCount: gutTops.length, hlCount: hlTops.length, marksCount: marksTops.length, bad };
})()`);

const results = [];
let fails = 0;
for (const theme of ["light", "dark"]) {
  for (const pct of [100, 150, 200]) {
    for (const fold of [false, true]) {
      await setCell(theme, pct, fold);
      await new Promise((r) => setTimeout(r, 350));
      const c = await collect();
      const ok = c.bad.length === 0;
      if (!ok) fails++;
      results.push({ theme, pct: pct + "%", fold: fold ? "on" : "off", ok, ...c });
      console.log((ok ? "PASS" : "FAIL") + " " + theme + " " + pct + "% fold=" + fold
        + " gutter=" + c.gutterCount + " hl=" + c.hlCount + " marks=" + c.marksCount
        + (c.bad.length ? " bad=" + JSON.stringify(c.bad.slice(0, 5)) : ""));
    }
  }
  await shot("align-" + theme + ".png");
}
writeFileSync(join(OUT, "align-results.json"), JSON.stringify(results, null, 2));
console.log(fails ? "总失败单元格: " + fails : "全矩阵 PASS");
process.exit(fails ? 1 : 0);
