// 冒烟（工单 code-ide-flow/04）：「一键修复直达」——IDE 编译失败按钮 →
// 跳生成页修复中心并自动开始修复循环。零依赖：fetch + WebSocket CDP 9231；
// webapp 8000。场景：S1 前置校验早退提示（无输出目录）→ S2 写盘守卫弹窗
// 与取消中止（伪造平台/工具链——测试环境无真实工具链）→ S3 自动开始进入
// 循环（fix-status「自动编译中…」+ AI 行动横幅）→ S4 感知集成回归（外部
// 写盘 → 磁盘变更面板出现）。
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
  try { ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('btn-code-compile-goto')`); } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }
await Eval(`localStorage.clear()`);
await cdp("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 1200));

// 打开样本目录 + 设为生成上下文（goto 可见性判据 = 目录 = 生成上下文）
await Eval(`import('/js/ui/generate-mainc-sync.js').then((m) => m.setMainCDiskContext(${JSON.stringify(SAMPLE)}))`);
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length === 3`);
await new Promise((r) => setTimeout(r, 800));

// ── S1：前置校验不满足（无输出目录）——跳转后自动调用 startFixCenter →
// 首个校验早退提示（验收 3：与手动入口同判据）
await Eval(`document.getElementById('btn-code-compile-goto').click()`);
check("S1 跳转：切到生成页 tab", await waitFor(`
  document.querySelector('nav button[data-tab="generate"]').classList.contains('active')`));
check("S1 自动开始：fix-errors-msg 出现前置校验提示", await waitFor(`
  (document.getElementById('fix-errors-msg').textContent || '').includes('请先生成工程')`,
  6000), await Eval(`document.getElementById('fix-errors-msg').textContent`));

// ── S2：写盘守卫（验收 2）——伪造平台/工具链 → 走到 guardCodeTabWrite
await Eval(`document.querySelector('nav button[data-tab="code"]').click()`);
await new Promise((r) => setTimeout(r, 300));
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]').click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
// 编辑框改内容（脏——不保存）
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '\\n// dirty edit\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await new Promise((r) => setTimeout(r, 300));
// 伪造：输出目录 + 平台 + 工具链可用 → startFixCenter 过校验 → 守卫（脏标签 → 弹窗）
await Eval(`(() => {
  document.getElementById('output-dir').value = ${JSON.stringify(SAMPLE)};
  return Promise.all([
    import('/js/ui/generate-recommend.js').then((m) => m.setChosenPlatform('stm32')),
    import('/js/ui/generate-fix.js').then((m) => m.setToolchains({ stm32: true, mspm0: true })),
  ]);
})()`);
await Eval(`document.getElementById('btn-code-compile-goto').click()`);
check("S2 守卫弹窗出现（保存全部并继续/取消）", await waitFor(`
  (() => {
    const o = document.querySelector('.ref-files-overlay');
    return !!o && (o.textContent || '').includes('保存全部并继续');
  })()`, 6000));
check("S2 循环未开始（fix-status 未变「自动编译中…」）", await Eval(`
  (document.getElementById('fix-status').textContent || '') !== '自动编译中…'`));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]').click()`);
await new Promise((r) => setTimeout(r, 400));
check("S2 取消：弹窗关闭且循环未开始", await Eval(`
  !document.querySelector('.ref-files-overlay')
  && (document.getElementById('fix-status').textContent || '') !== '自动编译中…'`));

// ── S3：自动开始进入循环（验收 1）——reload 清模块态，干净标签 + 全套伪造
await cdp("Page.reload", { ignoreCache: true });
await new Promise((r) => setTimeout(r, 1200));
await Eval(`import('/js/ui/generate-mainc-sync.js').then((m) => m.setMainCDiskContext(${JSON.stringify(SAMPLE)}))`);
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-tree [data-code-file]').length === 3`);
await new Promise((r) => setTimeout(r, 800));
await Eval(`(() => {
  document.getElementById('output-dir').value = ${JSON.stringify(SAMPLE)};
  document.getElementById('fix-errors-msg').textContent = '';
  document.getElementById('fix-status').textContent = '';
  return Promise.all([
    import('/js/ui/generate-recommend.js').then((m) => m.setChosenPlatform('stm32')),
    import('/js/ui/generate-fix.js').then((m) => m.setToolchains({ stm32: true, mspm0: true })),
  ]);
})()`);
// 注入 banner 显示观察者（循环秒级收敛：等断言时 banner 可能已隐藏——
// MutationObserver 在显示瞬间记痕，可靠断言 aiActionStart 被触发）
await Eval(`(() => {
  window.__s4ai = 0;
  const b = document.getElementById('ai-action-banner');
  if (!b) return false;
  new MutationObserver(() => { if (!b.classList.contains('hidden')) window.__s4ai = 1; })
    .observe(b, { attributes: true, attributeFilter: ['class'] });
  return true;
})()`);
await Eval(`document.getElementById('btn-code-compile-goto').click()`);
check("S3 自动开始：状态行「自动编译中…」", await waitFor(`
  (document.getElementById('fix-status').textContent || '') === '自动编译中…'`, 8000),
  await Eval(`document.getElementById('fix-status').textContent`));
check("S3 AI 行动横幅出现（aiActionStart 触发）", await waitFor(`window.__s4ai === 1`, 6000));
// 等循环终态（编译快速失败/完成 → 状态行或错误消息离开「自动编译中…」）
const settled = await waitFor(`
  (() => {
    const st = (document.getElementById('fix-status').textContent || '');
    const msg = (document.getElementById('fix-errors-msg').textContent || '');
    return st !== '自动编译中…' && (st !== '' || msg !== '');
  })()`, 20000);
check("S3 循环收敛（状态行/错误消息离开「自动编译中…」）", settled,
  await Eval(`document.getElementById('fix-status').textContent + ' | ' + document.getElementById('fix-errors-msg').textContent`));

// ── S4：感知集成回归（验收 4）——外部写盘 → 切回代码 tab → 面板出现
await Eval(`document.querySelector('nav button[data-tab="code"]').click()`);
await new Promise((r) => setTimeout(r, 300));
writeFileSync(join(SAMPLE, "main.c"), NEW_MAIN, "utf8");
await Eval(`document.querySelector('nav button[data-tab="generate"]').click()`);
await new Promise((r) => setTimeout(r, 300));
await Eval(`document.querySelector('nav button[data-tab="code"]').click()`);
check("S4 感知回归：磁盘变更面板出现（main.c 修改条目）", await waitFor(`
  (() => {
    const p = document.getElementById('code-change-panel');
    return !!p && !p.classList.contains('hidden')
      && !!document.querySelector('#code-change-list .code-change-item[data-change-path="main.c"]');
  })()`, 8000));

console.log(failed ? "SMOKE-04 有 FAIL" : "SMOKE-04 全 PASS");
process.exit(failed ? 1 : 0);
