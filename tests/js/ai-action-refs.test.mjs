// 结构护栏（工单 ai-action-banner/01）：静态断言「AI 行动中」横幅核心件存在
// ——ui/ai-banner.js 导出 aiActionStart/aiActionStop、fx/ai-action.js 导出
// aiActionStep/aiActionBannerLabel、index.html 槽位、预读接入点成对调用。
// 防删防改名。护栏断言含 :not(.hidden) 开关（评审抓到的阻断级坑：单类
// display:flex 会级联盖过 .hidden{display:none}，横幅永不隐藏）。
// 工单 02 追加：16 个生成页/任务页/母版/参数接入点的静态护栏（成对调用下限）。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const root = "../../src/contest_generator/static/js/";
const read = (p) => readFileSync(new URL(p, import.meta.url), "utf8");

const bannerSrc = read(root + "ui/ai-banner.js");
const actionSrc = read(root + "fx/ai-action.js");
const html = read("../../src/contest_generator/static/index.html");
const recommendSrc = read(root + "ui/generate-recommend.js");

test("ui/ai-banner.js 导出 aiActionStart / aiActionStop", () => {
  assert.match(bannerSrc, /export function aiActionStart\(label\)/);
  assert.match(bannerSrc, /export function aiActionStop\(\)/);
});

test("fx/ai-action.js 导出 aiActionStep 状态机与 aiActionBannerLabel 文案", () => {
  assert.match(actionSrc, /export function aiActionStep\(state, action\)/);
  assert.match(actionSrc, /export function aiActionBannerLabel\(label\)/);
});

test("index.html 含 #ai-action-banner 槽位与 #ai-action-label", () => {
  assert.match(html, /id="ai-action-banner" class="ai-action-banner hidden" role="status"/);
  assert.match(html, /id="ai-action-label"/);
});

test("index.html 横幅显隐走 :not(.hidden) 开关（防 display 级联盖过 .hidden）", () => {
  assert.match(html, /\.ai-action-banner \{ [^}]*display: none/);
  assert.match(html, /\.ai-action-banner:not\(\.hidden\) \{ display: flex; \}/);
});

test("ui/ai-banner.js 归零清空 label 文本（防旧 label 残留）", () => {
  // 探针 3 实证：归零只加 hidden 会留旧 label 文本在 DOM（「AI 行动中：编译修复」
  // 残留），隐藏语义 = 无行动——else 分支必须清空文本
  assert.match(bannerSrc, /else \{\s*el\.classList\.add\("hidden"\);\s*\/\/ 归零清空文本[\s\S]*?if \(labelEl\) labelEl\.textContent = "";\s*\}/);
});

