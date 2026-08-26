// generationOutputDirPayload 纯函数单测（工单 frontend-es-modules/08）：
// 桌面输出默认勾选时可不填手动目录；取消勾选时按手动目录发给后端。
// 直接 import fx/generate.js。
import test from "node:test";
import assert from "node:assert/strict";
import { generationOutputDirPayload } from "../../src/contest_generator/static/js/fx/generate.js";

test("桌面输出开启且手动目录为空 → 发送占位目录", () => {
  assert.equal(generationOutputDirPayload("", true), ".");
});

test("桌面输出开启且已有手动目录 → 原样带上但后端会忽略", () => {
  assert.equal(generationOutputDirPayload("D:/contest/demo", true), "D:/contest/demo");
});

test("桌面输出关闭 → 使用手动目录", () => {
  assert.equal(generationOutputDirPayload("D:/contest/demo", false), "D:/contest/demo");
});
