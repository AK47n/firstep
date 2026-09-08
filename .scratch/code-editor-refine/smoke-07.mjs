// 冒烟（code-editor-refine/07 选中代码快捷动作）：真实浏览器验证
// ①选中代码 → 浮动按钮「问 AI ▾」→ 动作菜单四项（解释/加中文注释/重构/问 AI）；
// ②点击「解释」→ 直发 /api/tasks/idea/chat/send（fetch 打桩捕获 history）→
// 消息文本 = 模板 + 选区引用（CDP 断言）+ 自动切 AI 面板；③AI 回复含
// <DIFF> → 面板出现「预览改动」按钮（既有预览/应用闭环入口）；④回复无
// <DIFF> → 纯文本展示、无预览按钮（解析不破坏）；⑤「问 AI」= 原行为（引用
// 插入输入框，不直发）；⑥清空选择 → 按钮隐藏 + 菜单关闭。零后端（chat
// 端点打桩）；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const SAMPLE = join(OUT, "sample-proj-07");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  "#include <stdio.h>",
  "",
  "int add(int a, int b) {",
  "  return a + b;",
  "}",
  "",
  "int main(void) {",
  "  printf(\"%d\\n\", add(1, 2));",
  "  return 0;",
  "}",
].join("\n"));

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
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith(pageUrl));
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
const waitFor = async (expr, ms = 8000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await Eval(`window.__smokeMarker = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
const openDir = (dir) => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(dir)}))`);
const openFile = (name) => Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')?.click()`);
// 选第 3-5 行（add 函数体：line3 '  return a + b;' 起点在第 2 行后 — 用行 3 全文）
const selectLines = () => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return false;
  const lines = ta.value.split('\\n');
  let s = 0;
  for (let i = 0; i < 2; i++) s += lines[i].length + 1;        // 行 3 起点
  let e = s;
  for (let i = 2; i < 5; i++) e += lines[i].length + 1;        // 到行 5 末（含换行）
  ta.focus();
  ta.setSelectionRange(s, e - 1);
  ta.dispatchEvent(new Event('mouseup', { bubbles: true }));
  return true;
})()`);
const clearSelection = () => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return false;
  ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new Event('mouseup', { bubbles: true }));
  return true;
})()`);
const ctxClickLabel = (label) => Eval(`(() => {
  const b = Array.from(document.querySelectorAll('.code-ctx-menu .code-ctx-item'))
    .find((x) => x.textContent === ${JSON.stringify(label)});
  if (!b) return false;
  b.click();
  return true;
})()`);
// chat/send 打桩：捕获最后一次请求 history；回复 = assistantMsg（可含 <DIFF>）
const stubChat = (assistantMsg) => Eval(`(() => {
  if (!window.__origFetch) window.__origFetch = window.fetch.bind(window);
  window.__chatSends = window.__chatSends || [];   // 累积不清零（多次 stubbing 计数连续）
  window.fetch = (url, init) => {
    if (String(url).includes('/api/tasks/idea/chat/send')) {
      const body = JSON.parse(init.body || '{}');
      window.__chatSends.push(body.history || []);
      return Promise.resolve(new Response(JSON.stringify({
        chat: { messages: [
          { role: 'user', content: (body.history || []).slice(-1)[0]?.content || '' },
          { role: 'assistant', content: ${JSON.stringify(assistantMsg)} },
        ], note: '' },
      }), { status: 200, headers: { 'content-type': 'application/json' } }));
    }
    return window.__origFetch(url, init);
  };
  return true;
})()`);

// ---- 准备 ----
await openDir(SAMPLE);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await openFile("main.c");
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await selectLines();
await waitFor(`!document.querySelector('.code-ai-selection-btn')?.classList.contains('hidden')`);
check("0 选中 → 浮动按钮显示", (await Eval(`!!document.querySelector('.code-ai-selection-btn')`)) === true
  && (await Eval(`document.querySelector('.code-ai-selection-btn').classList.contains('hidden')`)) === false);

