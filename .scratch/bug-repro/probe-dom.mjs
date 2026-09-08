// probe-dom.mjs：查 .code-layout 的子元素构成 + grid 自动流 + 各面板父级/网格位置
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page" && x.url.includes("8000"));
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

await cdp("Runtime.enable");
await cdp("Emulation.setDeviceMetricsOverride", { width: 1105, height: 578, deviceScaleFactor: 1, mobile: false });
await wait(300);

const ev = async (expression, awaitPromise = false) => {
  const r = await cdp("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
  if (r.result.exceptionDetails) { console.log("EXC:", JSON.stringify(r.result.exceptionDetails)); return null; }
  return r.result.result.value;
};

await ev(`(async () => {
  const m = await import("/js/ui/codeview.js");
  if (typeof m.openCodeViewer !== "function") return "no openCodeViewer";
  await m.openCodeViewer("C:/Users/luoji/Desktop/2024H_Auto_Car_MSPM0");
  return "ok";
})()`, true);
await wait(800);
await ev(`(() => {
  const items = [...document.querySelectorAll("[data-code-file]")];
  const item = items.find((b) => (b.dataset.codeFile || "").toLowerCase().endsWith("beep.c"));
  if (item) { item.click(); return "clicked"; }
  return "no beep.c";
})()`);
await wait(800);

const dump = await ev(`(() => {
  const layout = document.querySelector(".code-layout");
  const cs = getComputedStyle(layout);
  const kids = [...layout.children].map((el) => {
    const r = el.getBoundingClientRect();
    return { tag: el.tagName, id: el.id, cls: el.className,
      x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
      gcs: getComputedStyle(el).gridColumnStart, gce: getComputedStyle(el).gridColumnEnd,
      grs: getComputedStyle(el).gridRowStart, gre: getComputedStyle(el).gridRowEnd };
  });
  const panelInfo = (sel) => {
    const el = document.querySelector(sel); if (!el) return null;
    const r = el.getBoundingClientRect();
    const p = el.parentElement;
    return { sel, parentCls: p.className, parentId: p.id,
      x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
      gcs: getComputedStyle(el).gridColumnStart, grs: getComputedStyle(el).gridRowStart,
      display: getComputedStyle(el).display };
  };
  const card = document.querySelector("#tab-code .card");
  const cardCS = getComputedStyle(card);
  return {
    layoutKids: kids,
    gridAutoFlow: cs.gridAutoFlow,
    gridTemplateColumns: cs.gridTemplateColumns,
    gridTemplateRows: cs.gridTemplateRows,
    layoutRect: (() => { const r = layout.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; })(),
    cardDisplay: cardCS.display, cardFlexDirection: cardCS.flexDirection,
    cardKids: [...card.children].map((el) => el.id || el.className || el.tagName),
    panels: ["#code-compile-panel","#code-change-panel","#code-ai-chat-panel","#code-fix-panel",".code-statusbar","#code-viewer"].map(panelInfo),
    tabCodeCS: (() => { const c = getComputedStyle(document.querySelector("#tab-code")); return { display: c.display, flexDirection: c.flexDirection }; })(),
  };
})()`);
console.log(JSON.stringify(dump, null, 2));
ws.close();
