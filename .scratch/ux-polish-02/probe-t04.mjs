// ux-polish-02 探针：工单 04 冒烟——「去任务推进」自动加载当前会话上下文。
// 依赖：webapp 8000 + Chrome 9251（无 LLM 调用；用临时目录 .cproject 造最小
// mspm0 工程，/api/revise/context 反推成功走通主路径）。
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const FAKE_DIR = "C:/Users/luoji/AppData/Local/Temp/dsh-ux-t04-proj";

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
let contextCalls = 0;
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") {
    jsErrors.push(msg.params.exceptionDetails?.exception?.description || "exception");
  }
  if (msg.method === "Network.requestWillBeSent" && msg.params.request.url.includes("/api/revise/context")) {
    contextCalls++;
  }
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

// 模拟「刚生成完」：结果区目录文本 = 临时 mspm0 工程
await Eval(`document.getElementById('res-dir').textContent = ${JSON.stringify(FAKE_DIR)}`);
const callsBefore = contextCalls;
await Eval(`(async () => { const m = await import('/js/ui/goto-tasks.js'); await m.goTaskProgress(); return true; })()`);
await new Promise((r) => setTimeout(r, 900));
const st1 = await Eval(`({
  tasksTabActive: document.querySelector('#revise-tabs .revise-tab[data-tab="tasks"]').classList.contains('active'),
  dirInput: document.getElementById('revise-dir-input').value,
  loadStatus: document.getElementById('revise-load-status').textContent,
  msg: document.getElementById('revise-load-msg').textContent,
})`);
check("自动加载触发：切任务页签 + 填入目录 + 加载完成",
  st1.tasksTabActive && st1.dirInput === FAKE_DIR && st1.loadStatus === "加载完成",
  JSON.stringify(st1));
check("自动加载发起了 /api/revise/context 请求", contextCalls > callsBefore, "calls=" + contextCalls);

// 同目录再点：应跳过（不再发请求、状态保持）
const callsBefore2 = contextCalls;
await Eval(`(async () => { const m = await import('/js/ui/goto-tasks.js'); await m.goTaskProgress(); return true; })()`);
await new Promise((r) => setTimeout(r, 500));
const st2 = await Eval(`({
  tasksTabActive: document.querySelector('#revise-tabs .revise-tab[data-tab="tasks"]').classList.contains('active'),
  loadStatus: document.getElementById('revise-load-status').textContent,
  loaded: document.getElementById('revise-context').classList.contains('hidden') === false,
})`);
check("同目录再点：跳过重复加载（无新请求）", contextCalls === callsBefore2, "calls=" + contextCalls);
check("同目录再点：面板状态保持（已加载未重置）", st2.tasksTabActive && st2.loadStatus === "加载完成" && st2.loaded, JSON.stringify(st2));

check("无未捕获 JS 异常", jsErrors.length === 0, jsErrors.join(" | ").slice(0, 300));
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
process.exit(failed ? 1 : 0);
