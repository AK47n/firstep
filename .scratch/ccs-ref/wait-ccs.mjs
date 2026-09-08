// 轮询附着 CCS（127.0.0.1:3596），直到 Theia shell 出现；每 10s 一次截图，最多 60 次。
import { writeFileSync } from "node:fs";
const urlSubstr = "127.0.0.1:3596";
const CDP = 9251;

async function attach() {
  const list = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  const t = list.find((x) => x.type === "page" && (x.url || "").includes(urlSubstr));
  if (!t) return null;
  const ws = new WebSocket(t.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
  let seq = 0;
  const pending = new Map();
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
  const Eval = async (expr) => { const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }); return r.result?.result?.value; };
  return { ws, cdp, Eval };
}

for (let i = 1; i <= 60; i++) {
  try {
    const c = await attach();
    if (c) {
      const els = await c.Eval("document.querySelectorAll('*').length");
      const ready = await c.Eval("!!document.querySelector('.theia-app-shell, #theia-main-content-panel, .theia-main, .monaco-editor, .theia-core')");
      if (ready) {
        const shot = await c.cdp("Page.captureScreenshot", { format: "png" });
        writeFileSync(".scratch/ccs-ref/ccs-main.png", Buffer.from(shot.result.data, "base64"));
        console.log(`READY at try ${i} — shell ready, els=${els}`);
        process.exit(0);
      }
      console.log(`try ${i}: els=${els} not ready`);
    } else {
      console.log(`try ${i}: no target`);
    }
  } catch (e) {
    console.log(`try ${i}: err ${e.message}`);
  }
  await new Promise((r) => setTimeout(r, 10000));
}
console.log("GAVE UP");
process.exit(1);
