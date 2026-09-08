// 临时诊断：probe-13 roles=0 原因——直接 import 模块读真实状态
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
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
};
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const out = await Eval(`(async () => {
  const pins = await import("/js/ui/generate-pins.js");
  const rec = await import("/js/ui/generate-recommend.js");
  const roles = pins.pinRoles();
  return {
    chosenPlatform: rec.chosenPlatform,
    expandedLen: rec.expanded.length,
    expandedSlugs: rec.expanded.map((m) => m.slug),
    ledPins: (rec.expanded.find((m) => m.slug === "led") || {}).platforms ? Object.keys((rec.expanded.find((m) => m.slug === "led").platforms || {})["stm32"] || {}) : "no-led",
    roles: roles.length,
    roleKeys: roles.slice(0, 3).map((r) => r.key),
    roleItemsHTML: document.getElementById("pin-role-items")?.innerHTML.slice(0, 120) || null,
    hint: document.getElementById("instance-pin-hint")?.textContent || "",
    pickActive: !!document.querySelector(".instance-row.instance-picking"),
  };
})()`);
console.log(JSON.stringify(out, null, 2));
process.exit(0);
