// renderPriceReference 重绘前清空 tbody（防重复累积）结构钉：
// loadSettings 每次进设置页 / 保存设置都会调用 renderPriceReference，
// appendChild 追加不清空会把表格重复累积（曾出现重复 4 遍）。
// 运行：node --test tests/js/
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);
// 函数体断言按归属指向 ui/settings.js（阶段 2 工单 10 重指向）
const settingsSrc = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/settings.js", import.meta.url),
  "utf8"
);

test("renderPriceReference 重绘前清空 price-ref-rows", () => {
  const match = settingsSrc.match(/function renderPriceReference[\s\S]*?\n\}/);
  assert.ok(match, "settings.js 中未找到 renderPriceReference 函数体（改名了？）");
  const body = match[0];
  // 清空语句必须在 appendChild 之前（先清后画）
  const clearIdx = body.indexOf('rows.innerHTML = ""');
  const appendIdx = body.indexOf("rows.appendChild(tr)");
  assert.ok(clearIdx >= 0, "renderPriceReference 缺少 tbody 清空语句（重复累积回归）");
  assert.ok(appendIdx > clearIdx, "清空语句必须在追加之前");
});

test("index.html 定价表 tbody 存在且数据单源 = 后端（调用点随簇迁 settings.js）", () => {
  assert.match(html, /id="price-ref-rows"/);
  assert.match(settingsSrc, /renderPriceReference\(s\.price_reference\)/);
});
