// maincContentEmpty / maincFullscreenLabel 纯函数单测（工单 mainc-tools/01）：
// main.c 骨架工具栏的「空内容判断」与「全屏按钮文案切换」。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取（同 gen-overview.test.mjs，防 `} else {` 提前截断）
function extract(name) {
  const start = html.indexOf("function " + name);
  assert.ok(start !== -1, "index.html 中未找到 " + name + " 函数体（改名了？）");
  const open = html.indexOf("{", start);
  assert.ok(open !== -1, name + " 函数体缺少左花括号");
  let depth = 0;
  for (let i = open; i < html.length; i++) {
    if (html[i] === "{") depth++;
    else if (html[i] === "}") {
      depth--;
      if (depth === 0) {
        return new Function("return (" + html.slice(start, i + 1) + ")")();
      }
    }
  }
  throw new Error("未找到 " + name + " 函数体结束花括号");
}

const maincContentEmpty = extract("maincContentEmpty");
const maincFullscreenLabel = extract("maincFullscreenLabel");

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
