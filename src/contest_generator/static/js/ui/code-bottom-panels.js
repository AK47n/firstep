// ui/code-bottom-panels.js — 底部面板容器 + 页签条（工单 code-page-vscode-overhaul/06）
//
// 编译 / 磁盘变更 / AI 对话 / 修复 / 烧录五个独立堆叠面板收进单容器
// #code-bottom-panels + 页签条 #code-bottom-tabs：同一时刻只显示一个面板；
// 触发过（有内容）的页签才渲染（从未触发的面板页签不出现）；新消息自动
// showPanel(id) 切页签；各面板自己的 .collapsed 收起态独立保留（收起只收
// 内容，头部状态行常驻）。面板 DOM 与全部内部业务（事件 id、清空按钮、
// 收起按钮）不动——本模块只接管「显隐 + 页签」。
//
// 既有各面板「完成事件」把 classList.remove("hidden") 换成 showPanel(id)、
// 清空/无内容时 hidePanel(id)；容器显隐 = 有无已触发面板。
import { $ } from "/js/app.js";

export const PANEL_LABELS = {
  compile: "编译",
  change: "磁盘变更",
  ai: "AI 对话",
  fix: "修复",
  flash: "烧录",
};

const PANEL_IDS = {
  compile: "code-compile-panel",
  change: "code-change-panel",
  ai: "code-ai-chat-panel",
  fix: "code-fix-panel",
  flash: "code-flash-panel",
};

const shown = new Set();    // 已触发（有内容）的面板 id
let activeId = null;        // 当前展示的面板 id

function panelEl(id) { return $(PANEL_IDS[id]); }

// showPanel(id)：标记触发 + 切换为活动页签（新消息自动显现）。
export function showPanel(id) {
  if (!PANEL_IDS[id]) return;
  shown.add(id);
  activeId = id;
  renderTabs();
  applyActive();
}

// hidePanel(id)：无内容/清空 → 撤下页签；若正活动则退回最后一个仍触发的
// 面板；全部撤下 → 容器隐藏。
export function hidePanel(id) {
  shown.delete(id);
  if (activeId === id) {
    const rest = Object.keys(PANEL_IDS).filter((k) => shown.has(k));
    activeId = rest.length ? rest[rest.length - 1] : null;
  }
  renderTabs();
  applyActive();
}

function renderTabs() {
  const box = $("code-bottom-tabs");
  if (!box) return;
  const ids = Object.keys(PANEL_IDS).filter((k) => shown.has(k));
  box.innerHTML = ids.map((k) =>
    `<button type="button" class="code-bottom-tab${k === activeId ? " on" : ""}"`
    + ` data-bottom-tab="${k}" title="${PANEL_LABELS[k]}">${PANEL_LABELS[k]}</button>`
  ).join("");
}

function applyActive() {
  const c = $("code-bottom-panels");
  if (!c) return;
  if (!shown.size || !activeId) {
    c.classList.add("hidden");
  } else {
    c.classList.remove("hidden");
  }
  for (const k of Object.keys(PANEL_IDS)) {
    const el = panelEl(k);
    if (el) el.classList.toggle("hidden", k !== activeId);
  }
}

// initCodeBottomPanels()：页签条点击切换（host 在 initCodeViewer 调用）。
export function initCodeBottomPanels() {
  const box = $("code-bottom-tabs");
  if (!box) return;
  box.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-bottom-tab]");
    if (!btn || !shown.has(btn.dataset.bottomTab)) return;
    activeId = btn.dataset.bottomTab;
    renderTabs();
    applyActive();
  });
}
