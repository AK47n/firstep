// 冒烟（master-library-ui-2 系列）：母版库增强 UI——健康徽章 / 体积统计 /
// 文件树与树文件预览 / 高亮与复制钮 / 直接导入按钮 / 共享确认弹窗开合
// （经赛题库删除按钮实测工厂接线，取消不真删）。零真删零真导；工单 01-05
// 端点在 pytest 与 tests/js 覆盖。零依赖：node 内置 fetch + WebSocket 直连
// Chrome CDP（9251，需 Node ≥ 21）；webapp 8000 提供真实 /api/masters。
// 注：模块化后 state/masterCache 均为模块作用域（无 window 桥），就绪与
// 断言全部用 DOM 可观察事实。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

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
      && !!document.getElementById('tab-master')
      && !!document.getElementById('master-rows')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// ---- 切「母版」tab ----
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button')]
    .find((b) => b.dataset.tab === 'master');
  if (tab) tab.click();
  return !!tab;
})()`);
await waitFor(`document.querySelectorAll('#master-rows tr').length >= 1`);
const rowCount = await Eval(`document.querySelectorAll('#master-rows tr').length`);
check("母版列表已加载（真实库）", rowCount > 0, "rows=" + rowCount);

// ================= 工单 01：健康徽章 + 体积统计 =================
check("每行健康徽章（✓/⚠ pill，数量 = 行数）", await Eval(`
  document.querySelectorAll('#master-rows .master-health-pill').length
    === document.querySelectorAll('#master-rows tr').length`));
check("真实库双平台健康（均 ✓ 健康）", await Eval(`
  [...document.querySelectorAll('#master-rows .master-health-pill')]
    .every((p) => p.classList.contains('master-health-ok'))`));
check("表格表头含「健康」列", await Eval(`
  [...document.querySelectorAll('#master-rows')][0]
    && [...document.querySelectorAll('table th')].some((th) => th.textContent.trim() === '健康')`));

await Eval(`document.querySelector('#master-rows [data-master-detail="stm32"]')?.click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay')`);
check("详情弹窗：体积统计行（总体积/文件数）", await Eval(`
  (() => {
    const t = document.querySelector('.ref-detail-meta')?.textContent || '';
    return t.includes('总体积') && t.includes('文件数');
  })()`));

// ================= 工单 02：文件树 + 树文件预览 =================
check("全部文件树渲染（ul.master-tree + details 目录可收）", await waitFor(`
  (() => {
    const box = document.querySelector('.ref-files-overlay [data-master-tree]');
    return !!box && !!box.querySelector('ul.master-tree')
      && box.querySelectorAll('.master-tree details').length > 0;
  })()`));
check("树含非关键文件（ml_libs/ 开头条目）", await Eval(`
  [...document.querySelectorAll('.ref-files-overlay [data-master-tree-file]')]
    .some((b) => b.dataset.masterTreeFile.startsWith('ml_libs/'))`));
await Eval(`[...document.querySelectorAll('.ref-files-overlay [data-master-tree-file]')]
  .find((b) => b.dataset.masterTreeFile.startsWith('ml_libs/'))?.click()`);
check("树文件加载成功（内容 pre + #include 子串）", await waitFor(`
  (() => {
    const el = document.querySelector('.ref-files-overlay [data-master-content]');
    return !!el && !!el.querySelector('.master-file-pre') && (el.textContent || '').includes('#include');
  })()`));
check("树文件点选行高亮（.on）", await Eval(`
  !![...document.querySelectorAll('.ref-files-overlay [data-master-tree-file]')].find((b) =>
    b.classList.contains('on'))`));

// ================= 工单 03：高亮 + 复制按钮 =================
check("内容高亮 span（tok-* 类 > 0，C 高亮）", await Eval(`
  document.querySelectorAll('.ref-files-overlay [data-master-content] [class*="tok-"]').length > 0`));
check("复制按钮存在（data-master-copy）", await Eval(`
  !!document.querySelector('.ref-files-overlay [data-master-copy]')`));

// 关键文件（mspm0.syscfg）内容仍安全
await Eval(`document.querySelector('.ref-files-overlay .ref-files-close')?.click()`);
await waitFor(`!document.querySelector('.ref-files-overlay')`);
await Eval(`document.querySelector('#master-rows [data-master-detail="mspm0"]')?.click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay')`);
await Eval(`document.querySelector('.ref-files-overlay [data-master-file="mspm0.syscfg"]')?.click()`);
check("mspm0.syscfg 内容成功（addInstance 子串）", await waitFor(`
  (() => {
    const el = document.querySelector('.ref-files-overlay [data-master-content]');
    return !!el && !!el.querySelector('.master-file-pre') && (el.textContent || '').includes('addInstance');
  })()`));
await Eval(`document.querySelector('.ref-files-overlay .ref-files-close')?.click()`);
await waitFor(`!document.querySelector('.ref-files-overlay')`);

// ================= 工单 04：直接导入按钮就位（不真选不真导） =================
check("「直接导入替换」按钮与隐藏目录选择输入存在", await Eval(`
  !!document.getElementById('btn-direct-import')
  && !!document.getElementById('import-pick-dirs')`));

// ================= 工单 05：共享确认弹窗开合（经赛题库删除入口，取消不真删） =================
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button')]
    .find((b) => b.dataset.tab === 'topic');
  if (tab) tab.click();
  return !!tab;
})()`);
check("赛题库列表已加载（真实库，删除钮存在）", await waitFor(`
  document.querySelectorAll('[data-topic-del]').length > 0`));
await Eval(`document.querySelector('[data-topic-del]')?.click()`);
check("共享确认弹窗打开（confirm-modal + 双钮 + 删除文案）", await waitFor(`
  (() => {
    const o = document.querySelector('.ref-files-overlay');
    return !!o && !!o.querySelector('.confirm-modal')
      && !!o.querySelector('[data-confirm-ok]')
      && !!o.querySelector('[data-confirm-cancel]')
      && (o.textContent || '').includes('删除赛题');
  })()`));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]')?.click()`);
await waitFor(`!document.querySelector('.ref-files-overlay')`);
check("取消 → 关闭 + 删除钮仍在（零写库）", await Eval(`
  !document.querySelector('.ref-files-overlay')
  && document.querySelectorAll('[data-topic-del]').length > 0`));
await Eval(`document.querySelector('[data-topic-del]')?.click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay')`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))`);
await waitFor(`!document.querySelector('.ref-files-overlay')`);
check("Esc → 关闭", await Eval(`!document.querySelector('.ref-files-overlay')`));

// 截图存档（母版详情 + 树 + 高亮态）
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button')]
    .find((b) => b.dataset.tab === 'master');
  if (tab) tab.click();
})()`);
await waitFor(`!!document.querySelector('#master-rows [data-master-detail="stm32"]')`);
await Eval(`document.querySelector('#master-rows [data-master-detail="stm32"]')?.click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay')`);
await waitFor(`!!document.querySelector('.ref-files-overlay ul.master-tree')`);
const shot = await cdp("Page.captureScreenshot", { format: "png" });
mkdirSync(join(ROOT, ".scratch", "master-library-ui-2"), { recursive: true });
writeFileSync(join(ROOT, ".scratch", "master-library-ui-2", "shot-06-detail-tree.png"), Buffer.from(shot.result.data, "base64"));
console.log("shot-06-detail-tree.png 已存档");

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
