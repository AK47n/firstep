import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const html = readFileSync(resolve(root, "src/contest_generator/static/index.html"), "utf8");

function extract(name) {
  const m = html.match(new RegExp("function " + name + "[\\s\\S]*?\\n\\}"));
  assert.ok(m, "function " + name + " not found in index.html");
  // 自包含：用 new Function 构造，函数体内不得引用模块级常量
  return new Function(m[0] + "; return " + name + ";")();
}

const topicCardHTML = extract("topicCardHTML");

test("卡片结构：key/year/preview/操作按钮齐全", () => {
  const out = topicCardHTML({ key: "2024H", year: "2024", problem_text: "巡线小车" });
  assert.ok(out.includes('class="topic-card"'));
  assert.ok(out.includes('class="topic-key">2024H<'));
  assert.ok(out.includes('class="topic-year">2024<'));
  assert.ok(out.includes('class="topic-preview"'));
  assert.ok(out.includes("巡线小车"));
  assert.ok(out.includes('data-topic-use="2024H"'));
  assert.ok(out.includes('data-topic-del="2024H"'));
  assert.ok(out.includes("用此题生成"));
  assert.ok(out.includes("删除"));
});

test("题面预览截断：80 字 + 省略号，title 全文 200 字", () => {
  const long = "题".repeat(250);
  const out = topicCardHTML({ key: "2024H", year: "2024", problem_text: long });
  const preview = out.match(/<div class="topic-preview"[^>]*>([^<]*)</)[1];
  assert.equal(preview.length, 81); // 80 字 + …
  assert.ok(preview.endsWith("…"));
  assert.ok(out.includes("title=\"" + "题".repeat(200) + "…"));
});

test("题面不足 200 字：title 显示全文无省略号，preview 仍截断 80", () => {
  const short = "题".repeat(150);
  const out = topicCardHTML({ key: "2024H", year: "2024", problem_text: short });
  assert.ok(out.includes("title=\"" + short + "\""));
  const preview = out.match(/<div class="topic-preview"[^>]*>([^<]*)</)[1];
  assert.equal(preview.length, 81);
  assert.ok(preview.endsWith("…"));
});

test("特殊字符转义：key/year/题面中的 & < > \" '", () => {
  const out = topicCardHTML({ key: "A&B", year: "2024", problem_text: "a<b>c\"d'e" });
  assert.ok(out.includes("A&amp;B"));
  assert.ok(!out.includes("data-topic-use=\"A&B\"")); // 未转义会破坏属性
  assert.ok(out.includes("a&lt;b&gt;c&quot;d&#39;e"));
});

test("空字段兜底：key/year/problem_text 缺失不抛错", () => {
  const out = topicCardHTML({});
  assert.ok(out.includes('class="topic-key"></span>'));
  assert.ok(out.includes('class="topic-year"></span>'));
  assert.ok(out.includes('<div class="topic-preview" title=""></div>'));
});

test("HTML 已改用 #topic-grid 容器，无 tbody#topic-rows", () => {
  assert.ok(html.includes('<div id="topic-grid" class="topic-grid">'));
  assert.ok(!html.includes("topic-rows"));
  assert.ok(html.includes('grid.querySelectorAll("[data-topic-del]")'));
  assert.ok(html.includes('grid.querySelectorAll("[data-topic-use]")'));
});
