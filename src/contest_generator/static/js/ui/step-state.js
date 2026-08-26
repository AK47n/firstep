// ui/step-state.js — 生成页步骤完成态核心（阶段 2 工单 12）
//
// A↔ST 循环 cut 方案前半：STEP_NAV_CARD_SELECTOR / stepCard / markStepDone /
// markStepUndone / unmarkSteps / syncStep7 / stepDoneSet / STEP_TOTAL /
// syncStepDone / renderStepProgress / initStepNav IIFE / CARD_COLLAPSE_SELECTOR /
// initCardCollapse。零 A 依赖：syncStep7 参数化（env = 调用方传入
// {platform, expanded, roles, bindings, instances}——旧实现闭包读宿主
// chosenPlatform / expanded / pinRoles() / pinBindings / instances，ESM 模块
// 边界上不可达；参数化后 host（B/D 簇）调用点逐处传参，见 index.html）。
// 跨簇联动：syncStepDone 经 setOnStepChange 注册的回调通知总览 / 就绪面板
// （refreshGenOverview 工单 18 迁 / refreshReadinessPanel 工单 19 迁；注册
// 模式避免 step-state → generate-steps 环）。庆祝动画在 fx/generate.js。
// host 经顶部 import：读 stepDoneSet / STEP_NAV_CARD_SELECTOR，调 markStep* /
// syncStep7 / stepCard / initCardCollapse（启动区）。
import { $, toast } from "/js/app.js";
import { stepNavTitles, stepNavItemsHTML, stepNavCurrent, stepProgress, step7DoneState } from "/js/fx/draft.js";
import { attachCelebrate, syncCollapseBtn, collapseToggleAll } from "/js/fx/generate.js";

export const STEP_NAV_CARD_SELECTOR = "#tab-generate .gen-steps > .card";
export const STEP_TOTAL = 12;
export const CARD_COLLAPSE_SELECTOR = "#tab-generate .gen-steps > .card";

export const stepDoneSet = new Set();

// 跨簇联动接缝：host 启动区注册（总览 / 就绪面板刷新）；18/19 迁出后可继续
// 用注册模式（避免 generate-steps → step-state 环）。
let onStepChange = null;
export function setOnStepChange(fn) { onStepChange = fn; }

