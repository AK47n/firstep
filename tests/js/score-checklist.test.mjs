// 评分点核对清单纯函数单测（工单 score-checklist/01）：行文本 / 清单 HTML /
// 进度 / 导出文本（☑□）/ localStorage 解析与往返。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取（同 gen-overview.test.mjs 范式）；deps = 注入的兄弟函数依赖
function extract(name, deps) {
  const start = html.indexOf("function " + name);
  assert.ok(start !== -1, "index.html 中未找到 " + name + " 函数体（改名了？）");
  const open = html.indexOf("{", start);
  assert.ok(open !== -1, name + " 函数体缺少左花括号");
  let depth = 0;
  for (let i = open; i < html.length; i++) {
    if (html[i] === "{") depth++;
    else if (html[i] === "}") {
      depth--;
      if (depth === 0) {
        const fnSrc = html.slice(start, i + 1);
        if (deps && Object.keys(deps).length) {
          return new Function(...Object.keys(deps), "return (" + fnSrc + ")")(
            ...Object.values(deps)
          );
        }
        return new Function("return (" + fnSrc + ")")();
      }
    }
  }
  throw new Error("未找到 " + name + " 函数体结束花括号");
}

const scoreChecklistPartLabel = extract("scoreChecklistPartLabel");
const scoreChecklistScoreText = extract("scoreChecklistScoreText");
const scoreChecklistRefsText = extract("scoreChecklistRefsText");
const scoreChecklistId = extract("scoreChecklistId");
const scoreChecklistChecked = extract("scoreChecklistChecked");
const scoreChecklistLineText = extract("scoreChecklistLineText", {
  scoreChecklistPartLabel,
  scoreChecklistScoreText,
  scoreChecklistRefsText,
  scoreChecklistId,
});
const scoreChecklistKey = extract("scoreChecklistKey");
const scoreChecklistItemsHTML = extract("scoreChecklistItemsHTML", {
  scoreChecklistLineText,
  scoreChecklistId,
  scoreChecklistChecked,
});
const scoreChecklistProgressHTML = extract("scoreChecklistProgressHTML");
const scoreChecklistExportText = extract("scoreChecklistExportText", {
  scoreChecklistLineText,
  scoreChecklistId,
  scoreChecklistChecked,
});
const scoreChecklistParse = extract("scoreChecklistParse");
const scoreChecklistLoad = extract("scoreChecklistLoad", { scoreChecklistParse });
const scoreChecklistSave = extract("scoreChecklistSave");

const POINTS = [
  { id: "a1", part: "basic", score: 5, sentence_refs: ["1", "2"], description: "巡线稳定" },
  { id: "b2", part: "development", score: 10, sentence_refs: ["3"], description: "计时准确" },
  { id: "c3", part: "basic", score: undefined, description: "无分值条目" },
];

test("scoreChecklistPartLabel 分区字典", () => {
  assert.equal(scoreChecklistPartLabel("basic"), "基础");
  assert.equal(scoreChecklistPartLabel("development"), "发挥");
  assert.equal(scoreChecklistPartLabel("other"), "未知");
  assert.equal(scoreChecklistPartLabel(undefined), "未知");
});

test("scoreChecklistScoreText 分值字典", () => {
  assert.equal(scoreChecklistScoreText(5), "5 分");
  assert.equal(scoreChecklistScoreText(0), "0 分");
  assert.equal(scoreChecklistScoreText(undefined), "未标分");
  assert.equal(scoreChecklistScoreText("abc"), "未标分");
});

test("scoreChecklistRefsText 句子引用", () => {
  assert.equal(scoreChecklistRefsText(["1", "2"]), "句子 1、2");
  assert.equal(scoreChecklistRefsText([]), "未关联原文");
  assert.equal(scoreChecklistRefsText(undefined), "未关联原文");
});

test("scoreChecklistLineText 行文本：完整字段 + 缺 id 兜底", () => {
  assert.equal(
    scoreChecklistLineText(POINTS[0], 0),
    "a1｜基础｜5 分｜句子 1、2｜巡线稳定"
  );
  assert.equal(
    scoreChecklistLineText({ part: "development", description: "d" }, 1),
    "score-2｜发挥｜未标分｜未关联原文｜d"
  );
});

