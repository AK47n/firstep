// code.test.mjs — fx/code.js main.c 跳转交互件（工单 error-jump-task/02 评审
// 整改：maincJumpToLine 错误码路径 DOM 桩测试——no-textarea / empty /
// out-of-range / 成功 null）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  maincJumpToLine,
  maincLineOffsetRange,
} from "../../src/contest_generator/static/js/fx/code.js";

test("maincLineOffsetRange: 行号偏移（纯函数既有行为回归）", () => {
  const text = "int a;\nint b;\n";
  assert.deepEqual(maincLineOffsetRange(text, 1), { start: 0, end: 6 });
  assert.deepEqual(maincLineOffsetRange(text, 2), { start: 7, end: 13 });
  assert.equal(maincLineOffsetRange(text, 0), null);
  assert.equal(maincLineOffsetRange(text, "x"), null);
  // 末尾无 \n：split 只有 2 行，第 3 行越界
  const tail = "int a;\nint b;";
  assert.deepEqual(maincLineOffsetRange(tail, 3), null);
});

test("maincJumpToLine: 错误码分支（DOM 桩）", () => {
  // 桩：node 无 document——注入最小形状（成功分支需 hl 层 + textarea）
  const probeEl = () => ({
    style: {}, textContent: "", offsetTop: 0, offsetHeight: 0,
    remove() {},
  });
  const hl = {
    children: [],
    appendChild(el) { this.children.push(el); },
    removeChild() {},
  };
  let ta = null;
  const orig = globalThis.document;
  globalThis.document = {
    getElementById(id) {
      if (id === "main-c") return ta;
      if (id === "main-c-hl") return hl;
      return null;
    },
    createElement() { return probeEl(); },
  };
  try {
    // 无 textarea（预览未渲染）
    assert.equal(maincJumpToLine(1), "no-textarea");
    // 空内容
    ta = { value: "  \n ", clientHeight: 200 };
    assert.equal(maincJumpToLine(1), "empty");
    // 行号越界
    ta.value = "int main(void) {}\n";
    assert.equal(maincJumpToLine(99), "out-of-range");
    // 成功：展开 + 滚动 + 选中（closest 无卡片不折叠；hl stub 撑过量测）
    const selected = [];
    ta = {
      value: "int main(void) {}\n",
      clientHeight: 200,
      closest: () => null,
      scrollIntoView() {},
      focus() {},
      setSelectionRange(start, end) { selected.push([start, end]); },
      scrollTop: 0,
    };
    assert.equal(maincJumpToLine(1), null);
    assert.deepEqual(selected, [[0, 17]]);
  } finally {
    globalThis.document = orig;
  }
});
