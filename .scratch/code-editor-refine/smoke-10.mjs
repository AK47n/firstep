// 冒烟（code-editor-refine/10 保存自动编译开关）：真实浏览器验证
// ①默认关：手工保存不触发编译；②开启 → 手工保存触发编译（fetch 打桩捕获
// /api/compile + 面板状态行）；③编译中连续保存不重复触发（pending 桩）；
// ④刷新后开关持久化（localStorage）；⑤再点关闭。零真实编译（compile 端点
// 打桩）；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const SAMPLE = join(OUT, "sample-proj-10");
mkdirSync(SAMPLE, { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), "#include <stdio.h>\nvoid main10(void) {}\n");

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
const reload = async () => {
  await Eval(`window.__smokeMarker = 1; true`);
  await cdp("Page.reload", { ignoreCache: true });
  for (let i = 0; i < 100; i++) {
    try {
      if (await Eval(`document.readyState === 'complete' && !window.__smokeMarker
        && !!document.getElementById('tab-code') && !!document.getElementById('code-viewer')`)) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
};
await reload();
let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};
const openDir = (dir) => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(dir)}))`);
const openFile = (name) => Eval(`document.querySelector('#code-tree [data-code-file=${JSON.stringify(name)}]')?.click()`);
const dirty = () => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!ta) return false;
  ta.value = ta.value + '\\n// dirty ' + Date.now();
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
const save = () => Eval(`import('/js/ui/codeeditor.js').then((m) => m.saveActiveTab()); true`);
const stubCompile = () => Eval(`(() => {
  if (!window.__origFetch) window.__origFetch = window.fetch.bind(window);
  window.__compileCalls = 0;
  window.__pendingCompile = false;
  window.fetch = (url, init) => {
    if (String(url).includes('/api/compile')) {
      window.__compileCalls += 1;
      if (window.__pendingCompile) return new Promise(() => {});   // 永不完成：模拟编译中
      const sse = 'event: done\\ndata: ' + JSON.stringify({ passed: true, timed_out: false, parsed_errors: [], duration: 1.1, summary: { errors: 0, warnings: 0 } }) + '\\n\\n';
      return Promise.resolve(new Response(sse, { status: 200, headers: { 'content-type': 'text/event-stream' } }));
    }
    return window.__origFetch(url, init);
  };
  return true;
})()`);

// ---- 准备：清 storage + 打开目录 ----
await Eval(`localStorage.removeItem('firstep.autoCompileOnSave'); true`);
await stubCompile();
await openDir(SAMPLE);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await openFile("main.c");
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

// ---- 场景 1：默认关——保存不触发 ----
const btnText0 = await Eval(`document.querySelector('#btn-code-auto-compile').textContent`);
check("1 默认关（按钮文案）", btnText0.includes("关"), btnText0);
await dirty();
await save();
await new Promise((r) => setTimeout(r, 1000));
check("1b 关：手工保存不触发编译", (await Eval(`window.__compileCalls`)) === 0);

// ---- 场景 2：开启 → 保存触发编译 ----
await Eval(`document.querySelector('#btn-code-auto-compile').click(); true`);
check("2 点击后变为开", (await Eval(`document.querySelector('#btn-code-auto-compile').textContent.includes('开')`)) === true
  && (await Eval(`localStorage.getItem('firstep.autoCompileOnSave')`)) === "1");
await dirty();
await save();
check("2b 开启：保存触发编译 1 次", await waitFor(`window.__compileCalls === 1`));
check("2c 面板状态行编译成功", await waitFor(`document.querySelector('#code-compile-status')?.textContent.includes('编译成功')`));

// ---- 场景 3：编译中连续保存不重复 ----
await Eval(`window.__pendingCompile = true; true`);
await dirty();
await save();
const inFlight = await waitFor(`window.__compileCalls === 2`);   // 第 2 次 = 编译中（pending）
check("3 保存触发第二次编译（pending 中）", inFlight);
await dirty();
await save();
await new Promise((r) => setTimeout(r, 1000));
check("3b 编译中再保存不重复触发（仍 2 次）", (await Eval(`window.__compileCalls`)) === 2);

// ---- 场景 4：刷新后持久化（localStorage） ----
await reload();
check("4 刷新后按钮仍为开（持久化）",
  (await Eval(`document.querySelector('#btn-code-auto-compile')?.textContent.includes('开')`)) === true);

// ---- 场景 5：关（并清理） ----
await Eval(`document.querySelector('#btn-code-auto-compile').click(); true`);
check("5 再点关闭", (await Eval(`document.querySelector('#btn-code-auto-compile').textContent.includes('关')`)) === true
  && (await Eval(`localStorage.getItem('firstep.autoCompileOnSave')`)) === "0");

await Eval(`(() => { if (window.__origFetch) { window.fetch = window.__origFetch; delete window.__origFetch; } return true; })()`);
console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
