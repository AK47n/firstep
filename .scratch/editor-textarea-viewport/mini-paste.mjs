// 评审辅助：只测 ⑤ 超长粘贴的同步阻塞时长——openTab big.c → setCaret(0) →
// Input.insertText(150 行) → 立即连发 1+1 eval 采样 renderer 响应时间。
import { fileURLToPath } from "node:url";
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
if (!page) { console.error("无页面"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r.result?.result?.value;
};
const t0 = Date.now();
const log = (m) => console.log(`[${Date.now() - t0}ms] ${m}`);

log("open big.c");
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]')?.click(); true`);
await new Promise((r) => setTimeout(r, 1500));
log("setCaret 0");
await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0,0); return ta.selectionStart; })()`);
const lines = [];
for (let i = 0; i < 150; i++) lines.push("// paste line " + i);
const pasteText = lines.join("\n") + "\n";
log("Input.insertText（150 行）发送");
const insP = cdp("Input.insertText", { text: pasteText });
// 采样：insertText 命令本身 + renderer 响应
for (let i = 0; i < 12; i++) {
  const s = Date.now();
  const r = await Promise.race([insP, new Promise((res) => setTimeout(() => res("PENDING"), 3000))]);
  const dt = Date.now() - s;
  if (r !== "PENDING") { log("insertText 已返回: " + dt + "ms (命令完成)"); break; }
  if (i === 11) log("insertText 12×3s 仍未返回");
}
for (let i = 0; i < 4; i++) {
  const s = Date.now();
  const r = await Promise.race([Eval("1+1"), new Promise((res) => setTimeout(() => res("TIMEOUT"), 4000))]);
  log("eval 1+1 -> " + JSON.stringify(r) + " in " + (Date.now() - s) + "ms");
}
ws.close(); process.exit(0);
