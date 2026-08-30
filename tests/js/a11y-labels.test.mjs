// tests/js/a11y-labels.test.mjs — 裸输入 aria-label 补齐（工单 ux-walkthrough-02/19）：
// INPUT_A11Y_LABELS 的每个 id 必须真实存在于 index.html（防死键——补了
// 标签却找不到元素）；标签文本非空且含中文（名称与可见 placeholder 一致）。
// 另抽查：确认弹窗工厂的焦点逻辑不在此层（ui 胶水由浏览器侧验证）。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { INPUT_A11Y_LABELS } from "../../src/contest_generator/static/js/ui/a11y.js";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8",
);

test("INPUT_A11Y_LABELS 非空且每条标签为中文说明", () => {
  assert.ok(Object.keys(INPUT_A11Y_LABELS).length > 20, "覆盖应达「大量裸输入」量级");
  for (const [id, label] of Object.entries(INPUT_A11Y_LABELS)) {
    assert.ok(label && label.trim().length > 0, id + " 标签为空");
    assert.match(label, /[\u4e00-\u9fff]/, id + " 标签应为中文");
  }
});

test("每个 id 都真实存在于 index.html（input/textarea/select），防死键", () => {
  for (const id of Object.keys(INPUT_A11Y_LABELS)) {
    const re = new RegExp(
      '<(input|textarea|select)[^>]*id="' + id + '"');
    assert.match(html, re, "index.html 应含元素 #" + id);
  }
});

test("已有关联 label（for= 或包裹）的输入不在补齐表重复声明（表只放裸输入）", () => {
  // 手工抽查有关联输入的 id 不在表中：output-dir（label for）、
  // set-vision-detail-qa（label for）、project-dirs（label for——
  // 评审整改：曾误入表且文案 ≠ 可见 label，会覆盖关联名）
  for (const id of ["output-dir", "set-vision-detail-qa", "project-dirs"]) {
    assert.ok(!(id in INPUT_A11Y_LABELS),
      "#" + id + " 已有 label for 关联，不应重复进补齐表（aria-label 会覆盖可见文本）");
  }
});
