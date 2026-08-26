// 阶段 2 工单 03 探针：ui/progress.js 共享面板工厂在浏览器侧实况
// （动态 import + 独立 DOM 探针面板实例化 + 事件分发 + 秒表跳动，不碰真面板）
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

console.log("module loads:", await Eval('(async () => { const m = await import("/js/ui/progress.js"); return typeof m.makeProgressPanel === "function"; })()'));
console.log("pure fx bridged:", await Eval('typeof window.fmtClock === "function" && typeof window.fmtDuration === "function"'));
console.log("host stubs gone:", await Eval('document.documentElement.outerHTML.indexOf("function makeProgressPanel") === -1'));
console.log("live panel flight:", await Eval(`(async () => {
  const m = await import("/js/ui/progress.js");
  const host = document.createElement("div");
  host.id = "probe-recap";
  host.innerHTML = '<span id="probe-timer-total"></span><span id="probe-timer-round"></span>';
  document.body.appendChild(host);
  const p = m.makeProgressPanel({
    timerTotalId: "probe-timer-total", timerCallId: "probe-timer-round",
    totalLabel: "总用时 ", callLabel: "当前轮已等待 ",
    events: { ping: (d) => { window.__probePing = d.n; } },
  });
  p.start();
  await new Promise((r) => setTimeout(r, 1150));
  const total = document.getElementById("probe-timer-total").textContent;
  const calld = document.getElementById("probe-timer-round").textContent;
  p.handleEvent("ping", '{"n":7}');
  p.finish();
  const ok = /^总用时 00:0[12]$/.test(total) && /^当前轮已等待 00:0[12]$/.test(calld)
    && window.__probePing === 7 && p.p.finished === true && p.p.timerId === null;
  host.remove();
  return JSON.stringify({ ok, total, calld, ping: window.__probePing, finished: p.p.finished });
})()`));
console.log("rec panel dom intact:", await Eval('!!document.getElementById("rec-timer-total") && !!document.getElementById("rec-timer-round") && !!document.getElementById("rec-progress") && !!document.getElementById("prog-timer-total")'));
ws.close();
