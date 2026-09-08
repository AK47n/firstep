// 冒烟（code-viewer-editor/07）：右侧栏收起/展开——贴右缘 40px 竖向轨道。
// 断言：初始展开 → 点活动页签收起（rail 出现、面板/页签条隐藏、grid 右列
// 40px、localStorage 键 "1"）→ 点 rail「搜索」展开（search 面板可见、键 "0"）
// → 收起态 Ctrl+F 自动展开并聚焦查找框 → 展开态点大纲（非活动）仅切换。
// 零依赖 CDP（9251）+ webapp 8000。
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const SAMPLE = join(ROOT, ".scratch", "code-viewer-editor", "sample-proj");

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
const click = (sel) => Eval(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) return false; el.click(); return true; })()`);

// 确定性起点：清侧栏收起键 + reload（展开态）
await Eval(`localStorage.removeItem('firstep.codeSideCollapsed'); window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('code-viewer')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// 打开样本工程（rail 在侧栏内，先有目录才有意义）
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length >= 2`);

// ===== 初始 = 展开态 =====
check("初始（无键）：无 .side-collapsed", await Eval(`
  !document.querySelector('.code-layout')?.classList.contains('side-collapsed')`));
check("初始：tab 条可见 + 面板可见 + rail 隐藏", await Eval(`
  (() => {
    const tabs = document.querySelector('.code-side-tabs');
    const panel = document.querySelector('[data-code-side-panel="outline"]');
    const rail = document.querySelector('.code-side-rail');
    return !!tabs && getComputedStyle(tabs).display !== 'none'
      && !!panel && getComputedStyle(panel).display !== 'none'
      && !!rail && getComputedStyle(rail).display === 'none';
  })()`));
const mainW0 = await Eval(`document.querySelector('.code-pane-main').offsetWidth`);
const sideW0 = await Eval(`document.querySelector('.code-pane-side').offsetWidth`);

// ===== 展开态点活动页签（大纲）→ 收起 =====
await click('[data-code-side="outline"]');
check("点活动页签名「大纲」→ 收起（.side-collapsed）", await waitFor(`
  document.querySelector('.code-layout')?.classList.contains('side-collapsed')`));
check("收起态：rail 可见 / 页签条与面板隐藏 / 右列 40px", await Eval(`
  (() => {
    const tabs = document.querySelector('.code-side-tabs');
    const panel = document.querySelector('[data-code-side-panel="outline"]');
    const rail = document.querySelector('.code-side-rail');
    const side = document.querySelector('.code-pane-side');
    return getComputedStyle(rail).display === 'flex'
      && getComputedStyle(tabs).display === 'none'
      && getComputedStyle(panel).display === 'none'
      && side.offsetWidth === 40;
  })()`));
check("收起态：localStorage 键 = 1", await Eval(`localStorage.getItem('firstep.codeSideCollapsed') === '1'`));
const mainW1 = await Eval(`document.querySelector('.code-pane-main').offsetWidth`);
check("收起 → 编辑区吃满（.code-pane-main 变宽）", mainW1 > mainW0,
  mainW0 + " -> " + mainW1);

// ===== 收起态点 rail「搜索」→ 展开并切换 =====
await click('.code-side-rail-btn[data-code-side="search"]');
check("点 rail「搜索」→ 展开（.side-collapsed 移除）", await waitFor(`
  !document.querySelector('.code-layout')?.classList.contains('side-collapsed')`));
check("展开后：search 面板可见 + rail 隐藏 + 键 = 0", await Eval(`
  (() => {
    const search = document.querySelector('[data-code-side-panel="search"]');
    const rail = document.querySelector('.code-side-rail');
    return !search.classList.contains('hidden')
      && getComputedStyle(search).display !== 'none'
      && getComputedStyle(rail).display === 'none'
      && localStorage.getItem('firstep.codeSideCollapsed') === '0';
  })()`));
check("展开后的 tab 条：search 为活动 on", await Eval(`
  document.querySelector('.code-side-tabs [data-code-side="search"]')?.classList.contains('on')`));

// ===== 展开态点活动页签（search）→ 再收起 =====
await click('.code-side-tabs [data-code-side="search"]');
check("展开态点活动页签「搜索」→ 再收起", await waitFor(`
  document.querySelector('.code-layout')?.classList.contains('side-collapsed')
    && localStorage.getItem('firstep.codeSideCollapsed') === '1'`));

// ===== 收起态 Ctrl+F → 自动展开 + 聚焦查找框 =====
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true, bubbles: true, cancelable: true }))`);
check("收起态 Ctrl+F → 展开 + search 活动 + 查找框聚焦", await waitFor(`
  (() => {
    const layout = document.querySelector('.code-layout');
    const fi = document.getElementById('code-find-input');
    return layout && !layout.classList.contains('side-collapsed')
      && document.querySelector('.code-side-tabs [data-code-side="search"]')?.classList.contains('on')
      && document.activeElement === fi
      && localStorage.getItem('firstep.codeSideCollapsed') === '0';
  })()`));

