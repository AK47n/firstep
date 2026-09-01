// 工单 code-ide-ai/01：AiDiff 契约解析与选区上下文拼装（fx 纯件单测）
import test from "node:test";
import assert from "node:assert/strict";
import {
  parseAiDiff,
  selectionContextText,
} from "../../src/contest_generator/static/js/fx/ai-diff.js";

const HUNK = {
  line: 10,
  title: "填充 TODO「init sensor」",
  lines: [
    { kind: "ctx", text: "int main(void) {" },
    { kind: "del", text: "  // TODO: init sensor" },
    { kind: "add", text: "  sensor_init();" },
    { kind: "ctx", text: "  return 0;" },
  ],
};

test("parseAiDiff：合法 DIFF 块（TODO 标题 + 多 hunk）解析全字段", () => {
  const text = "好的，改这里：\n<DIFF>\n{\"path\":\"main.c\",\"stats\":{\"additions\":9,\"deletions\":9,\"hunks\":9},\"hunks\":["
    + JSON.stringify(HUNK)
    + ",{\"line\":20,\"title\":\"\",\"lines\":[{\"kind\":\"ctx\",\"text\":\"x\"},{\"kind\":\"add\",\"text\":\"y\"}]}]}\n</DIFF>\n完成";
  const d = parseAiDiff(text);
  assert.ok(d, "应有解析结果");
  assert.equal(d.path, "main.c");
  // stats 派生自 hunks（AI 提供的 9/9/9 被忽略——计数自洽保证）；
  // 第二 hunk 含 ctx 锚点（全 add 无锚点会被守卫拒绝——评审整改）
  assert.deepEqual(d.stats, { additions: 2, deletions: 1, hunks: 2 });
  assert.equal(d.hunks.length, 2);
  assert.equal(d.hunks[0].title, "填充 TODO「init sensor」");
  assert.equal(d.hunks[0].lines[1].kind, "del");
  assert.equal(d.hunks[1].line, 20);
  assert.equal(d.hunks[1].lines[0].kind, "ctx");
});

test("parseAiDiff：无 DIFF 块 → null（纯文本回复）", () => {
  assert.equal(parseAiDiff("这是回答，没有改动"), null);
  assert.equal(parseAiDiff(""), null);
});

test("parseAiDiff：块内非 JSON / 空 JSON → null 且不 throw", () => {
  assert.equal(parseAiDiff("<DIFF>not json</DIFF>"), null);
  assert.equal(parseAiDiff("<DIFF></DIFF>"), null);
  assert.equal(parseAiDiff("<DIFF>{}</DIFF>"), null);
});

test("parseAiDiff：结构非法（缺字段）→ null", () => {
  assert.equal(parseAiDiff(
    `<DIFF>{"path":"main.c","stats":{"additions":1,"deletions":1,"hunks":1},"hunks":[{"line":1,"lines":[]}]}</DIFF>`), null);
  assert.equal(parseAiDiff(
    `<DIFF>{"path":"main.c","stats":{"additions":1,"deletions":1,"hunks":1},"hunks":[{"line":0,"lines":[{"kind":"add","text":"x"}]}]}</DIFF>`), null);
  assert.equal(parseAiDiff(
    `<DIFF>{"path":"","stats":{"additions":0,"deletions":0,"hunks":0},"hunks":[]}</DIFF>`), null);
});

test("parseAiDiff：kind 越界 → null", () => {
  assert.equal(parseAiDiff(
    `<DIFF>{"path":"main.c","stats":{"additions":1,"deletions":1,"hunks":1},"hunks":[{"line":1,"title":"","lines":[{"kind":"replace","text":"x"}]}]}</DIFF>`), null);
});

test("parseAiDiff：hunk 全 add 无锚点行 → null（应用器需 ctx/del 匹配）", () => {
  assert.equal(parseAiDiff(
    `<DIFF>{"path":"main.c","hunks":[{"line":1,"title":"","lines":[{"kind":"add","text":"x"},{"kind":"add","text":"y"}]}]}</DIFF>`), null);
});

test("parseAiDiff：path 安全（拒绝 .. / 绝对路径）", () => {
  assert.equal(parseAiDiff(
    `<DIFF>{"path":"../etc/passwd","stats":{"additions":0,"deletions":0,"hunks":0},"hunks":[]}</DIFF>`), null);
  assert.equal(parseAiDiff(
    `<DIFF>{"path":"C:/windows/x.c","stats":{"additions":0,"deletions":0,"hunks":0},"hunks":[]}</DIFF>`), null);
});

test("parseAiDiff：多个 DIFF 块 → 取第一个合法块", () => {
  const a = `<DIFF>{"path":"a.c","stats":{"additions":0,"deletions":0,"hunks":0},"hunks":[]}</DIFF>`;
  const b = `<DIFF>{"path":"b.c","stats":{"additions":0,"deletions":0,"hunks":0},"hunks":[]}</DIFF>`;
  const d = parseAiDiff(a + "\n" + b);
  assert.equal(d.path, "a.c");
});

test("parseAiDiff：块内带 ```json 围栏也可解析", () => {
  const d = parseAiDiff("<DIFF>\n```json\n"
    + JSON.stringify({ path: "main.c", stats: { additions: 0, deletions: 0, hunks: 0 }, hunks: [] })
    + "\n```\n</DIFF>");
  assert.equal(d.path, "main.c");
});

test("selectionContextText：拼装含路径/行区间/语言 fence", () => {
  const t = selectionContextText("src/main.c", "c", 10, 25, "int x;\nint y;");
  assert.ok(t.includes("【代码引用 · src/main.c · 第 10-25 行】"), t);
  assert.ok(t.includes("```c\nint x;\nint y;\n```"), t);
});

test("selectionContextText：行号 1 起（含 1 行区间）", () => {
  const t = selectionContextText("main.c", "c", 1, 1, "a");
  assert.ok(t.includes("第 1-1 行"), t);
  assert.ok(t.includes("```c\na\n```"), t);
});
