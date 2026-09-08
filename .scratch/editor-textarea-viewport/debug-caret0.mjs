// debug-caret0：jump 后 caret=0 —— insertText vs 手打 keydown 的落点对比
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const SAMPLE = join(ROOT, ".scratch", "editor-textarea-viewport", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
const bigLines = [];
for (let i = 0; i < 6000; i++) bigLines.push("int var_" + i + " = " + i + ";  // " + i);
writeFileSync(join(SAMPLE, "big.c"), bigLines.join("\n"));
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
const waitFor = async (expr, ms = 12000) => { for (let i = 0; i < ms / 200; i++) { try { if (await Eval(expr)) return true; } catch {} await new Promise((r) => setTimeout(r, 200)); } return false; };
const step = async (label, fn) => { try { const v = await Promise.race([fn(), new Promise((_, rej) => setTimeout(() => rej(new Error("TIMEOUT " + label)), 10000))]); console.log("OK", label, JSON.stringify(v)); return v; } catch (e) { console.log("ERR", label, e.message); } };
const dump = (tag) => Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const m = ce.getActiveTab().content;
  const at = m.indexOf('Z');
  return { tag: ${JSON.stringify(tag)}, sel: [ta.selectionStart, ta.selectionEnd],
    taHead: ta.value.slice(0, 28), mCtx: at < 0 ? '' : m.slice(Math.max(0, at - 3), at + 14),
    taMatch: ta.value.slice(0, 10) };
})()`);

await step("open viewer", () => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`));
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);
await step("open big.c", () => Eval(`document.querySelector('#code-tree [data-code-file="big.c"]')?.click(); true`));
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await step("jump 3000", () => Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(3000); return true; })`));
await new Promise((r) => setTimeout(r, 300));
await step("setCaret0", () => Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0, 0); return [ta.selectionStart, ta.selectionEnd]; })()`));
await step("dump before insertText", () => dump("before"));
await step("insertText Z", () => cdp("Input.insertText", { text: "Z" }));
await step("dump after insertText", () => dump("after insertText"));
process.exit(0);
