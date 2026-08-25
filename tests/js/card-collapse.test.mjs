// collapseToggleAll / collapseBtnLabel 纯函数单测（工单 ui-polish-4/01 + ui-polish-11/05）：
// 生成页卡片折叠决策 + 折叠按钮 aria-label 同步（读屏可感知折叠/展开状态）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
// 抽取 collapseBtnLabel + syncCollapseBtn + collapseToggleAll 三个相邻函数
// （后者调用前者，需同一作用域构造）
const match = html.match(
  /function collapseBtnLabel[\s\S]*?function syncCollapseBtn[\s\S]*?function collapseToggleAll[\s\S]*?\n\}/
);
assert.ok(
  match,
  "index.html 中未找到 collapseBtnLabel/syncCollapseBtn/collapseToggleAll 函数体（改名了？）"
);
const fns = new Function(
  match[0] + "\nreturn { collapseBtnLabel, syncCollapseBtn, collapseToggleAll };"
)();
const { collapseBtnLabel, collapseToggleAll } = fns;
// 产物守卫：正则可能静默截断（惰性匹配首个 \n}），确保三函数都抽出
for (const name of ["collapseBtnLabel", "syncCollapseBtn", "collapseToggleAll"]) {
  assert.equal(typeof fns[name], "function", `${name} 未从 index.html 抽取成功`);
}

// 假卡片：只实现 .step-no 查询、classList.toggle、.card-collapse title/aria-label 回写
function fakeCard(n) {
  const state = { collapsed: false, btnTitle: "", ariaLabel: "" };
  const btnObj = {
    get title() { return state.btnTitle; },
    set title(v) { state.btnTitle = v; },
    setAttribute(k, v) { if (k === "aria-label") state.ariaLabel = v; },
  };
  return {
    _state: state,
    querySelector: (sel) =>
      sel === ".step-no" ? { textContent: String(n) }
      : sel === ".card-collapse" ? btnObj
      : null,
    classList: { toggle: (k, v) => { state.collapsed = v; } },
  };
}
const cards = [1, 2, 3, 4, 5].map(fakeCard);

test("collapseBtnLabel：折叠/展开语义文案", () => {
  assert.equal(collapseBtnLabel(true), "展开该卡片");
  assert.equal(collapseBtnLabel(false), "折叠该卡片");
});

test("折叠模式：已完成折叠、未完成保持展开，title 与 aria-label 同步", () => {
  const out = collapseToggleAll(cards, [1, 2, 3], true);
  assert.deepEqual(
    out.map((o) => ({ n: o.n, collapsed: o.collapsed })),
    [
      { n: 1, collapsed: true },
      { n: 2, collapsed: true },
      { n: 3, collapsed: true },
      { n: 4, collapsed: false },
      { n: 5, collapsed: false },
    ]
  );
  assert.equal(cards[0]._state.collapsed, true);
  assert.equal(cards[3]._state.collapsed, false);
  assert.equal(cards[0]._state.btnTitle, "展开");
  assert.equal(cards[0]._state.ariaLabel, "展开该卡片");
  assert.equal(cards[3]._state.btnTitle, "折叠");
  assert.equal(cards[3]._state.ariaLabel, "折叠该卡片");
});

test("展开模式：全部展开（collapse=false）", () => {
  const out = collapseToggleAll(cards, [1, 2, 3], false);
  assert.ok(out.every((o) => !o.collapsed));
  assert.equal(cards[0]._state.btnTitle, "折叠");
  assert.equal(cards[0]._state.ariaLabel, "折叠该卡片");
});

test("空完成集合：折叠模式也不折叠任何卡", () => {
  const out = collapseToggleAll(cards, [], true);
  assert.ok(out.every((o) => !o.collapsed));
});

test("无 .step-no 的卡（如实例卡）永不折叠", () => {
  const noBadge = { querySelector: () => null, classList: { toggle: (k, v) => { noBadge._c = v; } }, _c: false };
  const out = collapseToggleAll([noBadge], [1, 2], true);  // NaN 不在完成集合
  assert.ok(Number.isNaN(out[0].n));
  assert.equal(out[0].collapsed, false);
});
