// 冒烟（code-viewer-editor/05）：.md 编辑态 + main.c 步骤 8 联动 + 收尾文案。
// ——预览 →「编辑源码」→ 可编辑可保存（磁盘断言）→ 返回预览（脏点保留）；
// main.c 保存 → 生成上下文目录匹配 → 步骤 8 状态行「磁盘 main.c 已更新」；
// 文案：h2 = 代码编辑器、nav title 含「编辑器」。零依赖 CDP（9251）+ webapp 8000。
import { writeFileSync, readFileSync, utimesSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const SAMPLE = join(ROOT, ".scratch", "code-viewer-editor", "sample-proj");
const MAIN_C = join(SAMPLE, "main.c");
const README = join(SAMPLE, "readme.md");

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

// 确定性起点
writeFileSync(README, "# 样本工程\n\n正文段落。\n", "utf8");
writeFileSync(MAIN_C, "int base = 1;\n", "utf8");

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

// ===== 文案收尾 + 布局（工单 06：顶栏移除 → 状态条） =====
check("顶部工具栏已移除（.code-toolbar 不存在）", await Eval(`
  !document.querySelector('.code-toolbar')`));
check("目录提示在底部状态条（.code-statusbar）", await Eval(`
  (() => {
    const l = document.querySelector('.code-statusbar .code-dir-label');
    return !!l && (l.textContent || '').includes('未打开目录');
  })()`));
check("nav「代码」title 含「编辑器」", await Eval(`
  (() => {
    const b = document.querySelector('nav button[data-tab="code"]');
    return b && b.title.includes('编辑器');
  })()`));

// ===== .md 编辑态 =====
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length === 5`);
await Eval(`document.querySelector('#code-tree [data-code-file="readme.md"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer [data-md-line]')`);
check(".md 预览态 →「编辑源码」可见", await waitFor(`
  (() => {
    const b = document.getElementById('code-edit-md');
    return b && !b.classList.contains('hidden');
  })()`));
await Eval(`document.getElementById('code-edit-md')?.click()`);
check("点击「编辑源码」→ 编辑态（textarea + 行号）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return !!box.querySelector('.code-ta') && !!box.querySelector('.code-gutter')
      && document.getElementById('code-edit-md').classList.contains('hidden')
      && !document.getElementById('code-back-preview').classList.contains('hidden');
  })()`));
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '// md 已编辑\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("md 编辑 → 脏点 + Ctrl+S 保存 → 磁盘已变", await waitFor(`
  !!document.querySelector('#code-tabs .code-tab-dirty')`));
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true }))`);
check("md 保存成功 toast", await waitFor(`
  (() => {
    const t = document.getElementById('toast-root');
    return t && t.textContent.includes('已保存') && t.textContent.includes('readme.md');
  })()`));
check("md 磁盘断言（node 直读）", readFileSync(README, "utf8").trim().endsWith("// md 已编辑"));
check("md 保存后标题大纲仍在（resp.outline null 不清空）", await waitFor(`
  (() => {
    const items = [...document.querySelectorAll('#code-outline [data-outline-line]')];
    return items.some((b) => b.textContent.includes('样本工程'));
  })()`));
await Eval(`document.getElementById('code-back-preview')?.click()`);
check("返回预览 → 渲染态（内容保留脏点已清）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return !!box.querySelector('[data-md-line]')
      && !document.querySelector('#code-tabs .code-tab-dirty');
  })()`));

// ===== main.c 步骤 8 联动 =====
await Eval(`import('/js/ui/generate-mainc-sync.js').then((m) => m.setMainCDiskContext(${JSON.stringify(SAMPLE)}))`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = 'int base = 2;\\n// 编辑器改了 main.c\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await waitFor(`!!document.querySelector('#code-tabs .code-tab-dirty')`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true }))`);
check("保存 main.c → 步骤 8 状态行出现「磁盘 main.c 已更新」", await waitFor(`
  (() => {
    const box = document.getElementById('mainc-disk-state');
    return box && !box.classList.contains('hidden')
      && box.textContent.includes('磁盘 main.c 已更新');
  })()`));
check("步骤 8 状态行带「加载为编辑内容」按钮", await Eval(`
  (() => {
    const box = document.getElementById('mainc-disk-state');
    return !!box && !!box.querySelector('[data-mainc-reload]')
      && box.querySelector('[data-mainc-reload]').textContent === '加载为编辑内容';
  })()`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
