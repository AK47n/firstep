// 冒烟（code-page-vscode-overhaul/09 输入窗口化+阈值调整）：真实浏览器验证
// 5000 行 .c 逐键输入同步耗时 < 50ms（优化前 150-220ms；含窗口缓存/零强制
// 布局路径）、高亮阈值放宽后 5000 行仍真彩色（tok- span 存在）、窗口正确。
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
await waitFor(`(document.querySelector('#code-viewer .code-ta')?.value.length || 0) > 100000`);

// 阈值放宽（1MB）：5000 行 .c 仍有真彩色 token
check("5000 行真彩色（阈值放宽生效）", await Eval(`document.querySelectorAll('#code-viewer .code-hl span').length > 100`));

// 逐键输入同步耗时（光标文件尾；热身后取 10 次均值）
const res = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
  const times = [];
  for (let k = 0; k < 12; k++) {
    ta.value += 'x';
    const t0 = performance.now();
    ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
    if (k >= 2) times.push(performance.now() - t0);
  }
  return { avg: times.reduce((a, b) => a + b, 0) / times.length, max: Math.max(...times) };
})()`);
check("逐键输入同步 < 50ms（均值）", res.avg < 50, "avg=" + res.avg.toFixed(1) + "ms max=" + res.max.toFixed(1));
check("逐键输入同步 < 150ms（峰值——容忍 GC/预热抖动）", res.max < 150, "max=" + res.max.toFixed(1));

// 窗口仍正确（行数有界）
check("DOM 行数有界", await Eval(`document.querySelectorAll('#code-viewer .code-hl-line').length < 400`));

// 截图
const shot = await cdp("Page.captureScreenshot", { format: "png" });
if (shot.result?.data) writeFileSync(join(OUT, "shot-09-input-window-dark.png"), Buffer.from(shot.result.data, "base64"));
check("深色截图已保存", !!shot.result?.data);

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
