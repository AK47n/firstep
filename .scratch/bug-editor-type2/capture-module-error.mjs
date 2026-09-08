// 在 stale-cache 页签上重载并捕获 console/异常——锁定模块图失败的具体错误
async function main() {
  const ver = await (await fetch("http://127.0.0.1:9251/json/version")).json();
  const list = await (await fetch("http://127.0.0.1:9251/json/list")).json();
  const t = list.find((x) => x.type === "page" && x.url === "http://127.0.0.1:8000/" && x.id === "4459185C27F7D9DB101CBA22579A5E7C");
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
  let seq = 0; const pending = new Map();
  const logs = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === "Runtime.exceptionThrown") {
      const d = m.params.exceptionDetails;
      logs.push({ kind: "exception", text: ((d.exception && d.exception.description) || d.text || "").slice(0, 800) });
    } else if (m.method === "Runtime.consoleAPICalled") {
      logs.push({ kind: "console." + m.params.type,
        text: (m.params.args || []).map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 400) });
    } else if (m.method === "Log.entryAdded") {
      logs.push({ kind: "log." + m.params.entry.level, text: String(m.params.entry.text || "").slice(0, 400) });
    }
  };
  const cdp = (m, p = {}, sid) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p, ...(sid ? { sessionId: sid } : {}) })); });
  const a = await cdp("Target.attachToTarget", { targetId: t.id, flatten: true });
  const sid = a.result.sessionId;
  await cdp("Runtime.enable", {}, sid);
  await cdp("Log.enable", {}, sid);
  await cdp("Page.enable", {}, sid);
  await cdp("Page.navigate", { url: "http://127.0.0.1:8000/?repro=1" }, sid);
  await new Promise((r) => setTimeout(r, 5000));
  const state = await Promise.race([
    cdp("Runtime.evaluate", { expression: "({ platforms: document.querySelectorAll('#tab-generate .platform-card').length, tabs: document.querySelectorAll('nav button[data-tab]').length })", returnByValue: true }, sid),
    new Promise((res) => setTimeout(() => res("TIMEOUT"), 4000)),
  ]);
  console.log("page:", JSON.stringify(state));
  console.log("事件:", JSON.stringify(logs, null, 2));
  process.exit(0);
}
main().catch((e) => { console.error(e); process.exit(1); });
