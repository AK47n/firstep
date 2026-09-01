// 冒烟（工单 code-ide-ai/04）：C2 应用闭环——真实页面 + window.fetch 桩
// （chat/read|send 桩：reply 文本由 __stubReply 注入，含 <DIFF> 与否用例驱动）
// + **真实后端** /api/code/apply-diff（preview 只算不写 + 写模式 409 同口径，
// webapp 8000 已含工单 02 端点）。覆盖：无块无按钮 / 有块按钮出现 / 预览
// 模态（stats + hunk 行级 diff）/ 取消不写盘 / 确认 → 磁盘文件变化 + toast +
// 变更面板感知 / 409（预览后外部改盘 → 确认 → 提示重预览不覆盖）/
// 脏标签守卫（取消 → 中止）。零依赖：fetch + WebSocket CDP 9231。
import { mkdirSync, rmSync, writeFileSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-ide-ai", "sample-proj");

const DIFF_MAIN = "有 TODO 没处理：\n<DIFF>\n"
  + JSON.stringify({
    path: "main.c",
    hunks: [
      { line: 2, title: "填充 TODO「init sensor」", lines: [
        { kind: "del", text: "  // TODO: init sensor" },
        { kind: "add", text: "  // 已初始化传感器（AI 建议）" },
        { kind: "ctx", text: "  init();" },
      ] },
    ],
  })
  + "\n</DIFF>";
const DIFF_APP = "app.c 建议加头文件：\n<DIFF>\n"
  + JSON.stringify({
    path: "src/app.c",
    hunks: [
      { line: 1, title: "补充头文件", lines: [
        { kind: "del", text: "#include <stdint.h>" },
        { kind: "add", text: "#include <stdint.h>" },
        { kind: "add", text: "#include <string.h>" },
      ] },
    ],
  })
  + "\n</DIFF>";

const OLD_MAIN = "int main(void) {\n  // TODO: init sensor\n  init();\n  return 0;\n}\n";
const EXT_MAIN = "int main(void) {\n  // external edit\n  return 0;\n}\n";

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

// —— fetch 桩（chat；apply-diff 走真实后端）——
await Eval(`(() => {
  const real = window.fetch.bind(window);
  window.__stubReply = '这是普通回复（没有改动建议）。';
  window.fetch = (url, opts) => {
    const u = String(url);
    if (u.includes('/api/tasks/idea/chat/read')) {
      return Promise.resolve(new Response(JSON.stringify({ chat: { messages: [], note: '' } }), {
        status: 200, headers: { 'Content-Type': 'application/json' } }));
    }
    if (u.includes('/api/tasks/idea/chat/send')) {
      const body = JSON.parse((opts && opts.body) || '{}');
      const history = body.history || [];
      const reply = String(window.__stubReply || '');
      const chat = {
        messages: history.map((m, i) => ({ role: m.role, content: m.content, at: '14:0' + i }))
          .concat([{ role: 'assistant', content: reply, at: '14:09' }]),
        note: '',
      };
      return Promise.resolve(new Response(JSON.stringify({ reply, chat }), {
        status: 200, headers: { 'Content-Type': 'application/json' } }));
    }
    return real(url, opts);
  };
  return true;
})()`);

// 打开目录 → 打开 main.c
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]').click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);

const sendQuestion = async (text) => {
  await Eval(`(() => {
    const input = document.getElementById('code-ai-chat-input');
    input.value = ${JSON.stringify(text)};
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    return true;
  })()`);
};

// S1：普通回复 → 无按钮
await sendQuestion("这段有什么问题？");
await waitFor(`document.querySelectorAll('#code-ai-chat-body .sugg-msg.ai').length >= 1`);
check("普通回复：无「预览改动」按钮", await Eval(`
  document.querySelectorAll('#code-ai-chat-body [data-ai-preview]').length === 0 &&
  document.querySelector('#code-ai-chat-body').textContent.includes('普通回复')`));

// S2：DIFF 回复（main.c）→ 按钮出现 + DIFF 块剥离
await Eval(`window.__stubReply = ${JSON.stringify(DIFF_MAIN)}`);
await sendQuestion("把 TODO 补一下");
await waitFor(`!!document.querySelector('#code-ai-chat-body [data-ai-preview]')`);
check("DIFF 回复：按钮出现 + DIFF 块剥离显示", await Eval(`
  !!document.querySelector('#code-ai-chat-body [data-ai-preview]')
  && !document.querySelector('#code-ai-chat-body').textContent.includes('<DIFF>')
  && document.querySelector('#code-ai-chat-body').textContent.includes('预览改动')`));

