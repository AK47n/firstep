// 冒烟（code-viewer-editor/04）：保存冲突模态三路径——注入冲突（外部改
// mtime，模拟任务/深化/外部 IDE 写盘）→ 保存 → 模态（双列对比）→
// ①覆盖写盘：磁盘 = 编辑版 + 脏点清 + toast；②重新加载：tab = 磁盘版 +
// 脏点无 + toast；③取消：模态关 + 脏点保留。零依赖：node 内置 fetch +
// WebSocket 直连 Chrome CDP（9251）；webapp 8000 真实 API。
import { writeFileSync, readFileSync, utimesSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const SAMPLE = join(ROOT, ".scratch", "code-viewer-editor", "sample-proj");
const MAIN_C = join(SAMPLE, "main.c");

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
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
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

const bumpMtime = () => {
  const st = statSync(MAIN_C);
  utimesSync(MAIN_C, st.atime, new Date(st.mtime.getTime() + 2000));
};
const diskText = () => readFileSync(MAIN_C, "utf8");

await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// 先把 main.c 写回确定态（含一个待编辑基准）
writeFileSync(MAIN_C, "int base = 1;\n", "utf8");

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length === 5`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

// ===== 路径②前置：编辑 → 外部改 mtime → 保存 → 模态 =====
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = 'int base = 2;\\n// 我的编辑\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await waitFor(`!!document.querySelector('#code-tabs .code-tab-dirty')`);
bumpMtime();
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true }))`);
check("保存 → 冲突模态（双列对比 pre）", await waitFor(`
  (() => {
    const m = document.querySelector('.code-conflict-overlay');
    return !!m && m.querySelectorAll('.code-conflict-pre').length === 2
      && m.textContent.includes('磁盘版（外部修改）')
      && m.textContent.includes('我的编辑（未保存）');
  })()`));

// ===== 路径①：覆盖写盘 =====
await Eval(`document.querySelector('.code-conflict-overlay [data-conflict-action="overwrite"]')?.click()`);
check("覆盖写盘 → 磁盘 = 编辑版", await waitFor(`
  (() => {
    const t = document.getElementById('toast-root');
    return t && t.textContent.includes('覆盖了外部修改');
  })()`));
check("覆盖后磁盘内容 = 我的编辑（node 直读）", diskText() === "int base = 2;\n// 我的编辑\n");
check("覆盖后脏点清除 + 模态已关", await waitFor(`
  (() => {
    return !document.querySelector('.code-conflict-overlay')
      && !document.querySelector('#code-tabs .code-tab-dirty');
  })()`));
// 缓存同步（评审整改）：关 tab 再开 = 磁盘/保存版，非旧缓存
await Eval(`document.querySelector('#code-tabs [data-tab-path="main.c"] .code-tab-close')?.click()`);
await waitFor(`document.querySelectorAll('#code-tabs .code-tab').length === 0`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
check("保存后重开 tab = 磁盘版（memo 缓存已同步）", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return ta && ta.value === 'int base = 2;\\n// 我的编辑\\n';
  })()`));

// ===== 路径②：放弃并重新加载 =====
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '// 再次编辑\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await waitFor(`!!document.querySelector('#code-tabs .code-tab-dirty')`);
// 外部再改（内容也变，证明「磁盘版」= 真磁盘）
writeFileSync(MAIN_C, "int external = 99;\n", "utf8");
bumpMtime();
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true }))`);
await waitFor(`!!document.querySelector('.code-conflict-overlay')`);
await Eval(`document.querySelector('.code-conflict-overlay [data-conflict-action="reload"]')?.click()`);
check("重新加载 → tab 内容 = 磁盘版 + 脏点无", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return ta && ta.value === 'int external = 99;\\n'
      && !document.querySelector('#code-tabs .code-tab-dirty')
      && !document.querySelector('.code-conflict-overlay');
  })()`));
check("重新加载 toast（已重新加载磁盘版本）", await waitFor(`
  (() => {
    const t = document.getElementById('toast-root');
    return t && t.textContent.includes('已重新加载磁盘版本');
  })()`));

// ===== 路径③：取消（脏点保留） =====
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = 'int mine = 3;\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await waitFor(`!!document.querySelector('#code-tabs .code-tab-dirty')`);
bumpMtime();
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true }))`);
await waitFor(`!!document.querySelector('.code-conflict-overlay')`);
await Eval(`document.querySelector('.code-conflict-overlay [data-conflict-action="cancel"]')?.click()`);
check("取消 → 模态关 + 脏点保留（编辑未丢）", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return !document.querySelector('.code-conflict-overlay')
      && !!document.querySelector('#code-tabs .code-tab-dirty')
      && ta.value === 'int mine = 3;\\n';
  })()`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
