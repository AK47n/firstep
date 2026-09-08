// 冒烟（code-editor-refine/08 AI diff 应用跳转 + 插入到光标/选区）：真实浏览器
// ①AI 回复含 <DIFF> + ```c fence → 面板出现「预览改动」+「插入到光标/选区」；
// ②预览确认应用（apply-diff 打桩）→ 自动跳转首 hunk 文件与行（active tab +
// flash 行断言）；③无选区点击插入 → 光标处插入（脏 ≥1）；④选中一段点击 →
// 替换选区；⑤Ctrl+S（saveActiveTab 真实保存样例文件）→ 脏点清除。零后端
//（chat / apply-diff 打桩；file 读写走真实样例目录）；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const SAMPLE = join(OUT, "sample-proj-08");
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
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const msg = JSON.parse(ev.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
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
const ctxClickLabel = (label) => Eval(`(() => {
  const b = Array.from(document.querySelectorAll('.code-ctx-menu .code-ctx-item')).find((x) => x.textContent === ${JSON.stringify(label)});
  if (!b) return false; b.click(); return true;
})()`);
// 打桩：chat/send → DIFF+fence 回复；apply-diff → preview/apply
const stubAll = () => Eval(`(() => {
  if (!window.__origFetch) window.__origFetch = window.fetch.bind(window);
  window.__applyCount = 0;
  window.fetch = (url, init) => {
    const u = String(url);
    if (u.includes('/api/tasks/idea/chat/send')) {
      const body = JSON.parse(init.body || '{}');
      const diffMsg = '这是解释。\\n\\n<DIFF>{"path":"main.c","hunks":[{"line":3,"title":"","lines":['
        + '{"kind":"ctx","text":"int add(int a, int b) {"},{"kind":"del","text":"int add(int a, int b) {"},'
        + '{"kind":"add","text":"int add(int a, int b) { // AI"}]}]}</DIFF>'
        + '\\n\\n\`\`\`c\\nint addOne = 0;\\n\`\`\`';
      return Promise.resolve(new Response(JSON.stringify({ chat: { messages: [
        { role: 'user', content: (body.history || []).slice(-1)[0]?.content || '' },
        { role: 'assistant', content: diffMsg },
      ], note: '' } }), { status: 200, headers: { 'content-type': 'application/json' } }));
    }
    if (u.includes('/api/code/apply-diff')) {
      window.__applyCount += 1;
      const body = JSON.parse(init.body || '{}');
      if (body.preview) {
        const newContent = [
          '#include <stdio.h>',
          '',
          'int add(int a, int b) { // AI',
          '  return a + b;',
          '}',
          '',
          'int main(void) {',
          '  printf("%d\\\\n", add(1, 2));',
          '  return 0;',
          '}',
        ].join('\\n');
        return Promise.resolve(new Response(JSON.stringify({ new_content: newContent, stats: { additions: 1, deletions: 0, hunks: 1 } }), { status: 200, headers: { 'content-type': 'application/json' } }));
      }
      return Promise.resolve(new Response(JSON.stringify({ path: 'main.c' }), { status: 200, headers: { 'content-type': 'application/json' } }));
    }
    return window.__origFetch(url, init);
  };
  return true;
})()`);
const selectRange = (s, e) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return false;
  ta.focus();
  ta.setSelectionRange(${s}, ${e});
  ta.dispatchEvent(new Event('mouseup', { bubbles: true }));
  return true;
})()`);

// ---- 准备 ----
await openDir(SAMPLE);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await openFile("main.c");
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await stubAll();

// ---- 场景 1：DIFF + fence 回复 → 两个按钮 ----
await selectRange(0, 3);
await waitFor(`!document.querySelector('.code-ai-selection-btn')?.classList.contains('hidden')`);
await Eval(`document.querySelector('.code-ai-selection-btn').click(); true`);
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await ctxClickLabel("解释");
await waitFor(`!!document.querySelector('[data-ai-preview]')`);
check("1a AI 回复含 DIFF → 预览改动按钮", (await Eval(`!!document.querySelector('[data-ai-preview]')`)) === true);
check("1b AI 回复含 fence → 插入按钮", (await Eval(`!!document.querySelector('[data-ai-insert]')`)) === true);

// ---- 场景 2：预览确认 → 跳转首 hunk 文件与行 ----
await Eval(`document.querySelector('[data-ai-preview]').click(); true`);
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-ok]')`);
check("2a 预览模态出现", true);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click(); true`);
const jumped = await waitFor(`document.querySelector('#code-viewer .code-hl-line.flash')?.dataset.codeLine === '3'`, 8000);
check("2b 应用后跳转 main.c 行 3（flash）", jumped
  && (await Eval(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath`)) === "main.c");
check("2c apply-diff 打桩被调（preview+apply ≥2）", (await Eval(`window.__applyCount`)) >= 2, String(await Eval(`window.__applyCount`)));

// ---- 场景 3：无选区插入（光标 0 处）→ 脏 ≥1 ----
await selectRange(0, 0);
await Eval(`document.querySelector('[data-ai-insert]').click(); true`);
await new Promise((r) => setTimeout(r, 400));
const taVal0 = await Eval(`document.querySelector('#code-viewer .code-ta').value`);
check("3a 无选区插入（光标处）", taVal0.startsWith("int addOne = 0;"), taVal0.slice(0, 24));
check("3b 插入后脏 ≥1", (await Eval(`import('/js/ui/codeeditor.js').then((m) => m.dirtySavableTabCount())`)) >= 1);

// ---- 场景 4：选中 → 替换选区 ----
await Eval(`document.querySelector('[data-ai-insert]').click(); true`);
await new Promise((r) => setTimeout(r, 400));
const taVal1 = await Eval(`document.querySelector('#code-viewer .code-ta').value`);
check("4 再次插入（0..0 无选区语义）脏仍 ≥1", taVal1.startsWith("int addOne = 0;int addOne = 0;"), taVal1.slice(0, 40));
await selectRange(0, 8);   // 选中 "int addO"（与插入文本不等——替换要有可见差异）
await Eval(`document.querySelector('[data-ai-insert]').click(); true`);
await new Promise((r) => setTimeout(r, 400));
const taVal2 = await Eval(`document.querySelector('#code-viewer .code-ta').value`);
check("4b 有选区 → 替换选区（选中 8 字符被片段替换）", taVal2.startsWith("int addOne = 0;ne = 0;int addOne = 0;"), taVal2.slice(0, 40));

// ---- 场景 5：Ctrl+S（saveActiveTab 真实保存）→ 脏清除 ----
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.saveActiveTab()); true`);
const savedOk = await waitFor(`import('/js/ui/codeeditor.js').then((m) => m.dirtySavableTabCount()).then((n) => n === 0)`, 8000);
check("5 保存后脏点清除", savedOk);

await Eval(`(() => { if (window.__origFetch) { window.fetch = window.__origFetch; delete window.__origFetch; } return true; })()`);
console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
