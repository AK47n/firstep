// 实测候选 grid 方案：不同视口宽度下三列（树/中栏/侧栏）宽度
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page" && x.url.includes("8000"));
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const ev = async (expression, awaitPromise = false) => {
  const r = await cdp("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
  if (r.result.exceptionDetails) { console.log("EXC:", JSON.stringify(r.result.exceptionDetails)); return null; }
  return r.result.result.value;
};
await cdp("Runtime.enable");

const variants = {
  V0: "240px minmax(0, 1fr) 300px",
  V1: "minmax(0, 240px) minmax(150px, 1fr) minmax(0, 300px)",
  V2: "minmax(0, 240px) minmax(160px, 1fr) minmax(160px, 300px)",
};
// 先清掉 inline 树宽（模拟未拖拽过）
await ev(`(() => { document.querySelector(".code-layout").style.removeProperty("--code-tree-w"); return 1; })()`);
await wait(100);

for (const [name, cols] of Object.entries(variants)) {
  await ev(`(() => {
    let el = document.getElementById("probe-grid-css"); 
    if (!el) { el = document.createElement("style"); el.id = "probe-grid-css"; document.head.appendChild(el); }
    el.textContent = ".code-layout { grid-template-columns: ${cols} !important; }";
    return 1;
  })()`);
  const rows = [];
  for (const w of [1440, 1000, 800, 700, 565, 480]) {
    await cdp("Emulation.setDeviceMetricsOverride", { width: w, height: 800, deviceScaleFactor: 1, mobile: false });
    await wait(150);
    const r = await ev(`(() => {
      const layout = document.querySelector(".code-layout");
      const r0 = layout.querySelector(".code-pane-tree").getBoundingClientRect();
      const r1 = layout.querySelector(".code-pane-main").getBoundingClientRect();
      const r2 = layout.querySelector(".code-pane-side").getBoundingClientRect();
      return { tree: Math.round(r0.width), main: Math.round(r1.width), side: Math.round(r2.width), layoutW: Math.round(layout.getBoundingClientRect().width) };
    })()`);
    rows.push({ w, ...r });
  }
  console.log(name + " (" + cols + "):");
  for (const row of rows) console.log("  " + JSON.stringify(row));
}
ws.close();
