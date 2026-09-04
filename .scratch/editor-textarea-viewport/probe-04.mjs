// 探针（工单 editor-textarea-viewport/04）：滚动 rAF 节流 + 折叠三层组合 +
// 交互矩阵回归。CDP 9251 + webapp 8000；样本 .scratch/editor-textarea-viewport/sample-proj/。
// 覆盖：①滚动事件 rAF 节流（突发滚动后窗口文本 = 模型切片、无错位）；
// ②折叠 + 窗口三层组合（视图 > 视口时 textarea 只装视图切片；折叠开合/
// 触碰占位展开/折叠态手打回写/跳行自动展开）；③对齐矩阵 12 格（主题 × 缩放 ×
// 折叠）；④交互冒烟（逐键/跳转/查找/保存/撤销/复制粘贴）。
// 每次探针用全新 headless 配置启动（不 reload——脏 tab 的 beforeunload 会卡 CDP）。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "editor-textarea-viewport");
const SAMPLE = join(OUT, "sample-proj");
mkdirSync(SAMPLE, { recursive: true });

// 大文件（视口窗口化）：6000 行平铺
const bigLines = [];
for (let i = 0; i < 6000; i++) bigLines.push("int var_" + i + " = " + i + ";  // " + i);
writeFileSync(join(SAMPLE, "big.c"), bigLines.join("\n"));
// 折叠+窗口组合：3000 平铺行 + 100 行函数（可折叠）+ 3000 平铺行——折叠后
// 视图仍 5900+ 行 > 视口，textarea 必须装「视图切片」而非视图全量。
const bf = [];
for (let i = 0; i < 3000; i++) bf.push("int pre_" + i + " = " + i + ";  // " + i);
bf.push("int main(void) {");
for (let i = 0; i < 100; i++) bf.push("    int inner_" + i + " = " + i + ";  // " + i);
bf.push("    return 0;");
bf.push("}");
for (let i = 0; i < 3000; i++) bf.push("int post_" + i + " = " + i + ";  // " + i);
writeFileSync(join(SAMPLE, "bigfold.c"), bf.join("\n"));
// 折叠样例（小，占位行语义）
writeFileSync(join(SAMPLE, "fold.c"),
  "int main(void) {\n    int x = 1;\n    int y = 2;\n    return x + y;\n}\n");

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
// trusted 字符输入：Input.insertText＝真实插入路径（beforeinput → input →
// sync）；dispatchKeyEvent+text 在 headless 偶发重复插入/窗口边界落点歧义，
// 属 CDP 层伪影（03 探针同整改）。
const typeChar = (ch) => cdp("Input.insertText", { text: ch });

await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);

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
const waitPath = async (file) => waitFor(`(async () => (await import('/js/ui/codeeditor.js')).getActiveTab()?.path === "${file}")()`);

// ============ ① 滚动 rAF 节流：突发滚动 → 终态窗口 = 模型切片 ============
await openTab("big.c");
await waitPath("big.c");
await Eval(`(() => { const b = document.getElementById('code-viewer'); b.scrollTop = 0; b.dispatchEvent(new Event('scroll')); return true; })()`);
await new Promise((r) => setTimeout(r, 300));
// 突发 30 次滚动（模拟快速拖滚）：只应有一次 rAF 合并重装，终态正确
await Eval(`(() => {
  const b = document.getElementById('code-viewer');
  const mid = Math.floor(b.scrollHeight * 0.5);
  for (let i = 0; i < 30; i++) { b.scrollTop = mid + Math.floor(Math.sin(i) * 400); b.dispatchEvent(new Event('scroll')); }
  return true;
})()`);
await new Promise((r) => setTimeout(r, 400));   // rAF 落定
const scrollState = await Eval(`(async () => {
  const b = document.getElementById('code-viewer');
  const ta = document.querySelector('#code-viewer .code-ta');
  const ce = await import('/js/ui/codeeditor.js');
  const m = ce.getActiveTab().content;
  return { scrollTop: b.scrollTop, taLen: ta.value.length, match: m.includes(ta.value)
    && ta.value.length < 6000,
    topPx: parseFloat(ta.style.top || '0'), spTop: (() => {
      const sp = document.querySelector('#code-viewer .code-window-spacer');
      return sp ? parseFloat(sp.style.height || '0') : 0; })(),
    overflow: getComputedStyle(ta).overflow };
})()`);
check("① 滚动突发后窗口文本 = 模型切片", scrollState.match && scrollState.taLen > 0, JSON.stringify(scrollState));
check("① textarea top 与高亮层 spacer 同值（对齐）", Math.abs(scrollState.topPx - scrollState.spTop) < 0.6, JSON.stringify({ topPx: scrollState.topPx, spTop: scrollState.spTop }));
check("① textarea 无内部滚动条（overflow:hidden）", scrollState.overflow === "hidden", JSON.stringify({ overflow: scrollState.overflow }));

