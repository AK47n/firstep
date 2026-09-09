// 一次性小探针：确认 editor 负载真的装进了编辑器（big.c 模型长度 / 窗口化切片）。
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251, pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-editor-cdp-hang", "sample-proj");
const list = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const t = list.find((x) => x.type === "page" && x.url.startsWith(pageUrl));
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res, rej) => {
  const id = ++seq; const to = setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error("timeout " + method)); } }, 15000);
  pending.set(id, (m) => { clearTimeout(to); res(m); }); ws.send(JSON.stringify({ id, method, params }));
});
const Eval = async (e) => (await cdp("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true })).result?.result?.value;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 60; i++) { try { if (await Eval(`document.readyState==='complete' && !!document.getElementById('code-viewer')`)) break; } catch {} await sleep(250); }
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
for (let i = 0; i < 40; i++) { if (await Eval(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`)) break; await sleep(250); }
console.log("树里找到 big.c：", await Eval(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`));
await Eval(`document.querySelector('#code-tree [data-code-file="big.c"]')?.click()`);
await sleep(2500);
console.log("textarea 长度：", await Eval(`document.getElementById('code-editor-textarea')?.value?.length ?? -1`));
console.log("gutter 行数：", await Eval(`document.querySelectorAll('#code-gutter .code-line-no').length`));
console.log("code-edit 高度：", await Eval(`document.querySelector('.code-edit')?.style?.height ?? 'n/a'`));
console.log("标签数：", await Eval(`document.querySelectorAll('#code-tabs .code-tab').length`));
console.log("active tab 路径：", await Eval(`document.querySelector('#code-tabs .code-tab.active')?.dataset?.codeTab ?? document.querySelector('#code-tabs .code-tab.active')?.innerText ?? 'n/a'`));
ws.close();
