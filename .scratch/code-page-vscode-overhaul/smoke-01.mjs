// 冒烟（code-page-vscode-overhaul/01 行操作与反缩进）：真实浏览器验证
// Shift+Tab 反缩进 / Ctrl+Shift+K 删行 / Alt+↑↓ 移动行 / Shift+Alt+↑↓ 复制行 /
// Ctrl+L 选整行；**折叠与保存回归面**（2026-09-09 在途盘点补口）：
// Ctrl+Shift+[ 折叠 → 占位行 + gutter 箭头 + 视图文本；点箭头 / 点占位行 /
// Ctrl+Shift+] 三种展开路径；Ctrl+S 保存 → 脏点清 + toast + 磁盘内容 = 模型。
// 深色主题截图存档。零写库（只写脚本自建夹具 .scratch/.../sample-proj/main.c）。
// CDP 9251 + webapp 8000。
//
// 注（2026-09-09 盘点补口）：注入姿势必须「派发按键前重设光标」——编辑器在
// input 后按模型光标重渲染，直接在注入时设的选区会被覆盖成模型光标（旧脚本
// 因此对错光标做断言，5 项假红）。
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "code-page-vscode-overhaul");
const SAMPLE = join(OUT, "sample-proj");
const MAIN_C = join(SAMPLE, "main.c");
mkdirSync(SAMPLE, { recursive: true });
const ORIGINAL = [
  "void helper(void) {",
  "    int x = 0;",
  "}",
].join("\n");
writeFileSync(MAIN_C, ORIGINAL);

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
const settle = (ms = 250) => new Promise((r) => setTimeout(r, ms));

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
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
// 「代码」tab 激活——折叠快捷键（Ctrl+Shift+[/]）与 Ctrl+S 都以此为门。
await Eval(`document.querySelector('button[data-tab="code"]')?.click(); true`);
await settle(400);

// 工具：设定文本+选区（经 input 事件保持模型一致），按键（派发前重设光标），读结果
const setText = (text, s, e) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.value = ${JSON.stringify(text)};
  ta.setSelectionRange(${s}, ${e});
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
const press = (opts, sel) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ${sel ? `ta.setSelectionRange(${sel[0]}, ${sel[1]});` : ""}
  ta.dispatchEvent(new KeyboardEvent('keydown', ${JSON.stringify(opts)}));
  return true;
})()`);
const readTa = () => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  return { value: ta.value, sel: [ta.selectionStart, ta.selectionEnd] };
})()`);
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// ---- Shift+Tab 多行反缩进（选区覆盖整段，overhaul/01 回归修复）----
await setText("    a\n      b\nc", 0, 14);
await press({ key: "Tab", shiftKey: true, bubbles: true, cancelable: true }, [0, 14]);
await settle();
let r = await readTa();
check("Shift+Tab 多行反缩进（选区覆盖整段）",
  eq(r, { value: "a\n  b\nc", sel: [0, 5] }), JSON.stringify(r));

// ---- Ctrl+Shift+K 删行 ----
await setText("a\nb\nc", 2, 2);
await press({ key: "k", ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }, [2, 2]);
await settle();
r = await readTa();
check("Ctrl+Shift+K 删除中间行", eq(r, { value: "a\nc", sel: [2, 2] }), JSON.stringify(r));

// ---- Alt+↓ 移动行 ----
await setText("a\nb\nc", 0, 0);
await press({ key: "ArrowDown", altKey: true, bubbles: true, cancelable: true }, [0, 0]);
await settle();
r = await readTa();
check("Alt+↓ 下移当前行（光标随行）", eq(r, { value: "b\na\nc", sel: [2, 2] }), JSON.stringify(r));

// ---- Shift+Alt+↓ 复制行 ----
await setText("a\nb", 2, 2);
await press({ key: "ArrowDown", altKey: true, shiftKey: true, bubbles: true, cancelable: true }, [2, 2]);
await settle();
r = await readTa();
check("Shift+Alt+↓ 复制行（光标落副本）", eq(r, { value: "a\nb\nb", sel: [4, 4] }), JSON.stringify(r));

// ---- Ctrl+L 选整行 ----
await setText("abc\ndef\nghi", 5, 5);
await press({ key: "l", ctrlKey: true, bubbles: true, cancelable: true }, [5, 5]);
await settle();
r = await readTa();
check("Ctrl+L 选整行（含行尾换行）", eq({ v: r.value, s: r.sel[0], e: r.sel[1] },
  { v: "abc\ndef\nghi", s: 4, e: 8 }), JSON.stringify(r));

// ---- 只读文件不响应 ----
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.readOnly = true; return true;
})()`);
await setText("a\nb", 0, 0);
await press({ key: "ArrowDown", altKey: true, bubbles: true, cancelable: true }, [0, 0]);
await settle();
r = await readTa();
check("只读 textarea 行操作不生效", eq(r, { value: "a\nb", sel: [0, 0] }), JSON.stringify(r));
await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.readOnly = false; return true; })()`);

// ---- 帮助弹窗渲染新条目 ----
await Eval(`document.getElementById('btn-code-shortcuts')?.click(); true`);
const helpOk = await waitFor(`(document.body.textContent || '').includes('反缩进选中行')
  && (document.body.textContent || '').includes('删除当前行（组）')
  && (document.body.textContent || '').includes('选中整行（重复按扩展）')`);
