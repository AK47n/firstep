// settings-collapse.test.mjs — 设置页折叠纯函数单测（工单 settings-infoarch/01/02/03）：
// parseSettingsCollapse / settingsDefaultCollapsed / effectiveCollapsed /
// applySettingsCollapseState（卡片 + 计费小节两分支）+ settingsMasterLabel / sectionCollapseLabel。
// 核心块 syncCollapseBtn 已迁 fx/generate.js（工单 08），跨模块 import 注入；
// 设置页折叠块仍在 index.html（工单 10 迁入 fx/settings.js）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import { syncCollapseBtn } from "../../src/contest_generator/static/js/fx/generate.js";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 设置页折叠块：SETTINGS_COLLAPSE_KEY 常量起到 initSettingsCollapse 止
const match = html.match(
  /const SETTINGS_COLLAPSE_KEY[\s\S]*?function initSettingsCollapse[\s\S]*?\n\}/
);
assert.ok(match, "index.html 中未找到设置页折叠函数块（改名了？）");

const fns = new Function(
  "syncCollapseBtn",
  match[0] + "\nreturn { parseSettingsCollapse, settingsDefaultCollapsed, effectiveCollapsed, applySettingsCollapseState, settingsMasterLabel, sectionCollapseLabel };"
)(syncCollapseBtn);
const { parseSettingsCollapse, settingsDefaultCollapsed, effectiveCollapsed, applySettingsCollapseState, settingsMasterLabel, sectionCollapseLabel } = fns;
for (const name of ["parseSettingsCollapse", "settingsDefaultCollapsed", "effectiveCollapsed", "applySettingsCollapseState", "settingsMasterLabel", "sectionCollapseLabel"]) {
  assert.equal(typeof fns[name], "function", `${name} 未从 index.html 抽取成功`);
}

// 存储键契约：firstep.settingsCollapse.v1 必须出现在 index.html（防漂移）
assert.match(html, /firstep\.settingsCollapse\.v1/, "设置页折叠存储键 firstep.settingsCollapse.v1 缺失");

// 假卡片：只实现 classList.toggle / contains / querySelector(".card-collapse") /
// title/aria-label 回写；withNestedHead=true 时模拟「卡片内嵌计费小节」的祖先
// 关系（querySelector 会命中后代 head，但判别应看自身 class 而非后代查询）
function fakeCardEl(collapsed, withBtn = true, withNestedHead = false) {
  const state = { collapsed: !!collapsed, btnTitle: "", ariaLabel: "", headTouched: false };
  const btn = {
    set title(v) { state.btnTitle = v; },
    setAttribute(k, v) { if (k === "aria-label") state.ariaLabel = v; },
  };
  const head = {
    set title(v) { state.headTouched = true; },
    setAttribute(k, v) { if (k === "aria-label") state.headTouched = true; },
  };
  return {
    _state: state,
    _btn: btn,
    _head: head,
    querySelector: (sel) =>
      sel === ".settings-collapse-head" && withNestedHead ? head
      : sel === ".card-collapse" && withBtn ? btn : null,
    classList: {
      toggle: (k, v) => { if (k === "collapsed") state.collapsed = v; },
      contains: (k) => k === "collapsed" ? state.collapsed : false,
    },
  };
}

// 假计费小节：自身含 settings-collapse 类（判别走小节分支），
// querySelector(".settings-collapse-head") 返回头按钮，无 .card-collapse
function fakeSectionEl(collapsed) {
  const state = { collapsed: !!collapsed, headTitle: "", ariaLabel: "" };
  const head = {
    set title(v) { state.headTitle = v; },
    setAttribute(k, v) { if (k === "aria-label") state.ariaLabel = v; },
  };
  return {
    _state: state,
    querySelector: (sel) =>
      sel === ".settings-collapse-head" ? head : sel === ".card-collapse" ? null : null,
    classList: {
      toggle: (k, v) => { if (k === "collapsed") state.collapsed = v; },
      contains: (k) => k === "settings-collapse" ? true : (k === "collapsed" ? state.collapsed : false),
    },
  };
}

