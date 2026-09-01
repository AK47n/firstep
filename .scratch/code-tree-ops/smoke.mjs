// 冒烟（工单 code-tree-ops/01-03）：代码树操作 + 保存全部——真实 API + 真实
// 磁盘样本（.scratch/code-tree-ops/sample-proj，跑前重建跑后清理）：
// 新建文件（树 + 自动开 tab + 写盘）、新建文件夹（树出现）、重命名文件
// （树新名 + tab 路径更新）、重命名目录（子树 tab 路径更新）、删除文件
// （tab 关闭）、删除空目录、非空目录删除 → toast 400 中文、脏文件删除 →
// 两键确认（取消 / 保存全部继续）、保存全部按钮 + Ctrl+Shift+S（多脏落盘）。
// 零依赖：node 内置 fetch + WebSocket 直连 Edge CDP（9231）；webapp 8000
// 提供真实 /api/*（open/create/rename/delete/file/save）。
import { mkdirSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-tree-ops", "sample-proj");

// ---- 样本工程（真实磁盘；跑前重建保确定性，跑后清理） ----
const resetSample = () => {
  rmSync(SAMPLE, { recursive: true, force: true });
  mkdirSync(join(SAMPLE, "src"), { recursive: true });
  mkdirSync(join(SAMPLE, "empty"), { recursive: true });
  mkdirSync(join(ROOT, ".scratch", "code-tree-ops"), { recursive: true });
  writeFileSync(join(SAMPLE, "main.c"), "int main(void){return 0;}\n", "utf8");
  writeFileSync(join(SAMPLE, "src", "app.h"), "#pragma once\n", "utf8");
};

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.includes("127.0.0.1:8000"))
  || targets.find((t) => t.type === "page");
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
// 禁用网络缓存：Page.reload(ignoreCache) 对模块脚本事后请求不完全生效，
// 静态 JS 改动会被 Edge HTTP 缓存吞掉——用 Network.setCacheDisabled 彻底绕过。
await cdp("Network.enable");
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
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

resetSample();
let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? "  [" + extra + "]" : ""));
  if (!ok) failed++;
};

// 导航 + 刷新 → 打开样本目录
await cdp("Page.navigate", { url: pageUrl });
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('tab-code')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
check("打开样本目录：树含文件 + 目录（含空目录 empty）", await waitFor(`
  (() => {
    const files = [...document.querySelectorAll('#code-tree [data-code-file]')].map((b) => b.dataset.codeFile).sort();
    const dirs = [...document.querySelectorAll('#code-tree .code-tree-dir-name')].map((s) => s.textContent);
    return files.includes('main.c') && files.includes('src/app.h')
      && dirs.includes('src') && dirs.includes('empty') && !dirs.includes('Debug');
  })()`));
check("树头部新建按钮就位", await Eval(`
  !!document.getElementById('btn-code-tree-new-file')
  && !!document.getElementById('btn-code-tree-new-dir')
  && !!document.getElementById('btn-code-save-all')`));
check("行操作 ✎/🗑 按钮就位（文件行 + 目录行）", await Eval(`
  document.querySelectorAll('#code-tree [data-tree-op="rename"]').length >= 3
  && document.querySelectorAll('#code-tree [data-tree-op="delete"]').length >= 3`));

// ---- 新建文件 sensor.c：输入模态 → 树出现 + 自动开 tab + 写盘 ----
await Eval(`document.getElementById('btn-code-tree-new-file').click()`);
check("新建文件：输入模态出现（data-confirm-value）", await waitFor(`
  !!document.querySelector('.ref-files-overlay [data-confirm-value]')`));
await Eval(`(() => {
  const inp = document.querySelector('.ref-files-overlay [data-confirm-value]');
  inp.value = 'sensor.c';
  document.querySelector('[data-confirm-ok]').click();
})()`);
check("新建文件：树出现 sensor.c + 自动打开 tab", await waitFor(`
  !!document.querySelector('#code-tree [data-code-file="sensor.c"]')
  && !!document.querySelector('#code-tabs .code-tab[data-tab-path="sensor.c"]')`));
check("新建文件：磁盘已建空文件", await Eval(`
  (async () => {
    const d = await (await fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(SAMPLE)})
      + '&path=' + encodeURIComponent('sensor.c'))).json();
    return d.content === '' && d.size_bytes === 0;
  })()`));

