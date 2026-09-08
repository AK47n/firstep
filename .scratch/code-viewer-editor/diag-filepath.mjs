// 诊断 2：.code-file-path 信息条空态高度（非脏普通文件时按钮全 hidden）。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval: " + (r.result.exceptionDetails.exception?.description || "?"));
  return r.result?.result?.value;
};
const info = await Eval(`(() => {
  const p = document.querySelector('.code-file-path');
  const tabs = document.querySelector('#code-tabs');
  const viewer = document.querySelector('#code-viewer');
  const save = document.getElementById('btn-code-save');
  const editMd = document.getElementById('code-edit-md');
  const back = document.getElementById('code-back-preview');
  const cs = p ? getComputedStyle(p) : null;
  return {
    exists: !!p,
    pathHTML: p ? p.innerHTML.slice(0, 120) : null,
    pathHeight: p ? p.getBoundingClientRect().height : null,
    pathPadTop: cs ? cs.paddingTop : null,
    pathPadBot: cs ? cs.paddingBottom : null,
    pathLineHeight: cs ? cs.lineHeight : null,
    saveHidden: save ? save.classList.contains('hidden') : null,
    editMdHidden: editMd ? editMd.classList.contains('hidden') : null,
    backHidden: back ? back.classList.contains('hidden') : null,
    tabsBottom: tabs ? tabs.getBoundingClientRect().bottom : null,
    viewerTop: viewer ? viewer.getBoundingClientRect().top : null,
    pathTop: p ? p.getBoundingClientRect().top : null,
  };
})()`);
console.log(JSON.stringify(info, null, 1));
ws.close();
