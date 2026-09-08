// 诊断：编辑器首行上方空行来源（用户反馈）。只读查询，不改页面。
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
  const ta = document.querySelector('#code-viewer .code-ta');
  const edit = document.querySelector('#code-viewer .code-edit');
  const hl = document.querySelector('#code-viewer .code-hl');
  const gutter = document.querySelector('#code-viewer .code-gutter');
  if (!ta) return { err: 'no ta' };
  const lines = ta.value.split('\\n');
  return {
    beforeText: JSON.stringify(ta.value.slice(0, 30)),
    startsWithNL: ta.value.startsWith('\\n'),
    lineCount: lines.length,
    firstLineShown: JSON.stringify(lines[0]),
    secondLineShown: JSON.stringify(lines[1]),
    editPaddingTop: edit ? getComputedStyle(edit).paddingTop : null,
    viewerChildren: [...document.querySelector('#code-viewer').children]
      .map((c) => c.tagName + '.' + String(c.className)),
    editTop: edit ? edit.getBoundingClientRect().y : null,
    hlFirstTop: hl && hl.firstElementChild
      ? hl.firstElementChild.getBoundingClientRect().y : null,
    hlLines: hl ? hl.querySelectorAll('.code-hl-line').length : null,
    gutterLineCount: gutter ? gutter.querySelectorAll('.code-gutter-line').length : null,
    filePathEl: !!document.querySelector('#code-viewer .code-file-path'),
    activeTab: document.querySelector('#code-tabs .code-tab.on .code-tab-name')?.textContent || null,
    dir: document.querySelector('.code-dir-label')?.textContent || null,
  };
})()`);
console.log(JSON.stringify(info, null, 1));
ws.close();
