// 结构护栏（工单 newcomer-glossary/01）：静态断言新手词表核心件存在
// ——index.html 槽位 #glossary-card（位于左侧 .gen-sidebar 内、step-nav 之后）、
// ui/glossary.js 导出 initGlossary、index.html 成对 import + 调用。
// 防删防改名（对齐 ai-action-refs / step-done-refs 先例）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
const glue = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/glossary.js", import.meta.url),
  "utf8"
);

test("index.html 含 #glossary-card 容器（生成页底部槽位）", () => {
  assert.match(html, /id="glossary-card" class="glossary-card"/);
});

test("词表卡位置：左侧 .gen-sidebar 内、step-nav 之后（生成页内）", () => {
  const afterNav = html.indexOf('id="step-nav"');
  const slotAt = html.indexOf('id="glossary-card"');
  const stepsEnd = html.indexOf('id="tab-library"');
  assert.ok(
    html.indexOf('class="gen-sidebar"') >= 0 && afterNav >= 0 && slotAt > afterNav,
    "词表卡不在 .gen-sidebar / step-nav 之后"
  );
  assert.ok(slotAt < stepsEnd, "词表卡不在生成页内");
});

test("ui/glossary.js 导出 initGlossary", () => {
  assert.match(glue, /export function initGlossary\(\)/);
});

test("index.html 成对接入：import + initGlossary() 调用", () => {
  assert.match(html, /import \{ initGlossary \} from "\/js\/ui\/glossary\.js"/);
  assert.match(html, /initGlossary\(\);/);
});
