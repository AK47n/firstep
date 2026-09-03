// fx/undo-stack.js 纯函数单测（工单 editor-textarea-viewport/03）：
// 模型级快照撤销栈状态机——push（编辑前快照入栈 + 清空 redo + 上限 200）、
// undo/redo 步进（弹栈 + 当前状态入对侧）、空栈语义。快照字段契约 =
// {value, selStart, selEnd}（模型全文 + 模型选区），与窗口文本无关。
// 运行：node --test "tests/js/*.test.mjs"
import test from "node:test";
import assert from "node:assert/strict";
import {
  UNDO_LIMIT,
  undoPush,
  undoStep,
  redoStep,
} from "../../src/contest_generator/static/js/fx/undo-stack.js";

const S = (value, selStart = 0, selEnd = selStart) =>
  ({ value, selStart, selEnd });

test("undoPush：编辑前快照入栈、清空 redo、上限默认 200", () => {
  let undo = [];
  let redo = [S("r1"), S("r2")];
  const r = undoPush(undo, redo, S("s1"));
  assert.deepEqual(r.undo, [S("s1")]);
  assert.deepEqual(r.redo, []);   // 新编辑清空 redo（不串历史）

  let u = [];
  for (let i = 0; i < UNDO_LIMIT + 5; i++) u = undoPush(u, [], S("v" + i)).undo;
  assert.equal(u.length, UNDO_LIMIT);
  assert.equal(u[0].value, "v5");     // 丢最旧 5 条
  assert.equal(u[u.length - 1].value, "v" + (UNDO_LIMIT + 4));
});

test("undoStep：弹出最近编辑前快照、当前状态入 redo；空栈 → null", () => {
  const undo = [S("s0"), S("s1")];
  const redo = [];
  const cur = S("s2");
  const r = undoStep(undo, redo, cur);
  assert.ok(r);
  assert.equal(r.snap.value, "s1");          // 最近一次编辑前状态
  assert.deepEqual(r.undo, [S("s0")]);
  assert.deepEqual(r.redo, [S("s2")]);       // 当前状态入 redo
  assert.equal(undoStep([], [], cur), null); // 空栈
});

test("redoStep：弹出最近 redo 快照、当前状态入 undo；空栈 → null", () => {
  const r = redoStep([], [S("s2")], S("s1"));
  assert.ok(r);
  assert.equal(r.snap.value, "s2");
  assert.deepEqual(r.undo, [S("s1")]);
  assert.deepEqual(r.redo, []);
  assert.equal(redoStep([], [], S("x")), null);
});

test("往返：A→B→C 编辑后 undo→redo 状态与栈一致（撤销栈不串历史）", () => {
  let undo = [];
  let redo = [];
  // 编辑：A(初始) → B → C；每次编辑前 push 当前状态
  undo = undoPush(undo, redo, S("A")).undo;   // 编辑到 B 前
  undo = undoPush(undo, redo, S("B")).undo;   // 编辑到 C 前
  let cur = S("C");
  // undo：C → B
  let r = undoStep(undo, redo, cur);
  assert.equal(r.snap.value, "B");
  undo = r.undo; redo = r.redo; cur = S("B");
  // undo：B → A
  r = undoStep(undo, redo, cur);
  assert.equal(r.snap.value, "A");
  undo = r.undo; redo = r.redo; cur = S("A");
  // undo 空栈
  assert.equal(undoStep(undo, redo, cur), null);
  // redo：A → B
  r = redoStep(undo, redo, cur);
  assert.equal(r.snap.value, "B");
  undo = r.undo; redo = r.redo; cur = S("B");
  // redo：B → C
  r = redoStep(undo, redo, cur);
  assert.equal(r.snap.value, "C");
  undo = r.undo; redo = r.redo; cur = S("C");
  assert.deepEqual(redo, []);
  // undo 后新编辑 → redo 清空
  r = undoStep(undo, redo, cur);
  assert.equal(r.snap.value, "B");
  undo = r.undo; redo = r.redo;
  const r2 = undoPush(undo, redo, S("X"));
  assert.deepEqual(r2.redo, []);   // 新编辑清空 redo
  assert.deepEqual(r2.undo, [S("A"), S("X")]);
});

test("快照字段契约：{value, selStart, selEnd}——模型级而非窗口级", () => {
  const s = S("int a;\nint b;\n", 4, 7);
  assert.deepEqual(Object.keys(s).sort(), ["selEnd", "selStart", "value"]);
  assert.equal(typeof s.value, "string");
  assert.equal(typeof s.selStart, "number");
  assert.equal(typeof s.selEnd, "number");
});

test("undoPush：非法快照（null）→ 原栈原样返回（不污染）", () => {
  const undo = [S("a")];
  const redo = [S("b")];
  const r = undoPush(undo, redo, null);
  assert.equal(r.undo, undo);
  assert.equal(r.redo, redo);
});
