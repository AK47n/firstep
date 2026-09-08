// debug：逐步诊断 Tab / Enter / 手打 / redo——实际值打印 + 超时保护
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const SAMPLE = join(ROOT, ".scratch", "editor-textarea-viewport", "sample-proj");
const fetchT = async (url, ms = 5000) => { const c = new AbortController(); const t = setTimeout(() => c.abort(), ms); try { return await fetch(url, { signal: c.signal }); } finally { clearTimeout(t); } };
let targets = null;
for (let i = 0; i < 50 && !targets; i++) { try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {} if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300)); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
if (!page) { console.log("no page"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr, label = "") => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error((label || "eval") + " 异常: " + JSON.stringify(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails));
  return r.result?.result?.value;
};
const step = async (label, fn) => {
  try { const v = await Promise.race([fn(), new Promise((_, rej) => setTimeout(() => rej(new Error("STEP TIMEOUT " + label)), 10000))]); console.log("OK", label, typeof v === "string" ? v : JSON.stringify(v)); return v; }
  catch (e) { console.log("ERR", label, e.message); return null; }
};
const waitFor = async (expr, ms = 10000) => { for (let i = 0; i < ms / 200; i++) { try { if (await Eval(expr)) return true; } catch {} await new Promise((r) => setTimeout(r, 200)); } return false; };

await step("reload", () => cdp("Page.reload", { ignoreCache: true }));
await new Promise((r) => setTimeout(r, 2500));
await step("open viewer", () => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`));
console.log("tree ready:", await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`));
await step("click main.c", () => Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click(); true`));
console.log("ta ready:", await waitFor(`!!document.querySelector('#code-viewer .code-ta')`));

const dump = () => Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const tab = ce.getActiveTab();
  return { path: tab && tab.path, model: tab && tab.content, ta: ta && ta.value,
    sel: ta ? [ta.selectionStart, ta.selectionEnd] : null,
    taLen: ta ? ta.value.length : -1, modelLen: tab ? tab.content.length : -1 };
})()`);

await step("after open", dump);
await step("set abc", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.value = 'abc\\n'; ta.setSelectionRange(0, 0); ta.dispatchEvent(new InputEvent('input', { bubbles: true })); return true; })()`));
await step("after set abc", dump);
await step("press Tab", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })); return true; })()`));
await step("after Tab", dump);
await step("press Enter", () => Eval(`(async () => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); const ce = await import('/js/ui/codeeditor.js'); const m = ce.getActiveTab().content; ta.setSelectionRange(Math.min(0, m.length), Math.min(0, m.length)); ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })); return true; })()`));
await step("after Enter", dump);
await step("type x trusted", async () => {
  await cdp("Input.dispatchKeyEvent", { type: "keyDown", key: "x", code: "KeyX", windowsVirtualKeyCode: 88, nativeVirtualKeyCode: 88, text: "x" });
  await cdp("Input.dispatchKeyEvent", { type: "keyUp", key: "x", code: "KeyX", windowsVirtualKeyCode: 88, nativeVirtualKeyCode: 88 });
  return true;
});
await step("after type x", dump);
await step("undo", async () => {
  await cdp("Input.dispatchKeyEvent", { type: "keyDown", modifiers: 2, key: "z", code: "KeyZ", windowsVirtualKeyCode: 90, nativeVirtualKeyCode: 90 });
  await cdp("Input.dispatchKeyEvent", { type: "keyUp", modifiers: 2, key: "z", code: "KeyZ", windowsVirtualKeyCode: 90, nativeVirtualKeyCode: 90 });
  return true;
});
await step("after undo", dump);
await step("redo", async () => {
  await cdp("Input.dispatchKeyEvent", { type: "keyDown", modifiers: 2, key: "y", code: "KeyY", windowsVirtualKeyCode: 89, nativeVirtualKeyCode: 89 });
  await cdp("Input.dispatchKeyEvent", { type: "keyUp", modifiers: 2, key: "y", code: "KeyY", windowsVirtualKeyCode: 89, nativeVirtualKeyCode: 89 });
  return true;
});
await step("after redo", dump);
process.exit(0);
