// 生成前覆盖保护纯函数单测（工单 frontend-es-modules/08）：
// isConflictError（冲突 400 识别）+ conflictDirName（目录名提取）。
// 只测外部行为；CONFLICT_MSG_PREFIX 单源 = fx/generate.js（随域常量迁入）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import { isConflictError, conflictDirName, dirBasename, CONFLICT_MSG_PREFIX } from "../../src/contest_generator/static/js/fx/generate.js";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

const conflictMsg = "桌面上已有同名工程「Auto_Car_STM32」：为避免覆盖你的已有工程，请先删除该目录或修改题名后再生成（不会自动改名或覆盖）。同一赛题换平台再生成时，会自动使用带平台后缀的新目录（如 Auto_Car_MSPM0），不会误删旧工程";

test("isConflictError：前缀命中原 400 文案 → true", () => {
  assert.equal(isConflictError(conflictMsg), true);
});

test("isConflictError：未命中（其他错误/空值/非字符串）→ false", () => {
  assert.equal(isConflictError("AI 服务调用失败：超时"), false);
  assert.equal(isConflictError(""), false);
  assert.equal(isConflictError(null), false);
  assert.equal(isConflictError(undefined), false);
  assert.equal(isConflictError(42), false);
  assert.equal(isConflictError("已存在同名工程（前缀不同）"), false);
  assert.equal(isConflictError("桌面上已有同名工程：无引号形态（非冲突文案）"), false);
});

test("conflictDirName：提取「」内目录名", () => {
  assert.equal(conflictDirName(conflictMsg), "Auto_Car_STM32");
});

test("conflictDirName：无「」/空/非字符串 → 空串（confirm 文案降级）", () => {
  assert.equal(conflictDirName("桌面上已有同名工程：其他文案"), "");
  assert.equal(conflictDirName(""), "");
  assert.equal(conflictDirName(null), "");
  assert.equal(conflictDirName("「只有开头没有闭合"), "");
});

test("dirBasename：取输出目录路径末段（正反斜杠都认，工单 ux-walkthrough-02/03）", () => {
  assert.equal(dirBasename("C:\\Users\\a\\Desktop\\Auto_Car_STM32"), "Auto_Car_STM32");
  assert.equal(dirBasename("/home/user/Desktop/Auto_Car_STM32/"), "Auto_Car_STM32");
  assert.equal(dirBasename("Auto_Car_STM32"), "Auto_Car_STM32");
  assert.equal(dirBasename(""), "");
  assert.equal(dirBasename(null), "");
});

test("isConflictError 与 400 文案前缀一致性锚点（防前后端漂移）", () => {
  // 后端 GenerationConflictError 消息以本常量开头 → isConflictError 才能识别；
  // 单源 = fx/generate.js（index.html 不再定义，防双源回退）
  assert.equal(CONFLICT_MSG_PREFIX, "桌面上已有同名工程「");
  assert.ok(!html.includes("const CONFLICT_MSG_PREFIX"));
});