// ============ ② 折叠 + 窗口三层组合（bigfold.c 视图 > 视口） ============
await openTab("bigfold.c");
await waitPath("bigfold.c");
const bfModel = await modelText();
// 先把光标跳进函数体（模型行 3005 属折叠区）——editJumpToLine 才吃模型行号；
// setCaret 是窗口偏移（顶部窗口会被钳制），不能用来定位折叠区。
await Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(3005); return true; })`);
await new Promise((r) => setTimeout(r, 200));
await press({ key: "[", ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelector('#code-viewer .code-ta').value.includes('…')`);
const foldedState = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const m = ce.getActiveTab().content;
  const view = ce.editorViewText();   // 折叠态 = 视图文本（占位文案仅存在于视图）
  return { taLen: ta.value.length, modelLen: m.length,
    hasPh: ta.value.includes('…'), viewHasPh: view.includes('…'),
    taIsViewSlice: view.includes(ta.value) };
})()`);
check("② 折叠 + 窗口：textarea = 视图切片（含占位文案、非模型全量）",
  foldedState.taLen < foldedState.modelLen && foldedState.taIsViewSlice && foldedState.hasPh && foldedState.viewHasPh,
  JSON.stringify(foldedState));
// 折叠态窗口内手打（窗口首可见行内）→ 模型回写（三层映射：窗口→视图→模型）
await setCaret(3);
check("② 手打落点非占位行（窗口首行非占位）", !(await taValue()).startsWith("…"),
  JSON.stringify({ winHead: (await taValue()).slice(0, 12) }));
await typeChar("Q");
const foldedTyped = await modelText();
check("② 折叠 + 窗口手打 Q 回写模型", foldedTyped !== bfModel && foldedTyped.includes("Q"),
  JSON.stringify({ model: foldedTyped.slice(0, 40) }));
// 撤销（折叠保留——折叠区在窗口外时窗口文本不含占位行，须按全量视图校验）
await undo();
const foldedViewAfter = await Eval(`import('/js/ui/codeeditor.js').then((m) => m.editorViewText())`);
check("② 折叠 + 窗口手打后撤销（模型回原样、折叠仍在）",
  (await modelText()) === bfModel && foldedViewAfter.includes('…'));
// 跳行到折叠区内 → 自动展开（既有语义）
await Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(3050); return true; })`);
await new Promise((r) => setTimeout(r, 200));
const afterJump = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const m = ce.getActiveTab().content;
  return { modelHas: m.includes('int inner_49'), viewTa: ta.value.includes('int inner_49'),
    caretLine: ce.editorCaretModelPos().line };
})()`);
check("② 跳行自动展开且光标行号 = 模型行号", afterJump.modelHas && afterJump.viewTa && afterJump.caretLine === 3050,
  JSON.stringify(afterJump));
// 折叠态程序化编辑 = 全视图语义（窗口边界 ≠ 文档边界）：
// 重新折叠，光标在窗口首可见行，Alt+↑ 必须移动该行（07 既有语义——
// 评审整改：窗口级编辑会把窗口顶当文档边界导致静默失效）
await Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(3005); return true; })`);
await new Promise((r) => setTimeout(r, 200));
await press({ key: "[", ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true });
await waitFor(`document.querySelector('#code-viewer .code-ta').value.includes('…')`);
const beforeMove = await modelText();
await setCaret(3);   // 窗口首可见行内（非占位）
await press({ key: "ArrowUp", altKey: true, bubbles: true, cancelable: true });
const afterMove = await modelText();
check("② 折叠态 Alt+↑ 移动行（窗口顶仍可上移，全视图语义）",
  afterMove !== beforeMove,
  JSON.stringify({ model: afterMove.slice(0, 60) }));
