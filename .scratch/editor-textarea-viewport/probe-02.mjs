// 探针（工单 editor-textarea-viewport/02）：打开即窗口文本三明治 + 手打输入回写
// ——①打开 6000 行 .c 计时（renderMs ≤80ms；fetch 单列——后端零预算）；
// ②textarea = 视口高 + 窗口文本（非全量）；③手打字符回写模型/脏点/状态栏；
// ④结构编辑（Enter 自动缩进）回写 + 窗口重装；⑤滚动跟随（窗口文本 = 模型
// 当前窗口切片）；⑥跳行/查找可用；⑦逐键 input ≤25ms；⑧首屏/滚动中部截图。
// CDP 9251 + webapp 8000；样本 .scratch/editor-textarea-viewport/sample-proj/。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";
const OUT = join(ROOT, ".scratch", "editor-textarea-viewport");
const SAMPLE = join(OUT, "sample-proj");
mkdirSync(SAMPLE, { recursive: true });

// 6000 行样例 .c（每行 ~18 字符，共 ~110KB——与真实 6000 行 .c 同量级）
const bigLines = [];
for (let i = 0; i < 6000; i++) bigLines.push("int var_" + i + " = " + i + ";  // " + i);
writeFileSync(join(SAMPLE, "big.c"), bigLines.join("\n"));

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
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const msg = JSON.parse(ev.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
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

await Eval(`window.__probe = 1; true`);
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) {
  try {
    if (await Eval(`document.readyState === 'complete' && !window.__probe && !!document.getElementById('code-viewer')`)) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 300));
}
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="big.c"]')`);

// ---- ① 打开计时（冷开 = fetch + 渲染；热重开 = 纯前端渲染段 = probe-open 口径
// 的 renderMs——探针旧口径把二次 fetch 也算进 render，这里以缓存命中重开测纯渲染）----
const open = await Eval(`(async () => {
  const tF = performance.now();
  const resp = await fetch('/api/code/file?dir=' + encodeURIComponent(${JSON.stringify(SAMPLE)}) + '&path=' + encodeURIComponent('big.c'));
  const data = await resp.json();
  const fetchMs = performance.now() - tF;
  const ce = await import('/js/ui/codeeditor.js');
  const t0 = performance.now();
  await ce.openEditorFile('big.c');
  const coldMs = performance.now() - t0;   // 首次打开（含后端 fetch——预算外）
  const t1 = performance.now();
  await ce.openEditorFile('big.c');        // 已开标签：activateTab → renderPane（纯前端）
  const renderMs = performance.now() - t1;
  const box = document.getElementById('code-viewer');
  const ta = box.querySelector('.code-ta');
  return { fetchMs: Math.round(fetchMs * 100) / 100,
    renderMs: Math.round(renderMs * 100) / 100,
    openMs: Math.round(coldMs * 100) / 100,
    chars: data.content ? data.content.length : 0,
    taChars: ta ? ta.value.length : 0 };
})()`);
console.log("打开计时:", JSON.stringify(open));
check("打开纯前端渲染段 renderMs ≤ 80ms", open.renderMs <= 80, open.renderMs + "ms（fetch " + open.fetchMs + "ms 后端预算外）");
check("首次打开 openMs ≤ 200ms（含 fetch）", open.openMs <= 200, open.openMs + "ms");
check("textarea 只装窗口文本（<< 全文）", open.taChars > 0 && open.taChars < open.chars / 5, "窗口 " + open.taChars + " / 全文 " + open.chars);

// ---- ② 三明治几何：textarea 盖满视口、高度 = 视口 + overscan 上缘 ----
const geo = await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  const ta = box.querySelector('.code-ta');
  const br = box.getBoundingClientRect();
  const tr = ta.getBoundingClientRect();
  const topPx = parseFloat(ta.style.top || '0');
  const h = parseFloat(ta.style.height || '0');
  return { taTop: tr.top, boxTop: br.top, taBottom: tr.bottom, boxBottom: br.bottom,
    scrollTop: box.scrollTop, topPx, h, clientH: box.clientHeight,
    taText: ta.value, hlLines: box.querySelectorAll('.code-hl-line').length };
})()`);
check("textarea 覆盖视口顶部", Math.abs(geo.taTop - geo.boxTop) < 1, "taTop=" + geo.taTop + " boxTop=" + geo.boxTop);
check("textarea 覆盖视口底部（≥ 视口下缘）", geo.taBottom >= geo.boxBottom - 1, "taBottom=" + geo.taBottom + " boxBottom=" + geo.boxBottom);
check("textarea 高度 ≈ 视口高 + overscan 上缘", geo.h >= geo.clientH && geo.h <= geo.clientH + 200, "h=" + geo.h + " clientH=" + geo.clientH);
check("textarea top = 窗口起点 * 行高", Math.abs(geo.topPx - 0) < 0.5, "topPx=" + geo.topPx);

// ---- ④ 手打字符回写：模型、脏点、光标、行号 ----
const typed = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const before = ce.getActiveTab().content;
  ta.focus();
  ta.setSelectionRange(0, 0);
  const t = performance.now();
  ta.value = 'X' + ta.value;
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  const ms = performance.now() - t;
  const tab = ce.getActiveTab();
  return { dirty: tab.content !== tab.savedContent,
    modelOk: tab.content === 'X' + before && tab.content.startsWith('Xint var_0'),
    ms: Math.round(ms * 100) / 100,
    sel: ta.selectionStart, taLen: ta.value.length };
})()`);
check("手打 'X' 回写模型（窗口首 → 模型首）", typed.modelOk, JSON.stringify(typed));
check("手打后标签脏点", typed.dirty);
check("逐键 input ≤ 25ms", typed.ms <= 25, typed.ms + "ms");

