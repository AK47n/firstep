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
import { stepNavTitles, stepNavItemsHTML, stepNavCurrent, stepProgress, step7DoneState, step7WireMode } from "/js/fx/draft.js";
import { attachCelebrate, syncCollapseBtn, collapseToggleAll, GEN_CARD_COLLAPSE_KEY, parseGenCardCollapse, genCardInitialCollapsed, saveGenCardCollapse } from "/js/fx/generate.js";

export const STEP_NAV_CARD_SELECTOR = "#tab-generate .gen-steps > .card";
export const STEP_TOTAL = 12;
export const CARD_COLLAPSE_SELECTOR = "#tab-generate .gen-steps > .card";

export const stepDoneSet = new Set();

// 步骤 7 布线模式（工单 ux-polish-02/01）：'none' | 'configured' | 'default'。
// syncStep7 每次重算并广播（step7-wire-changed），总览/卡徽章据此区分
// 「已配置引脚」与「按默认布线生成（未手动配置）」——完成计数不变，展示不误导。
let step7Wire = "none";
export function step7WireGet() { return step7Wire; }

// 跨簇联动接缝：host 启动区注册（总览 / 就绪面板刷新）；18/19 迁出后可继续
// 用注册模式（避免 generate-steps → step-state 环）。
let onStepChange = null;
export function setOnStepChange(fn) { onStepChange = fn; }

// 步骤号解析（工单 ux-walkthrough-02/02）：接受非整数子步骤（6.5 多实例卡）。
// data-step 优先（6.5 显式标注），否则读徽章文本；解析失败 → NaN。
function stepNoOf(c) {
  const no = c.querySelector(".step-no");
  if (!no) return NaN;
  const raw = no.dataset && no.dataset.step !== undefined ? no.dataset.step : no.textContent;
  const v = Number(raw);
  return Number.isFinite(v) ? v : NaN;
}

