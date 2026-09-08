// 在 harness 浏览器（同一 user-data-dir，含旧缓存）里开一个新页签加载 :8000
// ——验证「旧缓存 + 新服务」是否让 JS 启动失败（平台卡空 / 无事件 / 模块 404）
async function main() {
  const ver = await (await fetch("http://127.0.0.1:9251/json/version")).json();
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
  let seq = 0; const pending = new Map();
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const cdp = (m, p = {}, sid) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p, ...(sid ? { sessionId: sid } : {}) })); });
  const c = await cdp("Target.createTarget", { url: "http://127.0.0.1:8000/" });
  const targetId = c.result.targetId;
  console.log("new target:", targetId);
  await new Promise((r) => setTimeout(r, 8000));
  const a = await cdp("Target.attachToTarget", { targetId, flatten: true });
  const sid = a.result.sessionId;
  const r = await Promise.race([
    cdp("Runtime.evaluate", {
      expression: "({ ready: document.readyState, platforms: document.querySelectorAll('#tab-generate .platform-card').length, banner: (document.getElementById('gen-banner')||{}).textContent, scripts: document.scripts.length })",
      returnByValue: true,
    }, sid),
    new Promise((res) => setTimeout(() => res("EVAL_TIMEOUT"), 5000)),
  ]);
  console.log("page state:", JSON.stringify(r));
  process.exit(0);
}
main().catch((e) => { console.error(e); process.exit(1); });
