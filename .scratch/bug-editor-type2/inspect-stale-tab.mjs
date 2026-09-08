// 深入检查 stale-cache 新页签：模块加载/失败请求/横幅可见性/全局状态
async function main() {
  const ver = await (await fetch("http://127.0.0.1:9251/json/version")).json();
  const targets = await (await fetch("http://127.0.0.1:9251/json/list")).json();
  const page = targets.find((t) => t.url === "http://127.0.0.1:8000/" && t.id !== undefined);
  // 找到最近创建的那个 target（stale-cache-test 创建的）——用 id 匹配
  const ws = new WebSocket(ver.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
  let seq = 0; const pending = new Map();
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const cdp = (m, p = {}, sid) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p, ...(sid ? { sessionId: sid } : {}) })); });
  const list = await cdp("Target.getTargets");
  const t = list.result.targetInfos.find((x) => x.type === "page" && x.url === "http://127.0.0.1:8000/" && x.attached === false) ||
    list.result.targetInfos.filter((x) => x.type === "page" && x.url === "http://127.0.0.1:8000/").pop();
  console.log("target:", JSON.stringify(t));
  const a = await cdp("Target.attachToTarget", { targetId: t.targetId, flatten: true });
  const sid = a.result.sessionId;
  const r = await Promise.race([
    cdp("Runtime.evaluate", { expression: `(() => {
      const perf = performance.getEntriesByType('resource');
      const bad = perf.filter((e) => e.responseStatus >= 400 || e.responseStatus === 0)
        .map((e) => e.name.replace('http://127.0.0.1:8000','') + ' -> ' + e.responseStatus);
      const js = perf.filter((e) => e.name.includes('/js/')).length;
      const app = perf.some((e) => e.name.endsWith('/js/app.js'));
      const banner = document.getElementById('gen-banner');
      const navBtns = document.querySelectorAll('nav button[data-tab]').length;
      return {
        resourceCount: perf.length, jsLoaded: js, appJs: app,
        bad,
        bannerVisible: banner ? !banner.classList.contains('hidden') : null,
        bannerText: banner ? banner.textContent.trim() : null,
        navBtns,
        stateGlobal: (typeof window.__boot_ok !== 'undefined') ? window.__boot_ok : 'n/a',
        platformCards: document.querySelectorAll('#tab-generate .platform-card').length,
      };
    })()`, returnByValue: true }, sid),
    new Promise((res) => setTimeout(() => res("EVAL_TIMEOUT"), 5000)),
  ]);
  console.log(JSON.stringify(r, null, 2));
  process.exit(0);
}
main().catch((e) => { console.error(e); process.exit(1); });
