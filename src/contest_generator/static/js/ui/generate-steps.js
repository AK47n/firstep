// ui/generate-steps.js — 生成页 · 草稿自动记忆 + 就绪总览（阶段 2 工单 18，
// 源自 index.html 生成页草稿与就绪总览两节）。
//
// DM 胶水全量迁入：DRAFT_KEY / DRAFT_FIELDS / collectDraftState / draftTimer /
// scheduleDraftSave / clearDraft / restoreDraft + 清除按钮与 4 个输入顶层监听
//（import 时绑定：module 脚本延迟执行，DOM 已就绪）；GEN_CRITICAL_STEPS /
// GEN_RECOMMENDED_STEPS / genOverviewTitles / genOverviewBadges / overviewPlanNow /
// genOverviewWarn / refreshGenOverview / FOCUS_TARGETS / runOverviewFill /
// initGenOverview（host 启动区调用——scroll/resize/操作区监听在函数内绑定）。
// 状态：本模块无跨簇 mutable 状态；stepDoneSet 拥有者 = ui/step-state.js
//（工单 12），本模块经 import 读；stepCard / stepNavTitles / markStepDone /
// STEP_NAV_CARD_SELECTOR 同（step-state / fx/draft）。
// 跨簇服务（readiness 簇）：readinessState 静态 import 自 ui/generate-readiness.js
//（工单 19 迁出后由工单 18 的接缝改为静态 import）。
// 纯件在 fx/*.js（draft / overview / readiness）；A 簇状态读（lastRecommend /
// selectedSlugs）与渲染（renderPlatforms / renderSelected / renderWarnings /
// renderRecommendResult）+ setter（setChosenPlatform / setSelectedSlugs /
// setCurrentTopicId）import 自 ui/generate-recommend.js；desktopTopicOutputEnabled
// import 自 ui/generate-core.js；syncMainCHighlight import 自 ui/generate-mainc.js。
import { $, state } from "/js/app.js";
import { draftState, draftSave, draftLoad, draftRestoreMeta, stepNavTitles } from "/js/fx/draft.js";
import { genOverviewChipsHTML, genOverviewSummaryHTML, overviewFillPlan, overviewReadyToGenerate, hasWarnContent } from "/js/fx/overview.js";
import { generateReadinessChecks } from "/js/fx/readiness.js";
import { readinessState } from "/js/ui/generate-readiness.js";  // 工单 19 迁出→静态 import（取代工单 18 接缝）
import { stepDoneSet, stepCard, STEP_NAV_CARD_SELECTOR, markStepDone } from "/js/ui/step-state.js";
import { setSelectedSlugs, setChosenPlatform, setCurrentTopicId, renderPlatforms, renderSelected, renderWarnings, renderRecommendResult, lastRecommend, selectedSlugs, chosenPlatform } from "/js/ui/generate-recommend.js";
import { desktopTopicOutputEnabled } from "/js/ui/generate-core.js";
import { syncMainCHighlight } from "/js/ui/generate-mainc.js";

// ---------------------------------------------------------------------------
// 生成页草稿自动记忆（工单 ui-polish-3/01）：localStorage 防误刷新丢失；
// 只存表单态，恢复不触发任何后端请求
// ---------------------------------------------------------------------------
const DRAFT_KEY = "firstep.draft.v1";
const DRAFT_FIELDS = ["problem", "topicId", "platform", "slugs", "mainC", "qa"];
// 已迁至 static/js/fx/draft.js（工单 07）：draftState / draftSave / draftLoad / draftRestoreMeta。
function collectDraftState() {
  return draftState(
    $("problem").value, $("topic-id").value,
    chosenPlatform || "", selectedSlugs,
    $("main-c").value, $("qa-text").value
  );
}
let draftTimer = null;
function scheduleDraftSave() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => { draftSave(localStorage, collectDraftState()); }, 400);
}
function clearDraft() {
  try { localStorage.removeItem(DRAFT_KEY); } catch (e) { /* 忽略 */ }
  $("draft-tip").classList.add("hidden");
}
function restoreDraft() {
  const d = draftRestoreMeta(draftLoad(localStorage));
  if (!d) return;
  if (d.problem) { $("problem").value = d.problem; markStepDone(1); }
  if (d.topicId) { $("topic-id").value = d.topicId; setCurrentTopicId(d.topicId); }
  if (d.platform && state.platforms.some((p) => p.id === d.platform)) {
    setChosenPlatform(d.platform);
    markStepDone(3);
  }
  if (d.slugs.length) { setSelectedSlugs(d.slugs); markStepDone(6); }
  if (d.mainC) { $("main-c").value = d.mainC; markStepDone(8); syncMainCHighlight(); }
  if (d.qa) { $("qa-text").value = d.qa; }
  if (d.platform || d.slugs.length) { renderPlatforms(); renderSelected(); renderWarnings(); }
  $("draft-tip").classList.remove("hidden");
}
$("btn-clear-draft").addEventListener("click", () => {
  clearDraft();
  const btn = $("btn-clear-draft");
  btn.textContent = "已清除";
  setTimeout(() => { btn.textContent = "清除草稿"; }, 1500);
});
$("btn-draft-clear").addEventListener("click", () => {
  clearDraft();
  const btn = $("btn-draft-clear");
  btn.textContent = "已清除";
  setTimeout(() => { btn.textContent = "清除草稿"; }, 1500);
});
$("problem").addEventListener("input", scheduleDraftSave);
$("topic-id").addEventListener("input", scheduleDraftSave);
$("main-c").addEventListener("input", scheduleDraftSave);
$("qa-text").addEventListener("input", scheduleDraftSave);


