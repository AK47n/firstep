// 探针 2：insertIntoActiveFile + 消息内容
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT("http://127.0.0.1:9251/json/list")).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000/"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const msg = JSON.parse(ev.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return { err: r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails) };
  return r.result?.result?.value;
};
console.log("fence 提取:", JSON.stringify(await Eval(`import('/js/fx/ai-insert.js').then((m) => m.aiFirstCodeBlock('解释 \\n\\n\`\`\`c\\nint addOne = 0;\\n\`\`\`'))`)));
console.log("insert 直接调:", JSON.stringify(await Eval(`import('/js/ui/codeeditor.js').then((m) => { try { return { ok: m.insertIntoActiveFile('int addOne = 0;') }; } catch (e) { return { err: e.message }; } })`)));
await new Promise((r) => setTimeout(r, 400));
console.log("值前 40:", await Eval(`document.querySelector('#code-viewer .code-ta').value.slice(0,40)`));
process.exit(0);