check("帮助弹窗渲染行操作条目", helpOk);
await Eval(`document.querySelector('.code-shortcuts-modal .modal-close, .code-shortcuts-modal [data-close]')?.click()
  ?? document.querySelector('.code-shortcuts-modal')?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })); true`);

// ================= 折叠回归面（overhaul/01 验收项：既有折叠正常） =================
const foldState = () => Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const ta = box.querySelector('.code-ta');
  return {
    value: ta.value,
    lines: box.querySelectorAll('.code-hl-line').length,
    arrows: box.querySelectorAll('[data-fold]').length,
    placeholders: box.querySelectorAll('[data-fold-expand]').length,
    gutter: [...box.querySelectorAll('.code-gutter-line')].map((e) => e.textContent).join('|'),
  };
})()`);
// 折叠 helper：光标落进函数体（模型偏移 20 = 第 2 行内）后按 Ctrl+Shift+[
const foldByKey = async () => {
  await Eval(`(() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    ta.focus(); ta.setSelectionRange(20, 20); return true;
  })()`);
  await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: '[', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); true`);
  return waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length > 0`, 4000);
};

await setText(ORIGINAL, 0, 0);
await settle(400);
let st = await foldState();
check("未折叠基线：3 行 + 无占位行", st.lines === 3 && st.placeholders === 0, JSON.stringify(st));
// 工单 code-fold-arrow/01：未折叠态可折叠行显示 ▾（鼠标折叠入口）
check("未折叠态：可折叠行 gutter 显示 ▾ 箭头",
  st.arrows === 1 && st.gutter === "▾1|2|3", JSON.stringify(st));
await Eval(`document.querySelector('#code-viewer [data-fold]')?.click(); true`);
check("点未折叠箭头 → 折叠（占位行出现 + 行号跳号）",
  await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length > 0`, 4000));
st = await foldState();
check("点未折叠箭头折叠后：占位行 1 + 箭头变 ▸",
  st.placeholders === 1 && st.arrows === 1 && st.gutter.startsWith("▸1|"), JSON.stringify(st));
await Eval(`document.querySelector('#code-viewer [data-fold]')?.click(); true`);
check("再点箭头 → 展开回未折叠态（▾ 仍在）",
  await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length === 0`, 4000));
st = await foldState();
check("展开后 gutter 回到 ▾1|2|3", st.arrows === 1 && st.gutter === "▾1|2|3", JSON.stringify(st));

check("Ctrl+Shift+[ 折叠 → 占位行 + gutter 箭头 + 视图文本",
  await foldByKey());
st = await foldState();
check("折叠态：可见行 2（模型 3 行 - 隐藏 2 行 + 占位 1 行）、占位文案在场",
  st.lines === 2 && st.placeholders === 1 && st.arrows === 1
  && st.value.includes("… 2 行") && st.gutter.startsWith("▸1|"),
  JSON.stringify(st));

await Eval(`document.querySelector('#code-viewer [data-fold]')?.click(); true`);
check("点 gutter 箭头 → 展开（占位行消失、行号回齐）",
  await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length === 0`, 4000));
st = await foldState();
check("展开态：3 行 + gutter ▾1|2|3（code-fold-arrow/01 后未折叠态也有箭头）",
  st.lines === 3 && st.gutter === "▾1|2|3", JSON.stringify(st));

await foldByKey();
await Eval(`document.querySelector('#code-viewer [data-fold-expand]')?.click(); true`);
check("点占位行 → 展开", await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length === 0`, 4000));

await foldByKey();
await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); ta.focus(); ta.setSelectionRange(0, 0); return true; })()`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: ']', ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true })); true`);
check("Ctrl+Shift+] → 展开", await waitFor(`document.querySelectorAll('#code-viewer [data-fold-expand]').length === 0`, 4000));

// ================= 保存回归面（overhaul/01 验收项：既有保存正常） =================
const SAVE_TEXT = "int main(void) {\n    return 0;\n}\n";
await setText(SAVE_TEXT, 0, 0);
await settle(400);
check("编辑后脏点出现", await Eval(`document.querySelectorAll('.code-tab-dirty').length`) === 1);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true })); true`);
check("Ctrl+S → 脏点清除", await waitFor(`document.querySelectorAll('.code-tab-dirty').length === 0`, 8000));
check("Ctrl+S → 成功 toast（已保存）",
  await Eval(`(document.querySelector('.toast')?.textContent || '').includes('已保存')`));
check("Ctrl+S → 磁盘内容 = 模型", readFileSync(MAIN_C, "utf8") === SAVE_TEXT,
  JSON.stringify(readFileSync(MAIN_C, "utf8")));

// ---- 深色主题截图 ----
await setText("int main(void) {\n    int x = 1;\n    return x;\n}\n", 16, 16);
await Eval(`document.documentElement.removeAttribute('data-theme')`);
await settle(250);
const box = await Eval(`(() => {
  const r = document.getElementById('code-viewer').getBoundingClientRect();
  return { x: Math.max(0, r.x), y: Math.max(0, r.y), w: r.width, h: r.height };
})()`);
const shot = await cdp("Page.captureScreenshot", {
  format: "png",
  clip: { x: box.x, y: box.y, width: box.w, height: box.h, scale: 1 },
});
writeFileSync(join(OUT, "shot-01-lineops-dark.png"), Buffer.from(shot.result.data, "base64"));
check("深色截图已保存", true);

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
