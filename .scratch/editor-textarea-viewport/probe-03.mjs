// 探针（工单 editor-textarea-viewport/03）：撤销栈全域化——模型级快照 + 手打
// 入栈 + 跨窗口语义 + 折叠态 + 程序化路径 + 粘贴/合成输入。
// CDP 9251 + webapp 8000；样本 .scratch/editor-textarea-viewport/sample-proj/。
// 覆盖：①Tab/Enter/行操作/注释/替换 撤销→重做；②手打输入（trusted 键）撤销→
// 重做；③跨窗口撤销（窗口 A 编辑 → 滚到窗口 B 编辑 → 连续撤销，模型级恢复）；
// ④折叠态手打/替换撤销（fold.c）；⑤超长粘贴（跨窗口/超窗）→ 模型 + 撤销；
// ⑥换 tab 后撤销栈隔离（不错撤到另一文件）。
// 注意：窗口化 syncTail 会把光标落到「编辑后模型光标」——每次 setText 后、
// 程序化按键前必须显式 setCaret（与旧全量态「选区保留」语义不同，属 02 既有
// 行为；探针对齐真实用户输入序列：输入 → 光标在编辑点 → 再按快捷键）。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "editor-textarea-viewport");
const SAMPLE = join(OUT, "sample-proj");
mkdirSync(SAMPLE, { recursive: true });

// 6000 行样例 .c（与 probe-02 同口径；二次生成保证存在）
const bigLines = [];
for (let i = 0; i < 6000; i++) bigLines.push("int var_" + i + " = " + i + ";  // " + i);
writeFileSync(join(SAMPLE, "big.c"), bigLines.join("\n"));
// 折叠样例 .c（多行函数体，可折叠）
writeFileSync(join(SAMPLE, "fold.c"),
  "int main(void) {\n    int x = 1;\n    int y = 2;\n    return x + y;\n}\n");
// 小文件（程序化路径功能验证；窗口 = 全文）
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
if (!page) { console.error("未找到页面 target"); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });
let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  else if (msg.method === "Page.javascriptDialogOpening") {
    // 探针不卡对话框（beforeunload 等——整洁页面理论不弹，兜底接受）
    const id = ++seq; pending.set(id, () => {}); ws.send(JSON.stringify({ id, method: "Page.handleJavaScriptDialog", params: { accept: true } }));
  }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 12000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};
let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// trusted 键盘：Ctrl+Z / Ctrl+Y（modifiers: 2 = Ctrl；8 = Shift）
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
// trusted 字符输入（Input.insertText＝真实插入路径：beforeinput → input →
// sync；比 dispatchKeyEvent+text 更确定——后者在 headless 偶发重复插入，
// 且窗口边界（overscan 顶部）落点有歧义，属 CDP 层伪影而非应用行为）。
const typeChar = async (ch) => cdp("Input.insertText", { text: ch });

// 每次探针用全新 headless 配置启动（无脏 tab、无缓存）→ 无需 Page.reload
// （脏 tab 的 beforeunload 会把 reload 卡成对话框，CDP 全挂——本探针不做
// reload，避免该陷阱；服务端静态文件直读磁盘）。
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);

const openTab = (file) => Eval(`document.querySelector('#code-tree [data-code-file="${file}"]')?.click(); true`);
const modelText = () => Eval(`import('/js/ui/codeeditor.js').then((m) => m.getActiveTab()?.content ?? '')`);
const taValue = () => Eval(`document.querySelector('#code-viewer .code-ta')?.value ?? ''`);
const setCaret = (pos) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(${pos}, ${pos});
  return ta.selectionStart;
})()`);
const press = (opts) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.dispatchEvent(new KeyboardEvent('keydown', ${JSON.stringify(opts)}));
  return true;
})()`);
const setTextViaInput = (text, s, e) => Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.value = ${JSON.stringify(text)};
  ta.setSelectionRange(${s}, ${e});
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
const waitPath = async (file) => waitFor(`(async () => (await import('/js/ui/codeeditor.js')).getActiveTab()?.path === "${file}")()`);

