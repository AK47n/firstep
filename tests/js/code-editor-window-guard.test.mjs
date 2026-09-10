// tests/js/code-editor-window-guard.test.mjs — 代码编辑器窗口/折叠渲染守卫
// （2026-09-09 在途盘点第六轮补口）。
//
// 两个缺陷在 CDP 冒烟里现形（smoke-01 5 项假红 / smoke-07 1 项红），均为 DOM
// 胶水层、纯件单测覆盖不到，本守卫做静态源断言把它们钉住：
//
//   ① 块选区坍缩：窗口化（08/09）后 applyEdit 的「非折叠窗口化」分支只把 end
//      传给 syncTail（窗口按光标重装），多行 Shift+Tab / Alt+↑↓ / Shift+Alt+↑↓
//      的纯件契约 {start, end} 被坍缩成光标 → 修复 = 该分支补
//      `if (start !== end) taSetRange(start, end)`。
//   ② 幽灵占位行：占位行被整体替换 → 折叠全展开、可见行数恰好不变时，syncTail
//      走增量 patch 分支（只 patch lines/hl、不动 gutter），旧折叠 gutter
//      （占位行 + 跳号行号）留在 DOM → 修复 = 该分支加 `!winCache.foldedView`
//      前提（上一版 gutter 不是折叠视图才允许增量）。
//
// 另钉 CDP 冒烟里的块选区期望不被悄悄放宽（验收证据不许静默变弱）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const ui = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/codeeditor.js", import.meta.url), "utf8");
const smoke01 = readFileSync(
  new URL("../../.scratch/code-page-vscode-overhaul/smoke-01.mjs", import.meta.url), "utf8");

test("applyEdit 非折叠窗口化分支：块选区还原（start !== end → taSetRange）", () => {
  const fnAt = ui.indexOf("function applyEdit(");
  assert.ok(fnAt > 0, "找不到 applyEdit");
  const winAt = ui.indexOf("if (taWinInfo && !viewModel) {", fnAt);
  const foldAt = ui.indexOf("if (viewModel) {", fnAt);
  assert.ok(winAt > 0 && foldAt > winAt, "applyEdit 分支结构变化（窗口化 / 折叠分支顺序）");
  const branch = ui.slice(winAt, foldAt);
  assert.ok(branch.includes("syncTail(Math.max(0, end | 0));"),
    "窗口化分支的 syncTail 调用变了——块选区还原的前提要重新确认");
  assert.ok(branch.includes("if (start !== end) taSetRange(start, end);"),
    "块选区还原缺失：多行行操作（Shift+Tab / Alt+↑↓ / Shift+Alt+↑↓）会坍缩成光标");
});

test("syncTail 增量 patch：上一版 gutter 为折叠视图时不走（防幽灵占位行）", () => {
  const at = ui.indexOf("const viewText = viewModel ? viewModel.text : tab.content;");
  assert.ok(at > 0, "找不到 syncTail 的 viewText 计算");
  const tail = ui.slice(at, at + 1200);
  assert.ok(tail.includes("!winCache.foldedView"),
    "增量 patch 分支缺 foldedView 前提：折叠全展开且行数不变时 gutter 不重建（幽灵占位行 + 行号错位）");
  assert.ok(ui.includes("foldedView: !!viewModel,"),
    "winBuild 未记录 foldedView（gutter 来源标记）——增量 patch 判据失去依据");
});

test("CDP 冒烟 smoke-01：块选区期望仍在（防悄悄放宽）", () => {
  for (const needle of [
    'value: "a\\n  b\\nc", sel: [0, 5]',   // Shift+Tab 多行反缩进：选区覆盖整段
    'value: "a\\nb\\nb", sel: [4, 4]',     // Shift+Alt+↓ 复制行：光标落副本
  ]) {
    assert.ok(smoke01.includes(needle), `smoke-01 缺块选区断言：${needle}`);
  }
});

// ---------------------------------------------------------------------------
// 第八轮补口（2026-09-09 CDP 实跑发现的两个缺陷）
// ---------------------------------------------------------------------------

