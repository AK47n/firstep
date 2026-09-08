// debug-fold：折叠态手打 / replaceAll / undo 逐步诊断（含自动接受 beforeunload 对话框）
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const SAMPLE = join(ROOT, ".scratch", "editor-textarea-viewport", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "fold.c"),
  "int main(void) {\n    int x = 1;\n    int y = 2;\n    return x + y;\n}\n");

const CDP = 9251, pageUrl = "http://127.0.0.1:8000/";
const fetchT = async (url, ms = 5000) => { const c = new AbortController(); const t = setTimeout(() => c.abort(), ms); try { return await fetch(url, { signal: c.signal }); } finally { clearTimeout(t); } };
let targets = null;
for (let i = 0; i < 50 && !targets; i++) { try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {} if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300)); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
const api = { }; // 预留
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  else if (m.method === "Page.javascriptDialogOpening") {
    // 自动接受 beforeunload / confirm / alert——探针不卡对话框
    const id = ++seq; pending.set(id, () => {}); ws.send(JSON.stringify({ id, method: "Page.handleJavaScriptDialog", params: { accept: true } }));
  }
};
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr, label = "") => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error((label || "eval") + " 异常: " + JSON.stringify(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails));
  return r.result?.result?.value;
};
const step = async (label, fn) => {
  try { const v = await Promise.race([fn(), new Promise((_, rej) => setTimeout(() => rej(new Error("STEP TIMEOUT " + label)), 10000))]); console.log("OK", label, typeof v === "string" ? v : JSON.stringify(v)); return v; }
  catch (e) { console.log("ERR", label, e.message); return undefined; }
};
const waitFor = async (expr, ms = 10000) => { for (let i = 0; i < ms / 200; i++) { try { if (await Eval(expr)) return true; } catch {} await new Promise((r) => setTimeout(r, 200)); } return false; };
const dump = (tag) => Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const tab = ce.getActiveTab();
  return { tag: ${JSON.stringify(tag)}, path: tab && tab.path, model: tab && tab.content,
    ta: ta && ta.value, sel: ta ? [ta.selectionStart, ta.selectionEnd] : null };
})()`);

await step("reload", () => cdp("Page.reload", { ignoreCache: true }));
await new Promise((r) => setTimeout(r, 2500));
await step("open viewer", () => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`));
console.log("tree:", await waitFor(`!!document.querySelector('#code-tree [data-code-file="fold.c"]')`));
await step("open fold.c", () => Eval(`document.querySelector('#code-tree [data-code-file="fold.c"]')?.click(); true`));
console.log("ta:", await waitFor(`!!document.querySelector('#code-viewer .code-ta')`));
await step("dump0", () => dump("open"));
await step("fold toggle", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0, 0); ta.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); return true; })()`));
console.log("folded:", await waitFor(`document.querySelector('#code-viewer .code-ta')?.value.includes('…')`));
await step("dump1", () => dump("folded"));
await step("set caret firstNl", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); const nl = ta.value.indexOf('\\n'); ta.focus(); ta.setSelectionRange(nl, nl); return nl; })()`));
await step("type Z", async () => {
  await cdp("Input.dispatchKeyEvent", { type: "keyDown", key: "Z", code: "KeyZ", windowsVirtualKeyCode: 90, nativeVirtualKeyCode: 90, text: "Z" });
  await cdp("Input.dispatchKeyEvent", { type: "keyUp", key: "Z", code: "KeyZ", windowsVirtualKeyCode: 90, nativeVirtualKeyCode: 90 });
  return true;
});
await step("dump2", () => dump("typed Z"));
await step("undo", async () => {
  await cdp("Input.dispatchKeyEvent", { type: "keyDown", modifiers: 2, key: "z", code: "KeyZ", windowsVirtualKeyCode: 90, nativeVirtualKeyCode: 90 });
  await cdp("Input.dispatchKeyEvent", { type: "keyUp", modifiers: 2, key: "z", code: "KeyZ", windowsVirtualKeyCode: 90, nativeVirtualKeyCode: 90 });
  return true;
});
await step("dump3", () => dump("undone"));
await step("replaceAll", () => Eval(`import('/js/ui/codeeditor.js').then((m) => m.replaceAllInActiveFile('x', 'XX'))`));
await step("dump4", () => dump("replaced"));
await step("undo", async () => {
  await cdp("Input.dispatchKeyEvent", { type: "keyDown", modifiers: 2, key: "z", code: "KeyZ", windowsVirtualKeyCode: 90, nativeVirtualKeyCode: 90 });
  await cdp("Input.dispatchKeyEvent", { type: "keyUp", modifiers: 2, key: "z", code: "KeyZ", windowsVirtualKeyCode: 90, nativeVirtualKeyCode: 90 });
  return true;
});
await step("dump5", () => dump("replaced undone"));
process.exit(0);
