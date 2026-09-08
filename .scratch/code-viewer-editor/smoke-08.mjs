// 冒烟（code-viewer-editor/07d）：栏显示隔离——用户反馈「所有栏底部都能
// 看到代码编辑器」= #tab-code id 级 display:flex 压过 section.page{display:none}
// 的常驻显示 bug。断言：每栏激活时其余 9 个 section 全部隐藏；代码栏激活
// 时 display:flex 且其余全 none；切换往返恢复。零依赖 CDP（9251）。
const CDP = 9251;
const targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws")); });
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
const cdp = (method, params = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval: " + (r.result.exceptionDetails.exception?.description || "?"));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 6000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

const TAB_IDS = ["generate", "topic", "code", "settings", "library",
  "reference", "pdf", "master", "changelog", "guide"];

// 逐栏激活：唯一 display!=none 的 section 必须是目标栏；其余全 none。
for (const tid of TAB_IDS) {
  await Eval(`document.querySelector('nav button[data-tab="${tid}"]')?.click()`);
  const ok = await waitFor(`(() => {
    const secs = [...document.querySelectorAll('section.page')];
    const target = document.getElementById('tab-' + ${JSON.stringify(tid)});
    const visible = secs.filter((s) => getComputedStyle(s).display !== 'none');
    return visible.length === 1 && visible[0] === target;
  })()`);
  check("激活「" + tid + "」→ 唯一可见 section = 目标（其余全隐藏）", ok);
}

// 往返：generate → code → generate，代码栏 display 精确断言
await Eval(`document.querySelector('nav button[data-tab="code"]')?.click()`);
check("代码栏激活 → display:flex（IDE 全宽布局）", await waitFor(`
  getComputedStyle(document.getElementById('tab-code')).display === 'flex'`));
await Eval(`document.querySelector('nav button[data-tab="generate"]')?.click()`);
check("切回生成栏 → 代码栏隐藏（display:none，用户反馈的 bug 修复）", await waitFor(`
  getComputedStyle(document.getElementById('tab-code')).display === 'none'
    && getComputedStyle(document.getElementById('tab-generate')).display !== 'none'`));

// 代码栏内部结构仍在（修复不影响编辑器本身）
await Eval(`document.querySelector('nav button[data-tab="code"]')?.click()`);
check("代码栏激活 → 编辑器结构在（.code-view + 标签条）", await waitFor(`
  !!document.querySelector('#tab-code .code-view')
    && !!document.querySelector('#tab-code #code-tabs')`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