// ---------------------------------------------------------------------------
// 就绪总览（与草稿段之间原为步骤完成集合注释——step-state 已于工单 12 迁出）
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// 生成页就绪总览（工单 gen-overview/01）：顶部步骤 chips + 摘要，状态与
// stepDoneSet / step-nav current 同源。宽屏（≥1180px）左侧 step-nav 可见时
// chips 隐藏（避免每步导航重复出现）；窄屏 step-nav 隐藏时 chips 兼作
// 唯一步骤导航。
// 关键路径 = 缺了就不能生成的步骤（题面/平台/模块/生成）；
// 软建议 = 不强制但强烈建议先走的步骤（AI 推荐/骨架）。
// ---------------------------------------------------------------------------
const GEN_CRITICAL_STEPS = [1, 3, 6, 9];
const GEN_RECOMMENDED_STEPS = [5, 8];
// 已迁至 static/js/fx/overview.js（工单 07）：genOverviewChipsHTML / genOverviewSummaryHTML /
// overviewFillPlan / overviewReadyToGenerate。
// 当前补齐计划（refreshGenOverview 显隐 / runOverviewFill 执行共用同一判定，
// 工单 gen-overview-act/01）：两个派生值只算一次，避免两处逐字重复
function overviewPlanNow(doneArr) {
  // canAdopt：有推荐结果且模块清单为空才自动采用（清单非空时 renderSelected
  // 已 markStepDone(6)，计划不含 6——显式判定防状态漂移误重复采用）
  const canAdopt = !!(lastRecommend && (lastRecommend.modules || []).length)
    && !selectedSlugs.length;
  const outputDirMissing = !desktopTopicOutputEnabled()
    && !$("output-dir").value.trim();
  return overviewFillPlan(doneArr, canAdopt, outputDirMissing);
}
// 已迁至 static/js/fx/overview.js（工单 07）：cardStepStatusHTML / hasWarnContent。
let genOverviewTitles = [];
let genOverviewBadges = {};
function genOverviewWarn(n) {
  return (n === 6 && hasWarnContent($("warnings")))
      || (n === 7 && hasWarnContent($("pin-warn-list")));
}
function refreshGenOverview() {
  const box = $("gen-overview");
  if (!box) return;
  const curEl = document.querySelector(".step-nav .step-dot.current");
  const current = curEl ? parseInt(curEl.dataset.step, 10) : NaN;
  const doneArr = Array.from(stepDoneSet);
  box.querySelectorAll(".ov-chip").forEach((chip) => {
    const n = parseInt(chip.dataset.step, 10);
    const isDone = stepDoneSet.has(n);
    const warn = !isDone && genOverviewWarn(n);
    chip.classList.toggle("done", isDone);
    chip.classList.toggle("warn", warn);
    chip.classList.toggle("current", n === current);
    const dot = chip.querySelector(".ov-dot");
    if (dot) dot.textContent = isDone ? "✓" : n;
  });
  // 左侧导航 dot 的 warn 同步（工单 ui-detail/01）：done/current 仍由
  // markStep* / initStepNav 维护，这里单向补 warn，互不覆盖
  document.querySelectorAll(".step-nav .step-dot").forEach((dot) => {
    const n = parseInt(dot.dataset.step, 10);
    dot.classList.toggle("warn", !stepDoneSet.has(n) && genOverviewWarn(n));
  });
  const summary = box.querySelector(".ov-summary");
  if (summary) {
    // 步骤导航位置随宽度切换（宽屏左侧 step-nav / 窄屏顶部 chips），
    // 摘要提示语跟随，避免指向不可见的导航
    const navHint = window.matchMedia("(max-width: 1179px)").matches
      ? "（点上方步骤条直达）" : "（点左侧步骤条直达）";
    summary.innerHTML = genOverviewSummaryHTML(doneArr, genOverviewTitles,
      GEN_CRITICAL_STEPS, GEN_RECOMMENDED_STEPS, navHint);
  }
  // 卡片标题状态徽章（A2）：已就绪 / 有警告 / 当前，其余隐藏
  genOverviewTitles.forEach((t) => {
    const badge = genOverviewBadges[t.n];
    if (!badge || !badge.isConnected) return;
    if (stepDoneSet.has(t.n)) {
      badge.className = "card-step-status done";
      badge.textContent = "✓ 已就绪";
    } else if (genOverviewWarn(t.n)) {
      badge.className = "card-step-status warn";
      badge.textContent = "⚠ 有警告";
    } else if (t.n === current) {
      badge.className = "card-step-status current";
      badge.textContent = "● 当前";
    } else {
      badge.className = "card-step-status";
      badge.textContent = "";
    }
  });
  // 行动区（工单 gen-overview-act/01）：补齐按钮仅有关键路径缺失时显示；
  // 生成按钮仅就绪（与 btn-generate 校验同源）时显示，且同步其禁用态
  const plan = overviewPlanNow(doneArr);
  const fillBtn = box.querySelector(".ov-fill");
  if (fillBtn) fillBtn.classList.toggle("hidden", plan.length === 0);
  const genBtn = box.querySelector(".ov-generate");
  if (genBtn) {
    const ready = overviewReadyToGenerate(generateReadinessChecks(readinessState()));
    const generating = !!( $("btn-generate") && $("btn-generate").disabled );
    genBtn.classList.toggle("hidden", !ready);
    if (genBtn.disabled !== generating) genBtn.disabled = generating;
  }
}
// 一键补齐（工单 gen-overview-act/01）：按计划依次滚到卡片 + 临时高亮，
// 半自动动作（聚焦题面/输出目录、自动采用已有推荐；平台只高亮不自动选）
const FOCUS_TARGETS = { 1: "problem", 9: "output-dir" };
function runOverviewFill() {
  const plan = overviewPlanNow(Array.from(stepDoneSet));
  let i = 0;
  const next = () => {
    if (i >= plan.length) return;
    const item = plan[i++];
    const card = stepCard(item.n);
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "start" });
      card.classList.add("ov-fill-target");
      setTimeout(() => { if (card) card.classList.remove("ov-fill-target"); }, 1600);
    }
    if (item.action === "focus" || item.action === "focus-dir") {
      const t = $(FOCUS_TARGETS[item.n]);
      if (t) t.focus();
    }
    if (item.action === "adopt") {
      // 自动采用既有推荐结果（可回退：renderSelected 后清单仍可增删；
      // 多实例回填/评分点/runExpand 全走 renderRecommendResult 既有路径）
      renderRecommendResult(lastRecommend, true);
    }
    setTimeout(next, 700);
  };
  next();
}
function initGenOverview() {
  const box = $("gen-overview");
  if (!box) return;
  const cards = Array.from(document.querySelectorAll(STEP_NAV_CARD_SELECTOR))
    .filter((c) => c.querySelector(".step-no"));
  genOverviewTitles = stepNavTitles(cards);
  if (!genOverviewTitles.length) return;
  box.innerHTML =
    '<div class="ov-chips">' + genOverviewChipsHTML(genOverviewTitles, [], NaN)
    + '</div><div class="ov-summary"></div><div class="ov-actions">'
    + '<button type="button" class="ov-fill hidden">一键补齐</button>'
    + '<button type="button" class="ov-generate primary hidden">生成</button>'
    + '</div>';
  box.addEventListener("click", (e) => {
    const fill = e.target.closest(".ov-fill");
    if (fill) { runOverviewFill(); return; }
    const gen = e.target.closest(".ov-generate");
    if (gen) {
      const btn = $("btn-generate");
      if (btn && !btn.disabled) btn.click();
      return;
    }
    const chip = e.target.closest(".ov-chip");
    if (!chip) return;
    const card = stepCard(parseInt(chip.dataset.step, 10));
    if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  // 卡片标题状态徽章（A2）：插在折叠按钮前（initCardCollapse 在其后追加折叠钮）
  cards.forEach((c) => {
    const no = c.querySelector(".step-no");
    const n = no ? parseInt(no.textContent, 10) : NaN;
    const h2 = c.querySelector("h2");
    if (!Number.isFinite(n) || !h2) return;
    const badge = document.createElement("span");
    badge.className = "card-step-status";
    h2.appendChild(badge);
    genOverviewBadges[n] = badge;
  });
  document.addEventListener("scroll", () => refreshGenOverview(), { passive: true });
  window.addEventListener("resize", () => refreshGenOverview(), { passive: true });
  refreshGenOverview();
}


// ---- 本簇导出面（host 顶部 import 活绑定调用点） ----
// host 实际使用：restoreDraft（启动区末位）/ initGenOverview（启动区）/
// scheduleDraftSave（A 簇 clusterDeps 注册闭包）/ refreshGenOverview
//（setOnStepChange 回调）。
export { restoreDraft, scheduleDraftSave, collectDraftState, clearDraft,
  initGenOverview, refreshGenOverview, runOverviewFill, overviewPlanNow };
