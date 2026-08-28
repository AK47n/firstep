// ui/revise-tabs.js — 第11步「修订与深化」卡内页签 DOM 胶水（工单 step11-tabs-ui/01：
// 点击 / 方向键切换 + 默认「修订」+ 上下文加载后（未手动切过页签）自动激活「任务推进」；
// 徽章就地刷新——01 为空快照，02 接入各簇只读 getter）。
import { $ } from "/js/app.js";
import { REVISE_TABS, reviseTabsHTML, revisePanelFor, reviseTabNext, reviseTabBadge } from "/js/fx/revise-tabs.js";

const state = { active: "revise", userPicked: false };

/** 各分区状态快照（工单 02 接入 generate-revise / generate-tasks / params /
 * delivery 的只读 getter；键 = 页签 key）。 */
function collectBadges() {
  return {};
}

/** 就地刷新徽章 span（不重建按钮：保焦点与 aria 状态）。 */
function refreshBadgeSpans() {
  const badges = collectBadges();
  for (const t of REVISE_TABS) {
    const span = document.querySelector(
      '#revise-tabs .revise-tab[data-tab="' + t.key + '"] .revise-tab-badge');
    if (!span) continue;
    const text = reviseTabBadge(t.key, badges[t.key]);
    span.textContent = text;
    span.classList.toggle("hidden", !text);
  }
}

/** 徽章刷新（02 由 step11-state-changed 事件驱动；01 空操作）。 */
export function refreshReviseBadges() {
  refreshBadgeSpans();
}

function showPanel(key) {
  for (const t of REVISE_TABS) {
    const el = $(revisePanelFor(t.key));
    if (el) el.classList.toggle("hidden", t.key !== key);
  }
}

function applyActive() {
  const nav = $("revise-tabs");
  if (!nav) return;
  nav.querySelectorAll(".revise-tab").forEach((btn) => {
    const on = btn.dataset.tab === state.active;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-selected", on ? "true" : "false");
    btn.tabIndex = on ? 0 : -1;
  });
  showPanel(state.active);
}

/** 切换页签（opts.user = 用户主动选择——记入 userPicked，取消后续自动切换）。 */
export function switchReviseTab(key, opts) {
  if (!REVISE_TABS.some((t) => t.key === key)) return;
  state.active = key;
  if (opts && opts.user) state.userPicked = true;
  applyActive();
}

export function initReviseTabs() {
  const nav = $("revise-tabs");
  if (!nav) return;
  nav.innerHTML = reviseTabsHTML(REVISE_TABS, state.active, collectBadges());
  applyActive();
  nav.addEventListener("click", (e) => {
    const btn = e.target.closest(".revise-tab");
    if (!btn) return;
    switchReviseTab(btn.dataset.tab, { user: true });
  });
  nav.addEventListener("keydown", (e) => {
    const keys = REVISE_TABS.map((t) => t.key);
    let next = -1;
    if (e.key === "ArrowRight") next = reviseTabNext(keys.indexOf(state.active), 1, keys.length);
    else if (e.key === "ArrowLeft") next = reviseTabNext(keys.indexOf(state.active), -1, keys.length);
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = keys.length - 1;
    else return;
    e.preventDefault();
    switchReviseTab(keys[next], { user: true });
    const btn = nav.querySelector('.revise-tab[data-tab="' + keys[next] + '"]');
    if (btn) btn.focus();
  });
  // 上下文加载完成：用户还没手动选过页签 → 自动切到「任务推进」（加载的下一步
  // 几乎总是拆解任务）；手动切过一次后不再打扰。
  window.addEventListener("revise-context-loaded", () => {
    if (!state.userPicked) switchReviseTab("tasks", {});
  });
}
