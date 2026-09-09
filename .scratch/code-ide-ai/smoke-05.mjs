// 冒烟（工单 code-ide-ai/03）：IDE AI 对话面板——真实页面 + window.fetch
// 桩劫持 /api/tasks/idea/chat/read|send（免真实 LLM 分钟级调用；桩经
// window.__stub* 挂钩可查写入参数）。覆盖：面板显隐（打开目录）/ 空态引导 /
// 历史渲染 / 选区浮动按钮出现与定位 / 点击 → 引用插入输入框（选区上下文
// 契约格式）/ Enter 发送 → 乐观气泡 → 落盘真相替换 / 桩断言 history 末条含
// 引用 / send 失败 → 输入回填 + bus状态归零 / 收起展开。零依赖：
// fetch + WebSocket CDP 9231；webapp 8000。
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-ide-ai", "sample-proj");

const OLD_MAIN = "int main(void) {\n  // TODO: init sensor\n  init();\n  return 0;\n}\n";

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

// —— fetch 桩：read 返回 __stubReadChat（缺省空聊天）；send 记录 history 到
// __stubSends，__stubSendFail 时 500（detail 中文）——
await Eval(`(() => {
  const real = window.fetch.bind(window);
  window.__stubSends = [];
  window.__stubReadChat = null;
  window.__stubSendFail = false;
  window.fetch = (url, opts) => {
    const u = String(url);
    if (u.includes('/api/tasks/idea/chat/read')) {
      const chat = window.__stubReadChat || { messages: [], note: '' };
      return Promise.resolve(new Response(JSON.stringify({ chat }), {
        status: 200, headers: { 'Content-Type': 'application/json' } }));
    }
    if (u.includes('/api/tasks/idea/chat/send')) {
      const body = JSON.parse((opts && opts.body) || '{}');
      window.__stubSends.push(body);
      if (window.__stubSendFail) {
        return Promise.resolve(new Response(JSON.stringify({ detail: '模拟失败：LLM 服务不可用' }), {
          status: 500, headers: { 'Content-Type': 'application/json', 'content-type': 'application/json' } }));
      }
      const history = body.history || [];
      const chat = {
        messages: history.map((m, i) => ({ role: m.role, content: m.content, at: '14:0' + i }))
          .concat([{ role: 'assistant', content: '模拟回复：建议补上 TODO 再继续。', at: '14:09' }]),
        note: '',
      };
      return Promise.resolve(new Response(JSON.stringify({ reply: '模拟回复', chat }), {
        status: 200, headers: { 'Content-Type': 'application/json' } }));
    }
    return real(url, opts);
  };
  return 'stubbed';
})()`);
check("fetch 桩安装", (await Eval(`!!window.fetch && window.__stubSends !== undefined`)));

// 打开样本目录：面板出现 + 空态引导
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
check("打开目录：AI 对话面板显示", await waitFor(`
  !document.getElementById('code-ai-chat-panel').classList.contains('hidden')`));
check("空态引导文案", await waitFor(
  `!!document.querySelector('#code-ai-chat-body .code-ai-chat-empty')`));
check("发送钮初始禁用", await Eval(
  `document.getElementById('btn-code-ai-send').disabled`));

// 预设历史 → 重新打开目录（走 setCodeAiDir 路径）→ 历史渲染
await Eval(`window.__stubReadChat = { messages: [
  { role: 'user', content: '引脚配置对不对？', at: '14:01' },
  { role: 'assistant', content: '建议检查 SDA/SCL 上拉。', at: '14:02' },
], note: '' }`);
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await waitFor(`document.querySelectorAll('#code-ai-chat-body .sugg-msg').length >= 2`);
check("历史气泡渲染（user+ai）", await Eval(`
  !!document.querySelector('#code-ai-chat-body .sugg-msg.user')
  && !!document.querySelector('#code-ai-chat-body .sugg-msg.ai')
  && document.querySelector('#code-ai-chat-body').textContent.includes('上拉')`));

// 打开 main.c（干净）→ 程序化选区 → 浮动按钮
await waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`);
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]').click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
check("浮动按钮初始隐藏", await Eval(`
  (() => { const b = document.querySelector('.code-ai-selection-btn');
    return b && b.classList.contains('hidden'); })()`));
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(18, 41);   // 第 2 行 " // TODO: init sensor"（含 init 片段）
  ta.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
  return true;
})()`);
check("选区后浮动按钮出现", await waitFor(`
  (() => { const b = document.querySelector('.code-ai-selection-btn');
    return b && !b.classList.contains('hidden') && b.style.left !== '' && b.style.top !== ''; })()`));
