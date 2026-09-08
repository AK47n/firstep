// 冒烟（code-editor-refine/06 文件树右键菜单）：真实浏览器验证
// ①文件行右键出四项（打开/复制相对路径/重命名/删除）；②复制 → clipboard
// （navigator.clipboard 打桩捕获）内容 = 相对路径；③目录行右键「展开/收起」
// 折叠定位；④Esc / 外部 mousedown / 滚动关闭；⑤连续右键跟随目标；⑥右键
// 重命名（复用 treeRename：模态输入 → 刷新树 + tab 联动）；⑦右键删除（复用
// treeDelete）；⑧脏 tab 删除弹脏保护确认（与悬浮一致）。零后端写库（操作走
// 真实 /api/code/tree/* 但目标是 .scratch 样例目录）；CDP 9251 + webapp 8000。
import { mkdirSync, writeFileSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-editor-refine");
const SAMPLE = join(OUT, "sample-proj-06");
mkdirSync(join(SAMPLE, "sub"), { recursive: true });
rmSync(join(SAMPLE, "renamed.c"), { force: true });   // 幂等：清上次运行改名残留（防重命名撞名）
writeFileSync(join(SAMPLE, "a.c"), "#include <stdio.h>\nvoid a(void) {}\n");
writeFileSync(join(SAMPLE, "b.c"), "#include <stdio.h>\nvoid b(void) {}\n");
writeFileSync(join(SAMPLE, "temp.c"), "#include <stdio.h>\nvoid t(void) {}\n");
writeFileSync(join(SAMPLE, "sub", "nested.c"), "#include <stdio.h>\nvoid n(void) {}\n");

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
const openDir = (dir) => Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(dir)}))`);
const rclick = (sel) => Eval(`(() => {
  const el = document.querySelector(${JSON.stringify(sel)});
  if (!el) return false;
  el.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true,
    clientX: 120, clientY: 160 }));
  return true;
})()`);
const ctxClick = (label) => Eval(`(() => {
  const btn = Array.from(document.querySelectorAll('.code-ctx-menu .code-ctx-item'))
    .find((b) => b.textContent === ${JSON.stringify(label)});
  if (!btn) return false;
  btn.click();
  return true;
})()`);

// ---- 准备 ----
await openDir(SAMPLE);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="a.c"]')`);
await Eval(`(() => {
  Object.defineProperty(navigator, 'clipboard', { value: {
    writeText: async (t) => { window.__copied = t; },
  }, configurable: true });
  return true;
})()`);

