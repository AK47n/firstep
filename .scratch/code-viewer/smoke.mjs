// 冒烟（code-viewer 系列）：代码查看器全链路——「代码」tab 打开样本目录 →
// 声音文件树（噪音目录不出现）→ 点文件加载只读视图（行号 + 高亮）→ 大纲
// 跳行 → 跨文件搜索命中跳转 → 当前文件 Ctrl+F → 最近记录卡「查看代码」按钮
// 存在（最近芯片纯件）。零写库（样本工程在 .scratch 下，git 忽略；不真生成）。
// 零依赖：node 内置 fetch + WebSocket 直连 Chrome CDP（9251，需 Node ≥ 21）；
// webapp 8000 提供真实 API。注：openCodeViewer 是 ui 模块导出（无 window 桥），
// 经动态 import 驱动；断言全部用 DOM 可观察事实。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

// ---- 样本工程（.scratch/code-viewer/sample-proj，git 忽略） ----
const SAMPLE = join(ROOT, ".scratch", "code-viewer", "sample-proj");
mkdirSync(join(SAMPLE, "src"), { recursive: true });
mkdirSync(join(SAMPLE, "Debug"), { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), [
  '#include "app.h"',
  "#define LED_GPIO 2",
  "",
  "void helper(void) {",
  "    int x = 0;",
  "}",
  "",
  "int main(void) {",
  "    helper();",
  "    return 0;",
  "}",
  "",
  "// STDIO 注释",
  "",
].join("\n"));
writeFileSync(join(SAMPLE, "src", "digit.c"),
  "void digit_init(void) {\n    // 数码管\n}\n");
writeFileSync(join(SAMPLE, "app.h"), "#pragma once\n// 主函数入口\n");
writeFileSync(join(SAMPLE, "readme.md"), "# 样本工程\n");
writeFileSync(join(SAMPLE, "Debug", "main.obj"), Buffer.from([0, 1, 2, 3]));

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

