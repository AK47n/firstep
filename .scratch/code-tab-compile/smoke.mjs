// 冒烟（工单 code-tab-compile/03-04）：代码栏编译闭环——状态栏「编译」→
// 自动保存（无脏标签零请求）→ SSE（mock）→ 底部面板状态行 + 错误列表 →
// 点错误行 → source-line mock 归一 → 打开/激活 tab + 选区跳行；再编译成功
// 路径（状态行切换）。零依赖：node 内置 fetch + WebSocket 直连 Edge CDP
//（9231）；编译/文件接口全部 window 层 mock，不需真工具链与真工程。
const CDP = 9231;
const pageUrl = "http://127.0.0.1:8000/";

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try {
    targets = await (await fetch(`http://127.0.0.1:${CDP}/json/list`)).json();
  } catch {}
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
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};

let ready = false;
// 重新加载页面：webapp 静态文件实时更新，但浏览器内存中的 JS 需刷新才换新
await cdp("Page.reload", { ignoreCache: true });
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !!document.getElementById('tab-code')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? "  [" + extra + "]" : ""));
  if (!ok) failed++;
};

// ---- mock 安装：目录打开 / 文件读取 / source-line / 编译 SSE（走 window 层
// ——app.js 的 apiGet/apiPost 与 fetch 都读 window 全局，模块加载后覆盖生效）----
const MAIN_SRC = ["int x = 0;", "void setup(void) {", "  x = 1;", "}", "int bad(void) {", "  return y;", "}", "int z = 2;", "void t1(void) {}", "void t2(void) {}"].join("\n");
const mocksOk = await Eval(`(async () => {
  const enc = new TextEncoder();
  const msrc = ${JSON.stringify(MAIN_SRC)};
  const json = (o) => new Response(JSON.stringify(o), { status: 200,
    headers: { 'Content-Type': 'application/json' } });
  const sse = (events) => new Response(new ReadableStream({
    start(c) {
      for (const [type, data] of events) {
        c.enqueue(enc.encode('event: ' + type + '\\ndata: ' + JSON.stringify(data) + '\\n\\n'));
      }
      c.close();
    },
  }), { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
  window.__fail = { platform: 'stm32', output_dir: 'D:/tmp/fakeproj', exit_code: 2,
    error_text: 'main.c:5: error', passed: false, timed_out: false,
    project_file: 'Project.uvprojx', command: 'uv4 -b', duration: 4.2,
    parsed_errors: [{ path: 'main.c', line: 5, message: '未定义的变量: y' }],
    summary: { errors: 1, warnings: 0 } };
  window.__fail2 = { platform: 'stm32', output_dir: 'D:/tmp/fakeproj', exit_code: 2,
    error_text: '..\\\\main.c:5: error', passed: false, timed_out: false,
    project_file: 'Project.uvprojx', command: 'uv4 -b', duration: 4.2,
    parsed_errors: [{ path: '..\\\\main.c', line: 5, message: 'UV4 形态错误' }],
    summary: { errors: 1, warnings: 0 } };
  window.__ok = { platform: 'stm32', output_dir: 'D:/tmp/fakeproj', exit_code: 0,
    error_text: '', passed: true, timed_out: false, project_file: 'Project.uvprojx',
    command: 'uv4 -b', duration: 3.2, parsed_errors: [],
    summary: { errors: 0, warnings: 1 } };
  window.__calls = { file: 0, sourceLine: 0 };
  // apiGet/apiPost 都走 window.fetch（app.js 单源），这里按 URL 路由 mock
  window.fetch = async (url, opts) => {
    const u = String(url);
    const p = new URL(u, location.origin);
    if (p.pathname === '/api/compile') {
      return sse([['compile_start', {}], ['done', window.__fail ?? window.__ok]]);
    }
    if (p.pathname === '/api/code/open') {
      const body = JSON.parse((opts && opts.body) || '{}');
      return json({ root: body.dir, files: [
        { path: 'main.c', size_bytes: msrc.length },
        { path: 'modules/led/code/led.c', size_bytes: 80 },
      ] });
    }
    if (p.pathname === '/api/compile/source-line') {
      window.__calls.sourceLine++;
      const body = JSON.parse((opts && opts.body) || '{}');
      return json({ path_resolved: String(body.path).replace(/\\\\/g, '/').replace(/^\\.\\//, '').replace(/^\\.\\.\\//, ''), line_text: '  return y;' });
    }
    if (p.pathname === '/api/code/file') {
      window.__calls.file++;
      const path = p.searchParams.get('path') || '';
      if (path.includes('..') || path.includes('\\\\')) {
        // 模拟 is_unsafe_path 拒绝（UV4 反斜杠形态）
        return new Response(JSON.stringify({ detail: '非法路径：' + path }),
          { status: 400, headers: { 'Content-Type': 'application/json' } });
      }
      return json({ path, size_bytes: msrc.length,
        content: msrc, outline: [{ kind: 'function', name: 'setup', line: 2 }],
        mtime_ns: '123', utf8: true });
    }
    if (p.pathname === '/api/code/save') return json({});
    return new Response(null, { status: 404 });
  };
  return true;
})()`);
check("mock 安装成功", mocksOk === true);

// ---- 切「代码」tab + openCodeViewer（动态 import：真实入口，非影子）----
await Eval(`document.querySelector('nav button[data-tab="code"]').click()`);
const opened = await Eval(`(async () => {
  const m = await import('/js/ui/codeview.js');
  m.openCodeViewer('D:/tmp/fakeproj');
  await new Promise((r) => setTimeout(r, 200));
  return document.querySelectorAll('#code-tree [data-code-file]').length;
})()`);
check("打开目录 → 树渲染 2 个文件", opened === 2, "files=" + opened);

