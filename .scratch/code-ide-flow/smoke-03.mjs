// 冒烟（工单 code-ide-flow/03）：「磁盘变更」面板——真实 API + 真实磁盘样本
// （.scratch/code-ide-flow/sample-proj 复用重建，跑后清理）：外部/AI 写盘 →
// 切回代码 tab → 面板出现（改/增/消失三态条目 + 计数摘要）→ main.c 行级
// diff 区（基线快照 vs 当前，stats 可见）→ 点击条目跳转打开 → 「清空并确认
// 已看」→ 面板隐藏 + 树徽章清空。零依赖：fetch + WebSocket CDP 9231；
// webapp 8000。
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-ide-flow", "sample-proj");

const OLD_MAIN = "int main(void) {\n  // TODO: init sensor\n  init();\n  return 0;\n}\n";
const NEW_MAIN = "int main(void) {\n  sensor_init();\n  init();\n  return 0;\n}\n";

const resetSample = () => {
  rmSync(SAMPLE, { recursive: true, force: true });
  mkdirSync(join(SAMPLE, "src"), { recursive: true });
  writeFileSync(join(SAMPLE, "main.c"), OLD_MAIN, "utf8");
  writeFileSync(join(SAMPLE, "readme.md"), "# 样本\n", "utf8");
  writeFileSync(join(SAMPLE, "src", "app.h"), "#pragma once\n", "utf8");
};

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.includes("127.0.0.1:8000"))
  || targets.find((t) => t.type === "page");
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
await cdp("Network.enable");
await cdp("Network.setCacheDisabled", { cacheDisabled: true });
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

resetSample();
let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? "  [" + extra + "]" : ""));
  if (!ok) failed++;
};

await cdp("Page.navigate", { url: pageUrl });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try { ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('tab-code')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
await Eval(`localStorage.clear()`);
await cdp("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 1200));

// 打开样本目录（首次 = 建基线 + main.c 内容快照）
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
check("打开样本目录：树含 main.c / readme.md / src/app.h", await waitFor(`
  document.querySelectorAll('#code-tree [data-code-file]').length === 3`));
check("无外部变更：磁盘变更面板隐藏", await Eval(`
  document.getElementById('code-change-panel').classList.contains('hidden')`));
// 等基线 main.c 快照落盘（openCodeViewer async 途中——probe 已 await commit）
await new Promise((r) => setTimeout(r, 800));

// 打开 main.c 标签（干净）
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]').click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

// 外部写盘：改 main.c + 新增 oled.c + 删除 readme.md
writeFileSync(join(SAMPLE, "main.c"), NEW_MAIN, "utf8");
writeFileSync(join(SAMPLE, "src", "oled.c"), "// oled\n", "utf8");
rmSync(join(SAMPLE, "readme.md"));

// 切回代码 tab（tab 钩子 → check）
await Eval(`document.querySelector('nav button[data-tab="generate"]').click()`);
await new Promise((r) => setTimeout(r, 300));
await Eval(`document.querySelector('nav button[data-tab="code"]').click()`);

check("面板出现：三类条目（改/增/消失）", await waitFor(`
  (() => {
    const items = [...document.querySelectorAll('#code-change-list .code-change-item')];
    const paths = items.map((b) => b.dataset.changePath).sort();
    return items.length === 3
      && paths.includes('main.c') && paths.includes('src/oled.c') && paths.includes('readme.md');
  })()`));
check("摘要：1 新增 · 1 修改 · 1 消失", await Eval(`
  document.getElementById('code-change-summary').textContent.includes('1 个新增')
  && document.getElementById('code-change-summary').textContent.includes('1 个修改')
  && document.getElementById('code-change-summary').textContent.includes('1 个消失')`));
check("消失条目置灰不可点（span disabled）", await Eval(`
  (() => {
    const el = document.querySelector('#code-change-list .code-change-item[data-change-path="readme.md"]');
    return !!el && el.tagName === 'SPAN' && el.classList.contains('disabled');
  })()`));
check("main.c 条目行级 diff 区（details + stats 行）", await Eval(`
  (() => {
    const d = document.querySelector('#code-change-list .code-change-diff');
    return !!d && !!d.querySelector('.diff-stats');
  })()`));
check("main.c diff hunk 标题为 TODO（填充 TODO「init sensor」）", await Eval(`
  (() => {
    const t = document.querySelector('#code-change-list .diff-hunk summary')?.textContent || '';
    return t.includes('填充 TODO「init sensor」');
  })()`));
check("点击新增条目 → 打开对应 tab", await waitFor(`
  (() => {
    const item = document.querySelector('#code-change-list button[data-change-path="src/oled.c"]');
    if (!item) return false;
    item.click();
    return true;
  })()`));
check("新增文件 tab 已打开（内容 = 磁盘）", await waitFor(`
  !!document.querySelector('#code-tabs .code-tab[data-tab-path="src/oled.c"]')
  && document.querySelector('#code-viewer .code-ta')?.value.includes('// oled')`));

// 试试 main.c diff 区的展开交互（details toggle 由原生处理——点击 summary）
await Eval(`document.querySelector('#code-change-list .code-change-diff summary')?.click()`);
check("diff 区可展开（details open）", await Eval(`
  document.querySelector('#code-change-list .code-change-diff')?.open === true`));

// 「清空并确认已看」
await Eval(`document.getElementById('btn-code-change-clear').click()`);
check("清空后：面板隐藏 + 摘要空", await waitFor(`
  document.getElementById('code-change-panel').classList.contains('hidden')`));
check("清空后：树「新/变」徽章消失", await Eval(`
  document.querySelectorAll('#code-tree .code-tree-badge').length === 0`));
check("清空后：toast 确认提示", await Eval(`
  [...document.querySelectorAll('#toast-root .toast-text')].some((t) => t.textContent.includes('已确认磁盘变更'))`));

// 再外部改一次 → 重新感知（清空只是确认点推进，感知链路仍在）
writeFileSync(join(SAMPLE, "main.c"), NEW_MAIN + "// again\n", "utf8");
await Eval(`import('/js/ui/codeview.js').then((m) => m.checkCodeDiskChanges().then(() => 'done'))`);
check("清空后外部再改：重新感知（面板再现 + main.c 变徽章）", await waitFor(`
  !document.getElementById('code-change-panel').classList.contains('hidden')
  && !!document.querySelector('#code-tree .code-tree-badge.b-mod')`));

rmSync(SAMPLE, { recursive: true, force: true });
console.log(failed === 0 ? "SMOKE-03 全 PASS" : `SMOKE-03 失败 ${failed} 项`);
process.exit(failed === 0 ? 0 : 1);
