// 评审诊断（04 工单）：①矩阵 setCell 的折叠格是否真正折叠；②折叠态无变更
// compositionend 是否把光标拉到窗口顶。只读检查 + 打开样本文件，不改盘。
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "editor-textarea-viewport", "sample-proj");

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
if (!page) { console.error("未找到页面 target"); process.exit(1); }
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
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const modelText = () => Eval(`import('/js/ui/codeeditor.js').then((m) => m.getActiveTab()?.content ?? '')`);
const key = (k, mods) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.dispatchEvent(new KeyboardEvent('keydown', {
    key: ${JSON.stringify(k)}, code: ${JSON.stringify(k === '[' ? 'BracketLeft' : 'BracketRight')},
    ctrlKey: ${mods.ctrl}, shiftKey: ${mods.shift}, bubbles: true, cancelable: true }));
  return true;
})()`);

// 激活 bigfold.c（与 probe 同路径；样本内容从未被编辑过，内存 tab 即全新）
await Eval(`document.querySelector('#code-tree [data-code-file="bigfold.c"]')?.click(); true`);
await sleep(1200);
const waitTa = async () => {
  for (let i = 0; i < 20; i++) {
    const ok = await Eval(`!!document.querySelector('#code-viewer .code-ta') && (async () => (await import('/js/ui/codeeditor.js')).getActiveTab()?.path?.endsWith('bigfold.c'))()`);
    if (ok) return true;
    await sleep(300);
  }
  return false;
};
if (!(await waitTa())) { console.error("bigfold.c 未就绪", await Eval(`document.querySelector('#code-viewer')?.innerHTML?.slice(0,120)`)); process.exit(1); }
const dump = async (tag) => {
  const s = await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); return { hasTa: !!ta, path: (document.querySelector('#code-tree .active')||{}).dataset?.codeFile, taLen: ta ? ta.value.length : -1, ph: ta ? ta.value.includes('…') : null }; })()`);
  console.log(tag, JSON.stringify(s));
};
await dump("就绪");
// 跳行到折叠区再折叠（与 probe ② 同路径，先验证折叠本身可用）
await Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(3005); return true; })`);
await sleep(300);
await dump("跳行3005后");
await key("[", { ctrl: true, shift: true });
await sleep(400);
await dump("折叠后");
const ph1 = await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); return ta ? ta.value.includes('…') : null; })()`);
console.log("前置：折叠后窗口含占位行 =", ph1);
if (ph1 === null) process.exit(1);

// —— 诊断 A：矩阵 setCell 同款操作（光标 0,0 + 快捷键）——
await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.setSelectionRange(0, 0); return true; })()`);
await key("]", { ctrl: true, shift: true });   // setCell: 先 ']'
await key("[", { ctrl: true, shift: true });   // fold=on 时再 '['
await sleep(300);
const ph2 = await Eval(`document.querySelector('#code-viewer .code-ta').value.includes('…')`);
console.log("诊断A 矩阵同款（光标0,0 + ] / [）后窗口含占位行 =", ph2, "=>", ph2 ? "折叠格有效" : "折叠格未真正折叠（空操作）");

// —— 诊断 B：折叠态无变更 compositionend 是否拉光标到窗口顶 ——
// 先确认当前窗口起点与光标位置
const st0 = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.setSelectionRange(10, 10);
  return { sel: ta.selectionStart, len: ta.value.length };
})()`);
console.log("诊断B 前置：光标窗口内偏移 =", st0.sel, "窗口长度 =", st0.len);
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
  ta.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true }));
  return true;
})()`);
await sleep(300);
const st1 = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  return { sel: ta.selectionStart, len: ta.value.length };
})()`);
console.log("诊断B 无变更 compositionend 后：光标偏移 =", st1.sel, "（10 =>", st1.sel, st1.sel === 0 ? "光标被拉到窗口顶 = 确认缺陷" : "保持原光标 = 无缺陷）");

// —— 诊断 B2：合成 input（无值变化，同 no-change 路径）——
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(10, 10);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
await sleep(300);
const st2 = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  return { sel: ta.selectionStart };
})()`);
console.log("诊断B2 无变更 input：光标偏移 =", st2.sel, st2.sel === 10 ? "保持" : "=> 被改动（缺陷）");

// —— 诊断 B3：确认 compositionend 处理链路本身可用（有变更 → 模型回写）——
const b3a = await modelText();
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(5, 5);
  ta.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
  ta.value = ta.value.slice(0, 5) + 'Z' + ta.value.slice(5);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  ta.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true }));
  return true;
})()`);
await sleep(300);
const b3b = await modelText();
console.log("诊断B3 组合变更回写模型：", b3a !== b3b && b3b.includes("Z") ? "是（链路可用）" : "否（链路未生效！）", b3b.slice(0, 12));
process.exit(0);
