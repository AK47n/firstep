// 冒烟（工单 code-ide-flow/02）：磁盘基线感知——真实 API + 真实磁盘样本
// （.scratch/code-ide-flow/sample-proj，跑前重建、跑后清理）：
// ①外部写盘 + 真切 tab 钩子 → 干净标签自动重载 + toast + 树「新/变」徽章；
// ②脏标签 → 绝不静默重载 + 「磁盘已变更」徽章 + 点徽章弹既有三选（取消）；
// ③main.c 写盘后树徽章与标签内容一致。
// 零依赖：node 内置 fetch + WebSocket 直连 Edge CDP（9231）；webapp 8000。
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-ide-flow", "sample-proj");

const resetSample = () => {
  rmSync(SAMPLE, { recursive: true, force: true });
  mkdirSync(join(SAMPLE, "src"), { recursive: true });
  writeFileSync(join(SAMPLE, "main.c"), "int main(void){ return 0; }\n", "utf8");
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

// 导航刷新 + 清基线（确定性：无上次会话残留）
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

// 打开样本目录（首次 = 建立基线）
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
check("打开样本目录：树含 main.c / readme.md / src/app.h", await waitFor(`
  (() => {
    const files = [...document.querySelectorAll('#code-tree [data-code-file]')].map((b) => b.dataset.codeFile).sort();
    return files.includes('main.c') && files.includes('readme.md') && files.includes('src/app.h');
  })()`));

// 打开 main.c 标签（干净）
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]').click()`);
check("打开 main.c 标签：旧内容可见", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return !!ta && ta.value.includes('return 0');
  })()`));

// ---- ① 外部写盘：改 main.c + 新增 src/oled.c → 真切 tab 钩子 ----
writeFileSync(join(SAMPLE, "main.c"), "int main(void){ return 42; }\n", "utf8");
writeFileSync(join(SAMPLE, "src", "oled.c"), "// oled\n", "utf8");
await Eval(`document.querySelector('nav button[data-tab="generate"]').click()`);
await new Promise((r) => setTimeout(r, 300));
await Eval(`document.querySelector('nav button[data-tab="code"]').click()`);
check("切回代码 tab：干净标签自动重载（内容 = 磁盘新值）", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return !!ta && ta.value.includes('return 42');
  })()`));
check("切回代码 tab：toast「已被外部更新，已自动重载」", await waitFor(`
  [...document.querySelectorAll('#toast-root .toast-text')].some((t) => t.textContent.includes('已被外部更新，已自动重载'))`));
check("树：新增 src/oled.c + 「新」徽章", await waitFor(`
  !!document.querySelector('#code-tree [data-code-file="src/oled.c"]')
  && !!document.querySelector('#code-tree .code-tree-badge.b-new')`));
check("树：main.c 行「变」徽章（外部修改）", await Eval(`
  !!document.querySelector('#code-tree [data-code-file="main.c"]')?.closest('li')
    ?.querySelector('.code-tree-badge.b-mod')`));
check("树：readme.md 无徽章（未变更）", await Eval(`
  !document.querySelector('#code-tree [data-code-file="readme.md"]')?.closest('li')
    ?.querySelector('.code-tree-badge')`));

// ---- ② 脏标签保护：编辑 main.c（不保存）→ 外部再改 → 切回 ----
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = 'int main(void){ return 7; } // 我的未保存编辑\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
})()`);
await new Promise((r) => setTimeout(r, 300));
writeFileSync(join(SAMPLE, "main.c"), "int main(void){ return 99; }\n", "utf8");
await Eval(`document.querySelector('nav button[data-tab="generate"]').click()`);
await new Promise((r) => setTimeout(r, 300));
await Eval(`document.querySelector('nav button[data-tab="code"]').click()`);
await new Promise((r) => setTimeout(r, 800));
check("脏标签：内容不被静默重载（仍是我的编辑）", await Eval(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return !!ta && ta.value.includes('我的未保存编辑') && !ta.value.includes('return 99');
  })()`));
check("脏标签：出现「磁盘已变更」徽章", await waitFor(`
  !!document.querySelector('#code-tabs .code-tab[data-tab-path="main.c"] .code-tab-disk')`));

// ---- ③ 点徽章弹既有三选（取消路径） ----
await Eval(`document.querySelector('#code-tabs .code-tab[data-tab-path="main.c"] .code-tab-disk').click()`);
check("点徽章：三选模态出现（保存冲突：覆盖/重载/取消）", await waitFor(`
  !!document.querySelector('.code-conflict-overlay')`));
await Eval(`document.querySelector('.code-conflict-overlay [data-confirm-cancel]').click()`);
check("取消：模态关闭，标签内容与徽章保留", await waitFor(`
  (() => {
    const overlay = document.querySelector('.code-conflict-overlay');
    const ta = document.querySelector('#code-viewer .code-ta');
    return !overlay && !!ta && ta.value.includes('我的未保存编辑')
      && !!document.querySelector('#code-tabs .code-tab-disk');
  })()`));

// ---- 清理 ----
rmSync(SAMPLE, { recursive: true, force: true });
console.log(failed === 0 ? "SMOKE-02 全 PASS" : `SMOKE-02 失败 ${failed} 项`);
process.exit(failed === 0 ? 0 : 1);
