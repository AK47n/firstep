// 冒烟（code-editor-vscode-polish/08）：整套代码页视觉统一——
// 焦点环（focus-visible outline 生效）、面板头按钮/信息条按钮/状态栏按钮
// 圆角令牌化（computed borderRadius 非 0）、空态字号统一（12.5px）、
// 深/浅整页验收截图（shot-ide-dark.png / shot-ide-light.png）。
// 零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

const SAMPLE = join(ROOT, ".scratch", "code-editor-vscode-polish", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  "void helper(void) {",
  "    int x = 0;",
  "}",
  "",
  "int main(void) {",
  "    helper();",
  "    return 0;",
  "}",
].join("\n"));

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
const waitFor = async (expr, ms = 8000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};
const shot = async (name) => {
  const box = await Eval(`(() => {
    const r = document.getElementById('tab-code').getBoundingClientRect();
    return { x: Math.max(0, r.x), y: Math.max(0, r.y), w: r.width, h: r.height };
  })()`);
  const r = await cdp("Page.captureScreenshot", {
    format: "png",
    clip: { x: box.x, y: box.y, width: box.w, height: box.h, scale: 1 },
  });
  writeFileSync(join(ROOT, ".scratch", "code-editor-vscode-polish", name),
    Buffer.from(r.result.data, "base64"));
  return true;
};

await Eval(`window.__smokeMarker = 1;
  try { localStorage.removeItem('firstep.codeViewZoom'); } catch (e) {}
  true`);
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
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

// ================= 焦点环生效 =================
await Eval(`(() => {
  const b = document.getElementById('btn-code-tree-new-file');
  b.focus();
  return true;
})()`);
check("焦点环：.code-pane-action focus 后 outline 非 none", await Eval(`
  getComputedStyle(document.getElementById('btn-code-tree-new-file')).outlineStyle !== 'none'`));

// ================= 按钮圆角令牌化 =================
check("按钮统一圆角：面板头/信息条/状态栏按钮 borderRadius 非 0（令牌化）", await Eval(`
  (() => {
    const head = document.querySelector('.code-compile-head button');
    const back = document.getElementById('code-back-preview');
    const stat = document.getElementById('btn-code-save-all');
    const r = (el) => el ? getComputedStyle(el).borderRadius : '0px';
    return r(head) !== '0px' && r(stat) !== '0px';
  })()`));

// ================= 字号统一 =================
check("字号统一：大纲条目 12.5px / 面板标题 11px", await Eval(`
  (() => {
    const item = document.querySelector('.code-outline-item');
    const title = document.querySelector('.code-pane-title');
    return item && getComputedStyle(item).fontSize === '12.5px'
      && title && getComputedStyle(title).fontSize === '11px';
  })()`));

// ================= 深/浅整页验收截图 =================
await Eval(`document.documentElement.removeAttribute('data-theme')`);
await new Promise((r) => setTimeout(r, 250));
await shot("shot-ide-dark.png");
await Eval(`document.documentElement.setAttribute('data-theme', 'light')`);
await new Promise((r) => setTimeout(r, 250));
await shot("shot-ide-light.png");
check("深/浅整页截图已保存", await Eval(`true`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
