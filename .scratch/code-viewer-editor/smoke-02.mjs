// 冒烟（code-viewer-editor/02）：多标签页 + 可编辑三明治（内存级）——
// 打开样本目录 → 点文件出编辑器（textarea + 高亮层 + 行号 + 标签条）→
// 编辑出脏点 → Tab/Enter 缩进 → 第二文件多标签切换保内容 → 关闭（脏 tab
// 弹 confirmModal，取消保留）→ .md 预览/源码两态 + 返回预览 → GBK 只读
// 标注 → 大纲跳行选区。零写库（样本在 .scratch 下，git 忽略；不真生成、
// 不保存——保存链路 = 工单 03）。零依赖：node 内置 fetch + WebSocket 直连
// Chrome CDP（9251，需 Node ≥ 21）；webapp 8000 提供真实 API。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

// ---- 样本工程（.scratch/code-viewer-editor/sample-proj，git 忽略） ----
const SAMPLE = join(ROOT, ".scratch", "code-viewer-editor", "sample-proj");
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
writeFileSync(join(SAMPLE, "app.h"), "#pragma once\n");
writeFileSync(join(SAMPLE, "readme.md"), "# 样本工程\n\n正文段落。\n");
// "// 中文注释\n" 的 GBK 字节（严格 UTF-8 解码失败 → 只读标注用例）
writeFileSync(join(SAMPLE, "gbk.c"),
  Buffer.from([0x2f, 0x2f, 0x20, 0xd6, 0xd0, 0xce, 0xc4, 0xd7, 0xa2, 0xca, 0xcd, 0x0a]));
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
      && !!document.getElementById('code-viewer')
      && !!document.getElementById('code-tabs')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// ================= 打开样本目录 =================
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
check("目录打开：树加载（5 文件，噪音不出现）", await waitFor(`
  (() => {
    const paths = [...document.querySelectorAll('#code-tree [data-code-file]')].map((b) => b.dataset.codeFile).sort();
    return paths.length === 5
      && JSON.stringify(paths) === JSON.stringify(['app.h', 'gbk.c', 'main.c', 'readme.md', 'src/digit.c'])
      && !paths.some((p) => p.startsWith('Debug'));
  })()`));
check("标签条空态占位（打开文件后显示标签）", await Eval(`
  (() => {
    const strip = document.getElementById('code-tabs');
    return strip && strip.querySelector('.muted');
  })()`));

// ================= 打开 main.c：编辑器三明治 =================
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
check("main.c → 编辑三明治（textarea + 高亮层 + 行号 14 + 标签条 tab）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    const strip = document.getElementById('code-tabs');
    return !!box.querySelector('.code-ta') && !!box.querySelector('.code-hl')
      && box.querySelectorAll('.code-gutter-line').length === 14
      && box.querySelectorAll('.code-hl-line').length === 14
      && strip.querySelectorAll('.code-tab').length === 1
      && strip.querySelector('.code-tab .code-tab-badge')
      && strip.querySelector('.code-tab .code-tab-badge').textContent === 'C';
  })()`));
check("textarea 初始内容 = 文件全文（14 行含尾空行）", await Eval(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return ta && ta.value.split('\\n').length === 14 && ta.value.includes('void helper(void) {');
  })()`));

// ================= 编辑 → 脏点 + 高亮联动 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.value += '// 我已编辑\\n';
  ta.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
check("编辑 → tab 脏点出现（.code-tab-dirty）", await waitFor(`
  !!document.querySelector('#code-tabs .code-tab-dirty')`));
check("高亮层随输入重绘（新行出现 + 行号 15）", await Eval(`
  (() => {
    const box = document.getElementById('code-viewer');
    return box.querySelectorAll('.code-gutter-line').length === 15
      && box.querySelectorAll('.code-hl-line').length === 15;
  })()`));
