// 生成前覆盖保护纯函数单测（工单 generate-overwrite/01）：
// isConflictError（冲突 400 识别）+ conflictDirName（目录名提取）。
// 只测外部行为；CONFLICT_MSG_PREFIX 经兄弟注入（同既有先例）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取（同 module-info-dialog.test.mjs 范式）；deps = 注入的兄弟函数依赖
function extract(name, deps) {
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
        const fnSrc = html.slice(start, i + 1);
        if (deps && Object.keys(deps).length) {
          return new Function(...Object.keys(deps), "return (" + fnSrc + ")")(
            ...Object.values(deps)
          );
        }
        return new Function("return (" + fnSrc + ")")();
      }
    }
  }
  throw new Error("未找到 " + name + " 函数体结束花括号");
}

// 与 index.html 内联 const 逐字一致（测试抽取函数体时注入同名常量）；
// 前缀含「：只认完整前缀形态（后端 f-string 模板恒为「前缀+「」），无「 的非冲突文案不误判。
const CONFLICT_MSG_PREFIX = "桌面上已有同名工程「";
const isConflictError = extract("isConflictError", { CONFLICT_MSG_PREFIX });
const conflictDirName = extract("conflictDirName");

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

test("isConflictError 与 400 文案前缀一致性锚点（防前后端漂移）", () => {
  // 后端 GenerationConflictError 消息以本常量开头 → isConflictError 才能识别
  assert.ok(html.includes("const CONFLICT_MSG_PREFIX = \"" + CONFLICT_MSG_PREFIX + "\""));
});
