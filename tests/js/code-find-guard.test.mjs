// tests/js/code-find-guard.test.mjs — 代码栏查找/替换交互守卫（2026-09-09 在途盘点补口）。
//
// 两个验收项在盘点时被判「部分落地」，本守卫把它们钉住：
//   1. 无命中时「替换 / 替换并下一处 / 全部替换」按钮禁用（此前只靠点击后 toast
//      兜底）——按钮态与计数同源（updateFindCount 内统一同步）。
//   2. 命中列表点击要成为「当前命中」（此前只 editJumpToLine，editorFind.index
//      不动，「第 N / 共 M 处」与当前高亮不跟随点击项）。
// 均为 DOM 胶水（ui 层），照 confirm-guard / handoff-note-guard 先例做静态源断言
// + 模块解析守卫（防「改文案顺坏拼接」）。
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import test from "node:test";
import assert from "node:assert/strict";

const src = (p) =>
  readFileSync(new URL("../../src/contest_generator/static/js/" + p, import.meta.url), "utf8");
const codeviewUi = src("ui/codeview.js");
const codeeditorUi = src("ui/codeeditor.js");

test("替换按钮可用态：由 updateFindCount 与计数同源同步（无命中 = 禁用）", () => {
  assert.ok(codeviewUi.includes("function setReplaceButtonsDisabled(disabled)"));
  assert.ok(codeviewUi.includes("setReplaceButtonsDisabled(!(q && status && status.total))"));
  for (const id of ["btn-code-replace-one", "btn-code-replace-next", "btn-code-replace-all"]) {
    assert.ok(codeviewUi.includes(`"${id}"`), `替换按钮 ${id} 未纳入可用态同步`);
  }
  // 初始态：进代码栏即禁用（无查询 = 无命中）
  assert.ok(codeviewUi.includes('updateFindCount({ total: 0, current: -1 }, "")'));
});

test("命中列表点击：更新当前命中索引 + 计数（不再只跳转）", () => {
  assert.ok(codeeditorUi.includes("export function editorFindSetCurrent(line)"));
  assert.ok(codeeditorUi.includes("editorFind.ranges.findIndex((r) => r.line === line)"));
  assert.ok(codeviewUi.includes("editorFindSetCurrent,"), "未从 codeeditor 导入 editorFindSetCurrent");
  assert.ok(codeviewUi.includes("const st = editorFindSetCurrent(line);"));
  assert.ok(codeviewUi.includes("updateFindCount(st, findInput ? findInput.value : \"\");"));
});

test("解析型守卫：改动的 ui 模块可解析", () => {
  const files = [
    "src/contest_generator/static/js/ui/codeview.js",
    "src/contest_generator/static/js/ui/codeeditor.js",
  ];
  const script = [
    'const fs=require("fs"),vm=require("vm");',
    "for(const f of process.argv.slice(1)){",
    '  new vm.SourceTextModule(fs.readFileSync(f,"utf8"),{identifier:f});',
    "}",
  ].join("");
  const r = spawnSync(process.execPath,
    ["--no-warnings", "--experimental-vm-modules", "-e", script, ...files],
    { cwd: new URL("../..", import.meta.url), encoding: "utf8" });
  assert.equal(r.status, 0, `模块解析失败：${r.stderr || r.stdout}`);
});