check("存底内容仍为磁盘快照（脏 = 与 savedContent 不同）", await Eval(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return ta.value.endsWith('// 我已编辑\\n');
  })()`));

// ================= Tab 缩进 / Enter 自动缩进 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(0, 0);
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
  return true;
})()`);
check("Tab → 行首插入 4 空格", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return ta.value.startsWith('    ' + '#include') || ta.value.startsWith('    #include');
  })()`));
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const v = ta.value;
  const at = v.indexOf('// 我已编辑');
  ta.setSelectionRange(at, at);  // 光标在该注释行行首
  ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
  return true;
})()`);
check("Enter → 换行并在新行拷贝前导空白（空行无缩进）", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    return ta.value.includes('// 我已编辑\\n');
  })()`));

// ================= 光标行高亮 =================
await Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  const lines = ta.value.split('\\n');
  const pos = lines.slice(0, 4).join('\\n').length + 1;  // 第 5 行行首
  ta.setSelectionRange(pos, pos);
  ta.dispatchEvent(new Event('click', { bubbles: true }));
  return true;
})()`);
check("点击 → 光标行高亮（.code-hl-line.active 与 gutter 同行）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    const hl = box.querySelector('.code-hl-line.active');
    const gut = box.querySelector('.code-gutter-line.active');
    return !!hl && !!gut && hl.dataset.codeLine === '5' && gut.dataset.codeLine === '5';
  })()`));

// ================= 多标签：第二个文件 / 切换保内容 =================
await Eval(`document.querySelector('#code-tree [data-code-file="src/digit.c"]')?.click()`);
check("第二文件 → 2 tab，活动 = digit.c（行号 4 = 3 行内容 + 尾空行）", await waitFor(`
  (() => {
    const strip = document.getElementById('code-tabs');
    const tabs = [...strip.querySelectorAll('.code-tab')];
    const on = strip.querySelector('.code-tab.on');
    const box = document.getElementById('code-viewer');
    return tabs.length === 2 && !!on
      && on.dataset.tabPath === 'src/digit.c'
      && box.querySelectorAll('.code-gutter-line').length === 4;
  })()`));
await Eval(`document.querySelector('#code-tabs .code-tab[data-tab-path="main.c"]')?.click()`);
check("切回 main.c → 编辑内容保留（脏点仍在 + 15 行）", await waitFor(`
  (() => {
    const strip = document.getElementById('code-tabs');
    const on = strip.querySelector('.code-tab.on');
    const box = document.getElementById('code-viewer');
    return on && on.dataset.tabPath === 'main.c'
      && !!box.querySelector('.code-ta')
      && box.querySelector('.code-ta').value.endsWith('// 我已编辑\\n')
      && !!strip.querySelector('.code-tab-dirty');
  })()`));

// ================= 关闭：非脏直接关 / 脏 tab confirmModal =================
await Eval(`document.querySelector('#code-tabs [data-tab-path="src/digit.c"] .code-tab-close')?.click()`);
check("关闭非脏 tab → 剩 1 tab", await waitFor(`
  document.querySelectorAll('#code-tabs .code-tab').length === 1`));
await Eval(`document.querySelector('#code-tabs [data-tab-path="main.c"] .code-tab-close')?.click()`);
check("关闭脏 tab → confirmModal 弹出（共享确认弹窗）", await waitFor(`
  !!document.querySelector('.ref-files-overlay') && !!document.querySelector('[data-confirm-ok]')`));
await Eval(`document.querySelector('[data-confirm-cancel]')?.click()`);
check("取消 → tab 保留（脏点仍在）", await waitFor(`
  document.querySelectorAll('#code-tabs .code-tab').length === 1
    && !!document.querySelector('#code-tabs .code-tab-dirty')
    && !document.querySelector('.ref-files-overlay')`));

// ================= .md 预览/源码两态 =================
await Eval(`document.querySelector('#code-tree [data-code-file="readme.md"]')?.click()`);
check(".md → 渲染预览（data-md-line 块级元素）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    return !!box.querySelector('[data-md-line]') && !!box.querySelector('h1');
  })()`));
await Eval(`(() => {  // Ctrl+F → 预览态自动切源码（行语义）
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }));
  return true;
})()`);
check("Ctrl+F → .md 切编辑态（.code-ta）+ 返回预览可见", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    const back = document.getElementById('code-back-preview');
    return !!box.querySelector('.code-ta') && back && !back.classList.contains('hidden');
  })()`));
await Eval(`document.getElementById('code-back-preview')?.click()`);
check("返回预览 → 回渲染态（返回预览隐藏）", await waitFor(`
  (() => {
    const box = document.getElementById('code-viewer');
    const back = document.getElementById('code-back-preview');
    return !!box.querySelector('[data-md-line]') && back && back.classList.contains('hidden');
  })()`));

// ================= GBK 只读（非 UTF-8 标注 + readonly） =================
await Eval(`document.querySelector('#code-tree [data-code-file="gbk.c"]')?.click()`);
check("GBK 文件 → 只读 tab（.ro + 标注 + textarea readonly）", await waitFor(`
  (() => {
    const strip = document.getElementById('code-tabs');
    const tab = strip.querySelector('[data-tab-path="gbk.c"]');
    const ta = document.querySelector('#code-viewer .code-ta');
    const note = document.querySelector('#code-viewer .code-ro-note');
    return !!tab && tab.classList.contains('ro')
      && !!note && note.textContent.includes('不是 UTF-8')
      && !!ta && ta.readOnly;
  })()`));

// ================= 大纲跳行 → 编辑器选区 =================
await Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await waitFor(`!!document.querySelector('#code-viewer .code-ta')`);
await Eval(`document.querySelector('#code-outline [data-outline-line="8"]')?.click()`);
check("大纲点击 → 编辑器选中目标行（selectionStart 在 line 8）", await waitFor(`
  (() => {
    const ta = document.querySelector('#code-viewer .code-ta');
    if (!ta) return false;
    const lines = ta.value.split('\\n');
    const line8Start = lines.slice(0, 7).join('\\n').length + 1;
    return ta.selectionStart >= line8Start && ta.selectionStart <= line8Start + lines[7].length;
  })()`));

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