// ============ ① 程序化路径：Tab / Enter / 行操作 / 注释 / 替换 ============
await openTab("main.c");
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

await setTextViaInput("abc\n", 0, 0);
await setCaret(0);
await press({ key: "Tab", bubbles: true, cancelable: true });
check("① Tab 缩进生效", (await taValue()) === "    abc\n" && (await modelText()) === "    abc\n", JSON.stringify({ ta: await taValue(), model: await modelText() }));
await undo();
check("① Tab 后 Ctrl+Z 撤销（模型级）", (await taValue()) === "abc\n" && (await modelText()) === "abc\n");
await redo();
check("① Tab 后 Ctrl+Y 重做", (await taValue()) === "    abc\n" && (await modelText()) === "    abc\n");

await setTextViaInput("    abc\n", 4, 4);
await setCaret(4);
await press({ key: "Enter", bubbles: true, cancelable: true });
check("① Enter 自动缩进生效", (await taValue()) === "    \n    abc\n", JSON.stringify({ ta: await taValue() }));
await undo();
check("① Enter 后 Ctrl+Z 撤销", (await taValue()) === "    abc\n" && (await modelText()) === "    abc\n");

await setTextViaInput("abc\n", 0, 0);
await setCaret(0);
await press({ key: "k", ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true });
check("① Ctrl+Shift+K 删行生效", (await taValue()) === "");
await undo();
check("① 删行后 Ctrl+Z 撤销", (await taValue()) === "abc\n" && (await modelText()) === "abc\n");

await setTextViaInput("int x;\n", 0, 0);
await setCaret(0);
await press({ key: "/", ctrlKey: true, bubbles: true, cancelable: true });
check("① 注释切换生效", (await taValue()) === "// int x;\n");
await undo();
check("① 注释后 Ctrl+Z 撤销", (await taValue()) === "int x;\n" && (await modelText()) === "int x;\n");

// 替换单个 + 替换全部（走查找 UI 入口）
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
check("① 替换单个生效", (await taValue()) === "bb = 1; a = 2;" && (await modelText()) === "bb = 1; a = 2;");
await undo();
check("① 替换单个后 Ctrl+Z 撤销", (await modelText()) === "a = 1; a = 2;");
await redo();
check("① 替换单个后 Ctrl+Y 重做", (await modelText()) === "bb = 1; a = 2;");
await Eval(`document.getElementById('btn-code-replace-all')?.click(); true`);
check("① 替换全部生效", (await modelText()) === "bb = 1; bb = 2;");
await undo();
check("① 替换全部后 Ctrl+Z 撤销（到替换单个态）", (await modelText()) === "bb = 1; a = 2;");

// ============ ② 手打输入（trusted 键）：撤销→重做 ============
await setTextViaInput("abc\n", 3, 3);
await setCaret(3);
await typeChar("x");
check("② 手打字符生效（模型）", (await modelText()) === "abcx\n" && (await taValue()) === "abcx\n", JSON.stringify({ model: await modelText() }));
await undo();
check("② 手打后 Ctrl+Z 撤销", (await modelText()) === "abc\n");
await redo();
check("② 手打后 Ctrl+Y 重做", (await modelText()) === "abcx\n", JSON.stringify({ model: await modelText() }));
// 连续手打 + 程序化混合：a → Tab → 撤销 → 撤销（程序化与手打同栈）
await setTextViaInput("abc\n", 0, 0);
await setCaret(0);
await typeChar("a");
await setCaret(0);
await press({ key: "Tab", bubbles: true, cancelable: true });
check("② 混合编辑生效", (await modelText()) === "    aabc\n", JSON.stringify({ model: await modelText(), ta: await taValue() }));
await undo();
check("② 撤销 Tab（先）", (await modelText()) === "aabc\n");
await undo();
check("② 撤销手打 a（后）", (await modelText()) === "abc\n");