// 新 tab 输入 + Ctrl+S 落盘
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = 'int sensor = 1;\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 200));
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true }))`);
check("新建文件：编辑 + Ctrl+S 落盘（脏点清除）", await waitFor(`
  !document.querySelector('#code-tabs .code-tab[data-tab-path="sensor.c"] .code-tab-dirty')`));
check("新建文件：磁盘内容已写入", await Eval(`
  (async () => {
    const d = await (await fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(SAMPLE)})
      + '&path=' + encodeURIComponent('sensor.c'))).json();
    return d.content === 'int sensor = 1;\\n';
  })()`));

// ---- 新建文件夹 include ----
await Eval(`document.getElementById('btn-code-tree-new-dir').click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-value]')`);
await Eval(`(() => {
  const inp = document.querySelector('.ref-files-overlay [data-confirm-value]');
  inp.value = 'include';
  document.querySelector('[data-confirm-ok]').click();
})()`);
check("新建文件夹：树出现 include", await waitFor(`
  [...document.querySelectorAll('#code-tree .code-tree-dir-name')].some((s) => s.textContent === 'include')`));

// ---- 重命名文件 sensor.c → adc.c（tab 路径更新） ----
await Eval(`(() => {
  const row = [...document.querySelectorAll('#code-tree [data-tree-op="rename"]')]
    .find((b) => b.dataset.treePath === 'sensor.c');
  row.click();
})()`);
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-value]')`);
await Eval(`(() => {
  const inp = document.querySelector('.ref-files-overlay [data-confirm-value]');
  inp.value = 'adc.c';
  document.querySelector('[data-confirm-ok]').click();
})()`);
check("重命名文件：树新名 adc.c", await waitFor(`
  !!document.querySelector('#code-tree [data-code-file="adc.c"]')
  && !document.querySelector('#code-tree [data-code-file="sensor.c"]')`));
check("重命名文件：tab 路径更新（data-tab-path=adc.c）", await waitFor(`
  !!document.querySelector('#code-tabs .code-tab[data-tab-path="adc.c"]')
  && !document.querySelector('#code-tabs .code-tab[data-tab-path="sensor.c"]')`));

// ---- 重命名目录 src → drivers（子树 tab 路径更新） ----
await Eval(`document.querySelector('#code-tree [data-code-file="src/app.h"]').click()`);
await waitFor(`!!document.querySelector('#code-tabs .code-tab[data-tab-path="src/app.h"]')`);
await Eval(`(() => {
  const row = [...document.querySelectorAll('#code-tree [data-tree-op="rename"]')]
    .find((b) => b.dataset.treePath === 'src');
  row.click();
})()`);
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-value]')`);
await Eval(`(() => {
  const inp = document.querySelector('.ref-files-overlay [data-confirm-value]');
  inp.value = 'drivers';
  document.querySelector('[data-confirm-ok]').click();
})()`);
check("重命名目录：树 drivers/app.h", await waitFor(`
  !!document.querySelector('#code-tree [data-code-file="drivers/app.h"]')
  && !document.querySelector('#code-tree [data-code-file="src/app.h"]')`));
check("重命名目录：tab 路径更新（drivers/app.h）", await waitFor(`
  !!document.querySelector('#code-tabs .code-tab[data-tab-path="drivers/app.h"]')`));

// ---- 删除文件 adc.c：脏 → 先两键（取消路径） ----
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  if (!document.querySelector('#code-tabs .code-tab[data-tab-path="adc.c"]')) return;
})()`);
await Eval(`document.querySelector('#code-tabs .code-tab[data-tab-path="adc.c"]').click()`);
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + 'int dirty = 2;\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 200));
await Eval(`(() => {
  const row = [...document.querySelectorAll('#code-tree [data-tree-op="delete"]')]
    .find((b) => b.dataset.treePath === 'adc.c');
  row.click();
})()`);
check("脏文件删除：先弹两键确认（保存全部并继续/取消）", await waitFor(`
  (() => {
    const ok = document.querySelector('[data-confirm-ok]');
    const cancel = document.querySelector('[data-confirm-cancel]');
    return !!ok && ok.textContent === '保存全部并继续' && !!cancel && cancel.textContent === '取消';
  })()`));
await Eval(`document.querySelector('[data-confirm-cancel]').click()`);
check("脏文件删除：取消 → 文件仍在（树 + tab 脏保留）", await waitFor(`
  !!document.querySelector('#code-tree [data-code-file="adc.c"]')
  && !!document.querySelector('#code-tabs .code-tab[data-tab-path="adc.c"] .code-tab-dirty')`));

// ---- 删除文件 adc.c：再删 → 保存全部继续 → 删除 ----
await Eval(`(() => {
  const row = [...document.querySelectorAll('#code-tree [data-tree-op="delete"]')]
    .find((b) => b.dataset.treePath === 'adc.c');
  row.click();
})()`);
await waitFor(`!!document.querySelector('[data-confirm-ok]')`);
await Eval(`document.querySelector('[data-confirm-ok]').click()`);
check("删除文件：保存全部后二次确认（删除）弹出", await waitFor(`
  (() => {
    const ok = document.querySelector('.ref-files-overlay [data-confirm-ok]');
    return !!ok && ok.textContent === '确认删除';
  })()`));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
check("删除文件：树移除 adc.c + tab 关闭", await waitFor(`
  !document.querySelector('#code-tree [data-code-file="adc.c"]')
  && !document.querySelector('#code-tabs .code-tab[data-tab-path="adc.c"]')`));

// ---- 删除空目录 include / 非空目录 drivers（400 toast） ----
await Eval(`(() => {
  const row = [...document.querySelectorAll('#code-tree [data-tree-op="delete"]')]
    .find((b) => b.dataset.treePath === 'include');
  row.click();
})()`);
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-ok]')`);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
check("删除空目录：树移除 include", await waitFor(`
  ![...document.querySelectorAll('#code-tree .code-tree-dir-name')].some((s) => s.textContent === 'include')`));

