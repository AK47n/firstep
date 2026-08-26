// 阶段 2 工单 12：推荐簇 A 迁 ui/generate-recommend.js + 步骤状态核心迁
// ui/step-state.js（同票交付；A↔ST 循环 cut 方案）。
// 删除段（物理升序，内容锚点寻址）：A 状态声明 / A 簇主体（2303-3061）/
// useTopic / ST 核心（步骤导航 + 完成态）/ ST 进度条 / 卡片折叠。
// host 改造：restoreDraft 三 setter / readiness setRecommendClarifications /
// syncStep7 六调用点参数化 / 启动区 setClusterDeps + setOnStepChange 注册 /
// 顶部 import 行。全程 CRLF 感知。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };

if (lines.some((l) => l.includes('from "/js/ui/generate-recommend.js"'))) throw new Error("import already present");

// ---- 1) host import：files.js import 之后追加两行
{
  const i = must(lines.findIndex((l) => l.includes('from "/js/ui/files.js"')), "files import");
  lines.splice(i + 1, 0,
    'import { renderPlatforms, renderModulePool, renderSelected, renderWarnings, renderRecommendResult, startRecommend, loadReferencePicker, useTopic, openModuleInfo, chosenPlatform, selectedSlugs, expanded, lastRecommend, selectedReferenceIds, autoReferenceIds, pythonTemplates, scorePoints, setChosenPlatform, setSelectedSlugs, setCurrentTopicId, setRecommendClarifications, setClusterDeps } from "/js/ui/generate-recommend.js";',
    'import { stepCard, markStepDone, markStepUndone, syncStep7, stepDoneSet, STEP_NAV_CARD_SELECTOR, initCardCollapse, setOnStepChange } from "/js/ui/step-state.js";');
}

// ---- 2) A 状态声明（全局状态段）→ 注记（instances / instancePinTarget 留 host）
{
  const a = must(lines.findIndex((l) => l === "// 全局状态"), "全局状态 header");
  const dashA = a - 1;
  if (!lines[dashA].startsWith("// ------")) throw new Error("dash before 全局状态 not found");
  const b = must(lines.findIndex((l) => l.startsWith("let instances = {}")), "instances decl");
  const removed = lines.slice(dashA, b).join(eol);
  for (const n of ["selectedSlugs", "expanded", "pythonTemplates", "warnings", "scorePoints"]) {
    if (!new RegExp("let\\s+" + n + "\\b").test(removed)) throw new Error("missing state " + n);
  }
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 全局状态",
    "// ---------------------------------------------------------------------------",
    "// 生成页推荐簇状态（selectedSlugs / expanded / pythonTemplates / warnings /",
    "// scorePoints / chosenPlatform / currentTopicId / topicPdfTextVisible /",
    "// lastRecommend / recProblem / recommendClarifications / selectedReferenceIds /",
    "// autoReferenceIds / referenceEntries）已随簇迁至 static/js/ui/generate-recommend.js",
    "// （阶段 2 工单 12）：host 经顶部 import 活绑定只读，写入经各 setter",
    "// （setChosenPlatform / setSelectedSlugs / setCurrentTopicId /",
    "// setRecommendClarifications）。instances / instancePinTarget 属引脚-多实例簇",
    "// （工单 13 迁），留 host。",
  ];
  lines.splice(dashA, b - dashA, ...note);
}

// ---- 3) A 簇主体（平台选择 → renderWarnings）→ 注记
{
  const a = must(lines.findIndex((l) => l.startsWith("// 生成页：2. 平台选择")), "A cluster header");
  const dashA = a - 1;
  if (!lines[dashA].startsWith("// ------")) throw new Error("dash before A cluster not found");
  const b = must(lines.findIndex((l) => l.startsWith("// 生成页：6.5 多实例配置")), "6.5 header");
  const dashB = b - 1;
  if (!lines[dashB].startsWith("// ------")) throw new Error("dash before 6.5 header not found");
  const removed = lines.slice(dashA, dashB).join(eol);
  for (const n of ["renderPlatforms", "startRecommend", "renderModulePool", "openModuleInfo", "renderSelected", "renderWarnings", "renderRecommendResult", "loadReferencePicker", "initModuleGrid", "renderRefSelected", "clearTopicSummary"]) {
    if (!new RegExp("function\\s+" + n + "\\b").test(removed)) throw new Error("missing function " + n);
  }
  if (!removed.includes("const recPanel = makeProgressPanel(")) throw new Error("missing recPanel");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 生成页：1-3 题面 / 推荐 / 参考选择 + 5 模块池 / 选中 / 警告（推荐簇 A）",
    "// ---------------------------------------------------------------------------",
    "// 已迁至 static/js/ui/generate-recommend.js（阶段 2 工单 12）：题面 PDF viewer /",
    "// 上传抽取 / 历史赛题取题面 useTopic / AI 推荐 SSE 流（recPanel / 进度 / 澄清）/",
    "// 参考文件选择器 / 模块池与推荐结果 / 已选清单与副产物模板 / 平台警告与功能组",
    "// 冲突 / 平台卡 renderPlatforms。状态随簇（chosenPlatform / selectedSlugs 等，",
    "// host 经 import 活绑定读、经 setter 写）；host 侧跨簇服务（引脚-多实例 /",
    "// 修复中心 / 草稿）经 setClusterDeps 接缝注册（见启动区），工单 13 / 16 / 18",
    "// 迁出后改静态 import。",
    "",
  ];
  lines.splice(dashA, dashB - dashA, ...note);
}

