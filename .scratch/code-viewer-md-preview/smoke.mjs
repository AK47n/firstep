// 冒烟（code-viewer-md-preview 系列）：代码查看器 .md 全链路——打开样本目录 →
// 点 readme.md 渲染预览（标题/表格/代码块/任务/引用/图片）+ 大纲标题滚动定位 →
// 跨文件搜索命中自动切临时源码 → Ctrl+F 切源码过滤 → 返回预览 / 点树回预览 →
// 非 .md（main.c）行为不变 → 预览 Ctrl+滚轮缩放联动。零依赖：node 内置 fetch +
// WebSocket 直连 Chrome CDP（9251，需 Node ≥ 21）；webapp 8000 提供真实 API。
// 断言全部用 DOM 可观察事实。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

// ---- 样本工程（.scratch/code-viewer-md-preview/sample-proj，git 忽略） ----
const SAMPLE = join(ROOT, ".scratch", "code-viewer-md-preview", "sample-proj");
mkdirSync(join(SAMPLE, "images"), { recursive: true });
mkdirSync(join(SAMPLE, "src"), { recursive: true });
mkdirSync(join(SAMPLE, "Debug"), { recursive: true });
writeFileSync(join(SAMPLE, "images", "pic.png"), Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64"));
writeFileSync(join(SAMPLE, "readme.md"), [
  "# 样本工程",
  "",
  "## 快速上手",
  "",
  "```c",
  "int main(void) { return 0; }",
  "```",
  "",
  "### 参数表",
  "",
  "| 参数 | 值 |",
  "| --- | --- |",
  "| THR | 130 |",
  "",
  "> 引用一行",
  "",
  "- 列表项",
  "- [ ] 待办",
  "- [x] 完成",
  "",
  "![图](images/pic.png) ![坏](../esc.png) ![绝](/abs.png) ![毒](javascript:bad)",
  "",
  "段落 **粗体** 与 [链接](https://example.com) 与 `行内码` 与 ~~删除~~。",
  "",
].join("\n"));
writeFileSync(join(SAMPLE, "main.c"),
  "#include <stdio.h>\n\nint main(void) {\n    return 0;\n}\n");
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
if (!page) { console.error("8000 页面不存在（先打开 http://127.0.0.1:8000/）"); process.exit(1); }
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
await Eval(`(() => {
  try { localStorage.removeItem('firstep.codeTreeWidth'); } catch {}
  try { localStorage.removeItem('firstep.codeViewZoom'); } catch {}
  return true;
})()`);
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

// ================= 打开样本目录 + 点 readme.md =================
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
check("目录打开：树含 readme.md / main.c / images（噪音 Debug 不出现）", await waitFor(`
  (() => {
    const paths = [...document.querySelectorAll('#code-tree [data-code-file]')]
      .map((b) => b.dataset.codeFile).sort();
    return paths.includes('readme.md') && paths.includes('main.c')
      && paths.includes('images/pic.png') && !paths.some((p) => p.startsWith('Debug'));
  })()`));
await Eval(`document.querySelector('#code-tree [data-code-file="readme.md"]')?.click()`);
check("readme.md 打开 → .code-md-preview 渲染（无行号 gutter）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return !!box.querySelector('.code-md-preview')
      && box.querySelector('.code-md-preview h1').textContent === '样本工程'
      && !box.querySelector('.code-gutter');
  })()`));
check("预览排版：表格/thead/代码块(高亮)/任务勾选/引用/粗体/链接/行内码/删除线", await Eval(`
  (() => {
    const p = document.querySelector('.code-md-preview');
    return !!p.querySelector('table thead th')
      && p.querySelector('tbody td').textContent === 'THR'
      && !!p.querySelector('pre code .tok-kw')
      && !!p.querySelector('li.md-task input[type="checkbox"][checked]')
      && !!p.querySelector('blockquote')
      && p.innerHTML.includes('<strong>粗体</strong>')
      && !!p.querySelector('a[href="https://example.com"]')
      && !!p.querySelector('code')
      && p.innerHTML.includes('<del>删除</del>');
  })()`));
check("本地图片 → /api/code/raw 相对路径归一（md 同根 images/）", await waitFor(`
  (() => {
    const img = document.querySelector('.code-md-preview img[src*="path=images%2Fpic.png"]');
    return !!img && img.complete && img.naturalWidth > 0;
  })()`));
check("坏引用（../、绝对、javascript:）→ 占位不请求（3 个 fallback）", await Eval(`
  (() => {
    const html = document.querySelector('.code-md-preview').innerHTML;
    return (html.match(/md-img-fallback/g) || []).length === 3
      && !html.includes('src="../') && !html.includes('src="/abs')
      && !html.includes('javascript:');
  })()`));
check("顶栏标签徽标 MD + 「返回预览」隐藏（预览态）", await Eval(`
  (() => {
    const tab = document.querySelector('#code-current-path .code-file-tab');
    const back = document.getElementById('code-back-preview');
    return !!tab && tab.querySelector('.code-file-tab-badge').textContent === 'MD'
      && back.classList.contains('hidden');
  })()`));

// ================= 大纲标题 + 预览内滚动定位 =================
check(".md 大纲 = 标题清单（H 徽标，按行序 1/3/9）", await waitFor(`
  (() => {
    const items = [...document.querySelectorAll('#code-outline [data-outline-line]')];
    return items.length === 3
      && items.every((b) => b.dataset.outlineKind === 'heading')
      && items.map((b) => b.dataset.outlineLine).join(',') === '1,3,9'
      && items.every((b) => b.querySelector('.code-outline-kind').textContent === 'H');
  })()`));
await Eval(`document.querySelector('#code-outline [data-outline-line="9"]')?.click()`);
check("大纲点击 → 预览内 [data-md-line=9] 滚动 + flash", await waitFor(`
  (() => {
    const h = document.querySelector('.code-md-preview [data-md-line="9"]');
    return !!h && (h.classList.contains('flash') || h.getBoundingClientRect().top < 200);
  })()`));

// ================= 跨文件搜索 → 临时源码 =================
await Eval(`(() => {
  document.querySelector('[data-code-side="search"]')?.click();
  document.getElementById('code-search-input').value = 'THR';
  document.getElementById('btn-code-search').click();
})()`);
check("搜索命中 readme.md:13（THR）", await waitFor(`
  (() => {
    const hits = [...document.querySelectorAll('#code-search-results [data-search-path="readme.md"]')];
    return hits.length === 1 && hits[0].dataset.searchLine === '13';
  })()`));
await Eval(`document.querySelector('#code-search-results [data-search-line="13"]')?.click()`);
check("命中 .md → 临时源码视图（gutter 行号 + flash 定行）+ 返回预览可见", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    const back = document.getElementById('code-back-preview');
    return !!box.querySelector('.code-gutter')
      && box.querySelectorAll('.code-pre-line').length >= 13
      && !!box.querySelector('.code-gutter-line.flash')
      && !back.classList.contains('hidden');
  })()`));