export function stepCard(n) {
  const cards = document.querySelectorAll(STEP_NAV_CARD_SELECTOR);
  return Array.from(cards).find((c) => stepNoOf(c) === n) || null;
}
export function markStepDone(n) {
  // 子步骤（非整数，如 6.5）不进 stepDoneSet——12 步总数与进度条不变；
  // 其完成态由 markSubStep 单独维护（工单 ux-walkthrough-02/02）
  const k = Number.isFinite(Number(n)) ? Number(n) : n;
  if (Number.isInteger(k)) syncStepDone(k, true);
  const item = document.querySelector('.step-nav .step-dot[data-step="' + k + '"]');
  if (item) {
    item.classList.add("done");
    const dot = item.querySelector(".dot");
    if (dot) dot.textContent = "✓";
  }
  const card = stepCard(k);
  if (card) { card.classList.add("done"); attachCelebrate(card); }
}
export function markStepUndone(n) {
  const k = Number.isFinite(Number(n)) ? Number(n) : n;
  if (Number.isInteger(k)) syncStepDone(k, false);
  const item = document.querySelector('.step-nav .step-dot[data-step="' + k + '"]');
  if (item) {
    item.classList.remove("done");
    const dot = item.querySelector(".dot");
    if (dot) dot.textContent = String(k);
  }
  const card = stepCard(k);
  if (card) card.classList.remove("done", "celebrate");
}
export function markSubStep(id, done) {
  // 非整数子步骤（6.5 多实例卡）完成态：只动 nav dot 与总览 chip，不进 stepDoneSet
  const item = document.querySelector('.step-nav .step-dot[data-step="' + id + '"]');
  if (item) {
    item.classList.toggle("done", done);
    const dot = item.querySelector(".dot");
    if (dot) dot.textContent = done ? "✓" : String(id);
  }
  const chip = document.querySelector('.ov-chip[data-step="' + id + '"]');
  if (chip) {
    chip.classList.toggle("done", done);
    const d = chip.querySelector(".ov-dot");
    if (d) d.textContent = done ? "✓" : String(id);
  }
}
export function unmarkSteps(steps) {
  for (const n of steps) markStepUndone(n);
}
export function syncStep7(env) {
  const roles = env.roles;
  const generated = stepDoneSet.has(9);
  const done = step7DoneState({
    chosenPlatform: env.platform,
    expandedCount: env.expanded.length,
    roles: roles,
    roleBound: roles.some((r) => env.bindings[r.key]),
    instBound: Object.values(env.instances || {}).some((arr) =>
      (arr || []).some((i) => i && i.pin)),
    generated: generated,
  });
  const wire = step7WireMode({
    chosenPlatform: env.platform,
    expandedCount: env.expanded.length,
    roles: roles,
    roleBound: roles.some((r) => env.bindings[r.key]),
    instBound: Object.values(env.instances || {}).some((arr) =>
      (arr || []).some((i) => i && i.pin)),
    generated: generated,
  });
  if (wire !== step7Wire) {
    step7Wire = wire;
    // 总览/卡徽章区分「已就绪」与「默认布线」（工单 ux-polish-02/01）：
    // 生成成功路径先 markStepDone(9)（触发 onStepChange 刷新）再 syncStep7，
    // 故 wire 变化需独立广播才能让徽章拿到最新模式
    window.dispatchEvent(new CustomEvent("step7-wire-changed"));
  }
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
  // 折叠记忆（工单 ux-polish-02/02）：单键 JSON {步骤号: bool}；用户选择优先。
  // 初始默认 = 已完成且非当前步折叠（首屏更清爽）；无步骤号卡（6.5 实例卡）
  // 不参与自动折叠与记忆。读取失败降级 {}，写入失败静默（沿草稿先例）。
  const stored = parseGenCardCollapse(localStorage.getItem(GEN_CARD_COLLAPSE_KEY));
  const persist = () => { saveGenCardCollapse(localStorage, stored); };
  const curEl = document.querySelector(".step-nav .step-dot.current");
  const currentNo = curEl ? Number(curEl.dataset.step) : NaN;
  for (const c of cards) {
    const h2 = c.querySelector("h2");
    if (!h2) continue;
    const n = stepNoOf(c);
    if (!Number.isInteger(n)) continue;  // 子步骤卡（6.5）不参与折叠记忆（既有设计）
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "card-collapse";
    const initial = genCardInitialCollapsed({
      no: n, done: stepDoneSet.has(n), current: n === currentNo, stored,
    });
    syncCollapseBtn(btn, initial);
    btn.textContent = "▾";
    const toggleCard = () => {
      const collapsed = c.classList.toggle("collapsed");
      syncCollapseBtn(btn, collapsed);
      if (Number.isFinite(n)) {
        stored[n] = collapsed;
        persist();
      }
    };
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleCard();
    });
    h2.appendChild(btn);
    h2.addEventListener("click", (e) => {
      if (e.target.closest(".card-collapse")) return;
      toggleCard();
    });
    // 默认规则落地 = 折叠状态类 + 按钮同步（记忆优先在初始判定内完成）
    if (initial) c.classList.add("collapsed");
  }
  const nav = $("step-nav");
  if (!nav) return;
  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.id = "btn-collapse-done";
  toggleBtn.textContent = "收起已完成";
  toggleBtn.style.cssText = "margin-top: var(--space-2);padding:2px 8px;font-size:11px;border-radius:var(--radius-full);color:var(--muted);";
  toggleBtn.addEventListener("click", () => {
    const doneCount = stepDoneSet ? stepDoneSet.size : 0;
    if (!doneCount) {   // 无完成步骤时点击无视觉变化 → 给明确反馈
      toast("info", "还没有已完成的步骤，先完成前面的步骤吧");
      return;
    }
    const collapsing = !toggleBtn.classList.contains("on");
    const out = collapseToggleAll(cards, stepDoneSet, collapsing);
    // 记忆与最终视觉态一致（工单 02：展开/收起都落盘，刷新后保持）
    for (const o of out) {
      if (Number.isFinite(o.n)) {
        stored[o.n] = o.collapsed;
        persist();
      }
    }
    toggleBtn.classList.toggle("on", collapsing);
    toggleBtn.textContent = collapsing ? "全部展开" : "收起已完成";
  });
  nav.appendChild(toggleBtn);
}

// 步骤导航构建（工单 ux-walkthrough-02/02 重构）：卡片可见性随展开/清空变化
//（6.5 多实例卡），导航项需在显隐切换后重建——buildStepNav 只重装 .step-dot
//（保留 initCardCollapse 追加的「收起已完成」按钮）并恢复整数步完成态。
let stepCards = [];
let stepNavUpdate = null;
// 点击导航后待定的步骤（工单 step-nav-clamp/01）：短卡（如步骤 11）贴页尾时
// scrollIntoView 的目标会被底部 clamp 在 maxScroll、页面停在原地，而位置高亮
// 又因「滚到底→强制末步」漂到 12——记录点击步骤并保持高亮，直到用户手动滚动。
let pickedStep = NaN;
const stepHeaderH = () =>
  parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--header-h")) || 0;