// ===== 展开态点非活动页签（大纲）→ 仅切换不收起 =====
await click('.code-side-tabs [data-code-side="outline"]');
check("展开态点「大纲」（非活动）→ 仅切换不收起", await waitFor(`
  (() => {
    const layout = document.querySelector('.code-layout');
    const outline = document.querySelector('[data-code-side-panel="outline"]');
    return layout && !layout.classList.contains('side-collapsed')
      && !outline.classList.contains('hidden')
      && getComputedStyle(outline).display !== 'none';
  })()`));

// ===== 收尾：收起态下编辑器仍可打开文件编辑（不影响视野的代价检查） =====
await click('.code-side-tabs [data-code-side="outline"]'); // 活动页签收起? 此刻活动=outline 已切换 → 收起
await waitFor(`document.querySelector('.code-layout')?.classList.contains('side-collapsed')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
check("收起态下仍可打开 main.c 编辑", await waitFor(`
  !!document.querySelector('#code-viewer .code-ta')`));
await click('.code-side-rail-btn[data-code-side="outline"]'); // 展开收尾，避免污染后续冒烟
check("收尾：恢复展开态（键 = 0）", await waitFor(`
  !document.querySelector('.code-layout')?.classList.contains('side-collapsed')
    && localStorage.getItem('firstep.codeSideCollapsed') === '0'`));

// ===== 07b：显式「收起」按钮（tab 条右端常驻入口，不再依赖隐藏捷径） =====
check("「收起」按钮常驻 tab 条右端", await Eval(`
  (() => {
    const b = document.querySelector('.code-side-tabs .code-side-collapse');
    return !!b && b.textContent.includes('收起')
      && getComputedStyle(b).display !== 'none';
  })()`));
await click('.code-side-tabs .code-side-collapse');
check("点「收起」按钮 → 收起（键 = 1）", await waitFor(`
  document.querySelector('.code-layout')?.classList.contains('side-collapsed')
    && localStorage.getItem('firstep.codeSideCollapsed') === '1'`));
check("收起态 rail 按钮带 title 提示（展开大纲/展开搜索）", await Eval(`
  (() => {
    const o = document.querySelector('.code-side-rail-btn[data-code-side="outline"]');
    const s = document.querySelector('.code-side-rail-btn[data-code-side="search"]');
    return !!o && o.title.includes('展开大纲') && !!s && s.title.includes('展开搜索');
  })()`));
await click('.code-side-rail-btn[data-code-side="outline"]');
check("最终收尾：展开态 + 键 = 0", await waitFor(`
  !document.querySelector('.code-layout')?.classList.contains('side-collapsed')
    && localStorage.getItem('firstep.codeSideCollapsed') === '0'`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
