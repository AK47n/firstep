// fx/disk-baseline.js 纯函数单测（工单 code-ide-flow/01）：快照规范化 /
// 三类变更对比 / LRU 裁剪。直接 import，子串断言防脆。
// 运行：node --test tests/js/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import {
  baselineSnapshot,
  baselineDiff,
  baselineHasChanges,
  baselineEvict,
} from "../../src/contest_generator/static/js/fx/disk-baseline.js";

test("baselineSnapshot：文件条目规范化，目录条目排除，空路径跳过", () => {
  const snap = baselineSnapshot([
    { path: "main.c", mtime_ns: "100", size_bytes: 12 },
    { path: "user/oled.c", mtime_ns: "200", size_bytes: 34 },
    { path: "user", is_dir: true },
    { path: "empty/", is_dir: true },
    { path: "no-mtime.c", size_bytes: 5 },
    { path: "", mtime_ns: "9", size_bytes: 1 },
  ]);
  assert.deepEqual(snap, {
    "main.c": { mtime_ns: "100", size_bytes: 12 },
    "user/oled.c": { mtime_ns: "200", size_bytes: 34 },
    "no-mtime.c": { mtime_ns: "", size_bytes: 5 },
  });
});

test("baselineSnapshot：mtime_ns 数字输入转字符串（与后端字符串口径一致）", () => {
  const snap = baselineSnapshot([{ path: "a.c", mtime_ns: 123456, size_bytes: 1 }]);
  assert.equal(snap["a.c"].mtime_ns, "123456");
});

test("baselineDiff：added / modified / removed 三分类", () => {
  const prev = baselineSnapshot([
    { path: "main.c", mtime_ns: "100", size_bytes: 12 },
    { path: "user/oled.c", mtime_ns: "200", size_bytes: 34 },
    { path: "gone.c", mtime_ns: "300", size_bytes: 8 },
  ]);
  const now = baselineSnapshot([
    { path: "main.c", mtime_ns: "100", size_bytes: 12 },     // 未变（mtime 同）
    { path: "user/oled.c", mtime_ns: "999", size_bytes: 40 }, // 修改（mtime 异）
    { path: "new.c", mtime_ns: "400", size_bytes: 3 },        // 新增
  ]);
  const d = baselineDiff(prev, now);
  assert.deepEqual(d.added, ["new.c"]);
  assert.deepEqual(d.modified, ["user/oled.c"]);
  assert.deepEqual(d.removed, ["gone.c"]);
  assert.equal(baselineHasChanges(d), true);
});

test("baselineDiff：mtime 字符串比较——内容相同但数值型字符串不同值不算修改", () => {
  const prev = baselineSnapshot([{ path: "a.c", mtime_ns: "101", size_bytes: 1 }]);
  const now = baselineSnapshot([{ path: "a.c", mtime_ns: "101", size_bytes: 2 }]);
  // 同 mtime 但大小变化 → 不算修改（事实源 = mtime，与 409 冲突检测同口径）
  assert.deepEqual(baselineDiff(prev, now), { added: [], modified: [], removed: [] });
  // 空串 vs 非空串 → 修改
  const prevNm = baselineSnapshot([{ path: "a.c", size_bytes: 1 }]);
  const nowNm = baselineSnapshot([{ path: "a.c", mtime_ns: "7", size_bytes: 1 }]);
  assert.deepEqual(baselineDiff(prevNm, nowNm).modified, ["a.c"]);
});

test("baselineDiff：边界——空基线全 added；空现快照全 removed；相同快照全空", () => {
  const empty = {};
  const full = baselineSnapshot([
    { path: "main.c", mtime_ns: "1", size_bytes: 1 },
    { path: "sub/x.h", mtime_ns: "2", size_bytes: 2 },
  ]);
  const d1 = baselineDiff(empty, full);
  assert.deepEqual(d1.added, ["main.c", "sub/x.h"]);
  assert.deepEqual(d1.modified, []);
  assert.deepEqual(d1.removed, []);
  const d2 = baselineDiff(full, empty);
  assert.deepEqual(d2.added, []);
  assert.deepEqual(d2.modified, []);
  assert.deepEqual(d2.removed, ["main.c", "sub/x.h"]);
  const d3 = baselineDiff(full, full);
  assert.deepEqual(d3, { added: [], modified: [], removed: [] });
  assert.equal(baselineHasChanges(d3), false);
});

test("baselineDiff：中文 / 子目录 / 空格路径不误判", () => {
  const prev = baselineSnapshot([{ path: "用户 手册/说明.md", mtime_ns: "10", size_bytes: 3 }]);
  const nowSame = baselineSnapshot([{ path: "用户 手册/说明.md", mtime_ns: "10", size_bytes: 3 }]);
  const nowNew = baselineSnapshot([
    { path: "用户 手册/说明.md", mtime_ns: "10", size_bytes: 3 },
    { path: "用户 手册/新增.md", mtime_ns: "11", size_bytes: 4 },
  ]);
  assert.deepEqual(baselineDiff(prev, nowSame).added, []);
  assert.deepEqual(baselineDiff(prev, nowNew).added, ["用户 手册/新增.md"]);
});

test("baselineEvict：超过 maxDirs 保留最新 ts；ts 相同保留先入（稳定）", () => {
  const store = {
    "/a": { ts: 100, files: {} },
    "/b": { ts: 300, files: {} },
    "/c": { ts: 200, files: {} },
  };
  const kept = baselineEvict(store, 2);
  assert.deepEqual(Object.keys(kept).sort(), ["/b", "/c"]);
  // ts 相同 → 保留先插入的（Object.keys 顺序 = 插入序；sort 稳定）
  const store2 = { "/x": { ts: 5, files: {} }, "/y": { ts: 5, files: {} }, "/z": { ts: 9, files: {} } };
  const kept2 = baselineEvict(store2, 2);
  assert.deepEqual(Object.keys(kept2).sort(), ["/x", "/z"]);
  // 不修改入参
  assert.deepEqual(Object.keys(store).sort(), ["/a", "/b", "/c"]);
  assert.deepEqual(Object.keys(store2).sort(), ["/x", "/y", "/z"]);
});

test("baselineEvict：maxDirs 非法 / 条目数不超限 → 原样返回", () => {
  const store = { "/a": { ts: 1, files: {} } };
  assert.deepEqual(baselineEvict(store, 5), store);
  assert.deepEqual(baselineEvict(store, -1), store);
  assert.deepEqual(baselineEvict(store, NaN), store);
});
