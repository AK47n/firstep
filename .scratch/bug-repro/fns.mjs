// 探针：检查 window 上代码栏相关函数 + 当前视口
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page" && x.url.includes("8000"));
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
await cdp("Runtime.enable");
const out = await cdp("Runtime.evaluate", { expression: `
({
  vp: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio },
  fns: ["openCodeViewer","openEditorFile","getCodeDir","initCodeAiChat","switchTab","showTab"].filter(n => typeof window[n] === "function"),
  imported: Object.keys(window).filter(k => /code|editor|showTab|tab/i.test(k)).slice(0, 60),
})
`, returnByValue: true });
console.log(JSON.stringify(out.result.result.value, null, 2));
ws.close();
