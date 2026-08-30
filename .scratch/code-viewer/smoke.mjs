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
check("目录打开：树加载 + 文件行按钮 + 噪声目录不出现", await waitFor(`
  (() => {
    const btns = document.querySelectorAll('#code-tree [data-code-file]');
    const paths = [...btns].map((b) => b.dataset.codeFile);
    return btns.length === 5 && !paths.some((p) => p.startsWith('Debug') || p.includes('.obj'));
  })()`));
check("目录路径显示在顶栏", await Eval(`
  (document.getElementById('code-dir-label').textContent || '').includes('sample-proj')`));

// ================= 点文件加载只读视图 =================
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
check("main.c 加载：行号 gutter + pre + C 高亮", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return !!box.querySelector('.code-gutter') && !!box.querySelector('.code-pre')
      && box.querySelectorAll('.code-gutter-line').length === 14
      && box.querySelectorAll('.code-pre [class*="tok-"]').length > 0;
  })()`));
check("点选文件行高亮（.on）", await Eval(`
  document.querySelector('#code-tree [data-code-file="main.c"]').classList.contains('on')`));
check("当前文件路径显示", await Eval(`
  document.getElementById('code-current-path').textContent === 'main.c'`));

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
check("大纲点击 → 跳行（gutter flash + 滚动）", await waitFor(`
  (() => {
    const view = document.getElementById('code-viewer');
    const flash = !!view.querySelector('.code-gutter-line.flash');
    return flash || view.scrollTop > 0;
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
check("搜索结果点击 → 跳文件 + 跳行（当前路径更新 + jump）", await waitFor(`
  (() => {
    const path = document.getElementById('code-current-path').textContent;
    return path === 'main.c' && !!document.getElementById('code-viewer').querySelector('.code-gutter-line.flash');
  })()`));

// ================= 当前文件 Ctrl+F =================
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }))`);
check("Ctrl+F 截获 → 文件内查找输入聚焦", await waitFor(`
  document.activeElement === document.getElementById('code-find-input')`));
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