test("marksCache 复用前提含编译错误签名（防重编成功后错误标记残留）", () => {
  // 缺陷：winRenderMarks 的复用分支把「缓存里带旧 error 段的清单」+「本次
  // 当前文件的错误段」拼起来；错误清空时 extra 为空 → 缓存里的旧 .code-mark-error
  // 段被原样复用，直到切标签（renderPane 清缓存）才消失。
  // 实测：code-editor-refine/smoke-05 场景 5「重编成功后色点/标记清除」FAIL
  // （gutter 色点清了、标记层残留 4 个 .code-mark-error）。
  const at = ui.indexOf("function winRenderMarks(");
  assert.ok(at > 0, "找不到 winRenderMarks");
  const body = ui.slice(at, at + 2600);
  assert.ok(body.includes("const compileSig = compileSigOf(errLines);"),
    "winRenderMarks 未计算编译错误签名");
  assert.ok(body.includes("&& marksCache.compileSig === compileSig"),
    "marksCache 复用前提缺编译错误签名：重编成功后旧错误标记会被复用回来");
  // 写缓存的三个出口都要带上签名（漏一处 = 复用判定永远不命中，退化成每次全量）
  const writes = ui.match(/marksCache = \{[^}]*\}/g) || [];
  assert.ok(writes.length >= 3, `marksCache 写入点数量异常：${writes.length}`);
  for (const w of writes) {
    assert.ok(w.includes("compileSig"), `marksCache 写入点缺 compileSig：${w}`);
  }
});

test("openEditorFile：晚到的旧请求不抢活动标签（openSeq 守卫）", () => {
  // 缺陷：openEditorFile 是 async 且三处调用点都不 await，快速连点两个文件时
  // 后发起的请求可能先返回 → 先发起的请求晚到后 activateTab 抢走活动标签
  // （实测状态 {"tabs":["b.c","a.c"],"active":"a.c","dirty":["a.c"]}）。
  const at = ui.indexOf("export async function openEditorFile(");
  assert.ok(at > 0, "找不到 openEditorFile");
  const body = ui.slice(at, at + 2600);
  assert.ok(body.includes("const req = ++openSeq;"), "openEditorFile 未登记请求序号");
  assert.ok(body.includes("const stale = req !== openSeq;"), "openEditorFile 未判定晚到请求");
  assert.ok(body.includes("if (!stale) activateTab(path);"),
    "晚到的旧请求仍会 activateTab（抢走用户已切到的文件）");
  assert.ok(/renderTabs\(\);\s*\n\s*if \(!stale\) activateTab\(path\);/.test(body),
    "晚到请求新增的标签未渲染：模型 2 个 tab / 标签栏 1 个（smoke-02 检查 0 偶发 FAIL 的另一半）");
  assert.ok(body.includes("return !stale;"),
    "openEditorFile 未返回「目标是否已成为活动标签」（editJumpToFile 依赖它）");
  // editJumpToFile：目标不是活动标签时不跳行（否则跳行落在别的文件上）
  const jumpAt = ui.indexOf("export async function editJumpToFile(");
  assert.ok(jumpAt > 0, "找不到 editJumpToFile");
  const jump = ui.slice(jumpAt, jumpAt + 700);
  assert.ok(jump.includes("if (active === false) return;"),
    "editJumpToFile 未守卫晚到请求：跳行会落在别的文件上");
});

test("CDP 冒烟 smoke-02：开标签后等 b.c 成为活动标签（防并发打开竞态）", () => {
  const smoke02 = readFileSync(
    new URL("../../.scratch/code-editor-refine/smoke-02.mjs", import.meta.url), "utf8");
  assert.ok(smoke02.includes(
    'await waitFor(`document.querySelector(\'#code-tabs .code-tab.on\')?.dataset.tabPath === "b.c"`);'),
    "smoke-02 缺「等 b.c 成为活动标签」等待：两次点击并发时会改到 a.c（场景 2 偶发 FAIL）");
});

// ---------------------------------------------------------------------------
// 工单 code-editor-perf-structural/01 补口（2026-09-09 第九轮）
// ---------------------------------------------------------------------------

test("syncTail 同步输入路径不读/写 scrollTop：强制深布局来源（结构性编辑 76ms → 10ms）", () => {
  // 缺陷：syncTail 里「行数变化 → 读 box.scrollTop/Left → winApplySize →
  // 写回同值」的滚动恢复。读写都发生在 winRender（写 innerHTML）+ winApplySize
  // （写 .code-edit 高度）之后 —— 布局已失效，读 scrollTop 强制一次整树深布局、
  // 写 scrollTop（需要 scroll extent）再强制一次；5000 行实测读 33.7ms + 写
  // 30.6ms/次，是回车同步耗时（78.9ms）的绝对大头。写回的值与刚读到的值相同，
  // 语义上是 no-op（浏览器自身保持 scrollTop，内容变矮时按需钳制）。
  // 修法 = 删掉这一次读写；滚动位置改由浏览器保持，窗口切片用 winView 缓存。
  const at = ui.indexOf("function syncTail(");
  assert.ok(at > 0, "找不到 syncTail");
  const nextFn = ui.indexOf("\nfunction ", at + 10);
  const raw = ui.slice(at, nextFn > at ? nextFn : at + 4000);
  assert.ok(raw.length > 1000, "syncTail 函数体提取异常（函数结构变化）");
  // 去注释后判定（注释里会写到历史实现与 `box.scrollTop` 字样，不算代码）
  const body = raw.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  for (const bad of ["box.scrollTop", "box.scrollLeft", "box.clientHeight"]) {
    assert.ok(!body.includes(bad),
      `syncTail 重新读了 ${bad}：同步输入路径的布局强制读（回车同步耗时回到 ~70ms）`);
  }
  assert.ok(!/box\.scroll(?:Top|Left)\s*=/.test(body),
    "syncTail 重新写了 scrollTop/scrollLeft：赋值需要 scroll extent，同样强制布局");
  // winView 缓存必须仍是窗口切片的来源（否则窗口按陈旧/缺失值切片）
  assert.ok(ui.includes("winView = { scrollTop: box.scrollTop, viewportH: box.clientHeight };"),
    "winReadView 不再刷新 winView 缓存：窗口切片失去滚动位置来源");
  assert.ok(ui.includes("return codeWindowRange(winView.scrollTop, winView.viewportH, winLineH,"),
    "winWindow 不再用 winView 缓存：删掉实时读之后窗口切片无从取值");
});