// ---- 场景 1：按钮 → 菜单四项 ----
await Eval(`document.querySelector('.code-ai-selection-btn').click(); true`);
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
const labels = await Eval(`Array.from(document.querySelectorAll('.code-ctx-menu .code-ctx-item')).map((b) => b.textContent).join('|')`);
check("1 动作菜单四项", labels === "解释|加中文注释|重构|问 AI", labels);

// ---- 场景 2：解释直发（模板 + 引用；DIFF 回复 → 预览按钮） ----
const DIFF_REPLY = '这是解释。\\n\\n<DIFF>{"path":"main.c","hunks":[{"line":3,"title":"","lines":['
  + '{"kind":"ctx","text":"  return a + b;"},{"kind":"del","text":"  return a + b;"},{"kind":"add","text":"  return a + b; // 和"}]}]}</DIFF>';
await stubChat(DIFF_REPLY);
await ctxClickLabel("解释");
const sendOk = await waitFor(`(window.__chatSends || []).length === 1`);
check("2 解释 → chat/send 直发 1 次", sendOk);
const lastSent = await Eval(`(window.__chatSends[0] || []).slice(-1)[0]?.content || ''`);
check("2b 发送文本 = 模板 + 选区引用",
  lastSent.includes("解释") && lastSent.includes("不要修改代码")
  && lastSent.includes("【代码引用 · main.c · 第 3-5 行】") && lastSent.includes("return a + b;"),
  lastSent.slice(0, 80));
check("2c 自动切 AI 面板并渲染 assistant", await waitFor(`!!document.querySelector('#code-ai-chat-body .sugg-msg.ai')`));
check("2d DIFF 回复 → 预览改动按钮", await waitFor(`!!document.querySelector('[data-ai-preview]')`));

// ---- 场景 3：重构（无 DIFF 回复 → 纯文本，无预览按钮，解析不破坏） ----
await stubChat("重构建议：可以直接内联 add 函数。");
await selectLines();
await Eval(`document.querySelector('.code-ai-selection-btn').click(); true`);
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await ctxClickLabel("重构");
const ok3 = await waitFor(`(window.__chatSends || []).length === 2`);
check("3 重构 → 第 2 次直发", ok3);
const sent3 = await Eval(`(window.__chatSends[1] || []).slice(-1)[0]?.content || ''`);
check("3b 重构文本含模板约束", sent3.includes("重构") && sent3.includes("<DIFF>"), sent3.slice(0, 60));
await new Promise((r) => setTimeout(r, 500));
check("3c 无 DIFF 回复 → 无预览按钮（纯文本展示）",
  (await Eval(`document.querySelectorAll('[data-ai-preview]').length`)) === 0
  && (await Eval(`document.querySelector('#code-ai-chat-body').textContent.includes('重构建议')`)) === true);

// ---- 场景 4：问 AI = 原行为（引用插入输入框，不直发） ----
await selectLines();
await Eval(`document.querySelector('.code-ai-selection-btn').click(); true`);
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await ctxClickLabel("问 AI");
await new Promise((r) => setTimeout(r, 300));
const inputVal = await Eval(`document.querySelector('#code-ai-chat-input')?.value || ''`);
check("4 问 AI → 引用插入输入框", inputVal.includes("【代码引用 · main.c · 第 3-5 行】"), inputVal.slice(0, 60));
check("4b 未新增直发", (await Eval(`(window.__chatSends || []).length`)) === 2);

// ---- 场景 5：清空选择 → 按钮隐藏 + 菜单关闭 ----
await selectLines();
await Eval(`document.querySelector('.code-ai-selection-btn').click(); true`);
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await clearSelection();
await new Promise((r) => setTimeout(r, 300));
check("5a 清空选择 → 按钮隐藏", (await Eval(`document.querySelector('.code-ai-selection-btn')?.classList.contains('hidden')`)) === true);
check("5b 清空选择 → 菜单关闭", (await Eval(`!!document.querySelector('.code-ctx-menu')`)) === false);

await Eval(`(() => { if (window.__origFetch) { window.fetch = window.__origFetch; delete window.__origFetch; } return true; })()`);
console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