test("parseSettingsCollapse：空/垃圾输入回 { }", () => {
  assert.deepEqual(parseSettingsCollapse(""), {});
  assert.deepEqual(parseSettingsCollapse("null"), {});
  assert.deepEqual(parseSettingsCollapse("{bad json"), {});
  assert.deepEqual(parseSettingsCollapse("42"), {});
  assert.deepEqual(parseSettingsCollapse("[]"), {});
});

test("parseSettingsCollapse：合法 JSON 对象透传", () => {
  assert.deepEqual(parseSettingsCollapse('{"libs":true,"llm-api":false}'), { libs: true, "llm-api": false });
});

test("settingsDefaultCollapsed：默认集成员判定", () => {
  assert.equal(settingsDefaultCollapsed("libs"), true);
  assert.equal(settingsDefaultCollapsed("toolchain"), true);
  assert.equal(settingsDefaultCollapsed("local-llm"), true);
  assert.equal(settingsDefaultCollapsed("vision"), true);
  assert.equal(settingsDefaultCollapsed("ai-billing"), true);
  assert.equal(settingsDefaultCollapsed("llm-api"), false);
  assert.equal(settingsDefaultCollapsed("app"), false);
  assert.equal(settingsDefaultCollapsed("usage"), false);
  assert.equal(settingsDefaultCollapsed("recent-wf"), false);
  assert.equal(settingsDefaultCollapsed("no-such-id"), false);
});

test("effectiveCollapsed：stored 覆盖默认（含显式 false 展开）", () => {
  assert.equal(effectiveCollapsed("libs", {}), true);          // 默认收起
  assert.equal(effectiveCollapsed("libs", { libs: false }), false); // 用户展开
  assert.equal(effectiveCollapsed("llm-api", {}), false);      // 默认展开
  assert.equal(effectiveCollapsed("llm-api", { "llm-api": true }), true); // 用户收起
  assert.equal(effectiveCollapsed("app", { app: true }), true);
  assert.equal(effectiveCollapsed("unknown", {}), false);
});

test("applySettingsCollapseState：卡片分支 class + title/aria-label 同步", () => {
  const el = fakeCardEl(false);
  applySettingsCollapseState(el, true);
  assert.equal(el._state.collapsed, true);
  assert.equal(el._state.btnTitle, "展开");
  assert.equal(el._state.ariaLabel, "展开该卡片");
  applySettingsCollapseState(el, false);
  assert.equal(el._state.collapsed, false);
  assert.equal(el._state.btnTitle, "折叠");
  assert.equal(el._state.ariaLabel, "折叠该卡片");
});

test("applySettingsCollapseState：计费小节分支 class + 头按钮 aria-label", () => {
  const el = fakeSectionEl(false);
  applySettingsCollapseState(el, true);
  assert.equal(el._state.collapsed, true);
  assert.equal(el._state.headTitle, "展开");
  assert.equal(el._state.ariaLabel, "展开计费区");
  applySettingsCollapseState(el, false);
  assert.equal(el._state.collapsed, false);
  assert.equal(el._state.ariaLabel, "折叠计费区");
});

test("applySettingsCollapseState：无按钮元素只切 class 不崩", () => {
  const el = fakeCardEl(false, false);
  applySettingsCollapseState(el, true);
  assert.equal(el._state.collapsed, true);
});

test("applySettingsCollapseState：卡片内嵌计费小节 head 后代仍走卡片分支（回归：祖先误判）", () => {
  const el = fakeCardEl(false, true, true);   // querySelector 会命中后代 .settings-collapse-head
  applySettingsCollapseState(el, true);
  assert.equal(el._state.collapsed, true);
  assert.equal(el._state.btnTitle, "展开");
  assert.equal(el._state.ariaLabel, "展开该卡片");
  assert.equal(el._state.headTouched, false);   // 后代 head 不应被触碰
});

test("settingsMasterLabel：全部折叠/非全折双向", () => {
  assert.equal(settingsMasterLabel(true), "全部展开");
  assert.equal(settingsMasterLabel(false), "全部收起");
});

test("sectionCollapseLabel：计费区折叠/展开双向", () => {
  assert.equal(sectionCollapseLabel(true), "展开计费区");
  assert.equal(sectionCollapseLabel(false), "折叠计费区");
});
