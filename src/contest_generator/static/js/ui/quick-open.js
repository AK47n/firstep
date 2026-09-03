// ui/quick-open.js — Ctrl+P 快速打开浮层（工单 code-editor-refine/09）
//
// 代码 tab 内 Ctrl+P → 全屏轻遮罩 + 顶部输入框 + 结果列表（树扁平清单
// /api/code/open 前端缓存 = codeview.getCodeTreeFiles）：实时 quickOpenMatch
// 匹配（basename 优先 → 路径子串 → 模糊，截断 50）；↑/↓ 选择、Enter 打开
// （openEditorFile 复用：已开激活既有 tab、tab 上限/只读/md 两态语义一致）、
// ×/Esc/点击遮罩关闭；关闭后焦点回归触发位（confirm.js 先例）；无匹配空态。
// 浮层样式 = 既有 overlay token（深浅主题）。模态纪律（评审整改）：本浮层不
// 叠开于 .ref-files-overlay（modal 优先），浮层开启期间吞掉其余 Ctrl 全局
// 快捷键（Ctrl+F/H/W/B/O 不穿透到背后）；纯匹配/高亮 = fx/codeview.js（node
// 单测）。
import { toast } from "/js/app.js";
import { esc } from "/js/fx/core.js";   // 转义单源（fx/core.js 头部约定）
import { quickOpenMatch, quickOpenHighlightParts, fileIconHTML } from "/js/fx/codeview.js";
import { getCodeTreeFiles, getCodeTreeDir, codeTabActive } from "/js/ui/codeview.js";
import { openEditorFile } from "/js/ui/codeeditor.js";

let overlay = null;
let input = null;
let listEl = null;
let results = [];
let selected = 0;
let openerEl = null;   // 浮层关闭后焦点回归触发位（confirm.js 先例）

function closeQuickOpen() {
  if (!overlay) return;
  overlay.remove();
  overlay = null;
  input = null;
  listEl = null;
  results = [];
  selected = 0;
  const opener = openerEl;
  openerEl = null;
  if (opener && opener.isConnected && typeof opener.focus === "function") opener.focus();
}

// highlightPath(path, rank, idx, query)：命中高亮——fx quickOpenHighlightParts
// 单源（rank0 basename 段 / rank1 路径段；模糊与非法 idx 不高亮），只做转义。
function highlightPath(path, rank, idx, query) {
  const parts = quickOpenHighlightParts(path, rank, idx, query);
  if (!parts) return esc(path);
  return esc(parts.before) + "<mark>" + esc(parts.mark) + "</mark>" + esc(parts.after);
}

function renderList(query) {
  const files = getCodeTreeFiles() || [];
  results = quickOpenMatch(files, query);
  selected = 0;
  if (!listEl) return;
  if (!query.trim()) {
    listEl.innerHTML = '<div class="quick-open-empty muted">输入文件名或路径开始搜索（当前工程 '
      + files.length + " 个文件）</div>";
    return;
  }
  if (!results.length) {
    listEl.innerHTML = '<div class="quick-open-empty muted">无匹配「' + esc(query.trim()) + '」</div>';
    return;
  }
  listEl.innerHTML = results.map((r, i) =>
    '<div class="quick-open-item' + (i === 0 ? " on" : "") + '" data-qo-index="' + i + '">'
    + '<span class="quick-open-ico" aria-hidden="true">' + fileIconHTML(r.path, false) + "</span>"
    + '<span class="quick-open-text">'
    + highlightPath(r.path, r.rank, r.idx, query.trim()) + "</span></div>").join("");
}

function moveSelection(delta) {
  if (!results.length) return;
  selected = (selected + delta + results.length) % results.length;
  listEl.querySelectorAll(".quick-open-item").forEach((el, i) => {
    el.classList.toggle("on", i === selected);
  });
  const on = listEl.querySelector(".quick-open-item.on");
  if (on) on.scrollIntoView({ block: "nearest" });
}

function openSelected() {
  const hit = results[selected];
  if (!hit) return;
  const path = hit.path;
  closeQuickOpen();
  openEditorFile(path);   // 复用既有打开语义：已开激活 / tab 上限 / 只读 / md 两态
}

function openQuickOpen() {
  if (overlay) { input && input.focus(); return; }
  if (document.querySelector(".ref-files-overlay")) return;   // 模态纪律：modal 优先，不叠开（评审整改）
  if (!getCodeTreeDir()) { toast("info", "请先打开工程目录（Ctrl+P 需要树清单）"); return; }
  openerEl = (typeof document !== "undefined" && document.activeElement)
    ? document.activeElement : null;
  overlay = document.createElement("div");
  overlay.className = "quick-open-overlay";
  overlay.innerHTML = '<div class="quick-open-box">'
    + '<div class="quick-open-head"><input class="quick-open-input"'
    + ' placeholder="输入文件名快速打开（Ctrl+P）" autocomplete="off" spellcheck="false">'
    + '<button type="button" class="quick-open-close" title="关闭">×</button></div>'
    + '<div class="quick-open-list"></div></div>';
  document.body.appendChild(overlay);
  input = overlay.querySelector(".quick-open-input");
  listEl = overlay.querySelector(".quick-open-list");
  renderList("");
  input.addEventListener("input", () => renderList(input.value));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); moveSelection(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); moveSelection(-1); }
    else if (e.key === "Enter") { e.preventDefault(); openSelected(); }
    else if (e.key === "Escape") { e.preventDefault(); closeQuickOpen(); }
    else if (e.key === "Tab") { e.preventDefault(); }   // 焦点陷阱：保持在输入框（Esc/Enter/↑↓ 足够）
  });
  overlay.querySelector(".quick-open-close").addEventListener("click", closeQuickOpen);
  listEl.addEventListener("click", (e) => {
    const item = e.target.closest("[data-qo-index]");
    if (!item) return;
    selected = Number(item.dataset.qoIndex);
    openSelected();
  });
  overlay.addEventListener("mousedown", (e) => {
    if (e.target === overlay) closeQuickOpen();
  });
  input.focus();
}

// initQuickOpen()：入口绑定（host 启动区调用）——Ctrl+P 全局拦截（仅代码
// tab 激活；浮层开着时 Ctrl+P 聚焦输入框）+ Esc 兜底关闭 + 浮层开启期间吞
// 其余 Ctrl 快捷键（capture 前置：防穿透到背后快捷键，评审整改）。
export function initQuickOpen() {
  document.addEventListener("keydown", (e) => {
    if (overlay && (e.ctrlKey || e.metaKey)) {
      if (e.key.toLowerCase() !== "p") {
        e.preventDefault();
        e.stopPropagation();
      }
      return;
    }
  }, true);
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "p") return;
    if (e.shiftKey) return;   // Ctrl+Shift+P 不拦截（预留命令面板语义，评审整改）
    if (!codeTabActive()) return;
    e.preventDefault();
    openQuickOpen();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || !overlay) return;
    e.preventDefault();
    closeQuickOpen();
  });
}