// ---- 场景 1：文件右键四项 + 菜单样式 ----
await rclick('#code-tree [data-code-file="a.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
const itemLabels = await Eval(`Array.from(document.querySelectorAll('.code-ctx-menu .code-ctx-item')).map((b) => b.textContent).join('|')`);
check("1 文件右键菜单四项", itemLabels === "打开|复制相对路径|重命名…|删除…", itemLabels);
const menuBg = await Eval(`(() => {
  const m = document.querySelector('.code-ctx-menu');
  return m ? getComputedStyle(m).backgroundColor : '';
})()`);
check("1b 菜单浮层背景非空（token 生效）", menuBg !== "" && menuBg !== "transparent", menuBg);

// ---- 场景 2：复制相对路径 → clipboard（打桩捕获） ----
await ctxClick("复制相对路径");
await waitFor(`window.__copied === "a.c"`);
check("2 复制相对路径 = a.c", (await Eval(`window.__copied`)) === "a.c");
check("2b 菜单已关闭", (await Eval(`!!document.querySelector('.code-ctx-menu')`)) === false);

// ---- 场景 3：打开文件开 tab ----
await rclick('#code-tree [data-code-file="a.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await ctxClick("打开");
check("3 打开 → a.c 开 tab", await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === 'a.c'`));

// ---- 场景 4：目录右键「展开 / 收起」 ----
const dirOpenBefore = await Eval(`document.querySelector('#code-tree details[data-dir-path="sub"]')?.open`);
await rclick('#code-tree details[data-dir-path="sub"] summary');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
const dirLabel = await Eval(`document.querySelector('.code-ctx-menu .code-ctx-item')?.textContent`);
check("4 目录菜单首项 = 展开 / 收起", dirLabel === "展开 / 收起", dirLabel);
await ctxClick("展开 / 收起");
const dirOpenAfter = await Eval(`document.querySelector('#code-tree details[data-dir-path="sub"]')?.open`);
check("4b 点击后目录收起（open 翻转）", dirOpenBefore === true && dirOpenAfter === false,
  String(dirOpenBefore) + "->" + String(dirOpenAfter));
await rclick('#code-tree details[data-dir-path="sub"] summary');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await ctxClick("展开 / 收起");   // 再展开（恢复）

// ---- 场景 5：Esc / 外部 mousedown / 滚动 关闭 ----
await rclick('#code-tree [data-code-file="b.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); true`);
await new Promise((r) => setTimeout(r, 200));
check("5a Esc 关闭", (await Eval(`!!document.querySelector('.code-ctx-menu')`)) === false);
await rclick('#code-tree [data-code-file="b.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await Eval(`document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); true`);
await new Promise((r) => setTimeout(r, 200));
check("5b 外部 mousedown 关闭", (await Eval(`!!document.querySelector('.code-ctx-menu')`)) === false);
await rclick('#code-tree [data-code-file="b.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await Eval(`document.dispatchEvent(new Event('scroll', { bubbles: true })); true`);
await new Promise((r) => setTimeout(r, 200));
check("5c 滚动关闭", (await Eval(`!!document.querySelector('.code-ctx-menu')`)) === false);

// ---- 场景 6：连续右键跟随目标 ----
await rclick('#code-tree [data-code-file="a.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await rclick('#code-tree [data-code-file="b.c"]');
await new Promise((r) => setTimeout(r, 200));
check("6 第二次右键菜单仍开（跟随新目标）", (await Eval(`!!document.querySelector('.code-ctx-menu')`)) === true);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); true`);

// ---- 场景 7：右键重命名（复用 treeRename + tab 联动） ----
await rclick('#code-tree [data-code-file="b.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await ctxClick("重命名…");
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-value]')`);
const renameDefault = await Eval(`document.querySelector('.ref-files-overlay [data-confirm-value]')?.value`);
check("7a 重命名模态默认值 = b.c", renameDefault === "b.c", renameDefault);
await Eval(`(() => {
  const inp = document.querySelector('.ref-files-overlay [data-confirm-value]');
  inp.value = 'renamed.c';
  inp.dispatchEvent(new Event('input', { bubbles: true }));
  document.querySelector('.ref-files-overlay [data-confirm-ok]').click();
  return true;
})()`);
check("7b 树刷新为 renamed.c（b.c 消失）",
  await waitFor(`!!document.querySelector('#code-tree [data-code-file="renamed.c"]') && !document.querySelector('#code-tree [data-code-file="b.c"]')`));

// ---- 场景 8：右键删除 ----
await rclick('#code-tree [data-code-file="temp.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await ctxClick("删除…");
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-ok]')`);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click(); true`);
check("8 删除后 temp.c 消失",
  await waitFor(`!document.querySelector('#code-tree [data-code-file="temp.c"]')`));

// ---- 场景 9：脏 tab 删除 → 脏保护确认（与悬浮一致） ----
await rclick('#code-tree [data-code-file="a.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await ctxClick("open");
await waitFor(`document.querySelector('#code-tabs .code-tab.on')?.dataset.tabPath === 'a.c'`);
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '\\n// dirty';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 400));
const dirtyCount = await Eval(`import('/js/ui/codeeditor.js').then((m) => m.dirtySavableTabCount())`);
check("9 前置：a.c 已脏", dirtyCount >= 1, String(dirtyCount));
await rclick('#code-tree [data-code-file="a.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await ctxClick("删除…");
const guardShown = await waitFor(`!!document.querySelector('.ref-files-overlay') && document.querySelector('.ref-files-overlay').textContent.includes('未保存修改')`);
check("9b 右键删除弹脏保护确认", guardShown);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]')?.click(); true`);
await new Promise((r) => setTimeout(r, 300));
check("9c 取消后 a.c 仍在树/未删",
  (await Eval(`!!document.querySelector('#code-tree [data-code-file="a.c"]')`)) === true);

// ---- 场景 10：脏 tab 重命名 → 脏保护确认（工单 06 整改：与删除同口径） ----
await rclick('#code-tree [data-code-file="a.c"]');
await waitFor(`!!document.querySelector('.code-ctx-menu')`);
await ctxClick("重命名…");
const renGuardShown = await waitFor(`!!document.querySelector('.ref-files-overlay') && document.querySelector('.ref-files-overlay').textContent.includes('未保存修改')`);
check("10 右键重命名弹脏保护确认", renGuardShown);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]')?.click(); true`);
await new Promise((r) => setTimeout(r, 300));
check("10b 取消后 a.c 仍在树（未改名）",
  (await Eval(`!!document.querySelector('#code-tree [data-code-file="a.c"]')`)) === true);

console.log(`\n${passed} PASS / ${failed} FAIL`);
process.exit(failed ? 1 : 0);