await Eval(`window.__smokeMarker = 1`);
// 树宽持久化（工单 code-viewer-tree-resize/01）：清键保证「初始 240px」确定性
await Eval(`try { localStorage.removeItem('firstep.codeTreeWidth'); } catch {}`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-code')
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

// ================= 工单 04：tab 骨架 + 选择文件夹按钮 =================
check("「代码」tab 按钮 + section 就位", await Eval(`
  !!document.querySelector('nav button[data-tab="code"]')
  && !!document.getElementById('tab-code')
  && !!document.getElementById('btn-code-pick-dir')`));
check("三栏容器就位（树 / 视图 / 侧栏）", await Eval(`
  !!document.getElementById('code-tree')
  && !!document.getElementById('code-viewer')
  && !!document.getElementById('code-outline')
  && !!document.getElementById('code-search-input')`));

// ================= 打开样本目录（openCodeViewer 桥 = 最近卡同路径） =================
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
check("目录打开：树加载（4 文件）+ 噪声目录不出现", await waitFor(`
  (() => {
    const btns = document.querySelectorAll('#code-tree [data-code-file]');
    const paths = [...btns].map((b) => b.dataset.codeFile).sort();
    return paths.length === 4
      && JSON.stringify(paths) === JSON.stringify(['app.h', 'main.c', 'readme.md', 'src/digit.c'])
      && !paths.some((p) => p.startsWith('Debug'));
  })()`));
check("树节点类型图标（文件 + 文件夹，树打磨 01）", await Eval(`
  (() => {
    const icons = document.querySelectorAll('#code-tree .code-tree-icon svg');
    return icons.length >= 5
      && !!document.querySelector('#code-tree .code-tree-dir summary .code-tree-icon svg')
      && document.querySelectorAll('#code-tree .code-tree-file .code-tree-icon svg').length >= 3;
  })()`));
check("目录路径显示在顶栏", await Eval(`
  (document.getElementById('code-dir-label').textContent || '').includes('sample-proj')`));

// ================= 工单 code-viewer-tree-resize/01：树面板拖拽调宽 =================
// 事件走合成 dispatch（与既有冒烟 el.click() / KeyboardEvent 同一风格——
// CDP Input.dispatchMouseEvent 在 reload 后 press 偶发被丢弃，不可靠）；
// 断言全部 DOM 可观察事实。
check("手柄就位（role=separator / aria-orientation=vertical / tabindex=0）", await Eval(`
  (() => {
    const h = document.getElementById('code-tree-resize');
    return !!h && h.getAttribute('role') === 'separator'
      && h.getAttribute('aria-orientation') === 'vertical'
      && h.getAttribute('tabindex') === '0';
  })()`));
check("初始树宽 240px（--code-tree-w 默认 + 存储已清）", await Eval(`
  document.querySelector('.code-layout').style.getPropertyValue('--code-tree-w') === '240px'`));
// 拖拽：pointerdown → pointermove(+120) → pointerup 合成序列
await Eval(`(() => {
  const h = document.getElementById('code-tree-resize');
  const r = h.getBoundingClientRect();
  const x = Math.round(r.x + r.width / 2), y = Math.round(r.y + r.height / 2);
  h.dispatchEvent(new PointerEvent('pointerdown', { pointerId: 1, clientX: x, clientY: y, bubbles: true, cancelable: true }));
  h.dispatchEvent(new PointerEvent('pointermove', { pointerId: 1, clientX: x + 120, clientY: y, bubbles: true, cancelable: true }));
  h.dispatchEvent(new PointerEvent('pointerup', { pointerId: 1, clientX: x + 120, clientY: y, bubbles: true, cancelable: true }));
  return true;
})()`);
check("拖拽 +120px → 树宽变化（≠240）+ localStorage 落盘同值", await waitFor(`
  (() => {
    const layout = document.querySelector('.code-layout');
    const w = layout.style.getPropertyValue('--code-tree-w');
    const stored = (() => { try { return localStorage.getItem('firstep.codeTreeWidth'); } catch { return null; } })();
    return /^\\d+px$/.test(w) && parseInt(w, 10) !== 240 && stored === String(parseInt(w, 10));
  })()`));
// 双击复位
await Eval(`document.getElementById('code-tree-resize')
  .dispatchEvent(new MouseEvent('dblclick', { bubbles: true }))`);
check("双击手柄 → 复位 240 并落盘", await waitFor(`
  (() => {
    const layout = document.querySelector('.code-layout');
    const stored = (() => { try { return localStorage.getItem('firstep.codeTreeWidth'); } catch { return null; } })();
    return layout.style.getPropertyValue('--code-tree-w') === '240px' && stored === '240';
  })()`));
// 键盘微调：聚焦手柄 → ArrowRight 16px 步进（240→256）
await Eval(`(() => {
  const h = document.getElementById('code-tree-resize');
  h.focus();
  h.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true, cancelable: true }));
  return true;
})()`);
check("键盘 ArrowRight → 256px 并落盘", await waitFor(`
  (() => {
    const layout = document.querySelector('.code-layout');
    const stored = (() => { try { return localStorage.getItem('firstep.codeTreeWidth'); } catch { return null; } })();
    return layout.style.getPropertyValue('--code-tree-w') === '256px' && stored === '256';
  })()`));
// 收尾复位 240（下一轮冒烟从确定性状态开始；截图默认宽度）
await Eval(`document.getElementById('code-tree-resize')
  .dispatchEvent(new MouseEvent('dblclick', { bubbles: true }))`);
check("收尾复位 240px（供截图/下轮冒烟确定性）", await waitFor(`
  document.querySelector('.code-layout').style.getPropertyValue('--code-tree-w') === '240px'`));

// ================= 点文件加载只读视图 =================
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
check("main.c 加载：行号 gutter + pre + C 高亮", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return !!box.querySelector('.code-gutter') && !!box.querySelector('.code-pre')
      && box.querySelectorAll('.code-gutter-line').length === 14
      && box.querySelectorAll('.code-pre [class*="tok-"]').length > 0;
  })()`));
check("内容行逐行元素就位（14 行，行高非 0，与 gutter 对齐）", await Eval(`
  (() => {
    const box = document.getElementById('code-viewer');
    const pre = [...box.querySelectorAll('.code-pre-line')];
    return pre.length === 14 && pre.every((el) => el.offsetHeight > 0)
      && pre.every((el, i) => el.dataset.codeLine === String(i + 1));
  })()`));
check("点选文件行高亮（.on）", await Eval(`
  document.querySelector('#code-tree [data-code-file="main.c"]').classList.contains('on')`));
check("顶栏文件标签（C main.c 观感，树打磨 01）", await Eval(`
  (() => {
    const tab = document.querySelector('#code-current-path .code-file-tab');
    return !!tab
      && tab.querySelector('.code-file-tab-badge').textContent === 'C'
      && tab.querySelector('.code-file-tab-name').textContent === 'main.c';
  })()`));
check("点击第 3 行 → 当前行高亮（内容 + 行号同索引，树打磨 02）", await Eval(`
  (() => {
    const pre = document.querySelectorAll('#code-viewer .code-pre-line')[2];
    if (!pre) return false;
    pre.click();
    const act = document.querySelector('#code-viewer .code-pre-line.active');
    const gut = document.querySelector('#code-viewer .code-gutter-line.active');
    return !!act && act.dataset.codeLine === '3' && !!gut && gut.textContent === '3';
  })()`));

// ================= 工单 03/05：大纲 =================
check("大纲条目就位（include / define / function 三类，按行序）", await waitFor(`
  (() => {
    const items = [...document.querySelectorAll('#code-outline [data-outline-line]')];
    return items.length === 4 && items[0].dataset.outlineLine === '1'
      && items[0].dataset.outlineKind === 'include'
      && items[1].dataset.outlineKind === 'define'
      && items[2].dataset.outlineKind === 'function';
  })()`));
await Eval(`document.querySelector('#code-outline [data-outline-line="8"]')?.click()`);
check("大纲点击 → 跳行（flash + 当前行移到目标行，树打磨 02）", await waitFor(`
  (() => {
    const view = document.getElementById('code-viewer');
    const flash = !!view.querySelector('.code-gutter-line.flash')
      && !!view.querySelector('.code-pre-line.flash');
    const moved = !!view.querySelector('.code-pre-line.active[data-code-line="8"]')
      && !!view.querySelector('.code-gutter-line.active[data-code-line="8"]');
    return (flash || view.scrollTop > 0) && !!moved;
  })()`));

// ================= 工单 02/05：跨文件搜索 =================
await Eval(`(() => {
  document.querySelector('[data-code-side="search"]')?.click();
  document.getElementById('code-search-input').value = 'helper';
  document.getElementById('btn-code-search').click();
})()`);
check("搜索命中列表（main.c:4 定义 + main.c:9 调用）", await waitFor(`
  (() => {
    const hits = [...document.querySelectorAll('#code-search-results [data-search-path="main.c"]')];
    return hits.length === 2 && hits.some((h) => h.dataset.searchLine === '4');
  })()`));
await Eval(`document.querySelector('#code-search-results [data-search-line="9"]')?.click()`);
check("搜索结果点击 → 跳文件 + 跳行（标签更新 + jump）", await waitFor(`
  (() => {
    const name = document.querySelector('#code-current-path .code-file-tab-name');
    return !!name && name.textContent === 'main.c'
      && !!document.getElementById('code-viewer').querySelector('.code-gutter-line.flash');
  })()`));

// ================= 当前文件 Ctrl+F =================
await Eval(`(() => {  // 先切回「大纲」侧栏，证明 Ctrl+F 自己会切到「搜索」栏
  document.querySelector('[data-code-side="outline"]')?.click();
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }));
})()`);
check("Ctrl+F 截获 → 切「搜索」侧栏（可见）→ 查找输入聚焦", await waitFor(`
  (() => {
    const panel = document.querySelector('[data-code-side-panel="search"]');
    return panel && !panel.classList.contains('hidden')
      && document.activeElement === document.getElementById('code-find-input');
  })()`));
await Eval(`(() => {
  const inp = document.getElementById('code-find-input');
  inp.value = 'STDIO';
  inp.dispatchEvent(new Event('input'));
})()`);
check("文件内过滤命中（main.c:13 注释行）", await waitFor(`
  (() => {
    const items = [...document.querySelectorAll('#code-find-results [data-find-line]')];
    return items.some((b) => b.dataset.findLine === '13');
  })()`));

// ================= 工单 code-viewer-zoom/01：Ctrl+滚轮缩放 =================
// 合成 WheelEvent（ctrlKey + deltaY）驱动——与既有冒烟同风格（不依赖 CDP
// Input 真实输入，reload 后 press 丢失不可靠）；断言 DOM 可观察事实
// （--code-zoom 变量 / gutter 与 pre 计算字号同步 / badge / localStorage）。
await Eval(`(() => {
  try { localStorage.removeItem('firstep.codeViewZoom'); } catch {}
  document.getElementById('code-viewer').dispatchEvent(
    new WheelEvent('wheel', { ctrlKey: true, deltaY: -100, bubbles: true, cancelable: true }));
  return true;
})()`);
check("Ctrl+滚轮上滚：preventDefault + 放大到 110%（gutter/pre 字号同步）", await waitFor(`
  (() => {
    const view = document.getElementById('code-viewer');
    if (view.style.getPropertyValue('--code-zoom') !== '1.1') return false;
    const g = parseFloat(getComputedStyle(view.querySelector('.code-gutter-line')).fontSize);
    const p = parseFloat(getComputedStyle(view.querySelector('.code-pre')).fontSize);
    return g > 13 && p > 13 && Math.abs(g - p) < 0.01;
  })()`));
check("缩放浮标显示 110%（.code-zoom-badge.show，挂主面板）", await Eval(`
  (() => {
    const b = document.querySelector('.code-pane-main > .code-zoom-badge');
    return !!b && b.classList.contains('show') && b.textContent === '110%';
  })()`));
check("持久化 firstep.codeViewZoom=110", await Eval(`
  (() => { try { return localStorage.getItem('firstep.codeViewZoom') === '110'; } catch { return false; } })()`));
check("Ctrl+滚轮 dispatchEvent 返回 false（preventDefault 已调用）", await Eval(`
  document.getElementById('code-viewer').dispatchEvent(
    new WheelEvent('wheel', { ctrlKey: true, deltaY: -100, bubbles: true, cancelable: true })) === false`));
// 连续下滚 15 档 → clamp 到下限 80%（badge 同步 80%）
await Eval(`(() => {
  const view = document.getElementById('code-viewer');
  for (let i = 0; i < 15; i++) {
    view.dispatchEvent(new WheelEvent('wheel', { ctrlKey: true, deltaY: 100, bubbles: true, cancelable: true }));
  }
  return true;
})()`);
check("连续下滚 15 档 → clamp 80%（变量 0.8 + 存储 80 + badge 80%）", await waitFor(`
  (() => {
    const view = document.getElementById('code-viewer');
    const stored = (() => { try { return localStorage.getItem('firstep.codeViewZoom'); } catch { return null; } })();
    const b = document.querySelector('.code-pane-main > .code-zoom-badge');
    return view.style.getPropertyValue('--code-zoom') === '0.8' && stored === '80' && !!b && b.textContent === '80%';
  })()`));
// reload 恢复：清 marker → 刷新 → 等新页 → 断言容器变量 + 存储同值
await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
{
  let zready = false;
  for (let i = 0; i < 100 && !zready; i++) {
    try {
      zready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
        && !!document.getElementById('code-viewer')`);
    } catch {}
    if (!zready) await new Promise((r) => setTimeout(r, 300));
  }
  if (!zready) { console.error("缩放 reload 后页面未就绪"); process.exit(1); }
}
check("reload 恢复 80%（容器 --code-zoom + 存储同值，静默不弹浮标）", await Eval(`
  (() => {
    const view = document.getElementById('code-viewer');
    const stored = (() => { try { return localStorage.getItem('firstep.codeViewZoom'); } catch { return null; } })();
    return view.style.getPropertyValue('--code-zoom') === '0.8' && stored === '80'
      && !document.querySelector('.code-zoom-badge.show');
  })()`));
