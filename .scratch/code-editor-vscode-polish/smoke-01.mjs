// 冒烟（code-editor-vscode-polish/01）：底部状态栏 VS Code 化——
// 打开样本目录（无文件 → 信息区空）→ 打开 main.c → 信息区出现
// Ln 1, Col 1 / C / UTF-8 / 空格: 4 / 100% → 移动光标 → Ln/Col 变化 →
// Ctrl+滚轮缩放 → 缩放百分比联动。零写库（样本在 .scratch 下，git 忽略；
// 不保存）。零依赖：node 内置 fetch + WebSocket 直连 Chrome CDP（9251）；
// webapp 8000 提供真实 API。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

// ---- 样本工程（.scratch/code-editor-vscode-polish/sample-proj，git 忽略） ----
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
      && !!document.getElementById('tab-code')
      && !!document.getElementById('code-statusbar-info')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// ================= 打开目录（不指定文件）→ 信息区空态 =================
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
check("目录打开：树加载（main.c 可见；其余样本文件各冒烟自建）", await waitFor(`
  (() => {
    const paths = [...document.querySelectorAll('#code-tree [data-code-file]')].map((b) => b.dataset.codeFile);
    return paths.includes('main.c');
  })()`));
check("无活动文件 → 信息区占位「未打开文件」", await Eval(`
  document.getElementById('code-statusbar-info').textContent.includes('未打开文件')`));

// ================= 打开 main.c → 状态栏信息出现 =================
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
check("打开 main.c → 信息区 Ln 1, Col 1 / C / UTF-8 / 空格: 4 / 100%", await waitFor(`
  (() => {
    const t = document.getElementById('code-statusbar-info').textContent;
    return t.includes('Ln 1, Col 1') && t.includes('C') && t.includes('UTF-8')
      && t.includes('空格: 4') && t.includes('100%');
  })()`));

// ================= 光标移动 → Ln/Col 联动 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const pos = ta.value.indexOf('void ') + 4;  // 第 3 行「void 」的末尾空格 = 第 5 列
  ta.setSelectionRange(pos, pos);
  ta.dispatchEvent(new Event('keyup', { bubbles: true }));
  return true;
})()`);
check("光标移到第 3 行第 5 列 → Ln 3, Col 5", await waitFor(`
  document.getElementById('code-statusbar-info').textContent.includes('Ln 3, Col 5')`));

// ================= 缩放联动 =================
await Eval(`(() => {
  const view = document.getElementById('code-viewer');
  view.dispatchEvent(new WheelEvent('wheel', { ctrlKey: true, deltaY: -100, bubbles: true, cancelable: true }));
  return true;
})()`);
check("Ctrl+滚轮放大 10% → 状态栏 110%", await waitFor(`
  document.getElementById('code-statusbar-info').textContent.includes('110%')`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
