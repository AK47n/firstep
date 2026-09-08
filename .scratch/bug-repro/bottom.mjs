// 探针：滚动到底部 + 状态栏/AI输入行子元素精确 dump
import { writeFileSync } from "node:fs";
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
await cdp("Page.enable");

// 滚动到底
await ev(`(() => { scrollTo(0, document.documentElement.scrollHeight); return scrollY; })()`);
await wait(300);
const d = await ev(`(() => {
  const q = (s) => document.querySelector(s);
  const info = (el) => { if (!el) return null; const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), display: cs.display, flex: cs.flex, whiteSpace: cs.whiteSpace }; };
  const sb = q(".code-statusbar");
  const row = q(".code-ai-chat-input-row");
  const body = q("#code-ai-chat-body");
  return {
    scrollY,
    statusbar: info(sb),
    statusbarKids: sb ? [...sb.children].map((c) => ({ tag: c.tagName, id: c.id, text: (c.innerText || "").slice(0, 24), ...info(c) })) : null,
    inputRow: info(row),
    inputKids: row ? [...row.children].map((c) => ({ tag: c.tagName, id: c.id, cls: c.className, ...info(c), valueLen: (c.value || "").length })) : null,
    aiBody: info(body),
    aiBodyText: body ? (body.innerText || "").slice(0, 200) : null,
    aiPanel: info(q("#code-ai-chat-panel")),
  };
})()`);
console.log(JSON.stringify(d, null, 2));
const s = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync("C:/Users/luoji/Desktop/firstep/.scratch/bug-repro/scrolled-bottom.png", Buffer.from(s.result.data, "base64"));
console.log("saved scrolled-bottom.png");
ws.close();
