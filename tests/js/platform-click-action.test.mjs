// platformClickAction 纯函数单测（工单 platform-click-guard/01）：平台卡点击决策三态——
// 重复点击已选平台 = same（无操作，防误触丢推荐勾选）；未选平台首次点击 = first（保留
// 下游选择，仅按新平台重展开）；切换平台 = switch（换平台语义，清空重来）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

function extract(name) {
  const match = html.match(new RegExp("function " + name + "[\\s\\S]*?\\n\\}"));
  assert.ok(match, "index.html 中未找到 " + name + " 函数体（改名了？）");
  return new Function("return (" + match[0] + ")")();
}

const platformClickAction = extract("platformClickAction");

test("重复点击当前已选平台 = same（无操作）", () => {
  assert.equal(platformClickAction("stm32", "stm32"), "same");
});

test("未选平台首次点击 = first（保留下游选择）", () => {
  assert.equal(platformClickAction(null, "stm32"), "first");
  assert.equal(platformClickAction(null, "mspm0"), "first");
});

test("切换平台 = switch（清空重来）", () => {
  assert.equal(platformClickAction("stm32", "mspm0"), "switch");
  assert.equal(platformClickAction("mspm0", "stm32"), "switch");
});
