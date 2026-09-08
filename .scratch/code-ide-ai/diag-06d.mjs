// 最小复现 S7：dirty 标签 + diff app 预览确认 → 写盘守卫弹窗
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-ide-ai", "sample-proj");

const DIFF_APP = "app.c 建议加头文件：\n<DIFF>\n"
  + JSON.stringify({
    path: "src/app.c",
    hunks: [
      { line: 1, title: "补充头文件", lines: [
        { kind: "del", text: "#include <stdint.h>" },
        { kind: "add", text: "#include <stdint.h>" },
        { kind: "add", text: "#include <string.h>" },
      ] },
    ],
  })
  + "\n</DIFF>";

rmSync(SAMPLE, { recursive: true, force: true });
mkdirSync(join(SAMPLE, "src"), { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), "int main(void) {\n  return 0;\n}\n", "utf8");
writeFileSync(join(SAMPLE, "src", "app.c"), "#include <stdint.h>\n", "utf8");
writeFileSync(join(SAMPLE, "readme.md"), "# 样本\n", "utf8");

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
const page = targets.find((t) => t.type === "page" && t.url.includes("127.0.0.1:8000")) || targets[0];
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) return "ERR: " + (r.result.exceptionDetails.exception?.description || "?");
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 6000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await cdp("Page.navigate", { url: pageUrl });
for (let i = 0; i < 100; i++) {
  try { if (await Eval(`document.readyState === 'complete' && !!document.getElementById('tab-code')`)) break; } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`localStorage.clear()`);
await cdp("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 1200));
await Eval(`(() => {
  const real = window.fetch.bind(window);
  window.fetch = (url, opts) => {
    const u = String(url);
    if (u.includes('/api/tasks/idea/chat/read')) {
      return Promise.resolve(new Response(JSON.stringify({ chat: { messages: [], note: '' } }), {
        status: 200, headers: { 'Content-Type': 'application/json' } }));
    }
    if (u.includes('/api/tasks/idea/chat/send')) {
      const body = JSON.parse((opts && opts.body) || '{}');
      const history = body.history || [];
      const reply = ${JSON.stringify(DIFF_APP)};
      const chat = {
        messages: history.map((m, i) => ({ role: m.role, content: m.content, at: '14:0' + i }))
          .concat([{ role: 'assistant', content: reply, at: '14:09' }]),
        note: '',
      };
      return Promise.resolve(new Response(JSON.stringify({ reply, chat }), {
        status: 200, headers: { 'Content-Type': 'application/json' } }));
    }
    return real(url, opts);
  };
  return true;
})()`);

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="src/app.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="src/app.c"]').click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
// 弄脏标签
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '// local dirty\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
// send
await Eval(`(() => {
  const input = document.getElementById('code-ai-chat-input');
  input.value = 'app.c 加个 string.h';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  return true;
})()`);
console.log("button appears:", await waitFor(`!!document.querySelector('#code-ai-chat-body [data-ai-preview]')`));
await Eval(`document.querySelector('#code-ai-chat-body [data-ai-preview]').click()`);
console.log("preview overlay:", await waitFor(`!!document.querySelector('.ref-files-overlay')`));
console.log("confirm-ok:", await Eval(`document.querySelectorAll('.ref-files-overlay [data-confirm-ok]').length`));
console.log("overlay text head:", await Eval(`(document.querySelector('.ref-files-overlay') || { innerHTML: '' }).innerHTML.replace(/<[^>]+>/g, ' ').slice(0, 300)`));
// 确认 → 守卫弹窗
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
console.log("guard overlay (未保存):", await waitFor(`
  (() => { const m = document.querySelector('.ref-files-overlay');
    return m && m.textContent.includes('未保存修改') && m.textContent.includes('保存全部并继续'); })()`));
console.log("guard overlay html:", await Eval(`(document.querySelector('.ref-files-overlay') || { innerHTML: '' }).innerHTML.replace(/<[^>]+>/g, ' ').slice(0, 300)`));
ws.close();