// ---- 4) useTopic → 注记
{
  const a = must(lines.findIndex((l) => l.startsWith("/** 赛题库「用此题生成」")), "useTopic jsdoc");
  const b = must(lines.findIndex((l) => l.startsWith("function renderProofreadRows()")), "renderProofreadRows");
  const removed = lines.slice(a, b).join(eol);
  if (!/async function useTopic\(key\)/.test(removed)) throw new Error("missing useTopic");
  const note = [
    "// 赛题库「用此题生成」已迁至 static/js/ui/generate-recommend.js（阶段 2 工单 12）：",
    "// useTopic 事务（取题面 → 填生成页 → 步 1 完成 → 切 tab 滚顶 → 加载题面页图）。",
    "// host（topic 簇）调用点 6639 / 6698 不变，经顶部 import 引用。",
    "",
  ];
  lines.splice(a, b - a, ...note);
}

// ---- 5) ST 核心（步骤导航 + 完成态 + syncStep7 + initStepNav IIFE）→ 注记
{
  const a = must(lines.findIndex((l) => l.startsWith("// 生成页步骤导航（工单 ui-polish/02）")), "step-nav header");
  const dashA = a - 1;
  if (!lines[dashA].startsWith("// ------")) throw new Error("dash before step-nav not found");
  const b = must(lines.findIndex((l) => l.startsWith("// 生成页草稿自动记忆（工单 ui-polish-3/01）")), "draft header");
  const dashB = b - 1;
  if (!lines[dashB].startsWith("// ------")) throw new Error("dash before draft header not found");
  const removed = lines.slice(dashA, dashB).join(eol);
  for (const n of ["stepCard", "markStepDone", "markStepUndone", "unmarkSteps", "syncStep7", "initStepNav"]) {
    if (!new RegExp("(function|const)\\s+" + n + "\\b").test(removed)) throw new Error("missing ST " + n);
  }
  if (!removed.includes("const STEP_NAV_CARD_SELECTOR")) throw new Error("missing STEP_NAV_CARD_SELECTOR");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 生成页步骤导航 / 完成态核心（工单 ui-polish/02）：已迁至",
    "// static/js/ui/step-state.js（阶段 2 工单 12）——STEP_NAV_CARD_SELECTOR /",
    "// stepCard / markStepDone / markStepUndone / unmarkSteps / syncStep7 /",
    "// initStepNav IIFE；host 经顶部 import 调用（syncStep7 已参数化，调用点传",
    "// {platform, expanded, roles, bindings, instances}）与读 stepDoneSet。",
    "",
  ];
  lines.splice(dashA, dashB - dashA, ...note);
}

// ---- 6) ST 进度条（STEP_TOTAL / stepDoneSet / syncStepDone / renderStepProgress）→ 注记
{
  const a = must(lines.findIndex((l) => l.startsWith("// 顶部流程进度条（工单 ui-polish-3/02）")), "progress header");
  const dashA = a - 1;
  if (!lines[dashA].startsWith("// ------")) throw new Error("dash before progress not found");
  const b = must(lines.findIndex((l) => l.startsWith("// 生成页就绪总览（工单 gen-overview/01）")), "overview header");
  const dashB = b - 1;
  if (!lines[dashB].startsWith("// ------")) throw new Error("dash before overview header not found");
  const removed = lines.slice(dashA, dashB).join(eol);
  for (const n of ["STEP_TOTAL", "stepDoneSet", "syncStepDone", "renderStepProgress"]) {
    if (!new RegExp("(const|function)\\s+" + n + "\\b").test(removed)) throw new Error("missing progress " + n);
  }
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 步骤完成集合与顶部进度条（工单 ui-polish-3/02）：STEP_TOTAL / stepDoneSet /",
    "// syncStepDone / renderStepProgress 已迁至 static/js/ui/step-state.js（阶段 2",
    "// 工单 12）；host 经 import 读 stepDoneSet（页签切换 / 总览 / 就绪面板），",
    "// 步骤变化联动总览 / 就绪面板经 setOnStepChange 注册（见启动区）。",
    "",
  ];
  lines.splice(dashA, dashB - dashA, ...note);
}

