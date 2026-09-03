// fx/ai-insert.js 纯函数单测（工单 code-editor-refine/08）：代码块提取 +
// 插入/替换位置计算。直接 import，子串断言防脆。运行：node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  aiFirstCodeBlock,
  aiCodeFenceCount,
  insertAtPosition,
} from "../../src/contest_generator/static/js/fx/ai-insert.js";

test("aiFirstCodeBlock：首个 ``` fence + 内容 trim", () => {
  assert.deepEqual(
    aiFirstCodeBlock("建议如下：\n```c\nint x = 1;\n```\n补充说明"),
    { code: "int x = 1;" }
  );
  assert.deepEqual(
    aiFirstCodeBlock("```\nvoid f() {}\n```"),
    { code: "void f() {}" }
  );
});

test("aiFirstCodeBlock：无 fence / 空块 / 非字符串 → null", () => {
  assert.equal(aiFirstCodeBlock("没有代码块"), null);
  assert.equal(aiFirstCodeBlock("```\n   \n```"), null);
  assert.equal(aiFirstCodeBlock(null), null);
  assert.equal(aiFirstCodeBlock("```\n\n```"), null);
});

test("aiCodeFenceCount：fence 标记数（每对 2；多块 = 计数 > 2）", () => {
  assert.equal(aiCodeFenceCount("```c\nint x;\n```"), 2);
  assert.equal(aiCodeFenceCount("```\na\n```\n```\nb\n```"), 4);
  assert.equal(aiCodeFenceCount("没有围栏"), 0);
  assert.equal(aiCodeFenceCount(null), 0);
});

test("insertAtPosition：无选区 = 光标处插入；有选区 = 替换", () => {
  const a = insertAtPosition("int x;", "// 注释\n", { start: 6, end: 6 });
  assert.equal(a.value, "int x;// 注释\n");
  assert.equal(a.selStart, 12);
  assert.equal(a.selEnd, 12);
  const b = insertAtPosition("int x; int y;", "long", { start: 4, end: 6 });
  assert.equal(b.value, "int long int y;");
  assert.equal(b.selStart, 8);
});

test("insertAtPosition：边界钳制 / 反向选区 / 空文本不破坏", () => {
  assert.equal(insertAtPosition("abc", "X", { start: 0, end: 0 }).value, "Xabc");
  assert.equal(insertAtPosition("abc", "X", { start: 99, end: 5 }).value, "abcX");
  assert.equal(insertAtPosition("abc", "X", { start: -5, end: 2 }).value, "Xc");
  assert.equal(insertAtPosition("abc", "", { start: 1, end: 1 }).value, "abc");
  assert.equal(insertAtPosition("", "中", { start: 0, end: 0 }).value, "中");
});

test("insertAtPosition：中文/无标点内容正常（含 CRLF 归一的块）", () => {
  const block = aiFirstCodeBlock("```c\nprintf(\"你好\r\n\");\n```");
  const r = insertAtPosition("int main() { }", block.code, { start: 12, end: 12 });
  assert.ok(r.value.includes("printf(\"你好\n\");"));
  assert.equal(r.value.length, "int main() { }".length + block.code.length);
});