test("index.html 横幅 CSS 含 sticky 吸顶与光带动画", () => {
  assert.match(html, /\.ai-action-banner \{ position: sticky; top: var\(--header-h\)/);
  assert.match(html, /@keyframes ai-flow/);
});

test("预读接入点成对调用（start 在请求前 / stop 在 finally）", () => {
  const startAt = recommendSrc.indexOf('aiActionStart("赛题预读")');
  const stopAt = recommendSrc.indexOf("aiActionStop();");
  assert.ok(startAt >= 0, "预读路径缺 aiActionStart");
  assert.ok(stopAt >= 0, "预读路径缺 aiActionStop");
  assert.ok(startAt < stopAt, "start 必须先于 stop");
});

// ---------------------------------------------------------------------------
// 工单 02：16 个场景接入点静态护栏（防删防改名）。每个接入文件必须 import
// 两函数；每文件 stop 调用数 >= start 调用数（成对下限：只 start 不 stop 会
// 让横幅永远常驻）；关键收尾路径抽查结构（start 在前、finally/终态在内）。
// ---------------------------------------------------------------------------
const coreSrc = read(root + "ui/generate-core.js");
const fixSrc = read(root + "ui/generate-fix.js");
const tasksSrc = read(root + "ui/generate-tasks.js");
const reviseSrc = read(root + "ui/generate-revise.js");
const paramsChatSrc = read(root + "ui/params-chat.js");
const masterSrc = read(root + "ui/master.js");

const importRe = /import \{ aiActionStart, aiActionStop \} from "\/js\/ui\/ai-banner\.js"/;
const srcs = [
  ["generate-recommend.js", recommendSrc],
  ["generate-core.js", coreSrc],
  ["generate-fix.js", fixSrc],
  ["generate-tasks.js", tasksSrc],
  ["generate-revise.js", reviseSrc],
  ["params-chat.js", paramsChatSrc],
  ["master.js", masterSrc],
];

for (const [name, src] of srcs) {
  test(name + " 接入 aiActionStart/aiActionStop import", () => {
    assert.match(src, importRe, name + " 缺 ai-banner import");
  });
  test(name + " stop 调用数 >= start 调用数（成对下限；哨兵结构豁免）", () => {
    const starts = (src.match(/aiActionStart\(/g) || []).length;
    const stops = (src.match(/aiActionStop\(/g) || []).length;
    if (src.includes("releaseBanner")) {
      // 哨兵结构（评审整改）：releaseBanner 单点释放 + 重发前 bannerReleased=false 开新一对，
      // 一 start 一 stop 由哨兵保证——静态数量需 +1（releaseBanner 内那一次）才够覆盖。
      assert.ok(stops + 1 >= starts, name + " 哨兵结构下 stop(" + stops + ") 不足覆盖 start(" + starts + ")");
    } else {
      assert.ok(stops >= starts, name + " stop(" + stops + ") < start(" + starts + ")");
    }
  });
}

test("任务簇接入：六个 start label 就位（规划/执行/想法/修正/商量/讨论）", () => {
  for (const label of ["任务规划", "任务执行", "想法分析", "直接修正", "全局商量", "任务讨论"]) {
    assert.ok(tasksSrc.includes('aiActionStart("' + label + '")'), "任务簇缺 start：" + label);
  }
});

test("修复簇接入：编译修复（两入口）与 AI 修复就位", () => {
  assert.equal((fixSrc.match(/aiActionStart\("编译修复"\)/g) || []).length, 2);
  assert.ok(fixSrc.includes('aiActionStart("AI 修复")'));
});

test("参数咨询 start 紧随 busy=true", () => {
  assert.match(paramsChatSrc, /paramsChatState\.busy = true;\s*aiActionStart\("参数咨询"\);/);
});

test("操作名清单完整（16 场景各一条 start）", () => {
  const labels = [
    "AI 推荐", "选型讨论", "生成骨架", "生成工程", "修订分析", "修订落地",
    "深化", "AI 修复", "编译修复", "参数咨询", "任务规划", "想法分析",
    "任务执行", "任务讨论", "全局商量", "母版提炼",
  ];
  for (const label of labels) {
    const hit = [recommendSrc, coreSrc, fixSrc, tasksSrc, reviseSrc, paramsChatSrc, masterSrc]
      .some((s) => s.includes('aiActionStart("' + label + '")'));
    assert.ok(hit, "缺操作名 start：" + label);
  }
});

test("推荐收尾全覆盖：stopRecProgress 与 done 事件各带 aiActionStop", () => {
  assert.match(recommendSrc, /function stopRecProgress\(\) \{   \/\/ 流未起 \/ 断线路径[\s\S]*?aiActionStop\(\);/);
  assert.match(recommendSrc, /done: \(ev\) => \{\s*recPanel\.finish\(\);\s*aiActionStop\(\);/);
  assert.match(recommendSrc, /question: \(ev\) => \{\s*recPanel\.finish\(\);\s*aiActionStop\(\);/);
  assert.match(recommendSrc, /error: \(ev\) => \{\s*recPanel\.finish\(\);\s*aiActionStop\(\);/);
});

test("生成骨架/生成工程收尾路径含 aiActionStop（finally 内）", () => {
  assert.match(coreSrc, /finally \{\s*aiActionStop\(\);\s*btn\.disabled = false;/);
  assert.match(coreSrc, /\} finally \{ releaseBanner\(\); \$\("btn-generate"\)\.disabled = false; \}/);
  // 覆盖确认弹窗等待期不显示横幅：catch 哨兵 stop + 重发前 reset/start（一 start 一 stop）
  assert.match(coreSrc, /stopStage\(\);\s*releaseBanner\(\);   \/\/ 首段请求已终态/);
  assert.match(coreSrc, /bannerReleased = false;   \/\/ 重发 = 新一对 start\/stop\n\s*aiActionStart\("生成工程"\);/);
});

test("母版提炼终态收口：finishProgress 与 failProgress 各带 aiActionStop", () => {
  assert.match(masterSrc, /function finishProgress\(report\) \{\s*aiActionStop\(\);/);
  assert.match(masterSrc, /function failProgress\(message\) \{\s*aiActionStop\(\);/);
  assert.match(masterSrc, /aiActionStart\("母版提炼"\);[\s\S]*?startProgress\(\);/);
});

test("修订分析/修订落地/深化 start 紧随各自 reviseSetBusy(true)", () => {
  assert.match(reviseSrc, /reviseSetBusy\(true\);\s*aiActionStart\("修订分析"\);/);
  assert.match(reviseSrc, /reviseSetBusy\(true\);\s*aiActionStart\("修订落地"\);/);
  assert.match(reviseSrc, /reviseSetBusy\(true\);\s*aiActionStart\("深化"\);/);
});
