// maincContentEmpty / maincFullscreenLabel 纯函数单测（工单 mainc-tools/01）：
// main.c 骨架工具栏的「空内容判断」与「全屏按钮文案切换」。
import test from "node:test";
import assert from "node:assert/strict";
import { maincContentEmpty, maincFullscreenLabel } from "../../src/contest_generator/static/js/fx/code.js";

test("maincContentEmpty：非空内容不拦截", () => {
  assert.equal(maincContentEmpty("int main(void) { return 0; }"), false);
  assert.equal(maincContentEmpty("  abc  "), false);
});

test("maincContentEmpty：空 / 纯空白内容拦截", () => {
  assert.equal(maincContentEmpty(""), true);
  assert.equal(maincContentEmpty("   "), true);
  assert.equal(maincContentEmpty("\n\t  \n"), true);
});

test("maincContentEmpty：非字符串按空处理（防御）", () => {
  assert.equal(maincContentEmpty(undefined), true);
  assert.equal(maincContentEmpty(null), true);
});

test("maincFullscreenLabel：未全屏显示「全屏」，全屏中显示「退出全屏」", () => {
  assert.equal(maincFullscreenLabel(false), "全屏");
  assert.equal(maincFullscreenLabel(true), "退出全屏");
});