// ---- ⑤ 结构编辑：Enter（keydown 拦截 → 自动缩进）→ 模型 + 窗口重装 ----
const enter = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const ta = document.querySelector('#code-viewer .code-ta');
  const tab = ce.getActiveTab();
  const before = tab.content;
  const beforeLines = before.split('\\n').length;
  ta.focus();
  const p = Math.min(ta.value.length - 1, 10);   // 窗口内中段
  ta.setSelectionRange(p, p);
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  const after = ce.getActiveTab().content;
  const afterLines = after.split('\\n').length;
  return { grewLine: afterLines === beforeLines + 1,
    taHasNewline: ta.value.includes('\\n'),
    sel: ta.selectionStart, modelLen: after.length, winLen: ta.value.length,
    caretLine: ce.editorCaretModelPos().line };
})()`);
check("Enter 结构编辑：模型 +1 行", enter.grewLine, JSON.stringify(enter));
check("Enter 后 textarea 重装窗口（含换行）", enter.taHasNewline);

// ---- ⑥ 滚动跟随：scroll → 窗口文本 = 模型当前窗口切片 ----
await Eval(`(() => {
  const box = document.getElementById('code-viewer');
  box.scrollTop = Math.floor(box.scrollHeight * 0.5);
  // headless 下程序化 scrollTop 不派发原生 scroll 事件（可见浏览器真实滚动会派发）——
  // 探针手动派发等价事件，验证「scroll → 窗口同步」处理链
  box.dispatchEvent(new Event('scroll'));
  return true;
})()`);
await waitFor(`(function() { const box = document.getElementById('code-viewer'); const ta = box.querySelector('.code-ta'); return box.scrollTop > 1000 && parseFloat(ta.style.top) > 1000; })()`, 8000);
const scroll = await Eval(`(async () => {
  const box = document.getElementById('code-viewer');
  const ta = box.querySelector('.code-ta');
  const hl = box.querySelector('.code-hl');
  const sp = hl.querySelector('.code-window-spacer');
  const lineEl = hl.querySelector('.code-hl-line');
  const spTop = parseFloat(sp ? sp.style.height : '0');
  const ce = await import('/js/ui/codeeditor.js');
  const tab = ce.getActiveTab();
  const tr = ta.getBoundingClientRect(); const br = box.getBoundingClientRect();
  // 窗口文本 = 模型连续切片（includes 即对拍——含首尾行拼接）
  return { match: tab.content.includes(ta.value) && ta.value.length < 5000,
    winLen: ta.value.length, topPx: parseFloat(ta.style.top || '0'),
    spTop,
    coverTop: tr.top <= br.top + 1, coverBottom: tr.bottom >= br.bottom - 1,
    scrollTop: box.scrollTop, viewportH: box.clientHeight };
})()`);
check("滚动后窗口文本 = 模型窗口切片", scroll.match, JSON.stringify({ winLen: scroll.winLen, topPx: scroll.topPx, scrollTop: scroll.scrollTop }));
check("滚动后 textarea top = 窗口起点 * 行高（与高亮层 spacer 同值）", Math.abs(scroll.topPx - scroll.spTop) < 0.6, scroll.topPx + " vs " + scroll.spTop);
check("滚动后 textarea 仍覆盖全视口", scroll.coverTop && scroll.coverBottom);

// ---- ⑦ 跳行（大纲/搜索共用路径）----
const jump = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  ce.editJumpToLine(3000);
  await new Promise((r) => setTimeout(r, 100));
  const ta = document.querySelector('#code-viewer .code-ta');
  const tab = ce.getActiveTab();
  const lines = tab.content.split('\\n');
  const at = lines[2999];
  return { found: ta.value.includes(at), line3000: at,
    selLine: Math.max(1, ta.value.slice(0, ta.selectionStart).split('\\n').length),
    modelCaretOk: ce.editorCaretModelPos().line === 3000 };
})()`);
check("跳行 3000：textarea 窗口含该行", jump.found, jump.line3000);check("跳行 3000：状态栏模型行号 = 3000", jump.modelCaretOk, JSON.stringify(jump));

// ---- ⑧ 查找可用 ----
const find = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  const st = ce.setEditorFind('var_2999');
  return { total: st.total, markRows: document.querySelectorAll('#code-viewer .code-marks-line').length };
})()`);
check("查找命中渲染", find.total > 0 && find.markRows > 0, JSON.stringify(find));
await Eval(`import('/js/ui/codeeditor.js').then((m) => m.setEditorFind(''))`);

// ---- 截图：首屏 + 滚动中部 ----
await Eval(`(() => { const box = document.getElementById('code-viewer'); box.scrollTop = 0; return true; })()`);
await new Promise((r) => setTimeout(r, 400));
let shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(OUT, "shot-02-first.png"), Buffer.from(shot.result.data, "base64"));
await Eval(`(() => { const box = document.getElementById('code-viewer'); box.scrollTop = Math.floor(box.scrollHeight * 0.5); return true; })()`);
await new Promise((r) => setTimeout(r, 400));
shot = await cdp("Page.captureScreenshot", { format: "png" });
writeFileSync(join(OUT, "shot-02-mid.png"), Buffer.from(shot.result.data, "base64"));

console.log("---- 汇总 ----");
console.log("PASS " + passed + " / FAIL " + failed);
writeFileSync(join(OUT, "probe-02-result.json"), JSON.stringify({
  open, geo, typed, enter, scroll, jump, find, passed, failed,
}, null, 2));
process.exit(failed ? 1 : 0);