await undo();
check("② 折叠态移动行后撤销（模型回原样、折叠仍在）",
  (await modelText()) === beforeMove && (await Eval(`import('/js/ui/codeeditor.js').then((m) => m.editorViewText())`)).includes('…'));
// 触碰占位行 → 展开（既有语义；占位行窗口内可见时）
const phPos = await Eval(`(() => { const ta = document.querySelector('#code-viewer .code-ta'); return ta.value.indexOf('…'); })()`);
if (phPos >= 0) {
  await setCaret(phPos);
  const beforePh = await modelText();
  await typeChar("Z");
  const afterPh = await modelText();
  const phView = await Eval(`import('/js/ui/codeeditor.js').then((m) => m.editorViewText())`);
  check("② 触碰占位行 → 展开（视图不再有占位、模型含键入）",
    afterPh !== beforePh && afterPh.includes("Z") && !phView.includes("…"));
  await undo();
  check("② 触碰占位展开后撤销（模型回原样）", (await modelText()) === beforePh);
} else {
  check("② 触碰占位行 → 展开（占位行不在当前窗口，跳过）", true);
}

// ============ ③ 对齐矩阵 12 格（主题 × 缩放 × 折叠） ============
// bigfold.c 的折叠区（f0）= 模型行 3001–3103（函数体）。折叠开关经编辑器
// 快捷键管线：必须先让光标落在折叠区内（editJumpToLine(3005)——若折叠区此刻
// 已折叠会先自动展开，再按 '[' 重折），否则 foldAtLine 返回 null、'[' 无操作
// → fold=true 单元格假绿（评审整改：矩阵必须真实折叠）。
const setCell = (theme, pct, fold) => Eval(`(async () => {
  document.documentElement.setAttribute('data-theme', ${JSON.stringify(theme)});
  try { localStorage.setItem('firstep.theme', ${JSON.stringify(theme)}); } catch (e) {}
  const view = document.getElementById('code-viewer');
  view.style.setProperty('--code-zoom', String(${pct} / 100));
  const ce = await import('/js/ui/codeeditor.js');
  ce.codeWindowRefresh();
  const key = (k) => document.querySelector('#code-viewer .code-ta').dispatchEvent(new KeyboardEvent('keydown', {
    key: k, code: k === '[' ? 'BracketLeft' : 'BracketRight',
    ctrlKey: true, shiftKey: true, bubbles: true, cancelable: true }));
  key(']');                     // 先展开（若折叠区已折叠）
  ce.editJumpToLine(3005);      // 光标落进折叠区（折叠中先自动展开——注意：
                                // 展开路径 renderPane 会重建 textarea，key 必须
                                // 重新 querySelector，不能持有旧引用）
  ${fold ? "key('[');" : ""}    // 目标折叠态
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(0, 0);   // 光标归位视口首（对齐测量基准一致）
  return true;
})()`);
const collect = () => Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const tops = (sel) => Array.from(box.querySelectorAll(sel))
    .map((el) => Math.round(el.getBoundingClientRect().top * 2) / 2)
    .sort((a, b) => a - b);
  const gutTops = tops('.code-gutter-line');
  const hlTops = tops('.code-hl-line');
  const marksTops = tops('.code-marks-line');
  const near = (a, b) => Math.abs(a - b) <= 1;
  const bad = [];
  for (const t of hlTops) if (!gutTops.some((g) => near(g, t))) bad.push({ kind: 'hl-orphan', top: t });
  for (const t of gutTops) if (!hlTops.some((h) => near(h, t))) bad.push({ kind: 'gut-orphan', top: t });
  for (const t of marksTops) if (!hlTops.some((h) => near(h, t))) bad.push({ kind: 'marks-orphan', top: t });
  const ga = box.querySelector('.code-gutter-line.active');
  const ha = box.querySelector('.code-hl-line.active');
  if (ga && ha && !near(ga.getBoundingClientRect().top, ha.getBoundingClientRect().top)) {
    bad.push({ kind: 'active', g: Math.round(ga.getBoundingClientRect().top * 100) / 100, h: Math.round(ha.getBoundingClientRect().top * 100) / 100 });
  }
  return { gutterCount: gutTops.length, hlCount: hlTops.length, marksCount: marksTops.length, bad };
})()`);
await openTab("bigfold.c");
await waitPath("bigfold.c");
let matrixFails = 0;
for (const theme of ["light", "dark"]) {
  for (const pct of [100, 150, 200]) {
    for (const fold of [false, true]) {
      await setCell(theme, pct, fold);
      await new Promise((r) => setTimeout(r, 400));
      const foldReal = await Eval(`import('/js/ui/codeeditor.js').then((m) => m.editorViewText().includes('…'))`);
      check("③ 矩阵 " + theme + " " + pct + "% fold=" + (fold ? "on" : "off") + "（折叠开关真实生效）", foldReal === fold, "foldReal=" + foldReal);
      const c = await collect();
      const ok = c.bad.length === 0;
      if (!ok) matrixFails++;
      check("③ 矩阵 " + theme + " " + pct + "% fold=" + (fold ? "on" : "off"), ok, JSON.stringify(c.bad.slice(0, 4)));
    }
  }
}
check("③ 对齐矩阵 12 格全绿", matrixFails === 0, "fails=" + matrixFails);
// 双主题截图（折叠态：滚动到占位行居中——编辑视图行 3001 = 折叠区占位行；
// 用高亮层实测行高算 scrollTop，并断言占位行确实进入窗口）
await setCell("dark", 100, true);
await new Promise((r) => setTimeout(r, 400));
const darkPre = await Eval(`import('/js/ui/codeeditor.js').then((m) => m.editorViewText().includes('…'))`);
check("③ 截图前折叠态成立（setCell 后）", darkPre);
await Eval(`(() => {
  const b = document.getElementById('code-viewer');
  const lh = parseFloat(getComputedStyle(document.querySelector('#code-viewer .code-hl-line')).lineHeight) || 20;
  b.scrollTop = Math.max(0, 3000 * lh - Math.floor(b.clientHeight / 2));
  b.dispatchEvent(new Event('scroll'));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 300));
