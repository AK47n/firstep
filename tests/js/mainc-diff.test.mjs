// fx/mainc-diff.js 纯函数单测（工单 code-ide-flow/03）：main.c 行级确定性
// diff 计算——与后端 deepen.py main_diff 同语义（difflib.unified_diff n=2
// 的行级 LCS + hunk 分组 + TODO 标题），供「磁盘变更」面板行级展示。
// 直接 import，子串断言防脆。运行：node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { maincDiffCompute, MAINc_DIFF_MAX_CELLS } from "../../src/contest_generator/static/js/fx/mainc-diff.js";

test("maincDiffCompute：无差异 → null", () => {
  assert.equal(maincDiffCompute("a\nb\nc\n", "a\nb\nc\n"), null);
  assert.equal(maincDiffCompute("", ""), null);
});

test("maincDiffCompute：单行替换——一个 hunk，line = hunk 起点（ctx 行，1 基）", () => {
  const d = maincDiffCompute(
    "l1\nl2\nold\nl4\nl5\n",
    "l1\nl2\nnew\nl4\nl5\n",
  );
  assert.ok(d);
  assert.equal(d.stats.additions, 1);
  assert.equal(d.stats.deletions, 1);
  assert.equal(d.stats.hunks, 1);
  assert.equal(d.hunks.length, 1);
  assert.equal(d.hunks[0].line, 1);   // @@ -1,5 +1,5 @@ 的 c=1（hunk 起点 = ctx 起点）
  const kinds = d.hunks[0].lines.map((l) => l.kind);
  const texts = d.hunks[0].lines.map((l) => l.text);
  assert.deepEqual(kinds, ["ctx", "ctx", "del", "add", "ctx", "ctx"]);
  assert.ok(texts.includes("old") && texts.includes("new"));
});

test("maincDiffCompute：两块变更相隔 ≤4 ctx 行 → 合并一个 hunk；相隔远 → 两个", () => {
  // 块1 在 3 行，块2 在 7 行（间隔 3 行 ctx ≤ 4 → 合并）
  const close = maincDiffCompute(
    "a1\na2\nX\na4\na5\na6\na7\nY\na9\na10\n",
    "a1\na2\nx\na4\na5\na6\na7\ny\na9\na10\n",
  );
  assert.equal(close.stats.hunks, 1);
  // 间隔 6 行 ctx > 4 → 两个 hunk
  const far = maincDiffCompute(
    "a1\na2\nX\na4\na5\na6\na7\na8\na9\na10\na11\nY\na13\na14\n",
    "a1\na2\nx\na4\na5\na6\na7\na8\na9\na10\na11\ny\na13\na14\n",
  );
  assert.equal(far.stats.hunks, 2);
});

test("maincDiffCompute：hunk 标题——删除行 TODO 注释 → 「填充 TODO「…」」", () => {
  const d = maincDiffCompute(
    "int main(void) {\n  // TODO: init motor\n  init();\n  return 0;\n}\n",
    "int main(void) {\n  motor_init();\n  init();\n  return 0;\n}\n",
  );
  assert.ok(d);
  const titles = d.hunks.map((h) => h.title);
  assert.ok(titles.some((t) => t.includes("填充 TODO「init motor」")),
    "titles=" + JSON.stringify(titles));
});

test("maincDiffCompute：超限（行数积 > cap）→ null（面板占位）", () => {
  const n = 2100;
  const a = [];
  const b = [];
  for (let i = 0; i < n; i++) { a.push("a" + i); b.push("b" + i); }
  assert.ok(a.length * b.length > MAINc_DIFF_MAX_CELLS);
  assert.equal(maincDiffCompute(a.join("\n"), b.join("\n")), null);
});

test("maincDiffCompute：\\r\\n 与 \\r 行尾归一（splitlines 语义）", () => {
  const d = maincDiffCompute("a\r\nb\r\nc\r\n", "a\r\ny\r\nc\r\n");
  assert.ok(d);
  assert.equal(d.stats.additions, 1);
  assert.equal(d.hunks[0].line, 1);
});
