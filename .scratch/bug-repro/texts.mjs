// 探针：在打开 main.c 的状态下，抓所有含 收起/发送/译 文本的元素 rect + 祖先链
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page" && x.url.includes("8000"));
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
await cdp("Runtime.enable");
const out = await cdp("Runtime.evaluate", { expression: `
(() => {
  const hits = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  let n;
  while ((n = walker.nextNode())) {
    const txt = (n.childNodes.length && [...n.childNodes].every(c => c.nodeType === 3)) ? n.textContent : "";
    if (!txt) continue;
    if (/收起|发送|译/.test(txt) && txt.length <= 12) {
      const r = n.getBoundingClientRect();
      const chain = [];
      let p = n;
      for (let i = 0; i < 6 && p; i++) { chain.push((p.id ? "#" + p.id : "") + (p.className && typeof p.className === "string" ? "." + p.className.split(" ").join(".") : "") + "[" + p.tagName + "]"); p = p.parentElement; }
      hits.push({ text: txt.trim(), tag: n.tagName, cls: n.className, rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }, chain: chain.join(" < ") });
    }
  }
  return { scrollY: scrollY, docH: document.documentElement.scrollHeight, hits };
})()
`, returnByValue: true });
console.log(JSON.stringify(out.result.result.value, null, 2));
ws.close();
