// step7DoneState 纯函数单测（工单 step7-done/01）：步骤 7「引脚配置」完成判定修正
// —— 原逻辑只在 pinBindings 非空时才标完成，默认布线 / 无需配置情况下永不显示完成。
// 修正后：平台已选且已展开模块，且满足其一——无角色（无需配置）/ 已显式绑定 /
// 多实例已配引脚 / 已按默认布线生成成功。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取（同 gen-overview.test.mjs / readiness-checks.test.mjs 范式）
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

const step7DoneState = extract("step7DoneState");

const base = { chosenPlatform: "stm32", expandedCount: 2, roles: [], roleBound: false, instBound: false, generated: false };

test("未选平台：不予完成（引脚无从谈起）", () => {
  assert.equal(step7DoneState({ ...base, chosenPlatform: "" }), false);
});

test("已选平台但未展开模块：premature，不予完成", () => {
  assert.equal(step7DoneState({ ...base, expandedCount: 0 }), false);
});

test("已展开但无引脚角色：无需配置 = 完成", () => {
  assert.equal(step7DoneState(base), true);
});

test("有角色未绑定未生成：未完成（默认流程生成前保持待办）", () => {
  assert.equal(step7DoneState({ ...base, roles: [{}] }), false);
});

test("有角色已显式绑定：完成", () => {
  assert.equal(step7DoneState({ ...base, roles: [{}], roleBound: true }), true);
});

test("有角色未绑定但已生成成功：默认布线被隐式接受 = 完成", () => {
  assert.equal(step7DoneState({ ...base, roles: [{}], generated: true }), true);
});

test("多实例已配引脚（无角色绑定、未生成）：完成", () => {
  assert.equal(step7DoneState({ ...base, roles: [{}, {}], instBound: true }), true);
});

test("多实例未配引脚：维持未完成", () => {
  assert.equal(step7DoneState({ ...base, roles: [{}], instBound: false }), false);
});