test("scoreChecklistKey 输出目录 → 存储键；空 → 空串", () => {
  assert.equal(scoreChecklistKey("D:/contest/demo"), "score-checklist:D:/contest/demo");
  assert.equal(scoreChecklistKey(""), "");
  assert.equal(scoreChecklistKey(null), "");
});

test("scoreChecklistItemsHTML 勾选态与转义", () => {
  const items = scoreChecklistItemsHTML(POINTS, new Set(["a1", "c3"]));
  assert.ok(items.includes('data-idx="0" checked') || items.includes('checked data-idx="0"'));
  assert.ok(items.includes("sp-item done"));
  assert.ok(items.includes("a1｜基础｜5 分｜句子 1、2｜巡线稳定"));
  assert.ok(items.includes(">b2｜发挥｜10 分｜句子 3｜计时准确</span>"));
  // 数组兼容（非 Set 输入仍按 indexOf 判定）
  const arrItems = scoreChecklistItemsHTML(POINTS, ["a1"]);
  assert.ok(arrItems.includes("sp-item done"));
  // 转义：描述/引用含 < > " ' 时实体化
  const esc = scoreChecklistItemsHTML(
    [{ id: "x", description: '<b>"hi"</b>' }], []);
  assert.ok(esc.includes("&lt;b&gt;&quot;hi&quot;&lt;/b&gt;"));
});

test("scoreChecklistItemsHTML 空/无 points → 占位文案不炸", () => {
  assert.ok(scoreChecklistItemsHTML([], []).includes("没有可核对的评分点"));
  assert.ok(scoreChecklistItemsHTML(null, null).includes("没有可核对的评分点"));
});

test("scoreChecklistProgressHTML 进度文案（含防御）", () => {
  assert.equal(scoreChecklistProgressHTML(2, 5), "已核对 2/5");
  assert.equal(scoreChecklistProgressHTML(0, 0), "已核对 0/0");
  assert.equal(scoreChecklistProgressHTML("abc", null), "已核对 0/0");
});

test("scoreChecklistExportText ☑/□ 混合 + 空输入", () => {
  const text = scoreChecklistExportText(POINTS, new Set(["a1"]));
  const lines = text.split("\n");
  assert.equal(lines.length, 3);
  assert.ok(lines[0].startsWith("☑ a1｜基础｜5 分｜句子 1、2｜巡线稳定"));
  assert.ok(lines[1].startsWith("□ b2｜发挥｜10 分｜句子 3｜计时准确"));
  assert.ok(lines[2].startsWith("□ c3｜基础｜未标分｜未关联原文｜无分值条目"));
  assert.equal(scoreChecklistExportText([], []), "");
  assert.equal(scoreChecklistExportText(null, null), "");
});

test("scoreChecklistParse 容错：null/坏 JSON/非数组/非字符串过滤 → Set", () => {
  assert.deepEqual(scoreChecklistParse(null), new Set());
  assert.deepEqual(scoreChecklistParse("not json"), new Set());
  assert.deepEqual(scoreChecklistParse('{"a":1}'), new Set());
  assert.deepEqual(scoreChecklistParse('["a","b",1,null]'), new Set(["a", "b"]));
});

test("scoreChecklistLoad/Save 往返 + storage 抛错容错（Set 契约）", () => {
  const store = new Map();
  const storage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, v),
  };
  assert.equal(scoreChecklistSave("k", ["a", "b"], storage), true);
  assert.deepEqual(scoreChecklistLoad("k", storage), new Set(["a", "b"]));
  assert.deepEqual(scoreChecklistLoad("nope", storage), new Set());
  // 抛错（隐私模式）→ 静默空 / 不写
  const throwing = {
    getItem: () => { throw new Error("denied"); },
    setItem: () => { throw new Error("denied"); },
  };
  assert.deepEqual(scoreChecklistLoad("k", throwing), new Set());
  assert.equal(scoreChecklistSave("k", ["a"], throwing), false);
  // 无 key / 无 storage 防御
  assert.equal(scoreChecklistSave("", ["a"], storage), false);
  assert.deepEqual(scoreChecklistLoad("k", null), new Set());
});
