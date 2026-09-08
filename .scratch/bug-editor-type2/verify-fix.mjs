// 修复验证：重载此前「新旧混装模块图」的 stale-cache 页签，
// no-cache 全量协商后必须启动成功（平台卡出现、无 SyntaxError）。
async function main() {
  const ver = await (await fetch("http://127.0.0.1:9251/json/version")).json();
  const list = await (await fetch("http://127.0.0.1:9251/json/list")).json();
  const t = list.find((x) => x.type === "page" && x.url.startsWith("http://127.0.0.1:8000") && x.id === "4459185C27F7D9DB101CBA22579A5E7C");
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
  let seq = 0; const pending = new Map();
  const logs = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === "Runtime.exceptionThrown") {
      const d = m.params.exceptionDetails;
      logs.push(((d.exception && d.exception.description) || d.text || "").slice(0, 500));
    }
  };
  const cdp = (m, p = {}, sid) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p, ...(sid ? { sessionId: sid } : {}) })); });
  const a = await cdp("Target.attachToTarget", { targetId: t.id, flatten: true });
  const sid = a.result.sessionId;
  await cdp("Runtime.enable", {}, sid);
  await cdp("Page.enable", {}, sid);
  await cdp("Page.navigate", { url: "http://127.0.0.1:8000/?verify=1" }, sid);
  await new Promise((r) => setTimeout(r, 6000));
  const state = await Promise.race([
    cdp("Runtime.evaluate", {
      expression: "({ platforms: document.querySelectorAll('#tab-generate .platform-card').length, banner: (document.getElementById('gen-banner')||{}).textContent, bannerHidden: (document.getElementById('gen-banner')||{classList:{contains:()=>null}}).classList.contains('hidden') })",
      returnByValue: true,
    }, sid),
    new Promise((res) => setTimeout(() => res("TIMEOUT"), 4000)),
  ]);
  console.log("state:", JSON.stringify(state));
  console.log("exceptions:", JSON.stringify(logs));
  const ok = state.result?.result?.value?.platforms === 2 && logs.length === 0;
  console.log(ok ? "PASS no-cache 修复：混装模块图启动成功" : "FAIL 仍失败");
  process.exit(ok ? 0 : 1);
}
main().catch((e) => { console.error(e); process.exit(1); });