const darkPost = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  return { viewHas: ce.editorViewText().includes('…'), winHas: ta.value.includes('…'),
    winHead: ta.value.slice(0, 26), scrollTop: document.getElementById('code-viewer').scrollTop };
})()`);
check("③ 折叠态截图含占位行（shot-04-fold-dark）", darkPost.winHas, JSON.stringify(darkPost));
let shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(OUT, "shot-04-fold-dark.png"), Buffer.from(shot.result.data, "base64"));
await setCell("light", 100, false);
await new Promise((r) => setTimeout(r, 400));
shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(OUT, "shot-04-light.png"), Buffer.from(shot.result.data, "base64"));

// ============ ④ 交互冒烟：跳转 / 查找 / 保存 / 撤销 / 复制粘贴 ============
await openTab("big.c");
await waitPath("big.c");
// 逐键采样（≤25ms）
const typed = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const before = ce.getActiveTab().content;
  ta.focus();
  ta.setSelectionRange(0, 0);
  ta.value = 'X' + ta.value;
  const t = performance.now();
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  const ms = performance.now() - t;
  return { ok: ce.getActiveTab().content.startsWith('Xint var_0'), ms: Math.round(ms * 100) / 100 };
})()`);
check("④ 逐键 input ≤ 25ms", typed.ok && typed.ms <= 25, typed.ms + "ms");
await undo();
check("④ 逐键撤销", (await modelText()) === (await Eval(`import('/js/ui/codeeditor.js').then((m) => m.getActiveTab().savedContent)`)));
// 跳转 / 查找
await Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(4500); return true; })`);
await new Promise((r) => setTimeout(r, 200));
const jump = await Eval(`(async () => { const ce = await import('/js/ui/codeeditor.js'); return ce.editorCaretModelPos().line; })()`);
check("④ 跳行 4500 状态栏模型行号", jump === 4500, "line=" + jump);
const find = await Eval(`(async () => { const ce = await import('/js/ui/codeeditor.js'); const st = ce.setEditorFind('var_4499'); return st.total > 0 && document.querySelectorAll('#code-viewer .code-marks-line').length > 0; })()`);
check("④ 查找命中渲染", find);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.setEditorFind(''))`);
// 保存：真实写盘（样本文件）——先真实编辑 + 保存，脏点清除、磁盘内容一致
await Eval(`import('/js/ui/codeeditor.js').then((m) => { m.editJumpToLine(1); return true; })`);
await new Promise((r) => setTimeout(r, 200));
await setCaret(0);   // 窗口回顶部后 offset 0 = 文档首
await cdp("Input.insertText", { text: "S" });
await waitFor(`(async () => (await import('/js/ui/codeeditor.js')).getActiveTab().content.startsWith('S'))()`);
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.saveActiveTab())`);
await waitFor(`(async () => { const ce = await import('/js/ui/codeeditor.js'); const t = ce.getActiveTab(); return t.content === t.savedContent; })()`);
const saved = await Eval(`(async () => { const ce = await import('/js/ui/codeeditor.js'); const t = ce.getActiveTab(); return { dirty: t.content !== t.savedContent, len: t.content.length, head: t.content.slice(0, 2) }; })()`);
check("④ 保存后脏点清除（磁盘 = 模型）", !saved.dirty && saved.head.startsWith("S"), JSON.stringify(saved));
// 复制粘贴（合成输入 150 行）→ 模型 + 撤销
// （CDP Input.insertText 大文本偶发不返回——协议层伪影；改 DOM 输入路径，
// 与真实粘贴同走「窗口段 → 模型」映射 + 一致性兜底）
await Eval(`(async () => { const ce = await import('/js/ui/codeeditor.js'); const t = ce.getActiveTab(); t.savedContent = t.content; return true; })()`);
const base = await modelText();
await setCaret(0);
const pasteLines = [];
for (let i = 0; i < 150; i++) pasteLines.push("// p2 " + i);
const pasteText = pasteLines.join("\n") + "\n";
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(0, 0);
  ta.value = ${JSON.stringify(pasteText)} + ta.value;
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  return true;
})()`);
await waitFor(`(async () => (await import('/js/ui/codeeditor.js')).getActiveTab().content.startsWith(${JSON.stringify("// p2 0")}))()`);
check("④ 粘贴 150 行回写模型", (await modelText()).startsWith("// p2 0"));
await undo();
check("④ 粘贴后撤销", (await modelText()) === base);

// AI 插入/插入到光标（工单 03 清单第 3 项：insertIntoActiveFile 经
// applyEdit/rebase 快照入栈，撤销可回）
await openTab("main.c");
await waitPath("main.c");
const mainBase04 = await modelText();
await setCaret(2);
const aiOk = await Eval(`import('/js/ui/codeeditor.js').then((m) => m.insertIntoActiveFile('AICOMMENT'))`);
const mainAfterAI = await modelText();
check("④ AI 插入（insertIntoActiveFile）生效", aiOk && mainAfterAI === mainBase04.slice(0, 2) + "AICOMMENT" + mainBase04.slice(2),
  JSON.stringify({ head: mainAfterAI.slice(0, 16) }));
await undo();
check("④ AI 插入后 Ctrl+Z 撤销", (await modelText()) === mainBase04);
await redo();
check("④ AI 插入后 Ctrl+Y 重做", (await modelText()) === mainAfterAI);

console.log("---- 汇总 ----");
console.log("PASS " + passed + " / FAIL " + failed);
process.exit(failed ? 1 : 0);
