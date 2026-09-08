// 冒烟（code-viewer-editor/03）：保存写盘链路——编辑 → Ctrl+S → 磁盘断言
// （node 直读文件内容已变）+ 脏点清除 + toast + 大纲刷新（新增函数条目）+
// 树节点大小刷新 + 409 冲突占位 toast（外部改 mtime 后保存）+ 只读（GBK）
// 保存拦截。零依赖：node 内置 fetch + WebSocket 直连 Chrome CDP（9251）；
// webapp 8000 提供真实 API（须为含工单 01 端点的新进程）。
import { mkdirSync, writeFileSync, readFileSync, utimesSync, statSync } from "node:fs";
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

const NEW_FN = "\n\nint extra_fn(void) {\n    return 1;\n}\n";

await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-viewer') && !!document.getElementById('btn-code-save')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

const diskBefore = readFileSync(MAIN_C, "utf8");

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length === 5`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

// ===== 编辑 → 保存按钮出现 → Ctrl+S → 磁盘断言 =====
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value.replace(/\\n$/, '') + ${JSON.stringify(NEW_FN)};
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("编辑 → 保存按钮可见（脏 + 非只读）", await waitFor(`
  (() => {
    const b = document.getElementById('btn-code-save');
    return b && !b.classList.contains('hidden');
  })()`));
const treeSizeBefore = await Eval(`(() => {
  const b = document.querySelector('#code-tree [data-code-file="main.c"] .muted');
  return b ? b.textContent : '';
})()`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true }))`);
check("Ctrl+S → 磁盘文件已写入（node 直读新函数）", await waitFor(`
  (() => {
    const t = document.getElementById('toast-root');
    return t && t.textContent.includes('已保存');
  })()`));
const diskAfter = readFileSync(MAIN_C, "utf8");
check("磁盘内容 = 编辑后内容（含 extra_fn）", diskAfter.includes("int extra_fn(void)") && diskAfter.endsWith("}\n"));
check("磁盘与编辑前不同（真实写盘，非仅内存）", diskAfter !== diskBefore);
check("脏点清除（标签无 .code-tab-dirty）", await waitFor(`
  !document.querySelector('#code-tabs .code-tab-dirty')`));
check("保存按钮隐藏（已无脏）", await waitFor(`
  document.getElementById('btn-code-save').classList.contains('hidden')`));

// ===== 大纲刷新（服务端重算响应直用）=====
check("大纲含新增函数 extra_fn（行号 17）", await waitFor(`
  (() => {
    const items = [...document.querySelectorAll('#code-outline [data-outline-line]')];
    return items.some((b) => b.textContent.includes('extra_fn'));
  })()`));

// ===== 树节点大小刷新 =====
const treeSizeAfter = await Eval(`(() => {
  const b = document.querySelector('#code-tree [data-code-file="main.c"] .muted');
  return b ? b.textContent : '';
})()`);
check("树节点大小已更新（保存前后文本不同）", treeSizeAfter !== treeSizeBefore && treeSizeAfter !== "",
  treeSizeBefore + " → " + treeSizeAfter);

// ===== 冲突 409 占位：外部改 mtime → 保存 → 中文 toast =====
const st = statSync(MAIN_C);
utimesSync(MAIN_C, st.atime, new Date(st.mtime.getTime() + 2000));
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value += '// 第二次编辑\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true }))`);
check("外部改 mtime 后保存 → 409 冲突模态出现（工单 04 接管）", await waitFor(`
  (() => {
    const m = document.querySelector('.code-conflict-overlay');
    return !!m && !!m.querySelector('[data-conflict-action="overwrite"]')
      && m.textContent.includes('已被外部修改');
  })()`));
check("冲突模态含双列对比（磁盘版 / 我的编辑）", await waitFor(`
  (() => {
    const m = document.querySelector('.code-conflict-overlay');
    return !!m && m.textContent.includes('磁盘版（外部修改）')
      && m.textContent.includes('我的编辑（未保存）')
      && !!m.querySelector('.code-conflict-pre');
  })()`));
await Eval(`document.querySelector('.code-conflict-overlay [data-confirm-cancel]')?.click()`);
check("取消 → 模态关闭 + 脏点保留（可重试）", await waitFor(`
  (() => {
    const m = document.querySelector('.code-conflict-overlay');
    return !m && !!document.querySelector('#code-tabs .code-tab-dirty');
  })()`));

// ===== 只读（GBK）保存拦截 =====
await Eval(`document.querySelector('#code-tree [data-code-file="gbk.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta.readonly, #code-viewer .code-ta[readonly]')`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true }))`);
check("GBK 只读保存 → 中文拦截 toast（不是 UTF-8）", await waitFor(`
  (() => {
    const t = document.getElementById('toast-root');
    return t && t.textContent.includes('不是 UTF-8');
  })()`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
