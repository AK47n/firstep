// 代码栏文件树「点文件名打不开文件」的守卫（工单 gen-chain-audit/02）。
//
// 真机 bug（deep 审计 Y1 取证，复现脚本 tests/browser/probe-tree-hit.mjs）：
// 文件行的 ✎/🗑 操作区原本是**绝对定位浮层**（`position:absolute; right:0;
// z-index:2`）盖在文件名按钮上方。hover 显形后把指针吃掉——
//   · 实测文件名按钮 225px 宽，操作容器 131px 且横向覆盖 58%，按钮正中央
//     （playwright hover 的落点）命中的是 `✎ 重命名`；
//   · playwright 连 hover 都做不了（`✎ rename intercepts pointer events`）；
//   · 真机表现：hover 行之后点文件名没有任何反应。
// 试过「给容器收窄宽度」（width:fit-content）——**治不了根**：绝对定位盒在
// `inline-flex` 下被块化，实测宽度仍是 131px（比自身两个按钮还宽）。根因是
// 「操作区与按钮在几何上重叠」，所以修法是让它们**不重叠**：文件行改 flex
// 兄弟布局（按钮 flex:1 占剩余宽度、操作区 flex:none 只占自身宽度）。
//
// 判据分两层：
//   ① 纯 CSS 结构守卫（本文件，node:test 直跑）：操作区不得再浮在文件按钮上；
//   ② 端到端真机断言（tests/browser/code-tree-click.spec.mjs）：真鼠标点文件名
//      → 编辑器真的打开，且 ✎/🗑 仍可点。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url), "utf8");

// 抽出某选择器的**最后一条**声明块（含内嵌注释）——同一选择器在本文件里可能
// 分两处出现（基础样式 + 覆写），生效的是后者。
function blockOf(selector) {
  const at = html.lastIndexOf("\n  " + selector + " {");
  assert.ok(at > 0, `index.html 里找不到 ${selector} 的样式块`);
  const open = html.indexOf("{", at);
  const close = html.indexOf("}", open);
  return html.slice(at, close + 1);
}

test("文件行的行操作区不得浮在文件名按钮上（否则吃完点击区）", () => {
  const fileActions = blockOf(".code-tree-file .code-tree-actions");
  assert.ok(!/position\s*:\s*absolute/.test(fileActions),
    "文件行的操作区又变回绝对定位浮层了 —— hover 显形后会吃掉文件名按钮的指针，"
    + "用户点文件名打不开文件（真机判例见文件头）：\n" + fileActions);
  assert.ok(/flex\s*:\s*none/.test(fileActions),
    "文件行的操作区应当是 flex:none（只占自身宽度），与按钮不重叠：\n" + fileActions);
});

test("文件行必须是 flex 行，文件名按钮占剩余宽度（两区永不重叠）", () => {
  const row = blockOf(".code-tree-file");
  assert.match(row, /display\s*:\s*flex/,
    `.code-tree-file 应为 flex 行容器（按钮 + 操作区 兄弟布局）：\n${row}`);
  const btn = blockOf(".code-tree-file button");
  assert.match(btn, /flex\s*:\s*1\s+1\s+auto/,
    `.code-tree-file button 应 flex:1 1 auto 占剩余宽度：\n${btn}`);
  assert.ok(!/padding-right\s*:\s*4[0-9]px/.test(btn),
    "文件按钮不该再靠 padding-right 预留操作区（改 flex 兄弟后由布局承担）：\n" + btn);
});

test("目录行的操作区仍是绝对定位（summary 结构没改，回退护栏）", () => {
  const dirActions = blockOf(".code-tree-dir .code-tree-actions");
  assert.match(dirActions, /position\s*:\s*absolute/,
    `目录行操作区应保持原样（summary 不便插兄弟）：\n${dirActions}`);
  const summary = blockOf(".code-tree-dir summary");
  assert.match(summary, /padding-right\s*:\s*4[0-9]px/,
    `.code-tree-dir summary 的 padding-right 仍是操作区预留：\n${summary}`);
});

test("操作按钮 hover 显形规则仍在（隐藏态不得改成 visibility 之类的占位）", () => {
  assert.match(html, /\.code-tree-file:hover \.code-tree-actions\s*\{\s*display:\s*inline-flex/,
    "文件行 hover 显形规则被改掉了 —— 操作按钮会永远看不见或永远占位");
  const base = blockOf(".code-tree-actions");
  assert.match(base, /display\s*:\s*none/,
    "操作区默认必须是 display:none（未 hover 不出现）：\n" + base);
});
