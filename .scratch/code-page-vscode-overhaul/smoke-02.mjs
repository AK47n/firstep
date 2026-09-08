// 冒烟（code-page-vscode-overhaul/02 Ctrl+/ 注释切换）：真实浏览器验证
// .c 逐行 // 加/去、含 /* */ 选区切块、XML 逐行 <!-- -->；深色截图存档。
// 零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-page-vscode-overhaul");
const SAMPLE = join(OUT, "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), "int main(void) { return 0; }\n");
writeFileSync(join(SAMPLE, "app.xml"), "<root/>\n");

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
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

const setText = (text, s, e) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.value = ${JSON.stringify(text)};
  ta.setSelectionRange(${s}, ${e});
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
const pressCtrlSlash = () => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.dispatchEvent(new KeyboardEvent('keydown',
    { key: '/', ctrlKey: true, bubbles: true, cancelable: true }));
  return true;
})()`);
const readTa = () => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  return { value: ta.value, selStart: ta.selectionStart, selEnd: ta.selectionEnd };
})()`);
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// 逐行加（光标）→ 再按去（光标回原列）
await setText("int x;", 3, 3);
await pressCtrlSlash();
let r = await readTa();
check("C 单行加注释", eq(r, { value: "// int x;", selStart: 6, selEnd: 6 }), JSON.stringify(r));
await pressCtrlSlash();
r = await readTa();
check("C 单行去注释", eq(r, { value: "int x;", selStart: 3, selEnd: 3 }), JSON.stringify(r));

// 多行逐行加（选区含行尾换行 → 扩展）
await setText("int a;\nint b;", 0, 7);
await pressCtrlSlash();
r = await readTa();
check("C 多行逐行加注释（选区扩展为整段）", eq(r, { value: "// int a;\n// int b;", selStart: 0, selEnd: 19 }), JSON.stringify(r));
await pressCtrlSlash();
r = await readTa();
check("C 多行去注释", eq(r, { value: "int a;\nint b;", selStart: 0, selEnd: 13 }), JSON.stringify(r));

// 块注释去（精确块选区）
await setText("/*int x;\nint y;*/", 0, 17);
await pressCtrlSlash();
r = await readTa();
check("C 块注释去（解除包围）", eq(r, { value: "int x;\nint y;", selStart: 0, selEnd: 13 }), JSON.stringify(r));

// XML 逐行加/去
await Eval(`document.querySelector('#code-tree [data-code-file="app.xml"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')
  && (document.querySelector('#code-viewer .code-ta')?.value || '').length < 20`);
await setText("<a>x</a>", 0, 8);
await pressCtrlSlash();
r = await readTa();
check("XML 逐行加注释", eq(r, { value: "<!-- <a>x</a> -->", selStart: 0, selEnd: 17 }), JSON.stringify(r));
await pressCtrlSlash();
r = await readTa();
check("XML 逐行去注释", eq(r, { value: "<a>x</a>", selStart: 0, selEnd: 8 }), JSON.stringify(r));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
