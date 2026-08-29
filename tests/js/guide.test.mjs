// guide.test.mjs — 新手指引教程页纯函数与静态标记契约（工单 beginner-guide/01）：
// fx/guide.js 的 GUIDE_TABS（4 子页签）/ guidePanelFor / guideTabNext 单测，
// 并读 index.html 钉住契约四联：按钮 data-guide-tab、面板 id guide-panel-*、
// 出现顺序、与 GUIDE_TABS 一一对应（防键四处漂移）。仿 fx/revise-tabs.test.mjs
// 与 nav-tabs-guard.test.mjs 先例。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { GUIDE_TABS, guidePanelFor, guideTabNext } from "../../src/contest_generator/static/js/fx/guide.js";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);

function countOccurrences(text, needle) {
  return text.split(needle).length - 1;
}

test("GUIDE_TABS：恰为 4 个子页签，key 唯一、文案非空", () => {
  assert.equal(GUIDE_TABS.length, 4, "教程应为 4 个子页签（准备/做题主线/编译与上板/交付与收尾）");
  const keys = GUIDE_TABS.map((t) => t.key);
  assert.equal(new Set(keys).size, keys.length, "子页签 key 不得重复");
  for (const t of GUIDE_TABS) {
    assert.ok(t.key && t.label, "子页签应同时有 key 与 label：" + JSON.stringify(t));
  }
});

test("guidePanelFor：面板 id 契约（guide-panel-<key>）", () => {
  for (const t of GUIDE_TABS) {
    assert.equal(guidePanelFor(t.key), "guide-panel-" + t.key);
  }
});

test("guideTabNext：方向键循环（回绕）", () => {
  assert.equal(guideTabNext(0, 1, 4), 1);
  assert.equal(guideTabNext(3, 1, 4), 0, "末位 +1 应回绕到首位");
  assert.equal(guideTabNext(0, -1, 4), 3, "首位 -1 应回绕到末位");
  assert.equal(guideTabNext(1, -1, 4), 0);
  assert.equal(guideTabNext(0, 1, 0), -1, "count=0 应返回 -1");
  assert.equal(guideTabNext(2, 1, 4), 3);
});

test("HTML 契约：每个子页签恰有一个按钮与一个面板，顺序与 GUIDE_TABS 一致", () => {
  for (const t of GUIDE_TABS) {
    assert.equal(countOccurrences(html, 'data-guide-tab="' + t.key + '"'), 1,
      "子页签 '" + t.key + "' 的按钮应恰好出现一次");
    assert.equal(countOccurrences(html, 'id="' + guidePanelFor(t.key) + '"'), 1,
      "面板 '" + guidePanelFor(t.key) + "' 应恰好出现一次");
  }
  const order = GUIDE_TABS.map((t) => html.indexOf('data-guide-tab="' + t.key + '"'));
  assert.deepEqual([...order].sort((a, b) => a - b), order,
    "子页签按钮在 index.html 中的顺序应与 GUIDE_TABS 一致");
});
