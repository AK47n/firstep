// 阶段 2 工单 05 探针：ui/pdf.js（PDF 资料库胶水）+ truncate 入 fx/core.js 实况
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
if (!page) { console.error("no page"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
};
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r.result?.result?.value ?? (r.result?.exceptionDetails ? "EXCEPTION: " + JSON.stringify(r.result.exceptionDetails.exception?.description).slice(0, 250) : "undefined");
};
await cdp("Runtime.enable");

console.log("modules load:", await Eval('(async () => { const m = await import("/js/ui/pdf.js"); return typeof m.loadPdfs === "function" && typeof m.initPdfToolbar === "function"; })()'));
console.log("truncate bridged:", await Eval('typeof window.truncate === "function" && window.truncate("abcdef", 5) === "abcde…"'));
console.log("host stubs gone:", await Eval('document.documentElement.outerHTML.indexOf("function loadPdfs") === -1 && document.documentElement.outerHTML.indexOf("function initPdfToolbar") === -1 && document.documentElement.outerHTML.indexOf("function truncate") === -1'));
console.log("pdf tab flight:", await Eval(`(async () => {
  document.querySelector('nav button[data-tab="pdf"]').click();
  await new Promise((r) => setTimeout(r, 700));   // 分发器 → loadPdfs
  const rows = document.getElementById("pdf-rows");
  const ok = document.getElementById("pdf-msg").textContent === "" && rows.children.length >= 1;
  const toolbarOk = !!document.getElementById("pdf-filter") && !!document.getElementById("pdf-sort") && !!document.getElementById("pdf-stats");
  const rcount = rows.children.length;
  const emptyHint = rows.textContent.includes("暂无 PDF") || rows.textContent.includes("正在读取");
  document.querySelector('nav button[data-tab="generate"]').click();
  return JSON.stringify({ ok, rcount, emptyHint, toolbarOk });
})()`));
ws.close();