// 打开 main.c（树点击真实路径）
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]').click()`);
await new Promise((r) => setTimeout(r, 300));
const tabOpen = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  return { ta: !!ta, tabs: document.querySelectorAll('#code-tabs [data-tab-path]').length };
})()`);
check("点 main.c → 编辑器打开（textarea + 1 个标签）", tabOpen.ta === true && tabOpen.tabs === 1, JSON.stringify(tabOpen));

// ---- 点「编译」→ 失败面板自动展开 + 状态行 + 错误列表 ----
await Eval(`document.getElementById('btn-code-compile').click()`);
for (let i = 0; i < 40; i++) {
  const done = await Eval(`document.getElementById('code-compile-status').textContent.includes('编译失败')`);
  if (done) break;
  await new Promise((r) => setTimeout(r, 200));
}
const failState = await Eval(`(() => ({
  panelHidden: document.getElementById('code-compile-panel').classList.contains('hidden'),
  status: document.getElementById('code-compile-status').textContent,
  cls: document.getElementById('code-compile-status').className,
  rows: document.querySelectorAll('#code-compile-errors .code-compile-error').length,
  first: document.querySelector('#code-compile-errors .code-compile-error')?.textContent || '',
  gotoHidden: document.getElementById('btn-code-compile-goto').classList.contains('hidden'),
  btnText: document.getElementById('btn-code-compile').textContent,
}))()`);
check("失败 → 面板展开", failState.panelHidden === false);
check("失败 → 状态行文案（N 个错误 + 耗时）", /编译失败 · 1 个错误/.test(failState.status), failState.status);
check("失败 → 状态行 err 配色", failState.cls.includes("err"));
check("失败 → 1 条错误行（path:line + 消息）", failState.rows === 1 && failState.first.includes("main.c:5") && failState.first.includes("未定义的变量"), failState.first);
check("非生成上下文 → 一键修复引导隐藏", failState.gotoHidden === true);
check("编译按钮恢复", failState.btnText === "编译");

// ---- 点错误行 → 打开/激活 main.c 并选区跳行（第 5 行）----
await Eval(`document.querySelector('#code-compile-errors .code-compile-error').click()`);
await new Promise((r) => setTimeout(r, 400));
const jump = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const lines = ta.value.split('\\n');
  let start = 0;
  for (let i = 0; i < 4; i++) start += lines[i].length + 1;
  const end = start + lines[4].length;
  return { start, end, selStart: ta.selectionStart, selEnd: ta.selectionEnd,
    active: !!document.querySelector('#code-tabs [data-tab-path="main.c"].on') };
})()`);
check("点错误行 → 选中第 5 行（偏移独立字面量）", jump.selStart === jump.start && jump.selEnd === jump.end, `sel=${jump.selStart}-${jump.selEnd} expect=${jump.start}-${jump.end}`);
check("点错误行 → main.c tab 激活", jump.active === true);
const calls1 = await Eval(`({ file: window.__calls.file, sourceLine: window.__calls.sourceLine })`);
check("兜底链首跳：/api/code/file 预检成功（source-line 零调用）", calls1.file >= 1 && calls1.sourceLine === 0, JSON.stringify(calls1));

// ---- 再编译（成功路径 mock）→ 状态行切换 + 列表空态 ----
await Eval(`window.__fail = window.__ok`);
await Eval(`document.getElementById('btn-code-compile').click()`);
for (let i = 0; i < 40; i++) {
  const done = await Eval(`document.getElementById('code-compile-status').textContent.includes('编译通过')`);
  if (done) break;
  await new Promise((r) => setTimeout(r, 200));
}
const okState = await Eval(`(() => ({
  status: document.getElementById('code-compile-status').textContent,
  cls: document.getElementById('code-compile-status').className,
  empty: document.querySelector('#code-compile-errors').textContent.includes('无结构化错误信息'),
}))()`);
check("成功 → 状态行文案（0 Error / 1 Warning + 耗时）", /编译成功 · 0 Error 1 Warning · 耗时 3.2s/.test(okState.status), okState.status);
check("成功 → 状态行 ok 配色", okState.cls.includes("ok"));
check("成功 → 错误列表空态提示", okState.empty === true);

// ---- UV4 `..\main.c` 形态：file 预检 400 → source-line 归一跳转（兜底第二跳）----
await Eval(`window.__fail = window.__fail2; window.__calls = { file: 0, sourceLine: 0 }`);
await Eval(`document.getElementById('btn-code-compile').click()`);
for (let i = 0; i < 40; i++) {
  const done = await Eval(`document.getElementById('code-compile-status').textContent.includes('编译失败')`);
  if (done) break;
  await new Promise((r) => setTimeout(r, 200));
}
await Eval(`document.querySelector('#code-compile-errors .code-compile-error').click()`);
await new Promise((r) => setTimeout(r, 400));
const uv4 = await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  const lines = ta.value.split('\\n');
  let start = 0;
  for (let i = 0; i < 4; i++) start += lines[i].length + 1;
  const end = start + lines[4].length;
  return { start, end, selStart: ta.selectionStart, selEnd: ta.selectionEnd,
    calls: window.__calls, badge: document.querySelector('#code-tabs [data-tab-path="main.c"]') ? 'tab' : null };
})()`);
check("UV4 形态 → 归一跳转：选区第 5 行", uv4.selStart === uv4.start && uv4.selEnd === uv4.end, `sel=${uv4.selStart}-${uv4.selEnd}`);
check("UV4 形态 → 兜底链：file 预检失败 1 次 + source-line 归一 1 次", uv4.calls.file === 1 && uv4.calls.sourceLine === 1, JSON.stringify(uv4.calls));

console.log(failed ? "FAIL " + failed + " 项" : "ALL PASS");
process.exit(failed ? 1 : 0);