// ============ ③ 跨窗口撤销（窗口 A 编辑 → 窗口 B 编辑 → 连续撤销） ============
await openTab("big.c");
await waitPath("big.c");
const bigBefore = await modelText();
await setCaret(0);
await typeChar("X");
check("③ 窗口 A 打 X（模型首）", (await modelText()).startsWith("Xint var_0"), JSON.stringify({ head: (await modelText()).slice(0, 20) }));
await Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(3000); return true; })`);
await waitFor(`(() => { const b = document.getElementById('code-viewer'); return b.scrollTop > 1000 && !!document.querySelector('#code-viewer .code-ta'); })()`);
await setCaret(5);   // 窗口内首可见行中部（真实用户点击位；insertText 在任意窗口偏移都可确定落位）
await typeChar("Y");
const midModel = await modelText();
const midDiag = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const m = ce.getActiveTab().content;
  const at = m.indexOf('Y');
  return { yAt: at, ctx: at < 0 ? '' : m.slice(Math.max(0, at - 2), at + 16),
    sel: [ta.selectionStart, ta.selectionEnd], taHead: ta.value.slice(0, 24) };
})()`);
check("③ 窗口 B 打 Y（模型中段）", midModel.includes("Y") && midDiag.yAt > 1000 && midModel.startsWith("Xint var_0"),
  JSON.stringify({ head: midModel.slice(0, 20), hasY: midModel.includes("Y"), ...midDiag }));
// 撤销 Y（当前在窗口 B）：模型恢复 = 仅剩 X；窗口文本 = 模型切片
await undo();
const afterUndo1 = await modelText();
check("③ 撤销 Y：模型只剩 X（跨窗口模型级恢复）", afterUndo1.startsWith("Xint var_0") && !afterUndo1.includes("Y"), JSON.stringify({ head: afterUndo1.slice(0, 20) }));
check("③ 撤销后窗口文本 = 模型切片", (await taValue()).length > 0 && afterUndo1.includes(await taValue()));
// 再撤销 X：模型回到原样（窗口随之回顶部）
await undo();
const afterUndo2 = await modelText();
check("③ 撤销 X：模型回原样", afterUndo2 === bigBefore);
// 重做 ×2
await redo();
check("③ 重做 X", (await modelText()).startsWith("Xint var_0"));
await redo();
const redone = await modelText();
check("③ 重做 Y", redone.includes("Y") && redone.startsWith("Xint var_0"), JSON.stringify({ head: redone.slice(0, 20) }));

