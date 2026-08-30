// tests/js/overview-dir-warn-guard.test.mjs — 就绪总览接入输出目录预警的接线护栏
// （工单 beginner-gap-closure/07）：钉住「总览摘要显示 ⚠ 预警段 + step9 同源标
// warn + 共享请求（按载荷 key 缓存 / 同 key 在途复用 / 失败静默 / 防重刷循环）」
// 不被后续改动拆散。静态断言（源级守卫），纯函数行为见 gen-overview.test.mjs
// 与 readiness-checks.test.mjs。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const stepsSrc = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/generate-steps.js", import.meta.url),
  "utf8"
);
const readinessSrc = readFileSync(
  new URL("../../src/contest_generator/static/js/ui/generate-readiness.js", import.meta.url),
  "utf8"
);

test("共享预警请求：generate-readiness.js 导出 ensure/get/cached 三件套（工单 07）", () => {
  assert.match(readinessSrc, /export async function ensureOutputDirWarn\(\)/);
  assert.match(readinessSrc, /export function getOutputDirWarnRow\(\)/);
  assert.match(readinessSrc, /export function outputDirWarnCached\(\)/);
  assert.match(readinessSrc, /function outputDirWarnPayload\(\)/);
  assert.match(readinessSrc, /_dirWarnInflight/, "应有同 key 在途复用状态");
});

test("面板路径行为不变：refreshOutputDirWarn 写 #readiness-warn-slot（工单 06 既有）", () => {
  assert.match(readinessSrc, /await ensureOutputDirWarn\(\)/);
  assert.match(readinessSrc, /readiness-warn-slot/);
});

test("总览接线：generate-steps.js 导入共享三件套（单条 import）", () => {
  assert.match(
    stepsSrc,
    /import \{ readinessState, desktopTopicOutputEnabled, ensureOutputDirWarn, getOutputDirWarnRow, outputDirWarnCached \} from "\/js\/ui\/generate-readiness\.js";/
  );
});

test("genOverviewWarn(9)：输出目录预警时第 9 步视为有警告（chip/dot/卡徽章同源）", () => {
  assert.match(stepsSrc, /stepNo === 9 && getOutputDirWarnRow\(\) != null/);
});

test("总览摘要：genOverviewSummaryHTML 调用带 getOutputDirWarnRow() 结果（第 6 参）", () => {
  assert.match(stepsSrc, /const dirWarn = getOutputDirWarnRow\(\);/);
  assert.match(
    stepsSrc,
    /genOverviewSummaryHTML\(doneArr, genOverviewTitles,\s*GEN_CRITICAL_STEPS, GEN_RECOMMENDED_STEPS, navHint, dirWarn\);/
  );
});

test("预警数据仅缓存未命中时取一次（防 fetch 后重刷循环）", () => {
  assert.match(stepsSrc, /if \(!outputDirWarnCached\(\)\)/);
  assert.match(stepsSrc, /void ensureOutputDirWarn\(\)\.then\(/);
  assert.match(stepsSrc, /refreshGenOverview\(\);/, "取回后应重刷一次总览");
});