test("性能工单验收脚本在位（防验收证据被删/静默放宽）", () => {
  const verify = readFileSync(
    new URL("../../.scratch/code-editor-perf-structural/verify-structural-edit.mjs", import.meta.url), "utf8");
  for (const needle of [
    "同步路径零布局强制读",
    "中部回车：滚动位置不跳（scrollTop 不变）",
    "中部回车：可见窗口行号序列不变（视口不位移）",
    "回车同步耗时 < 50ms（均值）",
  ]) {
    assert.ok(verify.includes(needle), `验收脚本缺断言：${needle}`);
  }
});

test("winRenderMarks 复用分支：缓存只存基础清单（状态段写回 = 旧括号/词标记复用回来）", () => {
  // 缺陷（2026-09-09 第九轮顺带修出）：复用分支把 `base.concat(extra)` 的结果
  // 写回 marksCache.marks —— 下次复用即把**上一次的括号/词/查找段**当基础段
  // 带回来。实测两处红：polish/smoke-06「光标移开 → 括号标记消失」（标记不消失）、
  // polish/smoke-05「光标移到 '{' 符号位 → 选中词标记消失」。
  const at = ui.indexOf("function winRenderMarks(");
  assert.ok(at > 0, "找不到 winRenderMarks");
  const nextFn = ui.indexOf("\nfunction ", at + 10);
  const raw = ui.slice(at, nextFn > at ? nextFn : at + 4000);
  const code = raw.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  assert.ok(code.includes("const base = marksCache.marks;"),
    "winRenderMarks 未区分基础清单（状态段会污染缓存）");
  assert.ok(/marks = extra\.length \? base\.concat\(extra\) : base;/.test(code),
    "合并式不是 base.concat(extra)（或又改回从 marksCache.marks 直接拼）");
  assert.ok(/marks: base \};/.test(code),
    "marksCache 未写回基础清单：状态段（括号/词/查找/错误）被当基础段缓存");
  assert.ok(!/marks: marks\s*\}/.test(ui),
    "marksCache 写回了合并结果 marks：下次复用会把旧状态段带回来");
  // 冒烟断言不许被悄悄放宽（两处红都是它抓到的）
  const smoke05 = readFileSync(
    new URL("../../.scratch/code-editor-vscode-polish/smoke-05.mjs", import.meta.url), "utf8");
  const smoke06 = readFileSync(
    new URL("../../.scratch/code-editor-vscode-polish/smoke-06.mjs", import.meta.url), "utf8");
  assert.ok(smoke06.includes("光标移开 → 括号标记消失"), "smoke-06 缺「括号标记消失」断言");
  assert.ok(smoke05.includes("选中词标记消失"), "smoke-05 缺「词标记消失」断言");
});

test("smoke-08「窗口内滚动零 DOM」断言不写死位移（窗口边界由纯件现算）", () => {
  // 旧断言写死 +5px：窗口 [start,end) 由 codeWindowRange 按滚动偏移精确重算，
  // 5px 可能跨过底部边界 → DOM 行数变 1 是正确行为，断言却判红。修订 = 用同一
  // 纯件现算「不跨边界」的位移。
  const smoke08 = readFileSync(
    new URL("../../.scratch/code-page-vscode-overhaul/smoke-08.mjs", import.meta.url), "utf8");
  assert.ok(smoke08.includes("codeWindowRange"), "smoke-08 未用纯件现算窗口边界");
  assert.ok(!smoke08.includes("b.scrollTop += 5"), "smoke-08 又写死了 +5px 位移");
});
