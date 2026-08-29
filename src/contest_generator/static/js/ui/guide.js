// ui/guide.js — 「新手指引」页 DOM 胶水（工单 beginner-guide/01：
// 子页签点击/方向键切换——按钮 active + 面板显隐 + aria-selected/tabIndex，
// 初始态一次给全；工单 02 起：正文渲染（fx/guide.js 数据单源）与
// 「跳到功能」按钮接线）。
import { $ } from "/js/app.js";
import { GUIDE_TABS, guidePanelFor, guideTabNext } from "/js/fx/guide.js";

const state = { active: "prepare" };

function showPanel(key) {
  for (const t of GUIDE_TABS) {
    const el = $(guidePanelFor(t.key));
    if (el) el.hidden = t.key !== key;
  }
}

function applyActive() {
  const nav = $("guide-tabs");
  if (!nav) return;
  nav.querySelectorAll(".guide-tab").forEach((btn) => {
    const on = btn.dataset.guideTab === state.active;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
    btn.tabIndex = on ? 0 : -1;
  });
  showPanel(state.active);
}

/** 切换子页签（key 不在 GUIDE_TABS 内则忽略）。 */
export function switchGuideTab(key) {
  if (!GUIDE_TABS.some((t) => t.key === key)) return;
  state.active = key;
  applyActive();
}

export function initGuide() {
  const nav = $("guide-tabs");
  if (!nav) return;
  applyActive();  // 初始态：roving tabindex / aria-selected 一次给全（评审整改：
                  // 静态标记只有首个按钮带 active，tabindex 默认全 0 与交互后不一致）
  nav.addEventListener("click", (e) => {
    const btn = e.target.closest(".guide-tab");
    if (!btn) return;
    switchGuideTab(btn.dataset.guideTab);
  });
  // 方向键 / Home / End 循环切换（tablist roving 惯例，同 revise-tabs 协议）
  nav.addEventListener("keydown", (e) => {
    const current = nav.querySelector(".guide-tab[data-guide-tab].active") ||
      nav.querySelector(".guide-tab[data-guide-tab]");
    if (!current) return;
    const idx = GUIDE_TABS.findIndex((t) => t.key === current.dataset.guideTab);
    if (idx < 0) return;
    let next = -1;
    if (e.key === "ArrowRight") next = guideTabNext(idx, 1, GUIDE_TABS.length);
    else if (e.key === "ArrowLeft") next = guideTabNext(idx, -1, GUIDE_TABS.length);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = GUIDE_TABS.length - 1;
    else return;
    if (next < 0) return;
    e.preventDefault();
    switchGuideTab(GUIDE_TABS[next].key);
    const btn = nav.querySelector('.guide-tab[data-guide-tab="' + GUIDE_TABS[next].key + '"]');
    if (btn) btn.focus();
  });
}
