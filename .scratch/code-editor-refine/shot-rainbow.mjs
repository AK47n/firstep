// B6（code-editor-refine/04 收口）：括号彩虹**双主题截图** + 逐层颜色断言。
//
// 源工单验收：「if(){while(){...}} 多层括号逐层颜色不同；深浅主题均可见（各截图一张）」。
// 实现：`fx/code-brackets.js` 的 bracketDepthMarks → `kind: bracket-depth-N` 直出 class
// （`.code-mark-bracket-depth-N` → `var(--bracket-rainbow-N)`，深浅主题各一套色）。
// 本脚本：打开 sample-proj-04/nest.c（内含真括号 + 注释/字符串里的假括号），
// 断「深度标记 ≥3 个且颜色互不相同」，两主题各截一张图。
//
// 依赖：webapp 8000 + Chrome headless CDP 9251。
import { writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { rebuildTab, connect } from "../cdp-harness.mjs";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const PORT = 9251;
const SAMPLE = join(ROOT, ".scratch", "code-editor-refine", "sample-proj-04");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const t = await rebuildTab({ port: PORT });
if (!t) { console.error("重建标签页失败"); process.exit(1); }
const c = await connect({ port: PORT, timeoutMs: 20000 });
const Eval = (e) => c.Eval(e);

let failed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (!ok) failed++;
};
const shot = async (name) => {
  const s = await c.cdp("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(ROOT, ".scratch", "code-editor-refine", name), Buffer.from(s.result.data, "base64"));
  console.log("截图已存档 " + name);
};

for (let i = 0; i < 120; i++) {
  if (await Eval(`document.readyState === 'complete' && !!document.getElementById('code-viewer')`)) break;
  await sleep(250);
}

// 深色主题起点（脚本自带前提，不依赖上一次运行留下的 localStorage）
await Eval(`document.documentElement.setAttribute('data-theme', 'dark')`);

// 打开样本工程 → nest.c
await Eval(`import('/js/ui/codeview.js').then((m) => m.openCodeViewer(${JSON.stringify(SAMPLE)}))`);
for (let i = 0; i < 60; i++) {
  if (await Eval(`!!document.querySelector('#code-tree [data-code-file="nest.c"]')`)) break;
  await sleep(250);
}
await Eval(`document.querySelector('#code-tree [data-code-file="nest.c"]')?.click()`);

const waitMarks = async () => {
  for (let i = 0; i < 60; i++) {
    const n = await Eval(`document.querySelectorAll('[class*="code-mark-bracket-depth-"]').length`);
    if (n >= 3) return n;
    await sleep(250);
  }
  return 0;
};
const colors = () => Eval(`[...new Set([...document.querySelectorAll('[class*="code-mark-bracket-depth-"]')]
  .map((m) => getComputedStyle(m).backgroundColor + '|' + m.className))]`);
const depthClasses = () => Eval(`[...new Set([...document.querySelectorAll('[class*="code-mark-bracket-depth-"]')]
  .flatMap((m) => [...m.classList].filter((x) => x.startsWith('code-mark-bracket-depth-'))))].sort()`);

const darkN = await waitMarks();
const darkColors = await colors();
const darkClasses = await depthClasses();
check("B6 深色：nest.c 括号深度标记 ≥3 个", darkN >= 3, "marks=" + darkN);
check("B6 深色：逐层颜色互不相同（≥3 色）", darkColors.length >= 3, JSON.stringify(darkColors));
check("B6 深色：深度 class 至少覆盖 3 层（depth-0/1/2…）", darkClasses.length >= 3, JSON.stringify(darkClasses));
await shot("shot-04-rainbow-dark.png");

// 浅色：与设置页主题开关同一属性（html[data-theme="light"] 覆盖令牌）
await Eval(`document.documentElement.setAttribute('data-theme', 'light')`);
await sleep(400);
const lightColors = await colors();
check("B6 浅色：逐层颜色互不相同（≥3 色）", lightColors.length >= 3, JSON.stringify(lightColors));
check("B6 浅色 ≠ 深色（主题令牌确实换了一套）",
  JSON.stringify(lightColors.map((s) => s.split("|")[0])) !== JSON.stringify(darkColors.map((s) => s.split("|")[0])));
await shot("shot-04-rainbow-light.png");

// 纯件层交叉核对：真括号被标记，注释/字符串里的假括号不被标记
const pure = await Eval(`(async () => {
  const m = await import('/js/fx/code-brackets.js');
  const dir = ${JSON.stringify(SAMPLE.replace(/\\/g, "/"))};
  const r = await (await fetch('/api/code/file?dir=' + encodeURIComponent(dir) + '&path=nest.c')).json();
  const marks = m.bracketDepthMarks(r.content);
  return { lines: marks.map((x) => x.line + ':' + x.start), kinds: [...new Set(marks.map((x) => x.kind))].sort(), text: r.content };
})()`);
console.log("纯件标记（供核对「假括号不误着色」）：", JSON.stringify(pure.lines), JSON.stringify(pure.kinds));
// nest.c 里的真括号：第 2 行 {、第 3 行 ( {、第 4 行 ( {、第 5 行 []、第 6 行 () —— 注释行 1、
// 字符串 "{ fake"、行尾注释 "( fake" 都不应进标记（列号断言见 tests/js 的深度单测）。
check("B6 纯件：标记只落在含真括号的行（第 1/6 行注释里的假括号不进）",
  pure.lines.length >= 6 && !pure.lines.some((l) => l.startsWith("1:")),
  JSON.stringify(pure.lines));

console.log("---- B6 总览 ----");
console.log((failed ? "FAILED " : "OK ") + "failed=" + failed);
c.close();
process.exit(failed ? 1 : 0);
