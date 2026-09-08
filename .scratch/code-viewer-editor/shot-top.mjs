// 截图：代码栏顶部 0..140px（与用户截图对照找黑线）。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });

const shot = await cdp("Page.captureScreenshot", {
  format: "png",
  clip: { x: 0, y: 0, width: 1440, height: 150, scale: 1 },
});
const { writeFileSync } = await import("node:fs");
writeFileSync(".scratch/code-viewer-editor/diag-top-150.png", Buffer.from(shot.result.data, "base64"));
console.log("shot saved");
process.exit(0);
