// 诊断（code-ide-ai/smoke-05「引用插入输入框（契约格式）」等 4 项 FAIL）：
// 打印 .code-ta 的值/选区、浮动按钮可见性、点击后输入框内容。
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync, rmSync, writeFileSync, writeSync } from "node:fs";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const PORT = 9231, PAGE_URL = "http://127.0.0.1:8000/";
const SAMPLE = join(ROOT, ".scratch", "code-ide-ai", "sample-proj");
const log = (s) => writeSync(2, s + "\n");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const OLD_MAIN = "int main(void) {\n  // TODO: init sensor\n  init();\n  return 0;\n}\n";
rmSync(SAMPLE, { recursive: true, force: true });
mkdirSync(join(SAMPLE, "src"), { recursive: true });
writeFileSync(join(SAMPLE, "main.c"), OLD_MAIN, "utf8");
writeFileSync(join(SAMPLE, "src", "app.c"), "#include <stdint.h>\n", "utf8");
writeFileSync(join(SAMPLE, "readme.md"), "# 样本\n", "utf8");

await rebuildTab({ port: PORT, pageUrl: PAGE_URL });
const c = await connect({ port: PORT, pageUrl: PAGE_URL, timeoutMs: 15000 });
await c.cdp("Page.enable");
await c.Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
await c.waitFor(`!!document.querySelector('#code-tree [data-code-file="main.c"]')`, 10000);
await c.Eval(`document.querySelector('#code-tree [data-code-file="main.c"]')?.click()`);
await c.waitFor(`!!document.querySelector('#code-viewer .code-ta')`, 10000);
await sleep(800);

log("ta 值： " + JSON.stringify(await c.Eval(`document.querySelector('#code-viewer .code-ta').value`)));
log("模型内容： " + JSON.stringify(await c.Eval(
  `import('/js/ui/codeeditor.js').then((m) => m.getActiveTab() && m.getActiveTab().content)`)));

await c.Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  ta.focus();
  ta.setSelectionRange(18, 41);
  ta.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
  return true;
})()`);
await sleep(600);
log("选区： " + JSON.stringify(await c.Eval(`(() => {
  const ta = document.querySelector('#code-viewer .code-ta');
  return { start: ta.selectionStart, end: ta.selectionEnd, sel: ta.value.slice(ta.selectionStart, ta.selectionEnd) };
})()`)));
log("浮动按钮： " + JSON.stringify(await c.Eval(`(() => {
  const b = document.querySelector('.code-ai-selection-btn');
  return b ? { hidden: b.classList.contains('hidden'), left: b.style.left, top: b.style.top, text: b.textContent } : null;
})()`)));
await c.Eval(`document.querySelector('.code-ai-selection-btn')?.click(); true`);
await sleep(600);
log("输入框： " + JSON.stringify(await c.Eval(
  `document.getElementById('code-ai-chat-input')?.value ?? null`)));
log("焦点： " + JSON.stringify(await c.Eval(
  `document.activeElement && (document.activeElement.id || document.activeElement.tagName)`)));
c.close();