// 收尾放大回 100%（下一轮冒烟/截图从确定性状态开始）
await Eval(`(() => {
  const view = document.getElementById('code-viewer');
  view.dispatchEvent(new WheelEvent('wheel', { ctrlKey: true, deltaY: -100, bubbles: true, cancelable: true }));
  view.dispatchEvent(new WheelEvent('wheel', { ctrlKey: true, deltaY: -100, bubbles: true, cancelable: true }));
  return true;
})()`);
check("收尾放大回 100%（--code-zoom=1 + 存储 100）", await waitFor(`
  (() => {
    const view = document.getElementById('code-viewer');
    const stored = (() => { try { return localStorage.getItem('firstep.codeViewZoom'); } catch { return null; } })();
    return view.style.getPropertyValue('--code-zoom') === '1' && stored === '100';
  })()`));

// ================= 工单 06：最近记录卡「查看代码」按钮 =================
check("recentChipHTML 含「查看代码」按钮（data-code-dir + 不破坏删除钮）", await Eval(`
  (() => {
    const chip = window.recentChipHTML({
      id: 'id1', ts: '1', status: 'compiled_ok', output_dir: 'C:/proj/x', platform: 'mspm0', slugs: ['dht11'],
    });
    return chip.includes('recent-code-open') && chip.includes('data-code-dir="C:/proj/x"')
      && chip.includes('recent-del');
  })()`));

// 截图存档（三栏 + 树 + 高亮态）
const shot = await cdp("Page.captureScreenshot", { format: "png" });
mkdirSync(join(ROOT, ".scratch", "code-viewer"), { recursive: true });
writeFileSync(join(ROOT, ".scratch", "code-viewer", "shot-06-code-view.png"), Buffer.from(shot.result.data, "base64"));
console.log("shot-06-code-view.png 已存档");

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
