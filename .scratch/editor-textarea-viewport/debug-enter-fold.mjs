// debug-enter-fold：bigfold.c 折叠+窗口态按 Enter（applyEdit 窗口级折叠回写）
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const SAMPLE = join(ROOT, ".scratch", "editor-textarea-viewport", "sample-proj");
const CDP = 9251, pageUrl = "http://127.0.0.1:8000/";
const fetchT = async (url, ms = 5000) => { const c = new AbortController(); const t = setTimeout(() => c.abort(), ms); try { return await fetch(url, { signal: c.signal }); } finally { clearTimeout(t); } };
let targets = null;
for (let i = 0; i < 50 && !targets; i++) { try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {} if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300)); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } else if (m.method === "Page.javascriptDialogOpening") { const id = ++seq; pending.set(id, () => {}); ws.send(JSON.stringify({ id, method: "Page.handleJavaScriptDialog", params: { accept: true } })); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => { const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }); if (r.result?.exceptionDetails) throw new Error("异常: " + JSON.stringify(r.result.exceptionDetails)); return r.result?.result?.value; };
const waitFor = async (expr, ms = 10000) => { for (let i = 0; i < ms / 200; i++) { try { if (await Eval(expr)) return true; } catch {} await new Promise((r) => setTimeout(r, 200)); } return false; };
const step = async (label, fn) => { try { const v = await Promise.race([fn(), new Promise((_, rej) => setTimeout(() => rej(new Error("TIMEOUT " + label)), 10000))]); console.log("OK", label, JSON.stringify(v)); return v; } catch (e) { console.log("ERR", label, e.message); } };
const dump = (tag) => Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const tab = ce.getActiveTab();
  return { tag: ${JSON.stringify(tag)}, modelLines: tab.content.split('\\n').length,
    viewTxt: ce.editorViewText().slice(0, 40), hasPh: ce.editorViewText().includes('…'),
    sel: ta ? [ta.selectionStart, ta.selectionEnd] : null };
})()`);

await step("open viewer", () => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`));
await waitFor(`!!document.querySelector('#code-tree [data-code-file="bigfold.c"]')`);
await step("open bigfold", () => Eval(`document.querySelector('#code-tree [data-code-file="bigfold.c"]')?.click(); true`));
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await step("jump 3005", () => Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(3005); return true; })`));
await new Promise((r) => setTimeout(r, 300));
await step("fold", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); return true; })()`));
await waitFor(`document.querySelector('#code-viewer .code-ta')?.value.includes('…')`);
await step("dump folded", () => dump("folded"));
const before = await Eval(`(async () => (await import('/js/ui/codeeditor.js')).getActiveTab().content.split('\\n').length)`);
// 窗口内任一位置按 Enter（keydown 拦截 → indentOnEnter → applyEdit 窗口级折叠回写）
await step("press Enter", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(5, 5); ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })); return true; })()`));
await new Promise((r) => setTimeout(r, 200));
await step("dump after enter", () => dump("enter"));
const after = await Eval(`(async () => (await import('/js/ui/codeeditor.js')).getActiveTab().content.split('\\n').length)`);
console.log("before/after lines:", before, after);
await step("undo", async () => {
  await cdp("Input.dispatchKeyEvent", { type: "keyDown", modifiers: 2, key: "z", code: "KeyZ", windowsVirtualKeyCode: 90, nativeVirtualKeyCode: 90 });
  await cdp("Input.dispatchKeyEvent", { type: "keyUp", modifiers: 2, key: "z", code: "KeyZ", windowsVirtualKeyCode: 90, nativeVirtualKeyCode: 90 });
  return true;
});
await step("dump after undo", () => dump("undo"));
process.exit(0);
