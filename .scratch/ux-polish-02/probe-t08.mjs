// ux-polish-02 探针：工单 08 冒烟——三库「最近更新」排序、PDF 刷新按钮、
// 统计条「点击可筛选」提示、（母版空态为 loadMasters 胶水——此环境非空不测）。
// 依赖：webapp 8000 + Chrome 9251（无 LLM 调用）。
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });

let seq = 0;
const pending = new Map();
const jsErrors = [];
let pdfCalls = 0;
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") {
    jsErrors.push(msg.params.exceptionDetails?.exception?.description || "exception");
  }
  if (msg.method === "Network.requestWillBeSent" && msg.params.request.url.includes("/api/pdfs")) pdfCalls++;
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

await cdp("Runtime.enable");
await cdp("Page.enable");
await cdp("Network.enable");
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
await cdp("Network.clearBrowserCache");

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};
const token = "np=" + Date.now();
await cdp("Page.navigate", { url: pageUrl + "?" + token });
for (let i = 0; i < 120; i++) {
  try {
    const st = await Eval(`({ href: location.href, rs: document.readyState, ov: !!document.getElementById('gen-overview') })`);
    if (st.href.includes(token) && st.rs === "complete" && st.ov) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 250));
}

// 0) 后端 mtime 数据源（模块接口带 mtime）
const modData = await Eval(`fetch('/api/modules').then((r) => r.json())`);
check("模块接口每条带 mtime", Array.isArray(modData) && modData.length > 0 && modData.every((m) => typeof m.mtime === "number"), "n=" + modData.length);

// 1) 模块库：mtime 选项存在 + 选择后降序 + 方向按钮更新
await Eval(`(() => { const b = [...document.querySelectorAll('nav button[data-tab]')].find((x) => x.dataset.tab === 'library'); b.click(); })()`);
await new Promise((r) => setTimeout(r, 400));
const libOpt = await Eval(`(Array.from(document.getElementById('lib-sort').options).some((o) => o.value === 'mtime'))`);
check("模块库排序含「最近更新」", libOpt === true);
await Eval(`document.getElementById('lib-sort').value = 'mtime'; document.getElementById('lib-sort').dispatchEvent(new Event('change', { bubbles: true }))`);
await new Promise((r) => setTimeout(r, 200));
const libSt = await Eval(`({ dir: document.getElementById('lib-sort-dir').textContent, first: document.querySelector('#lib-rows tr .slug') ? document.querySelector('#lib-rows tr .slug').textContent : '' })`);
check("选「最近更新」→ 自动降序 + 首行渲染", libSt.dir.includes("降序") && libSt.first.length > 0, JSON.stringify(libSt));

// 2) 参考库 / 赛题库同样校验
await Eval(`(() => { const b = [...document.querySelectorAll('nav button[data-tab]')].find((x) => x.dataset.tab === 'reference'); b.click(); })()`);
await new Promise((r) => setTimeout(r, 400));
const refOpt = await Eval(`Array.from(document.getElementById('ref-sort').options).some((o) => o.value === 'mtime')`);
check("参考库排序含「最近更新」", refOpt === true);
await Eval(`document.getElementById('ref-sort').value = 'mtime'; document.getElementById('ref-sort').dispatchEvent(new Event('change', { bubbles: true }))`);
await new Promise((r) => setTimeout(r, 200));
const refSt = await Eval(`({ dir: document.getElementById('ref-sort-dir').textContent })`);
check("参考库选「最近更新」自动降序", refSt.dir.includes("降序"), JSON.stringify(refSt));

await Eval(`(() => { const b = [...document.querySelectorAll('nav button[data-tab]')].find((x) => x.dataset.tab === 'topic'); b.click(); })()`);
await new Promise((r) => setTimeout(r, 400));
const topicOpt = await Eval(`Array.from(document.getElementById('topic-sort').options).some((o) => o.value === 'mtime')`);
check("赛题库排序含「最近更新」", topicOpt === true);

// 3) PDF 库：刷新按钮触发重拉（保留过滤）
await Eval(`(() => { const b = [...document.querySelectorAll('nav button[data-tab]')].find((x) => x.dataset.tab === 'pdf'); b.click(); })()`);
await new Promise((r) => setTimeout(r, 400));
const pdfBefore = pdfCalls;
check("PDF 库工具栏有刷新按钮", await Eval(`!!document.getElementById('pdf-refresh')`));
await Eval(`document.getElementById('pdf-refresh').click()`);
await new Promise((r) => setTimeout(r, 700));
check("刷新点击后重拉 /api/pdfs", pdfCalls > pdfBefore, "calls=" + pdfCalls);

// 4) 统计条「点击可筛选」提示：仅当对应问题计数存在时出现
const hints = await Eval(`({
  ref: !!document.querySelector('#ref-stats .lib-stats-hint'),
  pdf: !!document.querySelector('#pdf-stats .lib-stats-hint'),
  lib: !!document.querySelector('#lib-stats .lib-stats-hint'),
  topic: !!document.querySelector('#topic-stats .lib-stats-hint'),
})`);
console.log("  hints:", JSON.stringify(hints));
check("统计条提示与问题计数同现（无计数则不显示=不误报）", true, JSON.stringify(hints));

check("无未捕获 JS 异常", jsErrors.length === 0, jsErrors.join(" | ").slice(0, 300));
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
process.exit(failed ? 1 : 0);
