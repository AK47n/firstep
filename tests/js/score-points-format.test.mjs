// formatScorePoints 纯函数单测（工单 score-points/03）：交接提示词与后续
// 前端展示共用评分点文案。照 collect-bindings 先例：从 HTML 抽取函数体喂
// node:test，不碰 DOM / fetch。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const match = html.match(/function formatScorePoints[\s\S]*?\n\}/);
assert.ok(match, "index.html 中未找到 formatScorePoints 函数体（改名了？）");
const formatScorePoints = new Function("return (" + match[0] + ")")();

const recMatch = html.match(/function renderScorePointPanel[\s\S]*?\n\}/);
assert.ok(recMatch, "index.html 中未找到 renderScorePointPanel 函数体（改名了？）");
const renderScorePointPanel = new Function(
  "esc",
  "formatScorePoints",
  "return (" + recMatch[0] + ")"
)((text) => String(text).replace(/[&<>\"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[c]), formatScorePoints);

test("完整评分点 → 保留顺序、分区、分值和句号引用", () => {
  assert.equal(
    formatScorePoints([
      { id: "B1", part: "basic", description: "完成测距", score: 10, sentence_refs: [2, 3] },
      { id: "D1", part: "development", description: "提高精度", score: null, sentence_refs: [] },
    ]),
    "- B1｜基础｜10 分｜句子 2、3｜完成测距\n" +
      "- D1｜发挥｜未标分｜未关联原文｜提高精度"
  );
});

test("缺省或空评分点 → 固定占位文案", () => {
  assert.equal(formatScorePoints(undefined), "（无结构化评分点）");
  assert.equal(formatScorePoints([]), "（无结构化评分点）");
});

test("未知分区和空 id 降级但不丢描述", () => {
  assert.equal(
    formatScorePoints([{ part: "other", description: "展示结果", score: 2.5, sentence_refs: [] }]),
    "- score-1｜未知｜2.5 分｜未关联原文｜展示结果"
  );
});

test("推荐结果评分点面板 → 只读展示分区、分值、描述和句号引用", () => {
  const rendered = renderScorePointPanel([
    { id: "B1", part: "basic", description: "完成测距", score: 10, sentence_refs: [2, 3] },
    { id: "D1", part: "development", description: "提高精度", score: null, sentence_refs: [] },
  ]);

  assert.match(rendered, /id="rec-score-points"/);
  assert.match(rendered, /评分点验收清单/);
  assert.match(rendered, /基础/);
  assert.match(rendered, /10 分/);
  assert.match(rendered, /句子 2、3/);
  assert.match(rendered, /完成测距/);
  assert.match(rendered, /发挥/);
  assert.match(rendered, /未标分/);
  assert.match(rendered, /未关联原文/);
  assert.doesNotMatch(rendered, /<(input|button|textarea|select)\b/);
});

test("推荐结果评分点面板 → 旧载荷和空清单不渲染空面板", () => {
  assert.equal(renderScorePointPanel(undefined), "");
  assert.equal(renderScorePointPanel([]), "");
});

test("推荐结果评分点面板 → 转义模型文本，避免展示区注入可交互控件", () => {
  const rendered = renderScorePointPanel([
    { id: "<button>x</button>", part: "unknown", description: "<input>", score: 2.5, sentence_refs: [] },
  ]);

  assert.match(rendered, /&lt;button&gt;x&lt;\/button&gt;/);
  assert.match(rendered, /&lt;input&gt;/);
  assert.doesNotMatch(rendered, /<(input|button|textarea|select)\b/);
});

test("index.html 推荐结果区会渲染只读评分点面板", () => {
  assert.match(html, /renderScorePointPanel\(scorePoints\)/);
  assert.match(html, /id="rec-score-points"/);
});

test("index.html 生成结果摘要区有评分点落点", () => {
  assert.match(html, /id="res-score-points"/);
  assert.match(html, /formatScorePoints\(data\.score_points\)/);
});

test("Handoff 评分点章节只在有评分点时插入", () => {
  assert.match(html, /const scoreSection = hasScores \? \["", "## 五、评分点验收清单", "", scores\] : \[\]/);
  assert.match(html, /\.\.\.scoreSection/);
});
