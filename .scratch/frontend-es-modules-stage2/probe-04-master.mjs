// 阶段 2 工单 04 探针：ui/master.js（母版页胶水）+ ui/usage.js（用量服务）实况
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

console.log("modules load:", await Eval('(async () => { const m = await import("/js/ui/master.js"); const u = await import("/js/ui/usage.js"); return typeof m.loadMasters === "function" && typeof m.loadChangelog === "function" && typeof u.recordLLMUsage === "function" && typeof u.setLlmPricesDefaults === "function"; })()'));
console.log("fx bridge report rows:", await Eval('typeof window.decisionItem === "function" && typeof window.archiveItem === "function"'));
console.log("host stubs gone:", await Eval('document.documentElement.outerHTML.indexOf("function loadMasters") === -1 && document.documentElement.outerHTML.indexOf("const distPanel") === -1 && document.documentElement.outerHTML.indexOf("function renderReport") === -1'));
console.log("master tab flight:", await Eval(`(async () => {
  document.querySelector('nav button[data-tab="master"]').click();
  await new Promise((r) => setTimeout(r, 600));   // 分发器 → loadMasters
  const rows = document.getElementById("master-rows");
  const okTable = !!rows && document.getElementById("master-msg").textContent === "";
  const okProgDom = !!document.getElementById("prog-stepper") && !!document.getElementById("prog-log") && !!document.getElementById("btn-distill") && !!document.getElementById("btn-confirm");
  document.querySelector('nav button[data-tab="generate"]').click();
  return JSON.stringify({ okTable, rowCount: okTable ? rows.children.length : -1, okProgDom });
})()`));
console.log("changelog tab flight:", await Eval(`(async () => {
  document.querySelector('nav button[data-tab="changelog"]').click();
  await new Promise((r) => setTimeout(r, 600));
  const box = document.getElementById("changelog-list");
  const n = box.children.length;
  document.querySelector('nav button[data-tab="generate"]').click();
  return JSON.stringify({ children: n, hasContent: n > 0 || box.textContent.includes("暂无更新记录") });
})()`));
console.log("usage dom + reset wiring:", await Eval('(() => { const t = document.getElementById("usage-total"); const b = document.getElementById("btn-usage-reset"); return !!t && !!b && !!document.getElementById("usage-session"); })()'));
ws.close();
