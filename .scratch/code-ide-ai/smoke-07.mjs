// 冒烟（工单 code-ide-ai/06）：IDE 修复面板——真实页面 + window.fetch 桩
// （/api/compile 与 /api/fix-errors 的 SSE 流 + /api/fix-errors/rollback 均桩；
// 修复「落盘」由测试脚本直接写盘模拟——重编译前写盘 → onCompiled 感知联动
// 走真实 checkCodeDiskChanges → 变更面板出现）。覆盖：编译失败双按钮出现 /
// 「在此修复」→ 面板状态流转（状态行+轮次条+结果行）/ 回滚入口+确认 /
// 双面板同步（生成页 fix-status 同步广播）/ 感知联动（变更面板自动出现）/
// 收起展开 / 生成页入口存在（无输出目录 → 拦截文案）。零依赖，CDP 9231。
import { mkdirSync, rmSync, writeFileSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-ide-ai", "sample-proj");

const OLD_MAIN = "int main(void) {\n  // TODO: init sensor\n  init();\n  return 0;\n}\n";
const EXT_MAIN = "int main(void) {\n  // fixed by AI\n  init();\n  return 0;\n}\n";

const resetSample = () => {
  rmSync(SAMPLE, { recursive: true, force: true });
  mkdirSync(join(SAMPLE, "src"), { recursive: true });
  writeFileSync(join(SAMPLE, "main.c"), OLD_MAIN, "utf8");
  writeFileSync(join(SAMPLE, "src", "app.c"), "#include <stdint.h>\n", "utf8");
  writeFileSync(join(SAMPLE, "readme.md"), "# 样本\n", "utf8");
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

// —— fetch 桩：compile（SSE 模式由 __compileMode 控制 fail/pass）、fix-errors
// （fix 返回后自动切 pass——供重编译通过 0 警）、rollback（假 backup）——
await Eval(`(() => {
  const real = window.fetch.bind(window);
  const NL = String.fromCharCode(10);
  const sseOf = (events) => new Response(new ReadableStream({
    start(c) {
      const enc = new TextEncoder();
      for (const [t, d] of events) c.enqueue(enc.encode('event: ' + t + NL + 'data: ' + JSON.stringify(d) + NL + NL));
      c.close();
    },
  }), { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
  window.__compileMode = 'fail';
  window.__compileCount = 0;
  window.fetch = (url, opts) => {
    const u = String(url);
    if (u.includes('/api/compile')) {
      window.__compileCount++;
      const pass = window.__compileMode === 'pass';
      const done = pass
        ? { passed: true, timed_out: false, duration: 0.1,
            summary: { errors: 0, warnings: 0 }, error_text: '',
            parsed_errors: [] }
        : { passed: false, timed_out: false, duration: 0.1,
            summary: { errors: 1, warnings: 0 },
            error_text: 'bad code', parsed_errors: [{ path: 'main.c', line: 1, message: 'bad' }] };
      return Promise.resolve(sseOf([['done', done]]));
    }
    if (u.includes('/api/fix-errors') && !u.includes('rollback')) {
      return Promise.resolve(sseOf([
        ['parse_done', { error_count: 1, file_count: 1 }],
        ['fix_start', {}],
        ['apply_result', { file: 'main.c', line: 1, status: 'applied', reason: '修好了' }],
        ['done', { parsed: [{ path: 'main.c', line: 1, message: 'bad' }],
          fixes: [{ file: 'main.c', line: 1, status: 'applied', reason: '修好了' }],
          backup_id: 'b1' }],
      ])).then((r) => { window.__compileMode = 'pass'; return r; });
    }
    if (u.includes('/api/fix-errors/rollback')) {
      return Promise.resolve(new Response(JSON.stringify({ restored: ['main.c'] }), {
        status: 200, headers: { 'Content-Type': 'application/json' } }));
    }
    return real(url, opts);
  };
  return true;
})()`);

// 打开样本目录（**不设**生成上下文——新语义：任意打开目录编译失败都可
// 「在此修复」（空问题文本降级）；「去生成页」仍需生成上下文）
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);

// S1：IDE 编译（桩 fail）→ 编译面板 + 「在此修复」出现（非上下文目录）；
// 「去生成页」不出现
await Eval(`document.getElementById('btn-code-compile').click()`);
check("S1 编译失败：面板展开 + 错误行", await waitFor(`
  (() => { const p = document.getElementById('code-compile-panel');
    return !p.classList.contains('hidden')
      && !!document.querySelector('#code-compile-errors [data-compile-path]'); })()`));
check("S1 非上下文目录「在此修复」出现", await Eval(`
  !document.getElementById('btn-code-compile-fix-here').classList.contains('hidden')`));
check("S1 非上下文目录「去生成页」不出现", await Eval(`
  document.getElementById('btn-code-compile-goto').classList.contains('hidden')`));
check("S1 修复面板默认隐藏", await Eval(`document.getElementById('code-fix-panel').classList.contains('hidden')`));

// S1.5：设生成上下文 → 再编译失败 → 「去生成页」出现（J5 门控：goto 需上下文）
await Eval(`import('/js/ui/generate-mainc-sync.js').then((m) => m.setMainCDiskContext(${JSON.stringify(SAMPLE)}))`);
await Eval(`document.getElementById('btn-code-compile').click()`);
check("S1.5 生成上下文「去生成页」出现", await waitFor(`
  !document.getElementById('btn-code-compile-goto').classList.contains('hidden')`));

// S2：外部写盘（模拟修复落盘）→ 「在此修复」→ 循环（首编 fail → fix →
// 重编译 pass）→ 面板状态流转
writeFileSync(join(SAMPLE, "main.c"), EXT_MAIN, "utf8");
await Eval(`document.getElementById('btn-code-compile-fix-here').click()`);
check("S2 面板展开 + 循环启动（轮次条出现）", await waitFor(`
  (() => { const p = document.getElementById('code-fix-panel');
    const r = document.getElementById('code-fix-round');
    return !p.classList.contains('hidden') && r.textContent.includes('第 1/3 轮'); })()`));
check("S2 终态：状态行「重编译通过 ✅」", await waitFor(`
  document.getElementById('code-fix-status').textContent.includes('重编译通过 ✅')`));
check("S2 结果行：已修复 main.c:1", await Eval(`
  (() => { const rows = document.querySelectorAll('#code-fix-results .fix-row');
    return rows.length > 0 && rows[0].textContent.includes('已修复') && rows[0].textContent.includes('main.c:1'); })()`));
check("S2 回滚按钮可见（backup_id）", await Eval(`
  !document.getElementById('btn-code-fix-rollback').classList.contains('hidden')`));
check("S2 双面板同步：生成页 fix-status 同终态", await Eval(`
  document.getElementById('fix-status').textContent.includes('重编译通过 ✅')`));
check("S2 感知联动：变更面板出现（main.c 修改）", await waitFor(`
  (() => { const p = document.getElementById('code-change-panel');
    return !p.classList.contains('hidden') && p.textContent.includes('main.c'); })()`));

// S3：回滚 → 确认模态 → 桩 rollback → toast
await Eval(`document.getElementById('btn-code-fix-rollback').click()`);
check("S3 回滚确认模态出现", await waitFor(`
  (() => { const m = document.querySelector('.ref-files-overlay');
    return m && m.textContent.includes('确认回滚') && m.textContent.includes('回滚本次修复'); })()`));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
check("S3 回滚成功 toast", await waitFor(`
  (() => { const t = Array.from(document.querySelectorAll('#toast-root .toast.ok'));
    return t.some((e) => e.textContent.includes('已回滚 1 个文件')); })()`));

// S4：收起/展开（自己的 collapse 按钮）
await Eval(`document.getElementById('btn-code-fix-collapse').click()`);
check("S4 收起：结果区隐藏", await Eval(`
  (() => { const p = document.getElementById('code-fix-panel');
    const r = document.getElementById('code-fix-results');
    return p.classList.contains('collapsed')
      && getComputedStyle(r).display === 'none'; })()`));
await Eval(`document.getElementById('btn-code-fix-collapse').click()`);
check("S4 再展开", await Eval(`
  !document.getElementById('code-fix-panel').classList.contains('collapsed')`));

// S5：生成页入口存在（无输出目录 → 拦截文案——跳转路径可用，锁由核心单测覆盖）
await Eval(`document.getElementById('btn-code-compile-goto').click()`);
await new Promise((r) => setTimeout(r, 600));
check("S5 生成页入口：跳转后被「请先生成工程」拦截", await Eval(`
  (() => { const el = document.getElementById('fix-errors-msg');
    return el && el.textContent.includes('请先生成工程'); })()`));
const compileCount = await Eval(`window.__compileCount`);
console.log("  编译桩次数 = " + compileCount + "（IDE 2 + 循环首编 1 + 重编译 1 = 4；goto 被拦截未触发新循环）");
check("S5 拦截后无新编译请求", compileCount === 4);

console.log(failed === 0 ? "全部通过" : failed + " 项失败");
process.exit(failed === 0 ? 0 : 1);