export function stepCard(n) {
  const cards = document.querySelectorAll(STEP_NAV_CARD_SELECTOR);
  return Array.from(cards).find((c) => {
    const no = c.querySelector(".step-no");
    return no && parseInt(no.textContent, 10) === n;
  }) || null;
}
export function markStepDone(n) {
  syncStepDone(n, true);
  const item = document.querySelector('.step-nav .step-dot[data-step="' + n + '"]');
  if (item) {
    item.classList.add("done");
    const dot = item.querySelector(".dot");
    if (dot) dot.textContent = "✓";
  }
  const card = stepCard(n);
  if (card) { card.classList.add("done"); attachCelebrate(card); }
}
export function markStepUndone(n) {
  syncStepDone(n, false);
  const item = document.querySelector('.step-nav .step-dot[data-step="' + n + '"]');
  if (item) {
    item.classList.remove("done");
    const dot = item.querySelector(".dot");
    if (dot) dot.textContent = String(n);
  }
  const card = stepCard(n);
  if (card) card.classList.remove("done", "celebrate");
}
export function unmarkSteps(steps) {
  for (const n of steps) markStepUndone(n);
}
export function syncStep7(env) {
  const roles = env.roles;
  const done = step7DoneState({
    chosenPlatform: env.platform,
    expandedCount: env.expanded.length,
    roles: roles,
    roleBound: roles.some((r) => env.bindings[r.key]),
    instBound: Object.values(env.instances || {}).some((arr) =>
      (arr || []).some((i) => i && i.pin)),
    generated: stepDoneSet.has(9),
  });
  if (done) markStepDone(7);
  else markStepUndone(7);
}
export function syncStepDone(n, done) {
  if (done) stepDoneSet.add(n); else stepDoneSet.delete(n);
  renderStepProgress();
  if (onStepChange) onStepChange();
}
export function renderStepProgress() {
  const el = $("gen-progress");
  if (!el) return;
  const { pct, text } = stepProgress(stepDoneSet.size, STEP_TOTAL);
  el.querySelector(".gp-fill").style.width = pct + "%";
  el.querySelector(".gp-text").textContent = text;
  el.classList.toggle("hidden", pct === 0);
}
export function initCardCollapse() {
  const cards = Array.from(document.querySelectorAll(CARD_COLLAPSE_SELECTOR));
  for (const c of cards) {
    const h2 = c.querySelector("h2");
    if (!h2) continue;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "card-collapse";
    syncCollapseBtn(btn, false);
    btn.textContent = "▾";
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      syncCollapseBtn(btn, c.classList.toggle("collapsed"));
    });
    h2.appendChild(btn);
    h2.addEventListener("click", (e) => {
      if (e.target.closest(".card-collapse")) return;
      syncCollapseBtn(btn, c.classList.toggle("collapsed"));
    });
  }
  const nav = $("step-nav");
  if (!nav) return;
  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.id = "btn-collapse-done";
  toggleBtn.textContent = "收起已完成";
  toggleBtn.style.cssText = "margin-top:6px;padding:2px 8px;font-size:10px;border-radius:999px;color:var(--muted);";
  toggleBtn.addEventListener("click", () => {
    const doneCount = stepDoneSet ? stepDoneSet.size : 0;
    if (!doneCount) {   // 无完成步骤时点击无视觉变化 → 给明确反馈
      toast("info", "还没有已完成的步骤，先完成前面的步骤吧");
      return;
    }
    const collapsing = !toggleBtn.classList.contains("on");
    collapseToggleAll(cards, stepDoneSet, collapsing);
    toggleBtn.classList.toggle("on", collapsing);
    toggleBtn.textContent = collapsing ? "全部展开" : "收起已完成";
  });
  nav.appendChild(toggleBtn);
}

(function initStepNav() {
  const nav = $("step-nav");
  if (!nav) return;
  // 只收带 .step-no 徽章的步骤卡（6.5 多实例配置卡无徽章，不进导航）
  const cards = Array.from(document.querySelectorAll(STEP_NAV_CARD_SELECTOR))
    .filter((c) => c.querySelector(".step-no"));
  if (!cards.length) return;
  nav.innerHTML = stepNavItemsHTML(stepNavTitles(cards));
  nav.addEventListener("click", (e) => {
    const dot = e.target.closest(".step-dot");
    if (!dot) return;
    const card = stepCard(parseInt(dot.dataset.step, 10));
    if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  let ticking = false;
  const update = () => {
    ticking = false;
    const entries = cards.map((c) => {
      const no = c.querySelector(".step-no");
      const r = c.getBoundingClientRect();
      return { n: no ? parseInt(no.textContent, 10) : NaN, top: r.top };
    });
    let cur = stepNavCurrent(entries, 120);
    // 滚到底仍够不到阈值时（末卡较短）直接定位最后一步
    if (entries.length && window.innerHeight + window.scrollY
        >= document.documentElement.scrollHeight - 80) {
      cur = entries[entries.length - 1].n;
    }
    nav.querySelectorAll(".step-dot").forEach((d) => {
      d.classList.toggle("current", parseInt(d.dataset.step, 10) === cur);
    });
  };
  const onScroll = () => {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  };
  // 吸顶栏高度实时写入 CSS 变量（header 窄屏会换行变高，写死会挡住/留白）
  const syncHeaderH = () => {
    const h = document.querySelector("header");
    if (h) document.documentElement.style.setProperty(
      "--header-h", Math.ceil(h.getBoundingClientRect().height) + "px");
  };
  document.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", () => { syncHeaderH(); onScroll(); }, { passive: true });
  syncHeaderH();
  update();
})();
