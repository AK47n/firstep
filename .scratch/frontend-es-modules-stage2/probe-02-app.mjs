// 阶段 2 工单 02 探针：app.js 共享壳在浏览器侧的实况
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

console.log("window.$ no-pollution:", await Eval('typeof window.$ === "undefined" && typeof window.toast === "undefined" && typeof window.handle === "undefined"'));
console.log("theme btn wired:", await Eval('(() => { const b = document.getElementById("btn-theme"); return !!b && !!b.textContent && !!b.title; })()'));
const themeBefore = await Eval('document.documentElement.getAttribute("data-theme")');
await Eval('document.getElementById("btn-theme").click()');
const themeAfter = await Eval('document.documentElement.getAttribute("data-theme")');
console.log("theme toggle:", themeBefore, "->", themeAfter, themeBefore !== themeAfter ? "OK" : "FAIL");
await Eval('document.getElementById("btn-theme").click()');  // 复位
console.log("icons injected:", await Eval('(() => { const b = document.querySelector("[data-ico]"); return !!b && !!b.querySelector("svg"); })()'));
console.log("tab dispatcher:", await Eval('(() => { const b = document.querySelector(\'nav button[data-tab="library"]\'); b.click(); return document.getElementById("tab-library").classList.contains("active"); })()'));
await Eval('document.querySelector(\'nav button[data-tab="generate"]\').click()');  // 复位
console.log("gen-banner hidden:", await Eval('document.getElementById("gen-banner").classList.contains("hidden")'));
console.log("import chain ok (modules):", await Eval('performance.getEntriesByType("resource").filter(r => r.name.includes("/js/")).length'));
ws.close();
