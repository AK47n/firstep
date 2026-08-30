// ux-polish-02 探针：工单 02 冒烟——初始展开、手动折叠持久化、刷新保持、清理复原。
// 依赖：webapp 8000 + Chrome 9251（无 LLM 调用）。
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const KEY = "firstep.genCardCollapse.v1";

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
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  if (msg.method === "Runtime.exceptionThrown") {
    jsErrors.push(msg.params.exceptionDetails?.exception?.description || "exception");
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
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
await cdp("Network.clearBrowserCache");   // 模块缓存会残留旧版：先清缓存再导航

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};
const collapsedCards = () => Eval(`Array.from(document.querySelectorAll('#tab-generate .gen-steps > .card.collapsed')).map((c) => c.querySelector('.step-no') ? c.querySelector('.step-no').textContent.trim() : 'x').join(',')`);
// 等待新文档提交：href 命中 token 才继续（旧文档也有 gen-overview）
const navigateNew = async () => {
  const token = "np=" + Date.now();
  await cdp("Page.navigate", { url: pageUrl + "?" + token });
  for (let i = 0; i < 120; i++) {
    try {
      const st = await Eval(`({ href: location.href, rs: document.readyState, ov: !!document.getElementById('gen-overview') })`);
      if (st.href.includes(token) && st.rs === "complete" && st.ov) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, 250));
  }
  return false;
};

// 清理折叠记忆键后重载（起点干净）
await Eval(`localStorage.removeItem(${JSON.stringify(KEY)})`);
if (!(await navigateNew())) { console.error("页面未就绪"); process.exit(1); }

check("无记忆 + 无完成步骤 → 初始无折叠卡", (await collapsedCards()) === "");

// 手动折叠步骤 3 卡（点 h2 标题即 toggle）
await Eval(`(() => {
  const card = [...document.querySelectorAll('#tab-generate .gen-steps > .card')].find((c) => {
    const no = c.querySelector('.step-no'); return no && no.textContent.trim() === '3';
  });
  card.querySelector('h2').click();
})()`);
await new Promise((r) => setTimeout(r, 200));
check("手动折叠后卡 3 带 collapsed 类", (await collapsedCards()).split(",").includes("3"));
const stored1 = await Eval(`localStorage.getItem(${JSON.stringify(KEY)})`);
check("折叠写入 localStorage 记忆", stored1 && stored1.includes('"3":true'), String(stored1));

// 刷新后保持
if (!(await navigateNew())) { console.error("刷新未就绪"); process.exit(1); }
check("刷新后卡 3 仍折叠（记忆生效）", (await collapsedCards()).split(",").includes("3"));

// 清理：移除记忆键后重载 → 全展开
await Eval(`localStorage.removeItem(${JSON.stringify(KEY)})`);
if (!(await navigateNew())) { console.error("清理重载未就绪"); process.exit(1); }
check("清除记忆后恢复全展开", (await collapsedCards()) === "");

check("无未捕获 JS 异常", jsErrors.length === 0, jsErrors.join(" | ").slice(0, 300));
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
process.exit(failed ? 1 : 0);
