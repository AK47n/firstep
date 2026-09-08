// 冒烟（code-page-vscode-overhaul/08 滚动窗口化渲染）：真实浏览器验证
// 5000 行 .c 文件——DOM 内行数有界（远小于 5000）、滚动到中部窗口行号正确、
// 滚动流畅（同窗零 DOM 变更）、输入后窗口仍正确、行号/gutter/高亮对齐。
// CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-page-vscode-overhaul");
const SAMPLE = join(OUT, "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
const big = [];
for (let i = 1; i <= 5000; i++) {
  big.push(`int fn_${i}(int x) { return x + ${i}; }  // line ${i}`);
}
writeFileSync(join(SAMPLE, "big.c"), big.join("\n") + "\n");

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
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
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

await Eval(`window.__smokeMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]')?.click()`);
await waitFor(`(document.querySelector('#code-viewer .code-ta')?.value || '').length > 100000`);

const domLines = () => Eval(`({
  hl: document.querySelectorAll('#code-viewer .code-hl-line').length,
  gut: document.querySelectorAll('#code-viewer .code-gutter-line').length,
  firstHl: document.querySelector('#code-viewer .code-hl-line')?.dataset.codeLine || '0',
  lastHl: [...document.querySelectorAll('#code-viewer .code-hl-line')].pop()?.dataset.codeLine || '0',
  firstGut: document.querySelector('#code-viewer .code-gutter-line')?.dataset.codeLine || '0',
  taLen: document.querySelector('#code-viewer .code-ta').value.length,
})`);

// 初始：窗口有界（远小于 5000 行，含 overscan）
let d = await domLines();
check("初始 DOM 行数有界（< 400）", d.hl < 400 && d.gut < 400, "hl=" + d.hl + " gut=" + d.gut);
check("初始窗口从第 1 行开始", d.firstHl === "1" && d.firstGut === "1");
check("textarea 全量", d.taLen > 100000);

// 滚动到中部：窗口行号正确 + DOM 仍有界
await Eval(`(() => {
  const b = document.getElementById('code-viewer');
  b.scrollTop = b.scrollHeight * 0.5;
  return true;
})()`);
await new Promise((r) => setTimeout(r, 400));   // rAF 节流
d = await domLines();
const hlCount = d.hl;
const first = parseInt(d.firstHl, 10);
const last = parseInt(d.lastHl, 10);
check("中部滚动后 DOM 仍有界", hlCount < 400 && hlCount > 50, "hl=" + hlCount);
check("中部窗口行号区间正确（~2500 附近）", first > 2300 && first < 2700 && last > first, "[" + first + "," + last + "]");
check("行号与高亮窗口一致", d.firstGut === d.firstHl);

// 窗口内滚动（微小位移）→ DOM 不变（零重建）
const before = await domLines();
await Eval(`(() => { const b = document.getElementById('code-viewer'); b.scrollTop += 5; return true; })()`);
await new Promise((r) => setTimeout(r, 400));
const after = await domLines();
check("窗口内滚动零 DOM 变更", before.hl === after.hl && before.firstHl === after.firstHl);

// 大跨步滚动（跨窗口）→ 窗口重画
await Eval(`(() => { const b = document.getElementById('code-viewer'); b.scrollTop = 0; return true; })()`);
await new Promise((r) => setTimeout(r, 400));
d = await domLines();
check("回顶后窗口从第 1 行开始", d.firstHl === "1");

// 输入仍正常（末尾追加字符 → 窗口重建且值正确）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
  ta.value += 'x';
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  const b = document.getElementById('code-viewer');
  b.scrollTop = b.scrollHeight;
  return true;
})()`);
await new Promise((r) => setTimeout(r, 500));
check("输入后 textarea 值正确", await Eval(`document.querySelector('#code-viewer .code-ta').value.endsWith('x')`));
d = await domLines();
check("输入后窗口重新对齐（尾部行号）", parseInt(d.lastHl, 10) > 4900, "last=" + d.lastHl);

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
