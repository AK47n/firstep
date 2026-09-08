// y 方向测量：hl 行 rect.y vs 同行 guide span rect.y（找滚动窗口的 y 错位）
const CDP = 9251;
const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(t); }
};
let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000/"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + JSON.stringify(r.result.exceptionDetails));
  return r.result?.result?.value;
};
const out = await Eval(`(() => {
  const hlRows = [...document.querySelectorAll('#code-viewer .code-hl-line')];
  const mkRows = [...document.querySelectorAll('#code-viewer .code-marks-line')];
  const report = [];
  for (let i = 0; i < hlRows.length && i < mkRows.length; i++) {
    const hl = hlRows[i], mk = mkRows[i];
    const n = parseInt(hl.dataset.codeLine, 10);
    const ry = hl.getBoundingClientRect();
    const gy = mk.getBoundingClientRect();
    const guides = [...mk.querySelectorAll('.code-mark-guide')].map((g) => {
      const r = g.getBoundingClientRect();
      return { x: Math.round(r.left), y: Math.round(r.top), h: Math.round(r.height * 10) / 10 };
    });
    report.push({ n, hlY: Math.round(ry.top), mkY: Math.round(gy.top), dy: Math.round((gy.top - ry.top) * 10) / 10, guides });
  }
  // 窗口起点/scrollTop 信息
  const box = document.getElementById('code-viewer');
  const first = document.querySelector('#code-viewer .code-hl-line');
  const mkFirst = document.querySelector('#code-viewer .code-marks-line');
  return {
    rows: report.filter((r) => r.n >= 42 && r.n <= 60),
    scrollTop: Math.round(box.scrollTop),
    firstHLn: first ? first.dataset.codeLine : null,
    firstMKn: mkFirst ? mkFirst.dataset.codeLine : null,
    hlHTMLHead: document.querySelector('#code-viewer .code-hl')?.innerHTML.slice(0, 160) ?? '',
    mkHTMLHead: document.querySelector('#code-viewer .code-marks')?.innerHTML.slice(0, 160) ?? '',
  };
})()`);
console.log("scrollTop:", out.scrollTop, "firstHL:", out.firstHLn, "firstMK:", out.firstMKn);
console.log("hl head:", out.hlHTMLHead);
console.log("mk head:", out.mkHTMLHead);
for (const r of out.rows) console.log(`L${r.n} dy=${r.dy} mkY=${r.mkY} hlY=${r.hlY} guides=${JSON.stringify(r.guides)}`);
process.exit(0);
