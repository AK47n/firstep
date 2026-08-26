// confirm 统一守卫（工单 master-library-ui-2/05）：static/js 全树（ui + fx +
// app.js，递归）静态扫描无裸 confirm( / alert( 调用——原生窗已全迁共享弹窗
// （confirmModal）与 toast；扫描剥注释后再匹配（注释里允许出现历史的
// confirm() 字样）。
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const STATIC_JS_DIR = fileURLToPath(
  new URL("../../src/contest_generator/static/js/", import.meta.url),
);

function collectJsFiles(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...collectJsFiles(full));
    else if (entry.name.endsWith(".js")) out.push(full);
  }
  return out;
}

const jsFiles = collectJsFiles(STATIC_JS_DIR);

function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, " ")   // 块注释
    .replace(/\/\/[^\n]*/g, " ");        // 行注释
}

test("static/js 全树无裸 confirm( / alert( 调用（原生窗已全迁共享弹窗与 toast）", () => {
  assert.ok(jsFiles.length > 0, "扫描面为空：static/js 树未收集到文件");
  for (const f of jsFiles) {
    const src = stripComments(fs.readFileSync(f, "utf-8"));
    assert.ok(!/\bconfirm\(/.test(src), f + " 仍含裸 confirm( 调用");
    assert.ok(!/\balert\(/.test(src), f + " 仍含裸 alert( 调用");
  }
});