// S3：预览 → 模态（stats + hunk）→ 取消 → 磁盘未变
await Eval(`document.querySelector('#code-ai-chat-body [data-ai-preview]').click()`);
check("预览模态出现（stats + 行级 diff hunk）", await waitFor(`
  (() => { const b = document.querySelector('.ref-files-overlay .code-ai-preview-body');
    return b && b.textContent.includes('AI 改动效果') && b.querySelector('.diff-hunk')
      && b.querySelector('.diff-line.diff-add') && b.querySelector('.diff-line.diff-del'); })()`));
check("模态标题含路径", await Eval(`
  (() => { const t = document.querySelector('.ref-files-overlay');
    return t && t.textContent.includes('预览 AI 改动 · main.c'); })()`));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]').click()`);
await new Promise((r) => setTimeout(r, 500));
check("取消：磁盘未变", readFileSync(join(SAMPLE, "main.c"), "utf8") === OLD_MAIN);

// S4：再预览 → 确认 → 应用成功（磁盘变化 + toast + 变更面板感知）
await Eval(`document.querySelector('#code-ai-chat-body [data-ai-preview]').click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-ok]')`);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
check("成功 toast（已应用 AI 改动）", await waitFor(`
  (() => { const t = Array.from(document.querySelectorAll('#toast-root .toast.ok'));
    return t.some((e) => e.textContent.includes('已应用 AI 改动')); })()`));
check("磁盘文件 = 应用后内容", (() => {
  try { return readFileSync(join(SAMPLE, "main.c"), "utf8").includes("已初始化传感器（AI 建议）"); }
  catch { return false; }
})());
check("感知联动：变更面板出现（main.c 修改）", await waitFor(`
  (() => { const p = document.getElementById('code-change-panel');
    return !p.classList.contains('hidden') && p.textContent.includes('main.c'); })()`));

// S5：外部写盘回 OLD_MAIN + 感知重载（diff1 可再匹配）
writeFileSync(join(SAMPLE, "main.c"), OLD_MAIN, "utf8");
await Eval(`import('/js/ui/codeview.js').then((m) => m.checkCodeDiskChanges())`);
await waitFor(`(document.querySelector('#code-viewer .code-ta') || { value: '' }).value.includes('TODO: init sensor')`);

// S6：预览（模态打开）→ 外部改盘 → 确认 → 409 提示重预览 + 外部内容保留
await Eval(`document.querySelector('#code-ai-chat-body [data-ai-preview]').click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-ok]')`);
writeFileSync(join(SAMPLE, "main.c"), EXT_MAIN, "utf8");
await new Promise((r) => setTimeout(r, 300));   // 确保 mtime 与预览读盘值拉开
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
check("409：提示重预览（磁盘内容已变化）", await waitFor(`
  (() => { const t = Array.from(document.querySelectorAll('#toast-root .toast.error'));
    return t.some((e) => e.textContent.includes('磁盘内容已变化')); })()`));
check("409：未覆盖外部内容", readFileSync(join(SAMPLE, "main.c"), "utf8").includes("external edit"));

// S7：脏标签守卫（diff 指向 src/app.c——磁盘未动过，避开 main.c 混乱态）：
// 打开 app.c → 改标签内容不保存 → 预览确认 → 守卫弹窗 → 取消 → 中止
await Eval(`document.querySelector('#code-tree [data-code-file="src/app.c"]').click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')
  && document.querySelector('#code-viewer .code-ta').value.includes('stdint')`);
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value = ta.value + '// 本地未保存改动\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
await Eval(`window.__stubReply = ${JSON.stringify(DIFF_APP)}`);
await sendQuestion("app.c 加个 string.h");
await waitFor(`document.querySelectorAll('#code-ai-chat-body [data-ai-preview]').length >= 2`);
await Eval(`(() => { const b = document.querySelectorAll('#code-ai-chat-body [data-ai-preview]');
  b[b.length - 1].click(); return true; })()`);
if (!(await waitFor(`!!document.querySelector('.ref-files-overlay')`))) {
  console.log("S7 诊断——overlay 未出现；toasts:",
    await Eval(`Array.from(document.querySelectorAll('#toast-root .toast')).map((t) => t.textContent)`));
}
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-ok]')`);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
check("脏标签：写盘守卫弹窗出现", await waitFor(`
  (() => { const m = document.querySelector('.ref-files-overlay');
    return m && m.textContent.includes('未保存') && m.textContent.includes('保存全部并继续'); })()`));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]').click()`);
await new Promise((r) => setTimeout(r, 400));
check("守卫取消：中止（app.c 未被写）", (() => {
  const c = readFileSync(join(SAMPLE, "src", "app.c"), "utf8");
  return c.includes("stdint") && !c.includes("string.h") && !c.includes("本地未保存");
})());

console.log(failed === 0 ? "全部通过" : failed + " 项失败");
process.exit(failed === 0 ? 0 : 1);
