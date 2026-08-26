// 阶段 2 工单 06 探针：ui/files.js 共用文件件实况（导出 + 浏览器内功能回路）
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
if (!page) { console.error("no page"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
};
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r.result?.result?.value ?? (r.result?.exceptionDetails ? "EXCEPTION: " + JSON.stringify(r.result.exceptionDetails.exception?.description).slice(0, 250) : "undefined");
};
await cdp("Runtime.enable");

console.log("modules load:", await Eval('(async () => { const m = await import("/js/ui/files.js"); return typeof m.addFileRow === "function" && typeof m.collectFiles === "function" && typeof m.readPickedText === "function" && typeof m.pickFilesInto === "function" && typeof m.bindFilePicker === "function"; })()'));
console.log("host stubs gone:", await Eval('document.documentElement.outerHTML.indexOf("function addFileRow") === -1 && document.documentElement.outerHTML.indexOf("function collectFiles") === -1'));
console.log("functional round trip:", await Eval(`(async () => {
  const m = await import("/js/ui/files.js");
  const c = document.createElement("div");
  m.addFileRow(c, "a.c", "int x;");
  m.addFileRow(c, "b.h", "");
  const got = m.collectFiles(c);
  const ok = got && got["a.c"] === "int x;" && got["b.h"] === "" && c.children.length === 2;
  // 行内 ✕ 移除
  c.children[0].querySelector("button").click();
  const after = m.collectFiles(c);
  return JSON.stringify({ ok, after: after && after["b.h"] === "" && !after["a.c"] && c.children.length === 1 });
})()`));
console.log("bind call sites in host:", await Eval('document.documentElement.outerHTML.indexOf(\'bindFilePicker("btn-pick-mod-files"\') !== -1 && document.documentElement.outerHTML.indexOf(\'bindFilePicker("btn-ref-pick-files"\') !== -1'));
ws.close();
