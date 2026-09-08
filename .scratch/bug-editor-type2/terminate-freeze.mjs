// 尝试终止被冻结页面的执行，然后检查页面状态（寻找无限循环线索）
async function main() {
  const targets = await (await fetch("http://127.0.0.1:9251/json/list")).json();
  const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
  const ver = await (await fetch("http://127.0.0.1:9251/json/version")).json();
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
  let seq = 0; const pending = new Map();
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const cdp = (m, p = {}, sid) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p, ...(sid ? { sessionId: sid } : {}) })); });
  const a = await cdp("Target.attachToTarget", { targetId: page.id, flatten: true });
  const sid = a.result.sessionId;
  console.log("attached");
  console.log("terminate:", JSON.stringify(await Promise.race([cdp("Runtime.terminateExecution", {}, sid), new Promise((r) => setTimeout(() => r("TIMEOUT"), 3000))])));
  await new Promise((r) => setTimeout(r, 500));
  const e = await Promise.race([
    cdp("Runtime.evaluate", { expression: "({ ready: document.readyState, title: document.title, platforms: document.querySelectorAll('#tab-generate .platform-card').length, scripts: document.scripts.length, ta: !!document.getElementById('problem') })", returnByValue: true }, sid),
    new Promise((r) => setTimeout(() => r("TIMEOUT2"), 4000)),
  ]);
  console.log("eval after terminate:", JSON.stringify(e));
  if (e && e.result) console.log("value:", JSON.stringify(e.result.result));
  process.exit(0);
}
main().catch((e) => { console.error(e); process.exit(1); });