// ---- 7) 卡片折叠 → 注记
{
  const a = must(lines.findIndex((l) => l.startsWith("// 生成页卡片折叠（工单 ui-polish-4/01）")), "collapse header");
  const dashA = a - 1;
  if (!lines[dashA].startsWith("// ------")) throw new Error("dash before collapse not found");
  const b = must(lines.findIndex((l) => l.startsWith("// 设置页折叠（工单 settings-infoarch/01-03）")), "settings-collapse header");
  const dashB = b - 1;
  if (!lines[dashB].startsWith("// ------")) throw new Error("dash before settings-collapse header not found");
  const removed = lines.slice(dashA, dashB).join(eol);
  if (!removed.includes("const CARD_COLLAPSE_SELECTOR")) throw new Error("missing CARD_COLLAPSE_SELECTOR");
  if (!removed.includes("function initCardCollapse()")) throw new Error("missing initCardCollapse");
  const note = [
    "// ---------------------------------------------------------------------------",
    "// 生成页卡片折叠（工单 ui-polish-4/01）：CARD_COLLAPSE_SELECTOR / initCardCollapse",
    "// 已迁至 static/js/ui/step-state.js（阶段 2 工单 12）；host 启动区 7935 经 import 调用。",
    "",
  ];
  lines.splice(dashA, dashB - dashA, ...note);
}

// ---- 8) restoreDraft：三处 A 状态赋值改 setter
{
  const r = (from, to, what) => {
    const i = lines.findIndex((l) => l.includes(from));
    if (i < 0) throw new Error("replace anchor not found: " + what);
    if (!lines[i].includes(to)) lines[i] = lines[i].replace(from, to);
  };
  r("currentTopicId = d.topicId;", "setCurrentTopicId(d.topicId);", "restoreDraft currentTopicId");
  r("chosenPlatform = d.platform;", "setChosenPlatform(d.platform);", "restoreDraft chosenPlatform");
  r("selectedSlugs = d.slugs;", "setSelectedSlugs(d.slugs);", "restoreDraft selectedSlugs");
}

// ---- 9) readiness：recommendClarifications 清空改 setter
{
  const i = lines.findIndex((l) => /^\s+recommendClarifications = \[\];\s*$/.test(l));
  if (i < 0) throw new Error("readiness recommendClarifications reset not found");
  lines[i] = lines[i].replace("recommendClarifications = [];", "setRecommendClarifications([]);");
}

// ---- 10) syncStep7 六调用点参数化（env = {platform, expanded, roles, bindings, instances}）
const envArg = "syncStep7({ platform: chosenPlatform, expanded, roles: pinRoles(), bindings: pinBindings, instances })";
{
  let hits = 0;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l === "    syncStep7();" || l === "  syncStep7();") {
      lines[i] = l.replace("syncStep7();", envArg);
      hits++;
    } else if (l.includes("syncStep7();  // 按默认布线生成成功")) {
      lines[i] = l.replace("syncStep7();", envArg);
      hits++;
    }
  }
  if (hits !== 6) throw new Error("syncStep7 call sites expected 6, got " + hits);
}