// ================= Ctrl+F → 切源码过滤 =================
await Eval(`document.getElementById('code-back-preview')?.click()`);
check("返回预览按钮 → 回渲染预览（按钮隐藏）", await waitFor(`
  !!document.getElementById('code-viewer').querySelector('.code-md-preview')
    && document.getElementById('code-back-preview').classList.contains('hidden')`));
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }))`);
check("预览内 Ctrl+F → 自动切源码 + 聚焦查找输入（搜索栏可见）", await waitFor(`
  (() => {
    const panel = document.querySelector('[data-code-side-panel="search"]');
    return !!document.getElementById('code-viewer').querySelector('.code-gutter')
      && panel && !panel.classList.contains('hidden')
      && document.activeElement === document.getElementById('code-find-input');
  })()`));
await Eval(`(() => {
  const inp = document.getElementById('code-find-input');
  inp.value = '完成';
  inp.dispatchEvent(new Event('input'));
})()`);
check("源码态文件内过滤命中（readme.md 第 19 行）", await waitFor(`
  (() => {
    const items = [...document.querySelectorAll('#code-find-results [data-find-line]')];
    return items.some((b) => b.dataset.findLine === '19');
  })()`));

// ================= 点树内文件回预览 =================
await Eval(`document.querySelector('#code-tree [data-code-file="readme.md"]')?.click()`);
check("重新点树内文件 → 回预览（无 gutter + 按钮隐藏）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return !!box.querySelector('.code-md-preview') && !box.querySelector('.code-gutter')
      && document.getElementById('code-back-preview').classList.contains('hidden');
  })()`));

// ================= 非 .md 行为不变 =================
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
check("main.c：gutter + C 高亮 + 徽标 C（非 .md 零回归）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    const tab = document.querySelector('#code-current-path .code-file-tab');
    return !!box.querySelector('.code-gutter')
      && box.querySelectorAll('.code-pre [class*="tok-"]').length > 0
      && tab.querySelector('.code-file-tab-badge').textContent === 'C';
  })()`));

// ================= 预览 + Ctrl+滚轮缩放联动 =================
await Eval(`document.querySelector('#code-tree [data-code-file="readme.md"]')?.click()`);
await waitFor(`!!document.getElementById('code-viewer').querySelector('.code-md-preview')`);
await Eval(`document.getElementById('code-viewer').dispatchEvent(
  new WheelEvent('wheel', { ctrlKey: true, deltaY: -100, bubbles: true, cancelable: true }))`);
check("预览 Ctrl+滚轮上滚 → --code-zoom=1.1 且 .code-md-preview 字号联动 >15px", await waitFor(`
  (() => {
    const view = document.getElementById('code-viewer');
    if (view.style.getPropertyValue('--code-zoom') !== '1.1') return false;
    const size = parseFloat(getComputedStyle(document.querySelector('.code-md-preview')).fontSize);
    return size > 15;
  })()`));
await Eval(`document.getElementById('code-viewer').dispatchEvent(
  new WheelEvent('wheel', { ctrlKey: true, deltaY: 100, bubbles: true, cancelable: true }))`);
check("收尾缩回 100%（下滚一档 → --code-zoom=1）", await waitFor(`
  document.getElementById('code-viewer').style.getPropertyValue('--code-zoom') === '1'`));

// 截图存档
const shot = await cdp("Page.captureScreenshot", { format: "png" });
mkdirSync(join(ROOT, ".scratch", "code-viewer-md-preview"), { recursive: true });
writeFileSync(join(ROOT, ".scratch", "code-viewer-md-preview", "shot-md-preview.png"), Buffer.from(shot.result.data, "base64"));
console.log("shot-md-preview.png 已存档");

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
