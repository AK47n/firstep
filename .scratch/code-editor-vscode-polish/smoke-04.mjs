// 冒烟（code-editor-vscode-polish/04）：文件内查找高亮 + 计数——
// 输入「void」→ 编辑器标记层 3 处（2 hit + 1 current）、计数「第 1 / 共 3 处」
// → Enter 循环到第 2 处（选区落第二处）→ Shift+Enter 回第 1 处 → Esc 清空
// （标记层与计数消失）。零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

const SAMPLE = join(ROOT, ".scratch", "code-editor-vscode-polish", "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  "#include <stdint.h>",
  "",
  "void helper(void) {",
  "    int x = 0;",
  "}",
  "",
  "int main(void) {",
  "    helper();",
  "    return 0;",
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

await Eval(`window.__smokeMarker = 1;
  try { localStorage.removeItem('firstep.codeViewZoom'); } catch (e) {}
  true`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-find-input') && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// ================= 打开 main.c =================
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
check("打开 main.c → 编辑三明治就绪", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return !!box.querySelector('.code-ta') && !!box.querySelector('.code-marks')
      && box.querySelectorAll('.code-gutter-line').length === 10;
  })()`));

// ================= 查找「void」→ 高亮 + 计数 =================
await Eval(`(() => {
  const input = document.getElementById('code-find-input');
  input.value = 'void';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("标记层 3 处（2 hit + 1 current）+ 计数「第 1 / 共 3 处」", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    const cnt = document.getElementById('code-find-count');
    return cnt && !cnt.classList.contains('hidden') && cnt.textContent === '第 1 / 共 3 处'
      && box.querySelectorAll('.code-mark-hit').length === 2
      && box.querySelectorAll('.code-mark-current').length === 1;
  })()`));

// ================= Enter → 第 2 处（选区落第二处） =================
await Eval(`(() => {
  const input = document.getElementById('code-find-input');
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  return true;
})()`);
check("Enter → 第 2 / 共 3 处 + 选区覆盖第 2 处（行 3 列 13）", await waitFor(`
  (() => {
    const cnt = document.getElementById('code-find-count');
    if (!cnt || cnt.textContent !== '第 2 / 共 3 处') return false;
    const ta = document.querySelector('#code-viewer .code-ta');
    const lines = ta.value.split('\\n');
    const line3Start = lines.slice(0, 2).join('\\n').length + 1;
    return ta.selectionStart === line3Start + 12 && ta.selectionEnd === line3Start + 16;
  })()`));

// ================= Shift+Enter → 回第 1 处 =================
await Eval(`(() => {
  const input = document.getElementById('code-find-input');
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', shiftKey: true, bubbles: true, cancelable: true }));
  return true;
})()`);
check("Shift+Enter → 回第 1 / 共 3 处", await waitFor(`
  document.getElementById('code-find-count').textContent === '第 1 / 共 3 处'`));

// ================= Esc → 清空（标记与计数消失） =================
await Eval(`(() => {
  const input = document.getElementById('code-find-input');
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
  return true;
})()`);
check("Esc → 输入清空 + 计数隐藏 + 标记层无 mark span", await waitFor(`
  (() => {
    const cnt = document.getElementById('code-find-count');
    const box = document.getElementById('code-viewer');
    return document.getElementById('code-find-input').value === ''
      && cnt.classList.contains('hidden')
      && !box.querySelector('.code-mark-hit') && !box.querySelector('.code-mark-current');
  })()`));

// ================= 将替换 N 处 + 无匹配文案 =================
await Eval(`(() => {
  const input = document.getElementById('code-find-input');
  input.value = 'void';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("替换计数「将替换 3 处」可见", await waitFor(`
  (() => {
    const rc = document.getElementById('code-replace-count');
    return rc && !rc.classList.contains('hidden') && rc.textContent === '将替换 3 处';
  })()`));
await Eval(`(() => {
  const input = document.getElementById('code-find-input');
  input.value = 'zzz';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("无命中 → 计数「无匹配」+ 替换计数隐藏", await waitFor(`
  (() => {
    const cnt = document.getElementById('code-find-count');
    const rc = document.getElementById('code-replace-count');
    return cnt && !cnt.classList.contains('hidden') && cnt.textContent === '无匹配'
      && rc.classList.contains('hidden');
  })()`));

// ================= 编辑内容后标记层重算（评审整改 04） =================
await Eval(`(() => {
  const input = document.getElementById('code-find-input');
  input.value = 'void';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("恢复查询 void → 第 1 / 共 3 处", await waitFor(`
  document.getElementById('code-find-count').textContent === '第 1 / 共 3 处'`));
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = 'xx\\n' + ta.value;   // 顶部插入两行 → 命中位置整体下移
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("编辑后重算：命中仍 2 hit + 1 current、计数不变", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return box.querySelectorAll('.code-mark-hit').length === 2
      && box.querySelectorAll('.code-mark-current').length === 1
      && document.getElementById('code-find-count').textContent === '第 1 / 共 3 处';
  })()`));
await Eval(`(() => {
  const input = document.getElementById('code-find-input');
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
  return true;
})()`);
check("收尾 Esc → 标记层清除", await waitFor(`
  !document.querySelector('#code-viewer .code-mark-hit')`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
