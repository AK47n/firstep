// 生成前覆盖保护纯函数单测（工单 frontend-es-modules/08）：
// isConflictError（冲突 400 识别）+ conflictDirName（目录名提取）。
// 只测外部行为；CONFLICT_MSG_PREFIX 单源 = fx/generate.js（随域常量迁入）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import { isConflictError, conflictDirName, dirBasename, CONFLICT_MSG_PREFIX } from "../../src/contest_generator/static/js/fx/generate.js";
import { parseHttpError } from "../../src/contest_generator/static/js/fx/errors.js";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

const conflictMsg = "桌面上已有同名工程「Auto_Car_STM32」：为避免覆盖你的已有工程，请先删除该目录或修改题名后再生成（不会自动改名或覆盖）。同一赛题换平台再生成时，会自动使用带平台后缀的新目录（如 Auto_Car_MSPM0），不会误删旧工程";

// 真机 message 形态（工单 gen-chain-audit/01）：app.js 的 handle() 经
// fx/errors.parseError 统一加 `请求失败（HTTP 400）：` 前缀之后才 throw，
// generate-core 的 `catch (e)` 拿到的就是这一份——这是唯一真实入参。
const conflictMsgAsCaught = parseHttpError(400, { detail: conflictMsg }).text;

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

// 工单 gen-chain-audit/01（真机 W2b 抓到的 bug）：**唯一真实入参**是 catch 到
// 的那份 message —— 它已被 fx/errors 加上 `请求失败（HTTP 400）：` 前缀。
// 旧判据 `indexOf(prefix) === 0` 在真机上恒 false → 覆盖确认弹窗永不出现。
test("isConflictError：真机 message 形态（带 HTTP 400 前缀）仍命中 → true", () => {
  assert.ok(conflictMsgAsCaught.includes(CONFLICT_MSG_PREFIX), "前置：被抛出的 message 里应当含冲突前缀");
  assert.notEqual(conflictMsgAsCaught.indexOf(CONFLICT_MSG_PREFIX), 0,
    "前置：被抛出的 message **不以**冲突前缀开头（错误解析统一加了 HTTP 前缀）—— 这正是旧判据失效的原因");
  assert.equal(isConflictError(conflictMsgAsCaught), true,
    "isConflictError 必须识别带 HTTP 前缀的真机 message，否则桌面同名工程的覆盖确认入口不可达");
});

test("isConflictError：前缀出现在中段仍能提取目录名（覆盖确认文案要用）", () => {
  assert.equal(conflictDirName(conflictMsgAsCaught), "Auto_Car_STM32");
});

// 结构守卫：生产代码里不得再出现「前缀必须打头」的实现形状（防回退）。
test("isConflictError 判据不得回退成「开头匹配」", () => {
  const src = readFileSync(
    new URL("../../src/contest_generator/static/js/fx/generate.js", import.meta.url), "utf8");
  const body = src.slice(src.indexOf("export function isConflictError"));
  const fn = body.slice(0, body.indexOf("}"));
  assert.ok(!/indexOf\s*\(\s*CONFLICT_MSG_PREFIX\s*\)/.test(fn),
    "fx/generate.js 的 isConflictError 又用 indexOf(CONFLICT_MSG_PREFIX) 判开头了 —— 真机 message 带 HTTP 前缀，会再次失效");
  assert.ok(/includes\s*\(\s*CONFLICT_MSG_PREFIX\s*\)/.test(fn),
    "isConflictError 应当用 includes(CONFLICT_MSG_PREFIX) 判「包含」");
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
