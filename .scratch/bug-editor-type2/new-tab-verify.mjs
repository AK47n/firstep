// 全新页签（同一浏览器 profile / 同一 disk cache）加载 :8000 —— 真实桌面流程
// （双击 → 新页签）。验证 Clear-Site-Data 是否让首次加载即全量新鲜。
async function main() {
  const ver = await (await fetch("http://127.0.0.1:9251/json/version")).json();
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
  let seq = 0; const pending = new Map();
  const logs = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === "Runtime.exceptionThrown") {
      const d = m.params.exceptionDetails;
      logs.push(((d.exception && d.exception.description) || d.text || "").slice(0, 400));
    }
  };
  const cdp = (m, p = {}, sid) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p, ...(sid ? { sessionId: sid } : {}) })); });
  const c = await cdp("Target.createTarget", { url: "http://127.0.0.1:8000/" });
  const tid = c.result.targetId;
  const a = await cdp("Target.attachToTarget", { targetId: tid, flatten: true });
  const sid = a.result.sessionId;
  await cdp("Runtime.enable", {}, sid);
  await new Promise((r) => setTimeout(r, 7000));
  const state = await Promise.race([
    cdp("Runtime.evaluate", { expression: "({ platforms: document.querySelectorAll('#tab-generate .platform-card').length, bannerHidden: (document.getElementById('gen-banner')||{classList:{contains:()=>null}}).classList.contains('hidden') })", returnByValue: true }, sid),
    new Promise((res) => setTimeout(() => res("TIMEOUT"), 4000)),
  ]);
  console.log("new-tab state:", JSON.stringify(state));
  console.log("exceptions:", JSON.stringify(logs));
  process.exit(0);
}
main().catch((e) => { console.error(e); process.exit(1); });
