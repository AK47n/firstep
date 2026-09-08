// shot-now.mjs：截取当前 headless 页面状态（真实工程已打开 beep.c）
import { writeFileSync } from "node:fs";
const t = (await (await fetch("http://127.0.0.1:9231/json/list")).json()).find((x) => x.type === "page" && x.url.includes("8000"));
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => { ws.onopen = r; });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
await cdp("Page.enable");
const shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync("C:/Users/luoji/Desktop/firstep/.scratch/bug-repro/now-realproj.png", Buffer.from(shot.result.data, "base64"));
console.log("saved now-realproj.png");
ws.close();