// ============ ④ 折叠态：手打 + 替换撤销（模型级快照跨折叠语义） ============
await openTab("fold.c");
await waitPath("fold.c");
const foldBefore = await modelText();
// Ctrl+Shift+[ 折叠光标所在最内层折叠区（光标默认行 1 = 函数体内）——
// 04 整改：修饰键组合不再被括号自动闭合劫持（不得插入 "[]"）
await setCaret(0);
await press({ key: "[", ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelector('#code-viewer .code-ta').value.includes('…')`);
const foldedView = await taValue();
check("④ Ctrl+Shift+[ 折叠（未被括号劫持插入 [ ]）", !(await modelText()).startsWith("[]") && foldedView.includes("…"),
  JSON.stringify({ head: (await modelText()).slice(0, 4), ta: foldedView.slice(0, 20) }));
// 光标放首行末尾（不触碰占位行），trusted 打 Z
const firstNl = foldedView.indexOf("\n");
await setCaret(firstNl);
await typeChar("Z");
const foldedTyped = await modelText();
check("④ 折叠态手打 Z 回写模型", foldedTyped.includes("main(void) {Z"), JSON.stringify({ model: foldedTyped }));
await undo();
const foldedUndone = await modelText();
const foldedTa = await taValue();
check("④ 折叠态手打后撤销（折叠保留）",
  foldedUndone === foldBefore
  && foldedTa.includes("…")
  && foldedTa.length === foldedView.length,
  JSON.stringify({ model: foldedUndone, ta: foldedTa, modelOk: foldedUndone === foldBefore, foldStill: foldedTa.includes("…"), lenOk: foldedTa.length === foldedView.length }));
// 折叠态替换全部 → 撤销（rebase 路径快照补档）
const replCount = await Eval(`import('/js/ui/codeeditor.js').then((m) => m.replaceAllInActiveFile('x', 'XX'))`);
check("④ 折叠态 replaceAll 生效", replCount > 0 && (await modelText()) !== foldBefore, "count=" + replCount);
await undo();
const replUndone = await modelText();
const replTa = await taValue();
check("④ 折叠态 replaceAll 后撤销", replUndone === foldBefore && replTa.includes("…"),
  JSON.stringify({ model: replUndone, modelOk: replUndone === foldBefore, foldStill: replTa.includes("…") }));

// ============ ⑤ 超长粘贴（跨窗口/超窗）→ 模型 + 撤销 ============
await openTab("big.c");
await waitPath("big.c");
const bigBase = await modelText();
await setCaret(0);
const pasteLines = [];
for (let i = 0; i < 150; i++) pasteLines.push("// paste line " + i);
const pasteText = pasteLines.join("\n") + "\n";
// 模拟粘贴：直接改窗口文本 + input 事件（CDP Input.insertText 大文本偶发不返回，
// 属协议层伪影；本路径与真实粘贴同走「窗口段 → 模型」映射 + 一致性兜底）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(0, 0);
  ta.value = ${JSON.stringify(pasteText)} + ta.value;
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
await waitFor(`(async () => (await import('/js/ui/codeeditor.js')).getActiveTab().content.startsWith(${JSON.stringify("// paste line 0")}))()`);
const pasted = await modelText();
check("⑤ 超长粘贴回写模型（150 行）", pasted.startsWith("// paste line 0") && pasted.includes("// paste line 149") && pasted.length > bigBase.length, JSON.stringify({ len: pasted.length, base: bigBase.length }));
check("⑤ 粘贴后窗口文本 = 模型切片", pasted.includes(await taValue()) && (await taValue()).length < 5000);
await undo();
check("⑤ 粘贴后撤销（模型回原样）", (await modelText()) === bigBase, JSON.stringify({ now: (await modelText()).slice(0, 20) }));

// ============ ⑥ 换 tab 撤销栈隔离 ============
await openTab("main.c");
await waitPath("main.c");
const mainBase = await modelText();
await setCaret(0);
await typeChar("A");
const mainWithA = await modelText();
check("⑥ main.c 打 A", mainWithA === "A" + mainBase, JSON.stringify({ head: mainWithA.slice(0, 12) }));
await openTab("big.c");
await waitPath("big.c");
const bigWithB = await modelText();
await setCaret(0);
await typeChar("B");
const bigAfterB = await modelText();
check("⑥ big.c 打 B", bigAfterB === "B" + bigWithB && bigAfterB.startsWith("B"), JSON.stringify({ head: bigAfterB.slice(0, 12) }));
await undo();
check("⑥ big.c 撤销（只撤 B，不串 main.c）", (await modelText()) === bigWithB);
await openTab("main.c");
await waitPath("main.c");
const afterSwitch = await modelText();
check("⑥ main.c 内容未被错撤（A 仍在）", afterSwitch === mainWithA);
await undo();   // 栈已随换 tab 清空 → 无操作
check("⑥ 换 tab 后撤销栈隔离（空栈无操作）", (await modelText()) === afterSwitch);

console.log("---- 汇总 ----");
console.log("PASS " + passed + " / FAIL " + failed);
writeFileSync(join(OUT, "probe-03-result.json"), JSON.stringify({
  passed, failed,
}, null, 2));
process.exit(failed ? 1 : 0);
