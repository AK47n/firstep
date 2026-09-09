// 冒烟（code-page-vscode-overhaul/07 代码区视觉细节）：真实浏览器验证缩进
// 引导线渲染、括号配对描边、Ctrl+滚轮缩放后三明治对齐、深/浅双主题截图。
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
const CODE = '#include <stdio.h>\n\nvoid f(void) {\n    if (1) {\n        printf("x\\n");\n    }\n}\n';
writeFileSync(join(SAMPLE, "main.c"), CODE);

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
// CDP 超时守卫（第七轮）：渲染进程偶发无响应时命令永不返回 → 脚本静默挂死。
// 20s 无响应即抛错，让失败可见（而不是卡死）。
const cdp = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++seq;
    const t = setTimeout(() => {
      if (pending.has(id)) { pending.delete(id); reject(new Error("CDP 无响应（20s）: " + method + " —— 页面可能已挂死")); }
    }, 20000);
    pending.set(id, (msg) => { clearTimeout(t); resolve(msg); });
    ws.send(JSON.stringify({ id, method, params }));
  });
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
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')
  && (document.querySelector('#code-viewer .code-ta')?.value || '').includes('#include')`);

// 缩进引导线渲染（line4: 1 条、line5: 2 条）
const guideCount = await Eval(`document.querySelectorAll('#code-viewer .code-marks .code-mark-guide').length`);
check("缩进引导线渲染（≥3 条）", guideCount >= 3, "count=" + guideCount);

// 括号配对描边：光标落在第 4 行 { 之后 → 两段 .code-mark-bracket
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const p = ta.value.indexOf('{') + 1;
  ta.setSelectionRange(p, p);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
await waitFor(`document.querySelectorAll('#code-viewer .code-marks .code-mark-bracket').length === 2`);
check("括号配对描边（两段）", true);

// 缩放对齐：--code-zoom 1.5 → gutter 行高 == 高亮行高（1:1 不漂移）
await Eval(`document.querySelector('.code-view').style.setProperty('--code-zoom', '1.5'); true`);
await new Promise((r) => setTimeout(r, 200));
const align = await Eval(`(() => {
  const g = document.querySelector('#code-viewer .code-gutter-line');
  const h = document.querySelector('#code-viewer .code-hl-line');
  if (!g || !h) return null;
  return { gh: g.getBoundingClientRect().height, hh: h.getBoundingClientRect().height };
})()`);
check("缩放后 gutter 与高亮行高一致", !!align && Math.abs(align.gh - align.hh) < 0.51, JSON.stringify(align));
const guideCountZ = await Eval(`document.querySelectorAll('#code-viewer .code-marks .code-mark-guide').length`);
check("缩放后引导线仍渲染", guideCountZ >= 3);

// 深色截图
let shot = await cdp("Page.captureScreenshot", { format: "png" });
if (shot.result?.data) writeFileSync(join(OUT, "shot-07-visual-dark.png"), Buffer.from(shot.result.data, "base64"));
check("深色截图已保存", !!shot.result?.data);

// 浅色截图
await Eval(`document.documentElement.setAttribute('data-theme', 'light'); true`);
await new Promise((r) => setTimeout(r, 300));
const lightGuide = await Eval(`document.querySelectorAll('#code-viewer .code-marks .code-mark-guide').length`);
check("浅色主题引导线仍渲染", lightGuide >= 3);
shot = await cdp("Page.captureScreenshot", { format: "png" });
if (shot.result?.data) writeFileSync(join(OUT, "shot-07-visual-light.png"), Buffer.from(shot.result.data, "base64"));
check("浅色截图已保存", !!shot.result?.data);

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
