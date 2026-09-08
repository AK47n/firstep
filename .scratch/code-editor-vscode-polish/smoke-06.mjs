// 冒烟（code-editor-vscode-polish/06）：括号配对与自动闭合——
// '{' 自动闭合（{} 光标居中）→ '(return)' 选区包裹 → ')' 跳过（不重复）→
// Backspace 空()对删对 → 光标在 '(' 上配对高亮（.code-mark-bracket ×2）→
// 光标移开高亮消失。零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

const SAMPLE = join(ROOT, ".scratch", "code-editor-vscode-polish", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  "int main(void) {",
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

await Eval(`window.__smokeMarker = 1;
  try { localStorage.removeItem('firstep.codeViewZoom'); } catch (e) {}
  true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-viewer') && !!document.getElementById('code-tabs')`);
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
check("打开 main.c → 三明治就绪", await waitFor(`
  !!document.querySelector('#code-viewer .code-ta')`));

// ================= '{' 自动闭合 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: '{', bubbles: true, cancelable: true }));
  return true;
})()`);
check("'{' → 尾部出现 {} 且光标居中", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return ta.value.endsWith('{}')
      && ta.selectionStart === ta.value.length - 1 && ta.selectionEnd === ta.value.length - 1;
  })()`));

// ================= '(return)' 选区包裹 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const at = ta.value.indexOf('return');
  ta.setSelectionRange(at, at + 6);
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: '(', bubbles: true, cancelable: true }));
  return true;
})()`);
check("选中 return 输入 '(' → (return) 包裹", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return ta.value.includes('(return)') && ta.selectionStart === ta.value.indexOf('(return)') + 1;
  })()`));

// ================= ')' 跳过（先造空对） =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: '(', bubbles: true, cancelable: true }));
  return true;
})()`);
check("尾部输入 '(' → 出现 () 空对（光标居中）", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return ta.value.endsWith('()') && ta.selectionStart === ta.value.length - 1;
  })()`));
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.length - 1, ta.value.length - 1);   // 光标在 () 之间
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: ')', bubbles: true, cancelable: true }));
  return true;
})()`);
check("空 () 对中间输入 ')' → 跳过不重复（值不变、光标到 ) 后）", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return ta.value.endsWith('()') && ta.selectionStart === ta.value.length;
  })()`));

// ================= 空括号对退格删对 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.length - 1, ta.value.length - 1);   // 光标在 () 之间
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true, cancelable: true }));
  return true;
})()`);
check("空 () 对中间 Backspace → 整对删除", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return !ta.value.endsWith('()') && ta.value.endsWith('{}');
  })()`));

// ================= 配对高亮 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const at = ta.value.indexOf('main') + 4;   // 'main(' —— 光标在 '(' 上
  ta.setSelectionRange(at, at);
  ta.dispatchEvent(new Event('keyup', { bubbles: true }));
  return true;
})()`);
check("光标在 '(' 上 → .code-mark-bracket ×2", await waitFor(`
  document.querySelectorAll('#code-viewer .code-mark-bracket').length === 2`));
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new Event('keyup', { bubbles: true }));
  return true;
})()`);
check("光标移开 → 括号标记消失", await waitFor(`
  document.querySelectorAll('#code-viewer .code-mark-bracket').length === 0`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
