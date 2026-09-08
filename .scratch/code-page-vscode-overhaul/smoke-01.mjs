// 冒烟（code-page-vscode-overhaul/01 行操作与反缩进）：真实浏览器验证
// Shift+Tab 反缩进 / Ctrl+Shift+K 删行 / Alt+↑↓ 移动行 / Shift+Alt+↑↓ 复制行 /
// Ctrl+L 选整行；深色主题截图存档。零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-page-vscode-overhaul");
const SAMPLE = join(OUT, "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  "void helper(void) {",
  "    int x = 0;",
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

// 工具：设定文本+选区（经 input 事件保持模型一致），按键，读结果
const setText = (text, s, e) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.value = ${JSON.stringify(text)};
  ta.setSelectionRange(${s}, ${e});
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
const press = (opts) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.dispatchEvent(new KeyboardEvent('keydown', ${JSON.stringify(opts)}));
  return true;
})()`);
const readTa = () => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  return { value: ta.value, selStart: ta.selectionStart, selEnd: ta.selectionEnd };
})()`);
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// ---- Shift+Tab 多行反缩进 ----
await setText("    a\n      b\nc", 0, 14);
await press({ key: "Tab", shiftKey: true, bubbles: true, cancelable: true });
let r = await readTa();
check("Shift+Tab 多行反缩进", eq(r, { value: "a\n  b\nc", selStart: 0, selEnd: 5 }), JSON.stringify(r));

// ---- Ctrl+Shift+K 删行 ----
await setText("a\nb\nc", 2, 2);
await press({ key: "k", ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true });
r = await readTa();
check("Ctrl+Shift+K 删除中间行", eq(r, { value: "a\nc", selStart: 2, selEnd: 2 }), JSON.stringify(r));

// ---- Alt+↓ 移动行 ----
await setText("a\nb\nc", 0, 0);
await press({ key: "ArrowDown", altKey: true, bubbles: true, cancelable: true });
r = await readTa();
check("Alt+↓ 下移当前行（光标随行）", eq(r, { value: "b\na\nc", selStart: 2, selEnd: 2 }), JSON.stringify(r));

// ---- Shift+Alt+↓ 复制行 ----
await setText("a\nb", 2, 2);
await press({ key: "ArrowDown", altKey: true, shiftKey: true, bubbles: true, cancelable: true });
r = await readTa();
check("Shift+Alt+↓ 复制行（光标落副本）", eq(r, { value: "a\nb\nb", selStart: 4, selEnd: 4 }), JSON.stringify(r));

// ---- Ctrl+L 选整行 ----
await setText("abc\ndef\nghi", 5, 5);
await press({ key: "l", ctrlKey: true, bubbles: true, cancelable: true });
r = await readTa();
check("Ctrl+L 选整行（含行尾换行）", eq({ v: r.value, s: r.selStart, e: r.selEnd },
  { v: "abc\ndef\nghi", s: 4, e: 8 }), JSON.stringify(r));

// ---- 只读文件不响应 ----
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.readOnly = true; return true;
})()`);
await setText("a\nb", 0, 0);
await press({ key: "ArrowDown", altKey: true, bubbles: true, cancelable: true });
r = await readTa();
check("只读 textarea 行操作不生效", eq(r, { value: "a\nb", selStart: 0, selEnd: 0 }), JSON.stringify(r));
await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.readOnly = false; return true; })()`);

// ---- 帮助弹窗渲染新条目 ----
await Eval(`document.getElementById('btn-code-shortcuts')?.click(); true`);
const helpOk = await waitFor(`(document.body.textContent || '').includes('反缩进选中行')
  && (document.body.textContent || '').includes('删除当前行（组）')
  && (document.body.textContent || '').includes('选中整行（重复按扩展）')`);
check("帮助弹窗渲染行操作条目", helpOk);
await Eval(`document.querySelector('.code-shortcuts-modal .modal-close, .code-shortcuts-modal [data-close]')?.click()
  ?? document.querySelector('.code-shortcuts-modal')?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); true`);

// ---- 深色主题截图 ----
await setText("int main(void) {\n    int x = 1;\n    return x;\n}\n", 16, 16);
await Eval(`document.documentElement.removeAttribute('data-theme')`);
await new Promise((r) => setTimeout(r, 250));
const box = await Eval(`(() => {
  const r = document.getElementById('code-viewer').getBoundingClientRect();
  return { x: Math.max(0, r.x), y: Math.max(0, r.y), w: r.width, h: r.height };
})()`);
const shot = await cdp("Page.captureScreenshot", {
  format: "png",
  clip: { x: box.x, y: box.y, width: box.w, height: box.h, scale: 1 },
});
writeFileSync(join(OUT, "shot-01-lineops-dark.png"), Buffer.from(shot.result.data, "base64"));
check("深色截图已保存", true);

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
