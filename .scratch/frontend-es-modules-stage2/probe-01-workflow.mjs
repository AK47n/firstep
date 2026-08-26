// 阶段 2 工单 01 探针：fx/workflow.js 桥 + 设置 tab 最近工作流实况渲染
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
// 1) window 桥 5 名
const bridge = await Eval('["wfNum","formatWorkflowUsage","formatWorkflowCost","formatWorkflowSummary","formatWorkflowCall"].map(n => n + ":" + typeof window[n]).join(" | ")');
console.log("bridge:", bridge);
// 2) 切到设置 tab（分发器触发 loadSettings+loadRecentWorkflows+renderUsageStats）
await Eval('document.querySelector(\'[data-tab="settings"]\').click()');
await new Promise((r) => setTimeout(r, 1800));
const dom = await Eval('(() => { const el = document.getElementById("recent-workflows"); return "len=" + (el ? el.innerHTML.length : -1) + " head=" + (el ? el.textContent.trim().slice(0, 40) : "NO EL"); })()');
console.log("recent-workflows:", dom);
const err = await Eval('window.__wfProbeErr || "none"');
console.log("probe err:", err);
ws.close();