// 点击步骤泡泡 / 总览 chip 的统一滚动（工单 step-nav-clamp/01）：
// 1) 目标先扣吸顶栏高度（--header-h），卡片顶不被吸顶栏遮挡；
// 2) 卡片顶已越过最大滚动位置的短卡（start 目标必被 clamp 原地不动），
//    改按卡片居中落点 clamp 到 [0, maxScroll]，保证被点的卡片真正进入视口。
export function scrollToStep(n) {
  const card = stepCard(n);
  if (!card) return;
  pickedStep = n;
  const vh = window.innerHeight;
  const max = Math.max(0, document.documentElement.scrollHeight - vh);
  const rect = card.getBoundingClientRect();
  const cardTop = rect.top + window.scrollY;
  const start = cardTop - stepHeaderH() - 8;
  const target = start <= max
    ? Math.max(0, start)
    : Math.min(Math.max(cardTop + rect.height / 2 - vh / 2, 0), max);
  window.scrollTo({ top: target, behavior: "smooth" });
  if (stepNavUpdate) stepNavUpdate();
}
// 用户手动滚动（滚轮 / 触摸 / 方向键）视为放弃点击目标，恢复位置驱动高亮
window.addEventListener("wheel", () => { pickedStep = NaN; }, { passive: true });
window.addEventListener("touchmove", () => { pickedStep = NaN; }, { passive: true });
window.addEventListener("keydown", (e) => {
  if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End"].includes(e.key)) {
    pickedStep = NaN;
  }
}, { passive: true });

function buildStepNav() {
  const nav = $("step-nav");
  if (!nav) return;
  stepCards = Array.from(document.querySelectorAll(STEP_NAV_CARD_SELECTOR))
    .filter((c) => c.querySelector(".step-no") && !c.classList.contains("hidden"));
  nav.querySelectorAll(".step-dot").forEach((d) => d.remove());
  nav.insertAdjacentHTML("beforeend", stepNavItemsHTML(stepNavTitles(stepCards)));
  // 重建后恢复整数步完成态（stepDoneSet 是唯一权威；子步 6.5 由 markSubStep 恢复）
  for (const n of stepDoneSet) {
    const item = nav.querySelector('.step-dot[data-step="' + n + '"]');
    if (item) {
      item.classList.add("done");
      const dot = item.querySelector(".dot");
      if (dot) dot.textContent = "✓";
    }
  }
}

export function refreshStepNav() {
  buildStepNav();
  if (stepNavUpdate) stepNavUpdate();
}

(function initStepNav() {
  const nav = $("step-nav");
  if (!nav) return;
  buildStepNav();
  nav.addEventListener("click", (e) => {
    const dot = e.target.closest(".step-dot");
    if (!dot) return;
    scrollToStep(Number(dot.dataset.step));
  });
  let ticking = false;
  const update = () => {
    ticking = false;
    const entries = stepCards.map((c) => ({ n: stepNoOf(c), top: c.getBoundingClientRect().top }));
    let cur = stepNavCurrent(entries, 120);
    // 点击优先（工单 step-nav-clamp/01）：点击的卡片仍在视口内时保持点击结果，
    // 防止底部 clamp 场景下高亮被下方「滚到底→末步」规则掰到 12；
    // 点击目标已滚出视口 / 失效则放弃，回到位置驱动。
    let pickVisible = false;
    if (Number.isFinite(pickedStep)) {
      const pc = stepCards.find((c) => stepNoOf(c) === pickedStep);
      if (pc) {
        const r = pc.getBoundingClientRect();
        pickVisible = r.bottom > stepHeaderH() && r.top < window.innerHeight;
      }
      if (!pickVisible) pickedStep = NaN;
    }
    if (pickVisible) {
      cur = pickedStep;
    } else if (entries.length && window.innerHeight + window.scrollY
        >= document.documentElement.scrollHeight - 80) {
      // 滚到底仍够不到阈值时（末卡较短）直接定位最后一步
      cur = entries[entries.length - 1].n;
    }
    nav.querySelectorAll(".step-dot").forEach((d) => {
      d.classList.toggle("current", Number(d.dataset.step) === cur);
    });
  };
  stepNavUpdate = update;
  function onScroll() {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }
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
