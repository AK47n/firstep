// 验证：多行 /* */ 注释在窗口化代码编辑器逐行高亮中承接行仍为注释色；
// 且在注释内编辑、滚动跳转后配色保持正确。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9252;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "bug-editor-type2", "sample4");
mkdirSync(SAMPLE, { recursive: true });
const lines = [];
lines.push("/* 蜂鸣器驱动（MSPM0 占位实现）：地猛星排针已分配满，暂无蜂鸣器引脚。");
lines.push(" * 接线后按 stm32 侧 beep_stm32.c 同款实现（gpio 输出 + beep_beep 延时）。");
lines.push(" * 保留本模块是为了两平台 API 统一：beep_on/off 调用不因平台改写。 */");
for (let i = 0; i < 200; i++) lines.push("int var_" + i + " = " + i + ";  // " + i);
writeFileSync(join(SAMPLE, "main.c"), lines.join("\n"));

const fetchT = async (url, ms = 5000) => {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
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
let seq = 0; const pending = new Map();
ws.onmessage = (ev) => { const msg = JSON.parse(ev.data); if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); } };
const cdp = (m, p = {}) => new Promise((res) => { const id = ++seq; pending.set(id, res); ws.send(JSON.stringify({ id, method: m, params: p })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 12000) => {
  for (let i = 0; i < ms / 200; i++) { try { if (await Eval(expr)) return true; } catch {} await new Promise((r) => setTimeout(r, 200)); }
  return false;
};
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100; i++) { try { if (await Eval(`document.readyState === 'complete' && !!document.getElementById('code-viewer')`)) break; } catch {} await new Promise((r) => setTimeout(r, 300)); }
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
const out = await Eval(`(async () => {
  const ce = await import('/js/ui/codeeditor.js');
  await ce.openEditorFile('main.c');
  const box = document.getElementById('code-viewer');
  const ta = box.querySelector('.code-ta');
  const tab = ce.getActiveTab();
  const hlRows = () => Array.from(box.querySelectorAll('.code-hl-line'))
    .map((el) => ({ text: el.textContent, html: el.innerHTML }));
  const state = () => ({
    m1: hlRows()[1], m2: hlRows()[2], m3: hlRows()[3],
    lines: tab.content.split('\\n').slice(0, 4),
  });
  const open = state();
  // 在注释第 2 行（" * 接线后…"）行尾追加一个字母，模拟注释内编辑
  ta.focus();
  const nl1 = ta.value.indexOf('\\n');
  const nl2 = ta.value.indexOf('\\n', nl1 + 1);
  const p = nl2;                     // 第 2 行行尾（换行符前）
  ta.setSelectionRange(p, p);
  ta.value = ta.value.slice(0, p) + 'X' + ta.value.slice(p);
  ta.setSelectionRange(p + 1, p + 1);
  ta.dispatchEvent(new InputEvent('input', { bubbles: true }));
  const afterEdit = state();
  // 滚到中部再滚回顶部：跨窗口后配色仍正确
  box.scrollTop = 3000; box.dispatchEvent(new Event('scroll'));
  await new Promise((r) => setTimeout(r, 120));
  box.scrollTop = 0; box.dispatchEvent(new Event('scroll'));
  await new Promise((r) => setTimeout(r, 120));
  const afterScroll = state();
  return { open, afterEdit, afterScroll };
})()`);
console.log(JSON.stringify(out, null, 2));
const hasCom = (row) => row.html.includes('tok-com');
const ok = out.open.m1 && hasCom(out.open.m2) && hasCom(out.open.m3)
  && hasCom(out.afterEdit.m1) && hasCom(out.afterEdit.m2) && hasCom(out.afterEdit.m3)
  && out.afterEdit.lines[1].includes('X')
  && hasCom(out.afterScroll.m2) && hasCom(out.afterScroll.m3);
console.log(ok ? "PASS 多行注释承接行高亮正确（含编辑/滚动）" : "FAIL 多行注释承接行高亮不符");
process.exit(ok ? 0 : 1);
