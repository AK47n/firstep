// 冒烟（工单 compile-error-jump/01）：错误列表点 main.c 行 → 预览卡滚动到
// 视口 + main-c 选中目标行（selectionStart/End 独立字面量断言）+ 内部滚动；
// 非 main.c 行维持展开源码行（apiPost mock）；空 main.c → toast 不跳转。
// 零依赖：node 内置 fetch + WebSocket 直连 Edge CDP（9231）。
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page");
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
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

let ready = false;
// 重新加载页面：webapp 静态文件实时更新，但浏览器内存中的 JS 需刷新才换新
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('main-c')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? "  [" + extra + "]" : ""));
  if (!ok) failed++;
};

// ---- 切「生成」tab，写入 60 行定长内容（第 40 行可独立计算偏移）----
await Eval(`document.querySelector('[data-tab="generate"]').click()`);
const payload = await Eval(`(() => {
  const ta = document.getElementById('main-c');
  const lines = [];
  for (let i = 1; i <= 60; i++) lines.push('void func_' + String(i).padStart(3, '0') + '(void) { int t = 1; }');
  ta.value = lines.join('\\n');
  ta.dispatchEvent(new Event('input'));
  return { len: ta.value.length, lastLen: lines[59].length, l40: lines[39].length };
})()`);
await new Promise((r) => setTimeout(r, 300));

// 独立字面量：每行同长 L = "void func_" (10) + 3 + "(void) { int t = 1; }" (21) = 34
const L = 34, line40Start = 39 * (L + 1), line40End = line40Start + L;
check("预览内容自检：第 40 行长度 = 34", payload.l40 === L, "l40=" + payload.l40);

// ---- 渲染错误列表：main.c:40 + led.c:3 ----
await Eval(`(() => {
  window.apiPost = async () => ({ line_text: 'return 0;' });   // 冒烟 mock，避免真调后端
  document.getElementById('output-dir').value = 'D:/tmp/ledproj';   // fixToggleSource 需要
  fixRenderResults([
    { path: 'main.c', line: 40, message: '未定义的变量: hx711' },
    { path: 'modules/led/code/led.c', line: 3, message: '缺少分号' },
  ], [], 2);
  return document.querySelectorAll('#fix-results .fix-row').length;
})()`);
await new Promise((r) => setTimeout(r, 200));

// ---- 点 main.c 错误行 → 跳转定位 ----
await Eval(`document.querySelectorAll('#fix-results .fix-row')[0].click()`);
await new Promise((r) => setTimeout(r, 800));   // smooth scroll 动画

const sel = await Eval(`(() => {
  const ta = document.getElementById('main-c');
  return { start: ta.selectionStart, end: ta.selectionEnd, scrollTop: ta.scrollTop, valueLen: ta.value.length };
})()`);
check("点 main.c 行 → selectionStart = 行 40 起点", sel.start === line40Start, "start=" + sel.start);
check("点 main.c 行 → selectionEnd = 行 40 终点（含整行）", sel.end === line40End, "end=" + sel.end);
check("点 main.c 行 → 预览内部滚动到选区（scrollTop > 0）", sel.scrollTop > 0, "scrollTop=" + sel.scrollTop);

const cardVisible = await Eval(`(() => {
  const card = document.getElementById('main-c').closest('.card');
  const r = card.getBoundingClientRect();
  return r.top < innerHeight && r.bottom > 0 && !card.classList.contains('collapsed');
})()`);
check("main.c 卡可见（在视口内且未折叠）", cardVisible === true);

// ---- 点 led.c 行 → 维持展开源码行（回归）----
await Eval(`document.querySelectorAll('#fix-results .fix-row')[1].click()`);
await new Promise((r) => setTimeout(r, 300));
const led = await Eval(`(() => {
  const row = document.querySelectorAll('#fix-results .fix-row')[1];
  const src = row.querySelector('.fix-source');
  const ta = document.getElementById('main-c');
  return { srcText: src ? src.textContent : null, start: ta.selectionStart, end: ta.selectionEnd };
})()`);
check("点 led.c 行 → 展开源码行（.fix-source 出现）", led.srcText !== null && led.srcText.includes("3: return 0;"), "src=" + led.srcText);
check("点 led.c 行 → main.c 选区不被扰动", led.start === line40Start && led.end === line40End, `start=${led.start},end=${led.end}`);

// ---- 折行场景：第 20 行超长（软换行开启，pre-wrap 折 2-3 行）→ 行 40 逻辑
// 偏移随内容长度变化（独立推导字面量：38×34 + 333 字节前 39 行 + 39 个 \n =
// 1664），视觉位置下移，滚动量必须跟着下移（量测驱动，无像素公式）----
await Eval(`(() => {
  const ta = document.getElementById('main-c');
  const lines = [];
  for (let i = 1; i <= 60; i++) lines.push('void func_' + String(i).padStart(3, '0') + '(void) { int t = 1; }');
  lines[19] = 'void func_020(void) { int t = ' + 'x'.repeat(300) + '; }';   // 第 20 行超长
  ta.value = lines.join('\\n');
  ta.dispatchEvent(new Event('input'));
  fixRenderResults([{ path: 'main.c', line: 40, message: '折行定位' }], [], 2);
})()`);
await Eval(`document.querySelectorAll('#fix-results .fix-row')[0].click()`);
await new Promise((r) => setTimeout(r, 600));
const wrapState = await Eval(`(() => {
  const ta = document.getElementById('main-c');
  return { start: ta.selectionStart, end: ta.selectionEnd, scrollTop: ta.scrollTop };
})()`);
const wrapStart = 38 * 34 + 333 + 39;   // 前 39 行字节和 + 39 个 \n
check("折行下选区仍正确（逻辑行偏移随内容长度变化）", wrapState.start === wrapStart && wrapState.end === wrapStart + 34, `start=${wrapState.start},expect=${wrapStart}`);
check("折行下滚动量更大（提前折行把目标行推低）", wrapState.scrollTop > sel.scrollTop, `wrapped=${wrapState.scrollTop} plain=${sel.scrollTop}`);

// ---- 空 main.c → toast 不跳转 ----
await Eval(`(() => {
  const ta = document.getElementById('main-c');
  ta.value = '';
  ta.dispatchEvent(new Event('input'));
  fixRenderResults([{ path: 'main.c', line: 5, message: 'x' }], [], 2);
})()`);
await Eval(`document.querySelectorAll('#fix-results .fix-row')[0].click()`);
await new Promise((r) => setTimeout(r, 300));
const emptyState = await Eval(`(() => {
  const ta = document.getElementById('main-c');
  const toasts = Array.from(document.querySelectorAll('#toast-root .toast')).map((t) => t.textContent);
  return { start: ta.selectionStart, toasts: toasts.join('|') };
})()`);
check("空 main.c 点错误行 → 不选中（selectionStart = 0）", emptyState.start === 0, "start=" + emptyState.start);
check("空 main.c 点错误行 → toast 提示", emptyState.toasts.includes("main.c 还没有内容"), emptyState.toasts);

console.log(failed === 0 ? "SMOKE ALL PASS" : `SMOKE FAILED (${failed})`);
process.exit(failed === 0 ? 0 : 1);
