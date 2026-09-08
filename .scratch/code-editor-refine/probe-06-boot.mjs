// 探针：smoke-06 整页失效定位——import app.js / 模块错误
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
  if (r.result?.exceptionDetails) return { err: r.result.exceptionDetails.exception?.description || "?" };
  return r.result?.result?.value;
};
console.log("readyState:", await Eval(`document.readyState`));
console.log("code-tree exists:", await Eval(`!!document.getElementById('code-tree')`));
console.log("import app.js:", JSON.stringify(await Eval(`import('/js/app.js').then((m) => typeof m.copyText).catch((e) => 'ERR: ' + e.message)`)));
console.log("import code-tree-ops:", JSON.stringify(await Eval(`import('/js/ui/code-tree-ops.js').then((m) => typeof m.initCodeTreeOps).catch((e) => 'ERR: ' + e.message)`)));
console.log("import generate-core:", JSON.stringify(await Eval(`import('/js/ui/generate-core.js').then(() => 'ok').catch((e) => 'ERR: ' + e.message)`)));
console.log("import recent:", JSON.stringify(await Eval(`import('/js/ui/recent.js').then(() => 'ok').catch((e) => 'ERR: ' + e.message)`)));
console.log("import master:", JSON.stringify(await Eval(`import('/js/ui/master.js').then(() => 'ok').catch((e) => 'ERR: ' + e.message)`)));
console.log("import pdf:", JSON.stringify(await Eval(`import('/js/ui/pdf.js').then(() => 'ok').catch((e) => 'ERR: ' + e.message)`)));
console.log("import generate-mainc:", JSON.stringify(await Eval(`import('/js/ui/generate-mainc.js').then(() => 'ok').catch((e) => 'ERR: ' + e.message)`)));
process.exit(0);
