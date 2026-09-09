// 冒烟（code-page-vscode-overhaul/04 程序化编辑撤销栈）：真实浏览器验证
// Tab/Enter/括号/行操作/注释/替换（单个+全部）后 Ctrl+Z 撤销、Ctrl+Y 重做
// ——用 CDP Input.dispatchKeyEvent 发 trusted 按键（合成 KeyboardEvent 不会
// 触发浏览器默认撤销行为）。零写库；CDP 9251 + webapp 8000。
//
// 注（2026-09-09 第七轮补口）：注入姿势 = 「派发按键前重设选区 + 等渲染落定」。
// setText 直写 ta.value 后编辑器按模型光标重渲染，注入时设的选区会被覆盖成
// 模型光标（旧脚本 Tab/Enter/手输 3 项因此假红）。
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
// CDP 调用超时守卫（第七轮）：渲染进程偶发无响应时，命令永不返回 → 脚本静默
// 挂死（无任何输出）。20s 无响应即抛错并给出「页面无响应」提示。
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
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

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
const settle = (ms = 250) => new Promise((r) => setTimeout(r, ms));
const taValue = () => Eval(`document.querySelector('#code-viewer .code-ta').value`);
// trusted Ctrl+Z / Ctrl+Y（modifiers: 2 = Ctrl）
const zod = async (key, shift) => {
  const mods = 2 | (shift ? 8 : 0);
  const vk = key.toUpperCase() === "Z" ? 90 : 89;
  await cdp("Input.dispatchKeyEvent", {
    type: "keyDown", modifiers: mods, key: shift ? "Z" : key, code: "Key" + key.toUpperCase(),
    windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk,
  });
  await cdp("Input.dispatchKeyEvent", {
    type: "keyUp", modifiers: mods, key: shift ? "Z" : key, code: "Key" + key.toUpperCase(),
    windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk,
  });
};
const undo = () => zod("z", false);
const redo = () => zod("y", false);

// ---- Tab 缩进 ----
await setText("abc\n", 0, 0);
await press({ key: "Tab", bubbles: true, cancelable: true }, [0, 0]);
await settle();
check("Tab 缩进生效", (await taValue()) === "    abc\n");
await undo();
await settle();
check("Tab 后 Ctrl+Z 撤销", (await taValue()) === "abc\n");
await redo();
await settle();
check("Tab 后 Ctrl+Y 重做", (await taValue()) === "    abc\n");

// ---- Enter 自动缩进 ----
await setText("    abc\n", 4, 4);
await press({ key: "Enter", bubbles: true, cancelable: true }, [4, 4]);
await settle();
check("Enter 自动缩进生效", (await taValue()) === "    \n    abc\n");
await undo();
await settle();
check("Enter 后 Ctrl+Z 撤销", (await taValue()) === "    abc\n");

// ---- 括号自动闭合 ----
await setText("abc\n", 0, 0);
await press({ key: "{", bubbles: true, cancelable: true }, [0, 0]);
await settle();
check("括号闭合生效", (await taValue()) === "{}abc\n");
await undo();
await settle();
check("括号后 Ctrl+Z 撤销", (await taValue()) === "abc\n");

// ---- 行操作：Ctrl+Shift+K 删行 ----
await setText("abc\n", 0, 0);
await press({ key: "k", ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }, [0, 0]);
await settle();
check("删行生效", (await taValue()) === "");
await undo();
await settle();
check("删行后 Ctrl+Z 撤销", (await taValue()) === "abc\n");

// ---- 注释切换 ----
await setText("int x;\n", 0, 0);
await press({ key: "/", ctrlKey: true, bubbles: true, cancelable: true }, [0, 0]);
await settle();
check("注释生效", (await taValue()) === "// int x;\n");
await undo();
await settle();
check("注释后 Ctrl+Z 撤销", (await taValue()) === "int x;\n");

// ---- 替换单个 ----
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.value = 'a = 1; a = 2;';
  ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  const f = document.getElementById('code-find-input');
  f.value = 'a';
  f.dispatchEvent(new InputEvent('input', { bubbles: true }));
  const r = document.getElementById('code-replace-input');
  r.value = 'bb';
  return true;
})()`);
await Eval(`document.getElementById('btn-code-replace-one')?.click(); true`);
check("替换单个生效", (await taValue()) === "bb = 1; a = 2;");
await undo();
check("替换后 Ctrl+Z 撤销", (await taValue()) === "a = 1; a = 2;");
await redo();
check("替换后 Ctrl+Y 重做", (await taValue()) === "bb = 1; a = 2;");

// ---- 替换全部 ----
await Eval(`document.getElementById('btn-code-replace-all')?.click(); true`);
check("替换全部生效", (await taValue()) === "bb = 1; bb = 2;");
await undo();
check("替换全部后 Ctrl+Z 撤销", (await taValue()) === "bb = 1; a = 2;");

// ---- 键盘直接输入（回归：手输撤销不被打断）----
await setText("abc\n", 3, 3);
// 派发 trusted 按键前重设选区（同 press：setText 后编辑器按模型光标重渲染）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus(); ta.setSelectionRange(3, 3); return true;
})()`);
await cdp("Input.dispatchKeyEvent", {
  type: "keyDown", key: "x", code: "KeyX",
  windowsVirtualKeyCode: 88, nativeVirtualKeyCode: 88, text: "x",
});
await cdp("Input.dispatchKeyEvent", {
  type: "keyUp", key: "x", code: "KeyX",
  windowsVirtualKeyCode: 88, nativeVirtualKeyCode: 88,
});
check("手输字符生效", (await taValue()) === "abcx\n");
await undo();
check("手输后 Ctrl+Z 撤销", (await taValue()) === "abc\n");

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