// ---- 11) 跨簇接缝注册（setClusterDeps + setOnStepChange）→ 启动区之前
{
  const a = must(lines.findIndex((l) => l === "// 启动"), "启动 header");
  const dashA = a - 1;
  if (!lines[dashA].startsWith("// ------")) throw new Error("dash before 启动 not found");
  const block = [
    "// ---------------------------------------------------------------------------",
    "// 跨簇接缝注册（阶段 2 工单 12）：推荐簇 A 迁出后，模块内对 host 侧跨簇服务的",
    "// 调用经 setClusterDeps / setOnStepChange 注册进来（模块无法 import host 作用域）：",
    "//   - setClusterDeps：引脚-多实例（renderPinCard / renderInstanceConfig /",
    "//     loadPinBoard / resetPinState / resetInstances / clearInstanceTarget /",
    "//     backfillInstances——工单 13 迁出后改静态 import）、修复中心",
    "//     （updateFixCenterAvailability——工单 16 迁）、草稿（scheduleDraftSave——",
    "//     工单 18 迁）。",
    "//   - setOnStepChange：步骤完成态变化 → 总览（refreshGenOverview——工单 18 迁）/",
    "//     就绪面板（refreshReadinessPanel——工单 19 迁）；注册模式避免",
    "//     step-state → generate-steps 环。",
    "setClusterDeps({",
    "  scheduleDraftSave: () => scheduleDraftSave(),",
    "  updateFixCenterAvailability: () => updateFixCenterAvailability(),",
    "  resetPinState: () => { pinBindings = {}; pinUnbound = new Set(); pinHighlight = null; pinHint(\"\"); },",
    "  resetInstances: () => { instances = {}; instancePinTarget = null; renderInstanceConfig(); },",
    "  clearInstanceTarget: () => { instancePinTarget = null; },",
    "  renderPinCard: () => renderPinCard(),",
    "  renderInstanceConfig: () => renderInstanceConfig(),",
    "  loadPinBoard: () => loadPinBoard(),",
    "  backfillInstances: (dataInstances) => {",
    "    for (const slug of Object.keys(dataInstances)) {",
    "      instances[slug] = (dataInstances[slug] || []).map((i) => ({",
    "        name: String(i.name || \"\"), variant: i.variant || \"\", pin: i.pin || \"\",",
    "      }));",
    "    }",
    "    instancePinTarget = null;  // 旧选脚目标可能越界，清掉防陈旧高亮",
    "  },",
    "});",
    "setOnStepChange(() => { refreshGenOverview(); refreshReadinessPanel(); });",
    "",
  ];
  lines.splice(dashA, 0, ...block);
}

// ---- 校验
const out = lines.join(eol);
for (const n of ["renderPlatforms", "useTopic", "startRecommend", "renderModulePool", "openModuleInfo", "renderSelected", "renderWarnings", "renderRecommendResult", "loadReferencePicker", "initModuleGrid", "stepCard", "markStepDone", "markStepUndone", "unmarkSteps", "syncStep7", "syncStepDone", "renderStepProgress", "initCardCollapse"]) {
  if (new RegExp("(function|const)\\s+" + n + "\\b").test(out)) throw new Error("residual definition of " + n);
}
if (/const (STEP_TOTAL|stepDoneSet|STEP_NAV_CARD_SELECTOR|CARD_COLLAPSE_SELECTOR)\b/.test(out)) throw new Error("residual ST const");
if (/^let (selectedSlugs|expanded|pythonTemplates|warnings|scorePoints|chosenPlatform|currentTopicId|lastRecommend|recProblem|recommendClarifications|selectedReferenceIds|autoReferenceIds|referenceEntries|topicPdfTextVisible)\b/m.test(out)) throw new Error("residual A state decl");
// 写点零残留（host 侧不再裸赋值 A 状态；恢复草稿改 setter；局部声明与注释跳过）
for (const v of ["chosenPlatform", "selectedSlugs", "expanded", "warnings", "scorePoints", "currentTopicId", "lastRecommend", "recProblem", "recommendClarifications", "selectedReferenceIds", "autoReferenceIds", "referenceEntries", "pythonTemplates", "topicPdfTextVisible"]) {
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l.trim().startsWith("//")) continue;
    if (new RegExp("(const|let|var)\\s+" + v + "\\s*=").test(l)) continue;  // 局部声明（如 topic 簇 const expanded = ...）
    if (new RegExp("(^|[;{}[\\s])" + v + "\\s*=(?!=)").test(l)) throw new Error("residual assignment of " + v + " -> line " + (i + 1) + ": " + l.trim());
  }
}
for (const frag of ['setChosenPlatform(d.platform)', 'setSelectedSlugs(d.slugs)', 'setCurrentTopicId(d.topicId)', 'setRecommendClarifications([])']) {
  if (!out.includes(frag)) throw new Error("host write via setter missing: " + frag);
}
if ((out.match(/syncStep7\(\{ platform: chosenPlatform/g) || []).length !== 6) throw new Error("syncStep7 param call sites != 6");
if (!out.includes("setClusterDeps({") || !out.includes("scheduleDraftSave: () => scheduleDraftSave()")) throw new Error("setClusterDeps registration missing");
if (!out.includes('setOnStepChange(() => { refreshGenOverview(); refreshReadinessPanel(); })')) throw new Error("setOnStepChange registration missing");
if (!out.includes('from "/js/ui/generate-recommend.js"') || !out.includes('from "/js/ui/step-state.js"')) throw new Error("new imports missing");

writeFileSync(p, out, "utf8");
console.log("OK: A+ST moved; host rewired; lines now", lines.length);
