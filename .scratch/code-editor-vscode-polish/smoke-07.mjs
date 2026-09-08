// 冒烟（code-editor-vscode-polish/07）：代码折叠——
// Ctrl+Shift+[ 折叠（gutter 出现占位行/模型行号跳号、textarea = 视图文本）→
// 箭头点击展开 → 占位行点击展开 → 折叠态下跳行（editJumpToLine 落在折叠区
// 内）自动展开 → 折叠态编辑（内容经偏移映射写模型、脏点出现、折叠保持）。
// 零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

const SAMPLE = join(ROOT, ".scratch", "code-editor-vscode-polish", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  "void helper(void) {",
  "    int x = 0;",
  "}",
  "",
  "int main(void) {",
  "    helper();",
  "    return 0;",
  "}",
].join("\n"));
writeFileSync(join(SAMPLE, "readme.md"), "# 样本\n\n正文段落。\n");

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

await Eval(`window.__smokeMarker = 1;
  try { localStorage.removeItem('firstep.codeViewZoom'); } catch (e) {}
  true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-viewer') && !!document.getElementById('code-tabs')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
const gutterNos = `[...document.querySelectorAll('#code-viewer .code-gutter-line')].map((g) => g.dataset.codeLine)`;

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
check("打开 main.c → 8 行 gutter", await waitFor(`
  document.querySelectorAll('#code-viewer .code-gutter-line').length === 8`));

// ================= Ctrl+Shift+[ 折叠 helper =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.indexOf('helper'), ta.value.indexOf('helper'));
  document.dispatchEvent(new KeyboardEvent('keydown', {
    key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true,
  }));
  return true;
})()`);
check("Ctrl+Shift+[ → 折叠：gutter 7 行（占位 1）+ 模型行号跳号 + 视图文本含占位", await waitFor(`
  (() => {
    const g = ${gutterNos};
    const ta = document.querySelector('#code-viewer .code-ta');
    return g.length === 7 && g[0] === '1' && g[1] === '2'
      && g[2] === '4' && g[6] === '8'
      && !!document.querySelector('#code-viewer .code-gutter-ph')
      && ta.value.includes('… 2 行');
  })()`));

// ================= 箭头点击展开 =================
await Eval(`document.querySelector('#code-viewer .code-fold-arrow[data-fold="0"]')?.click()`);
check("箭头点击 → 展开（gutter 回 8 行）", await waitFor(`
  document.querySelectorAll('#code-viewer .code-gutter-line').length === 8`));

// ================= 占位行点击展开 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.indexOf('helper'), ta.value.indexOf('helper'));
  document.dispatchEvent(new KeyboardEvent('keydown', {
    key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true,
  }));
  return true;
})()`);
await waitFor(`!!document.querySelector('#code-viewer .code-gutter-ph')`);
await Eval(`document.querySelector('#code-viewer .code-gutter-ph')?.click()`);
check("占位行点击 → 展开（gutter 回 8 行）", await waitFor(`
  document.querySelectorAll('#code-viewer .code-gutter-line').length === 8`));

// ================= 折叠态跳行自动展开 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.indexOf('helper'), ta.value.indexOf('helper'));
  document.dispatchEvent(new KeyboardEvent('keydown', {
    key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true,
  }));
  return true;
})()`);
await waitFor(`!!document.querySelector('#code-viewer .code-gutter-ph')`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.editJumpToLine(2))`);
check("跳行到折叠区内（行 2）→ 自动展开（选区落行 2 行首）", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return !document.querySelector('#code-viewer .code-gutter-ph')
      && ta.selectionStart === 'void helper(void) {\\n'.length;
  })()`));

// ================= 折叠态编辑（映射写模型 + 脏点 + 折叠保持） =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(ta.value.indexOf('helper'), ta.value.indexOf('helper'));
  document.dispatchEvent(new KeyboardEvent('keydown', {
    key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true,
  }));
  return true;
})()`);
await waitFor(`!!document.querySelector('#code-viewer .code-gutter-ph')`);
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const at = ta.value.indexOf('helper');
  ta.value = ta.value.slice(0, at) + 'void helper2' + ta.value.slice(at + 'void helper'.length);
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("折叠态编辑：脏点出现 + 折叠保持（占位仍在）", await waitFor(`
  !!document.querySelector('#code-tabs .code-tab-dirty')
    && !!document.querySelector('#code-viewer .code-gutter-ph')
    && document.querySelector('#code-viewer .code-ta').value.includes('helper2')`));

// ================= 全展开残留（占位整块替换 → 全部展开回全量） =================
// 上一用例结束时折叠仍激活（编辑保持折叠）——直接替换占位行文本。
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value.replace('… 2 行', 'NEW');
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("占位整块替换 → 全部展开：无占位、视图无占位文案、gutter 7 行（2 隐藏行被 1 行替换）", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return !document.querySelector('#code-viewer .code-gutter-ph')
      && !ta.value.includes('… 2 行')
      && ta.value.includes('NEW')
      && document.querySelectorAll('#code-viewer .code-gutter-line').length === 7;
  })()`));

// ================= .md 预览标题折叠 =================
await Eval(`(() => {
  const enc = encodeURIComponent('readme.md');
  return import('/js/ui/codeview.js').then(() => {
    document.querySelector('#code-tree [data-code-file="readme.md"]')?.click();
    return true;
  });
})()`);
check(".md 预览 → details.code-md-fold + summary 点击收起", await waitFor(`
  (() => {
    const d = document.querySelector('#code-viewer details.code-md-fold');
    return !!d && !!d.querySelector('summary') && d.open === true;
  })()`));
await Eval(`document.querySelector('#code-viewer details.code-md-fold summary')?.click()`);
check("summary 点击 → 组收起（details.open = false）", await waitFor(`
  !document.querySelector('#code-viewer details.code-md-fold').open`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
