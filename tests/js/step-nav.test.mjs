// stepNavTitles / stepNavItemsHTML / stepNavCurrent 纯函数单测（工单 frontend-es-modules/07）：
// 生成页左侧步骤导航的标题抽取、胶囊项 HTML 生成、滚动高亮判定。
// 直接 import fx/draft.js（不再字符串提取）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  stepNavTitles, stepNavItemsHTML, stepNavCurrent,
} from "../../src/contest_generator/static/js/fx/draft.js";

// 假卡片：只实现 .step-no / h2 两个查询
const card = (no, text) => ({
  querySelector: (sel) =>
    sel === ".step-no" ? { textContent: no }
    : sel === "h2" ? { textContent: text }
    : null,
});

test("stepNavTitles 提取编号并去掉 h2 里的编号前缀", () => {
  const cards = [card("1", "1赛题原文"), card("12", "12交接提示词")];
  assert.deepEqual(stepNavTitles(cards), [
    { n: 1, title: "赛题原文" },
    { n: 12, title: "交接提示词" },
  ]);
});

test("stepNavTitles 缺徽章 / 缺 h2 时兜底", () => {
  const cards = [{ querySelector: () => null }];
  assert.deepEqual(stepNavTitles(cards), [{ n: NaN, title: "" }]);
});

test("stepNavItemsHTML 生成胶囊结构：dot 数字 + label 标题", () => {
  const out = stepNavItemsHTML([
    { n: 1, title: "赛题原文" },
    { n: 2, title: "赛题简介" },
  ]);
  assert.equal(out.match(/class="step-dot"/g).length, 2);
  assert.ok(out.includes('data-step="1"'));
  assert.ok(out.includes('<span class="dot">1</span>'));
  assert.ok(out.includes('<span class="label">赛题原文</span>'));
  assert.ok(out.includes('title="赛题原文"'));
});

test("stepNavItemsHTML 超长标题截断为 12 字符加省略号，title 保留全文", () => {
  const longTitle = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳";
  const out = stepNavItemsHTML([{ n: 10, title: longTitle }]);
  assert.ok(out.includes('<span class="label">甲乙丙丁戊己庚辛壬癸子丑…</span>'));
  assert.ok(out.includes('title="' + longTitle + '"'));
});

test("stepNavItemsHTML 转义标题中的引号（label 与 title 都转义）", () => {
  const out = stepNavItemsHTML([{ n: 7, title: '引脚配置"板图"' }]);
  assert.ok(out.includes('<span class="label">引脚配置&quot;板图&quot;</span>'));
  assert.ok(out.includes('title="引脚配置&quot;板图&quot;"'));
});

test("stepNavCurrent 取最后一个越过阈值的步号", () => {
  const entries = [
    { n: 1, top: 0 },
    { n: 2, top: 60 },
    { n: 3, top: 200 },
  ];
  assert.equal(stepNavCurrent(entries, 120), 2);
});

test("stepNavCurrent 无越过者时取第一步", () => {
  const entries = [
    { n: 1, top: 500 },
    { n: 2, top: 900 },
  ];
  assert.equal(stepNavCurrent(entries, 120), 1);
});

test("stepNavCurrent 空列表返回 NaN", () => {
  assert.ok(Number.isNaN(stepNavCurrent([], 120)));
});
