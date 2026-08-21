// stepNavTitles / stepNavDotsHTML / stepNavCurrent 纯函数单测（工单 ui-polish/02）：
// 生成页左侧步骤导航的标题抽取、圆点 HTML 生成、滚动高亮判定。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

function extract(name) {
  const match = html.match(new RegExp("function " + name + "[\\s\\S]*?\\n\\}"));
  assert.ok(match, "index.html 中未找到 " + name + " 函数体（改名了？）");
  return new Function("return (" + match[0] + ")")();
}

const stepNavTitles = extract("stepNavTitles");
const stepNavDotsHTML = extract("stepNavDotsHTML");
const stepNavCurrent = extract("stepNavCurrent");

// 假卡片：只实现 .step-no / h2 两个查询
const card = (no, text) => ({
  querySelector: (sel) =>
    sel === ".step-no" ? { textContent: no }
    : sel === "h2" ? { textContent: text }
    : null,
});

test("stepNavTitles 提取编号并去掉 h2 里的编号前缀", () => {
  const cards = [card("1", "1赛题原文"), card("12", "12交接提示词（Handoff）")];
  assert.deepEqual(stepNavTitles(cards), [
    { n: 1, title: "赛题原文" },
    { n: 12, title: "交接提示词（Handoff）" },
  ]);
});

test("stepNavTitles 缺徽章 / 缺 h2 时兜底", () => {
  const cards = [{ querySelector: () => null }];
  assert.deepEqual(stepNavTitles(cards), [{ n: NaN, title: "" }]);
});

test("stepNavDotsHTML 为每步生成圆点按钮", () => {
  const titles = [
    { n: 1, title: "赛题原文" },
    { n: 2, title: "赛题简介" },
  ];
  const out = stepNavDotsHTML(titles);
  assert.equal(out.match(/class="step-dot"/g).length, 2);
  assert.ok(out.includes('data-step="1"'));
  assert.ok(out.includes(">1</button>"));
  assert.ok(out.includes('title="赛题简介"'));
});

test("stepNavDotsHTML 转义标题中的引号", () => {
  const out = stepNavDotsHTML([{ n: 7, title: '引脚配置"板图"' }]);
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