check("按钮位置非零（选区末行右侧）", await Eval(`
  (() => { const b = document.querySelector('.code-ai-selection-btn');
    return parseFloat(b.style.left) > 0 && parseFloat(b.style.top) > 0; })()`));

// 点击按钮 → 动作菜单（工单 code-editor-refine/07：解释 / 加中文注释 / 重构 / 问 AI）
// 注（2026-09-09 第八轮）：按钮行为由「直接插引用」升级为「开动作菜单」，原断言
// 「点击后输入框出现引用」已过期——改为先断菜单四项，再点「问 AI」（= 原插引用行为）。
await Eval(`document.querySelector('.code-ai-selection-btn').click()`);
check("浮动按钮点击 → 动作菜单四项（解释/加中文注释/重构/问 AI）", await waitFor(`
  (() => { const m = document.querySelector('.code-ctx-menu');
    if (!m) return false;
    const labels = Array.from(m.querySelectorAll('.code-ctx-item')).map((b) => b.textContent.trim());
    return labels.length === 4 && labels[0] === '解释' && labels[1] === '加中文注释'
      && labels[2] === '重构' && labels[3] === '问 AI'; })()`));
await Eval(`(() => {
  const items = Array.from(document.querySelectorAll('.code-ctx-menu .code-ctx-item'));
  const ask = items.find((b) => b.textContent.trim() === '问 AI');
  ask?.click();
  return true;
})()`);
check("引用插入输入框（契约格式）", await waitFor(`
  (() => { const v = document.getElementById('code-ai-chat-input').value;
    const fence = String.fromCharCode(96).repeat(3);
    return v.includes('【代码引用 · main.c · 第') && v.includes(fence + 'c') && v.includes('init s'); })()`));
check("输入框聚焦", await Eval(`document.activeElement === document.getElementById('code-ai-chat-input')`));

// 输入问题 → Enter 发送 → 乐观/落盘渲染 + 桩断言
await Eval(`(() => {
  const input = document.getElementById('code-ai-chat-input');
  input.value = input.value + '\\n\\n这个 TODO 怎么处理？';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  return true;
})()`);
check("发送后 AI 回复气泡出现", await waitFor(`
  document.querySelectorAll('#code-ai-chat-body .sugg-msg.ai').length >= 2
  && document.querySelector('#code-ai-chat-body').textContent.includes('模拟回复')`));
check("历史引用消息卡片化（details + summary）", await Eval(`
  (() => { const card = document.querySelector('#code-ai-chat-body details.code-ai-ref');
    return card && card.querySelector('summary').textContent.includes('代码引用 · main.c · 第')
      && card.querySelector('pre.code-ai-ref-code'); })()`));
check("桩收到 history 且末条 user 含引用", await Eval(`
  (() => { const s = window.__stubSends;
    const last = s[s.length - 1] || {};
    const u = (last.history || []).slice(-1)[0] || {};
    return s.length >= 1 && u.role === 'user'
      && u.content.includes('【代码引用 · main.c · 第') && u.content.includes('TODO 怎么处理'); })()`));
check("发送后 busy 状态清除", await waitFor(
  `document.getElementById('code-ai-chat-status').textContent === ''`));

// 失败路径：回填输入 + 状态恢复
await Eval(`(() => {
  window.__stubSendFail = true;
  const input = document.getElementById('code-ai-chat-input');
  input.value = '这条会失败';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
  return true;
})()`);
check("失败后输入回填可重发", await waitFor(
  `document.getElementById('code-ai-chat-input').value === '这条会失败'`));
await Eval(`window.__stubSendFail = false`);

// 收起 / 展开
await Eval(`document.getElementById('btn-code-ai-collapse').click()`);
check("收起（collapsed + 按钮文字切换）", await Eval(`
  document.getElementById('code-ai-chat-panel').classList.contains('collapsed')
  && document.getElementById('btn-code-ai-collapse').textContent === '展开'`));
await Eval(`document.getElementById('btn-code-ai-collapse').click()`);
check("展开恢复", await Eval(`
  !document.getElementById('code-ai-chat-panel').classList.contains('collapsed')
  && document.getElementById('btn-code-ai-collapse').textContent === '收起'`));

console.log(failed === 0 ? "全部通过" : failed + " 项失败");
process.exit(failed === 0 ? 0 : 1);
