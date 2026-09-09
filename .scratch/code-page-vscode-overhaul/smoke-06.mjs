// 冒烟（code-page-vscode-overhaul/06 底部面板 tab 化）：真实浏览器验证单容器
// + 页签条行为——初始隐藏零页签、showPanel 自动切页签、点击切换、同一时刻
// 只显示一个、hidePanel 撤页签、全撤容器隐藏、各面板 .collapsed 独立保留。
// 不触发真实编译/烧录/AI API（用模块直接驱动）；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-page-vscode-overhaul");
const SAMPLE = join(OUT, "sample-proj");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), "int main(void) { return 0; }\n");

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
      && !!document.getElementById('tab-code') && !!document.getElementById('code-bottom-panels')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

check("初始容器隐藏且无页签", await Eval(`document.getElementById('code-bottom-panels').classList.contains('hidden')
  && document.querySelectorAll('#code-bottom-tabs .code-bottom-tab').length === 0`));

const show = (id) => Eval(`import('/js/ui/code-bottom-panels.js').then((m) => { m.showPanel(${JSON.stringify(id)}); return true; })`);

await show("compile");
check("showPanel(compile)：容器显示 + 页签 1 个", await Eval(`!document.getElementById('code-bottom-panels').classList.contains('hidden')
  && document.querySelectorAll('#code-bottom-tabs .code-bottom-tab').length === 1
  && document.querySelector('[data-bottom-tab="compile"]')?.classList.contains('on')`));
check("仅编译面板可见", await Eval(`!document.getElementById('code-compile-panel').classList.contains('hidden')
  && document.getElementById('code-change-panel').classList.contains('hidden')`));

await show("ai");
check("showPanel(ai)：自动切换 AI 页签", await Eval(`document.querySelector('[data-bottom-tab="ai"]')?.classList.contains('on')
  && document.querySelectorAll('#code-bottom-tabs .code-bottom-tab').length === 2`));
check("同一时刻只显示一个面板", await Eval(`!document.getElementById('code-ai-chat-panel').classList.contains('hidden')
  && document.getElementById('code-compile-panel').classList.contains('hidden')`));

// 点击页签切换回编译
await Eval(`document.querySelector('[data-bottom-tab="compile"]')?.click(); true`);
check("点击页签切换回编译", await Eval(`document.querySelector('[data-bottom-tab="compile"]')?.classList.contains('on')
  && !document.getElementById('code-compile-panel').classList.contains('hidden')
  && document.getElementById('code-ai-chat-panel').classList.contains('hidden')`));

// AI 收起态独立保留：收起 → 切走 → 切回仍收起（头部在、内容隐藏）
await show("ai");
await Eval(`document.getElementById('btn-code-ai-collapse')?.click(); true`);
check("AI 面板可收起", await Eval(`document.getElementById('code-ai-chat-panel').classList.contains('collapsed')`));
await Eval(`document.querySelector('[data-bottom-tab="compile"]')?.click(); true`);
await Eval(`document.querySelector('[data-bottom-tab="ai"]')?.click(); true`);
check("切回后收起态保留", await Eval(`document.getElementById('code-ai-chat-panel').classList.contains('collapsed')`));

// hidePanel：撤页签 + 活动回退
await Eval(`import('/js/ui/code-bottom-panels.js').then((m) => { m.hidePanel('compile'); return true; })`);
check("hidePanel(compile)：页签移除且活动回退 ai", await Eval(`document.querySelectorAll('#code-bottom-tabs .code-bottom-tab').length === 1
  && document.querySelector('[data-bottom-tab="ai"]')?.classList.contains('on')`));
await Eval(`import('/js/ui/code-bottom-panels.js').then((m) => { m.hidePanel('ai'); return true; })`);
check("全部撤下 → 容器隐藏", await Eval(`document.getElementById('code-bottom-panels').classList.contains('hidden')`));

// 截图（两页签展示态）
await show("compile");
await show("change");
const shot = await cdp("Page.captureScreenshot", { format: "png" });
if (shot.result?.data) writeFileSync(join(OUT, "shot-06-bottom-tabs-dark.png"), Buffer.from(shot.result.data, "base64"));
check("深色截图已保存", !!shot.result?.data);

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
