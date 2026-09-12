// 诊断：连接已开的 Chrome 调试端口，读当前页 URL/标题 + 控制台报错 + 关键 DOM 是否渲染。
// 只读（不导航、不 eval 业务代码、不改页面状态）。
// 用法：node .scratch/exclusive-group-gap-audit/diag-page.mjs [port]
const port = process.argv[2] || "9251";

async function rpc(ws, id, method, params = {}) {
  return new Promise((resolve, reject) => {
    const onMsg = (ev) => {
      let m;
      try { m = JSON.parse(ev.data); } catch { return; }
      if (m.id !== id) return;
      ws.removeEventListener("message", onMsg);
      if (m.error) reject(new Error(method + ": " + JSON.stringify(m.error)));
      else resolve(m.result);
    };
    ws.addEventListener("message", onMsg);
    ws.send(JSON.stringify({ id, method, params }));
    setTimeout(() => { ws.removeEventListener("message", onMsg); reject(new Error(method + " 超时（页面可能真的挂死）")); }, 8000);
  });
}

const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const pages = list.filter((t) => t.type === "page");
console.log(`调试端口 ${port}：${list.length} 个 target，其中 page ${pages.length} 个`);
for (const p of pages) {
  console.log(`  - ${p.title}  ${p.url}`);
}

const target = pages.find((p) => /127\.0\.0\.1:8000/.test(p.url)) || pages[0];
if (!target) { console.log("没有可诊断的页面"); process.exit(0); }
console.log(`\n=== 诊断目标：${target.url} ===`);

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));

let seq = 1;
const nextId = () => seq++;
const logs = [];
const errors = [];
ws.addEventListener("message", (ev) => {
  let m; try { m = JSON.parse(ev.data); } catch { return; }
  if (m.method === "Runtime.consoleAPICalled") {
    const text = (m.params.args || []).map((a) => a.value ?? a.description ?? a.type).join(" ");
    logs.push(`[${m.params.type}] ${text}`);
  }
  if (m.method === "Runtime.exceptionThrown") {
    const d = m.params.exceptionDetails || {};
    errors.push(`${d.text || ""} ${(d.exception && (d.exception.description || d.exception.value)) || ""}`.trim());
  }
  if (m.method === "Log.entryAdded") {
    logs.push(`[log:${m.params.entry.level}] ${m.params.entry.text}`);
  }
});

await rpc(ws, nextId(), "Runtime.enable");
await rpc(ws, nextId(), "Log.enable");
await new Promise((r) => setTimeout(r, 1200));

async function evalJs(expr) {
  const res = await rpc(ws, nextId(), "Runtime.evaluate", {
    expression: expr, returnByValue: true, awaitPromise: false,
  });
  if (res.exceptionDetails) return "!! " + (res.exceptionDetails.text || "eval 抛错");
  return res.result.value;
}

console.log("\n--- 页面是否还被脚本驱动（卡死判据）---");
console.log("readyState        :", await evalJs("document.readyState"));
console.log("document.title    :", await evalJs("document.title"));
console.log("主线程心跳测试     :", await evalJs("(() => { const t=Date.now(); let n=0; while(Date.now()-t<50) n++; return 'ok(' + n + ' 次循环)'; })()"));
console.log("关键 DOM 计数      :", await evalJs(`JSON.stringify({
  navTabs: document.querySelectorAll('.nav-tab, [data-tab], nav button').length,
  moduleCards: document.querySelectorAll('#module-grid .module-card, .module-card').length,
  groupCards: document.querySelectorAll('.group-card').length,
  recChips: document.querySelectorAll('.rec-chip, .recommend-chip, .chip').length,
  overlays: document.querySelectorAll('.ref-files-overlay, .overlay, [data-overlay]').length,
  bodyChildren: document.body.children.length,
  scripts: document.querySelectorAll('script').length,
})`));

console.log("\n--- 控制台报错（异常）---");
console.log(errors.length ? errors.slice(0, 20).join("\n") : "（无异常）");
console.log("\n--- 控制台消息（最近 30 条）---");
console.log(logs.length ? logs.slice(-30).join("\n") : "（无消息）");
ws.close();
process.exit(0);