await Eval(`(() => {
  const row = [...document.querySelectorAll('#code-tree [data-tree-op="delete"]')]
    .find((b) => b.dataset.treePath === 'drivers');
  row.click();
})()`);
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-ok]')`);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
check("删除非空目录：toast 400 中文（树保留）", await waitFor(`
  (() => {
    const t = document.querySelector('.toast-text');
    return !!t && t.textContent.includes('目录非空')
      && !!document.querySelector('#code-tree [data-code-file="drivers/app.h"]');
  })()`));

// ---- 保存全部：main.c 与 drivers/app.h 各改脏 → 按钮一次落盘 ----
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]').click()`);
await waitFor(`!!document.querySelector('#code-tabs .code-tab[data-tab-path="main.c"]')`);
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = 'int main(void){return 1;}\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await Eval(`document.querySelector('#code-tree [data-code-file="drivers/app.h"]').click()`);
await waitFor(`!!document.querySelector('#code-tabs .code-tab[data-tab-path="drivers/app.h"]')`);
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '// 改\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 250));
const dirtyBefore = await Eval(`document.querySelectorAll('#code-tabs .code-tab-dirty').length`);
check("保存全部前：2 个脏标签", dirtyBefore === 2, "dirty=" + dirtyBefore);
await Eval(`document.getElementById('btn-code-save-all').click()`);
check("保存全部按钮：脏点全清 + toast 计数", await waitFor(`
  (() => {
    const t = [...document.querySelectorAll('.toast-text')].some((el) => el.textContent.includes('已保存全部 2 个文件'));
    return document.querySelectorAll('#code-tabs .code-tab-dirty').length === 0 && t;
  })()`));
check("保存全部：磁盘内容均已落盘", await Eval(`
  (async () => {
    const a = await (await fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(SAMPLE)})
      + '&path=' + encodeURIComponent('main.c'))).json();
    const b = await (await fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(SAMPLE)})
      + '&path=' + encodeURIComponent('drivers/app.h'))).json();
    return a.content === 'int main(void){return 1;}\\n' && b.content.includes('// 改');
  })()`));

// ---- Ctrl+Shift+S：再改脏 → 快捷键落盘 ----
await Eval(`(() => {
  const tab = document.querySelector('#code-tabs .code-tab[data-tab-path="main.c"]');
  tab.click();
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + 'int x = 9;\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 200));
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'S', ctrlKey: true, shiftKey: true, bubbles: true }))`);
check("Ctrl+Shift+S：脏点全清 + 双文件落盘", await waitFor(`
  document.querySelectorAll('#code-tabs .code-tab-dirty').length === 0`));
check("Ctrl+Shift+S：磁盘 content 已写入（main.c + app.h）", await Eval(`
  (async () => {
    const a = await (await fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(SAMPLE)})
      + '&path=' + encodeURIComponent('main.c'))).json();
    const b = await (await fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(SAMPLE)})
      + '&path=' + encodeURIComponent('drivers/app.h'))).json();
    return a.content.includes('int x = 9;') && b.content.includes('// 改');
  })()`));

rmSync(SAMPLE, { recursive: true, force: true });
console.log(failed ? "FAIL " + failed + " 项" : "ALL PASS");
process.exit(failed ? 1 : 0);
