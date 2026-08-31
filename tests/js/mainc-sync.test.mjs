// mainc-sync 纯函数单测（工单 mainc-codeview-bridge/01）：
// main.c 磁盘同步状态行的语义与渲染——状态标签/警示色、路径转义、
// 差异判定（含 null/undefined 防御）。直接 import fx/mainc-sync.js。
import test from "node:test";
import assert from "node:assert/strict";
import {
  maincDiskState, maincDiskStateHTML, maincDiffers,
} from "../../src/contest_generator/static/js/fx/mainc-sync.js";

test("maincDiskState 三态语义：written/changed/synced，未知态为空", () => {
  assert.deepEqual(maincDiskState("written"), { kind: "ok", label: "main.c 已写入磁盘" });
  assert.deepEqual(maincDiskState("changed"), { kind: "warn", label: "磁盘 main.c 已更新" });
  assert.deepEqual(maincDiskState("synced"), { kind: "ok", label: "已同步磁盘版本" });
  assert.deepEqual(maincDiskState("none"), { kind: "", label: "" });
  assert.deepEqual(maincDiskState(""), { kind: "", label: "" });
});

test("maincDiskStateHTML：渲染标签 + 目录（转义）+ 加载按钮；changed 按钮文案不同", () => {
  const written = maincDiskStateHTML("written", "D:\\a&b\\proj");
  assert.match(written, /main\.c 已写入磁盘/);
  assert.match(written, /D:\\a&amp;b\\proj/);          // & 转义
  assert.match(written, /data-mainc-reload/);
  assert.match(written, /从磁盘重新加载/);
  const changed = maincDiskStateHTML("changed", "D:\\proj");
  assert.match(changed, /磁盘 main\.c 已更新/);
  assert.match(changed, /加载为编辑内容/);
  // 无目录：不渲染目录 span，仅标签 + 按钮
  const noDir = maincDiskStateHTML("written", "");
  assert.match(noDir, /main\.c 已写入磁盘/);
  assert.doesNotMatch(noDir, /mainc-disk-dir/);
});

test("maincDiskStateHTML：未知态返回空串（不渲染）", () => {
  assert.equal(maincDiskStateHTML("none", "D:\\proj"), "");
  assert.equal(maincDiskStateHTML("whatever", "D:\\proj"), "");
});

test("maincDiffers：逐字节不等判定；null/undefined 防御为空串", () => {
  assert.equal(maincDiffers("a", "a"), false);
  assert.equal(maincDiffers("a", "b"), true);
  assert.equal(maincDiffers("a", ""), true);
  assert.equal(maincDiffers("", ""), false);
  assert.equal(maincDiffers(null, ""), false);
  assert.equal(maincDiffers(undefined, ""), false);
  assert.equal(maincDiffers(null, "a"), true);
  assert.equal(maincDiffers(0, "0"), false);           // 数字统一按字符串比较
  assert.equal(maincDiffers(0, "1"), true);
});
