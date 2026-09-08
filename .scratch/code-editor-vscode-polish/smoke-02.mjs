// 冒烟（code-editor-vscode-polish/02）：编辑器视觉精修——
// 空态居中（.code-empty）→ 打开 main.c → 三明治键位完好（回归）+ 行高亮 +
// 右留白 24px（.code-hl/.code-ta 同步）→ GBK 只读标注存在 → 深/浅两张验收
// 截图（shot-editor-dark.png / shot-editor-light.png）。零写库；CDP 9251 +
// webapp 8000。
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
writeFileSync(join(SAMPLE, "gbk.c"),
  Buffer.from([0x2f, 0x2f, 0x20, 0xd6, 0xd0, 0xce, 0xc4, 0xd7, 0xa2, 0xca, 0xcd, 0x0a]));

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
const shot = async (name) => {
  const box = await Eval(`(() => {
    const r = document.getElementById('tab-code').getBoundingClientRect();
    return { x: Math.max(0, r.x), y: Math.max(0, r.y), w: r.width, h: r.height };
  })()`);
  const r = await cdp("Page.captureScreenshot", {
    format: "png",
    clip: { x: box.x, y: box.y, width: box.w, height: box.h, scale: 1 },
  });
  writeFileSync(join(ROOT, ".scratch", "code-editor-vscode-polish", name),
    Buffer.from(r.result.data, "base64"));
  return true;
};

await Eval(`window.__smokeMarker = 1;
  try { localStorage.removeItem('firstep.codeViewZoom'); } catch (e) {}
  true`);
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

// ================= 空态居中 =================
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
check("空态：.code-empty 存在且居中（text-align center）", await waitFor(`
  (() => {
    const el = document.querySelector('#code-viewer .code-empty');
    if (!el) return false;
    return getComputedStyle(el).textAlign === 'center'
      && el.textContent.includes('点左侧文件');
  })()`));

// ================= 打开 main.c：三明治完好（回归）+ 右留白 =================
check("目录树加载（main.c 可见）", await waitFor(`
  !!document.querySelector('#code-tree [data-code-file="main.c"]')`));
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
check("打开 main.c → 三明治键位完好（ta + hl + gutter 10 + 无 .code-empty）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return !!box.querySelector('.code-ta') && !!box.querySelector('.code-hl')
      && box.querySelectorAll('.code-gutter-line').length === 10
      && !box.querySelector('.code-empty');
  })()`));
check("右留白统一：.code-hl 与 .code-ta padding-right = 24px", await waitFor(`
  (() => {
    const hl = document.querySelector('#code-viewer .code-hl');
    const ta = document.querySelector('#code-viewer .code-ta');
    return !!hl && !!ta
      && getComputedStyle(hl).paddingRight === '24px'
      && getComputedStyle(ta).paddingRight === '24px';
  })()`));
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const pos = ta.value.indexOf('void ');
  ta.setSelectionRange(pos, pos);
  ta.dispatchEvent(new Event('click', { bubbles: true }));
  return true;
})()`);
check("当前行高亮仍在（.code-hl-line.active = 第 3 行）", await waitFor(`
  (() => {
    const hl = document.querySelector('#code-viewer .code-hl-line.active');
    return !!hl && hl.dataset.codeLine === '3';
  })()`));

// ================= GBK 只读标注 =================
await Eval(`document.querySelector('#code-tree [data-code-file="gbk.c"]')?.click()`);
check("GBK 文件 → 只读标注 .code-ro-note 存在", await waitFor(`
  !!document.querySelector('#code-viewer .code-ro-note')`));

// ================= 深浅两张验收截图 =================
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await Eval(`document.documentElement.removeAttribute('data-theme')`);   // 默认深色
await new Promise((r) => setTimeout(r, 250));
await shot("shot-editor-dark.png");
check("深色截图已保存", await Eval(`true`));
await Eval(`document.documentElement.setAttribute('data-theme', 'light')`);
await new Promise((r) => setTimeout(r, 250));
await shot("shot-editor-light.png");
check("浅色截图已保存", await Eval(`true`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
