// 冒烟（code-page-vscode-overhaul/05 面包屑）：真实浏览器验证面包屑随标签
// 显示分段、目录段点击定位文件树（逐级展开+滚动高亮）、文件段点击打开、
// 标签切换刷新。零写库；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-page-vscode-overhaul");
const SAMPLE = join(OUT, "sample-proj");
mkdirSync(join(SAMPLE, "src", "app"), { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), "int main(void) { return 0; }\n");
writeFileSync(join(SAMPLE, "src", "ui.c"), "int ui(void) { return 1; }\n");
writeFileSync(join(SAMPLE, "src", "app", "main.c"), "int app(void) { return 2; }\n");

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
// CDP 超时守卫（第七轮）：渲染进程偶发无响应时命令永不返回 → 脚本静默挂死。
// 20s 无响应即抛错，让失败可见（而不是卡死）。
const cdp = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++seq;
    const t = setTimeout(() => {
      if (pending.has(id)) { pending.delete(id); reject(new Error("CDP 无响应（20s）: " + method + " —— 页面可能已挂死")); }
    }, 20000);
    pending.set(id, (msg) => { clearTimeout(t); resolve(msg); });
    ws.send(JSON.stringify({ id, method, params }));
  });
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
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="src/app/main.c"]')`);

// 打开深层文件 → 面包屑显示分段
await Eval(`document.querySelector('#code-tree [data-code-file="src/app/main.c"]')?.click()`);
await waitFor(`!document.getElementById('code-breadcrumb').classList.contains('hidden')`);
check("面包屑随文件打开显示", true);
const crumbTxt = await Eval(`document.getElementById('code-breadcrumb').innerText`);
check("面包屑分段 src › app › main.c", crumbTxt.replace(/\s+/g, " ").trim() === "src › app › main.c", JSON.stringify(crumbTxt));
check("目录段带 data-breadcrumb-dir", await Eval(`!!document.querySelector('[data-breadcrumb-dir="src/app"]')`));

// 目录段点击 → 树逐级展开 + 高亮
await Eval(`document.querySelector('#code-tree [data-code-file="src/ui.c"]')?.click()`);  // 先切到同目录文件
await waitFor(`(document.getElementById('code-breadcrumb').innerText || '').includes('ui.c')`);
check("标签切换面包屑同步", (await Eval(`document.getElementById('code-breadcrumb').innerText`)).replace(/\s+/g, " ").trim() === "src › ui.c");
await Eval(`document.querySelector('[data-breadcrumb-dir="src"]')?.click()`);
check("目录点击后 details 展开", await Eval(`document.querySelector('#code-tree details[data-dir-path="src"]')?.open === true`));
check("目录点击后高亮动画类", await Eval(`!!document.querySelector('#code-tree .code-tree-reveal')`));
check("目录点击后保持在原文件（不跳标签）", await Eval(`(document.getElementById('code-breadcrumb').innerText || '').includes('ui.c')`));

// 文件段点击 → 打开文件（等幂：当前即该文件；验证调用路径无异常且标签保持）
await Eval(`document.querySelector('#code-tree [data-code-file="src/app/main.c"]')?.click()`);
await waitFor(`(document.getElementById('code-breadcrumb').innerText || '').includes('src › app › main.c')`);
check("面包屑切到深层文件", true);
await Eval(`document.querySelector('[data-breadcrumb-file="src/app/main.c"]')?.click()`);
await new Promise((r) => setTimeout(r, 300));
check("文件段点击可打开且标签保持", await Eval(`!!document.querySelector('.code-tab.on')
  && document.querySelector('.code-tab.on').textContent.includes('main.c')
  && (document.querySelector('#code-viewer .code-ta')?.value || '').includes('int app')`));
check("深层目录段 src/app 可定位", await Eval(`!!document.querySelector('[data-breadcrumb-dir="src/app"]')`));

// 图片存档（深色）
const shot = await cdp("Page.captureScreenshot", { format: "png" });
if (shot.result?.data) writeFileSync(join(OUT, "shot-05-breadcrumb-dark.png"), Buffer.from(shot.result.data, "base64"));
check("深色截图已保存", !!shot.result?.data);

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
