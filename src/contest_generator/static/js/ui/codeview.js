// ui/codeview.js — 代码 tab 容器胶水（工单 code-viewer/04-05 + code-viewer-editor/02）
//
// 「代码」tab 的目录/树/侧栏/工具栏：选择文件夹（/api/pick-directory）→
// 打开目录（/api/code/open）→ 树 → 右侧栏大纲/跨文件搜索/文件内查找 →
// 字号缩放 / 树调宽。中栏（多标签 + 可编辑三明治 + 保存）全部归
// ui/codeeditor.js——本模块经其导出面联动（openEditorFile / getActiveTab /
// editJumpToLine / editJumpToFile / setMdMode / setCodeDir /
// onActiveTabChanged / isMdPreviewActive）。纯件在 fx/codeview.js /
// fx/codeeditor.js。
import { $, apiGet, apiPost, toast, toastError } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import { codeZoomClamp, parseZoomStored, isMainCPath } from "/js/fx/code.js";
import { isTabSavable } from "/js/fx/codeeditor.js";  // 保存判据单源（code-viewer-editor/03）
import {
  baselineSnapshot,
  baselineDiff,
  baselineHasChanges,
  baselineEvict,
} from "/js/fx/disk-baseline.js";  // 磁盘基线对比纯件（code-ide-flow/01——事实源不依赖事件载荷）
import { getMainCDiskDir, loadDiskMainC, refreshMainCDiskState } from "/js/ui/generate-mainc-sync.js";  // main.c 磁盘同步（mainc-codeview-bridge/03 + code-viewer-editor/05：保存后步骤 8 状态行刷新）
import { scrollToStep } from "/js/ui/step-state.js";  // 跳回生成页滚动到步骤 8（mainc-codeview-bridge/03）
import {
  buildCodeTree,
  codeTreeHTML,
  outlineHTML,
  outlineEmptyHTML,
  searchListHTML,
  fileFindFilter,
  treeWidthClamp,
  parseTreeWidthStored,
  CODE_TREE_WIDTH_MAX,
  CODE_TREE_WIDTH_DEFAULT,
  TREE_CHANGE_NEW,
  TREE_CHANGE_MODIFIED,
} from "/js/fx/codeview.js";
import {
  setCodeDir,
  openEditorFile,
  getActiveTab,
  editJumpToLine,
  editJumpToFile,
  setMdMode,
  isMdPreviewActive,
  onActiveTabChanged,
  onFileSaved,
  openTabPaths,
  dirtyTabPaths,
  setDiskChanged,
  clearDiskChanged,
  reloadTabFromDisk,
} from "/js/ui/codeeditor.js";

// 模块态：当前目录 / 扁平清单（中栏状态在 codeeditor.js）
let codeDir = "";
let codeFiles = [];
// 树徽章（code-ide-flow/02）：磁盘基线对比结果 {path → "new"|"modified"}，
// renderCodeTree 交 buildCodeTree/codeTreeHTML 渲染「新/变」徽章。
let codeTreeChanges = {};

// ===== 磁盘基线（工单 code-ide-flow/02）=====
// 事实源 = 磁盘基线对比（spec：不消费 fix/task/deepen 事件载荷——那些只有
// main.c diff 或刷新即丢）。localStorage 只进胶水层（fx 无副作用约定，同
// firstep.codeTreeWidth 先例）；store = {dir → {ts, files}}，files 为
// baselineSnapshot 规范化快照；目录隔离 + evict（fx/disk-baseline.js）。
const CODE_BASELINE_KEY = "firstep.codeBaseline";
const CODE_BASELINE_MAX_DIRS = 8;  // LRU 上限（存过多目录的旧基线无意义）

function baselineStoreLoad() {
  try {
    const v = JSON.parse(localStorage.getItem(CODE_BASELINE_KEY) || "{}");
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch (e) { return {}; }
}

function baselineStoreSave(store) {
  try { localStorage.setItem(CODE_BASELINE_KEY, JSON.stringify(store)); } catch (e) { /* 静默 */ }
}

// baselineStoreCommit(store, dir, snap)：目录条目落盘（ts 刷新 + evict）。
function baselineStoreCommit(store, dir, snap) {
  store[dir] = { ts: Date.now(), files: snap };
  baselineStoreSave(baselineEvict(store, CODE_BASELINE_MAX_DIRS));
}

// baselineDiffDisk(dir, files)：当前磁盘清单 vs 已有基线 → diff（**纯计算
// 不推进基线**——基线 = 用户最后确认点，对比只探测；推进只在：首次打开
// 目录建立 / 保存·重载单文件 / 「清空并确认已看」/ 树操作整体对齐）。无
// 基线（首次打开此目录）→ null（调用方建立基线，不感知）。
function baselineDiffDisk(dir, files) {
  const store = baselineStoreLoad();
  const prev = store[dir];
  if (!prev || !prev.files) return null;
  return baselineDiff(prev.files, baselineSnapshot(files));
}

// baselineCommitDisk(dir, files)：确认点整体推进——基线 = 当前磁盘快照
// （首次打开 / 树操作 / 「清空并确认已看」）。
function baselineCommitDisk(dir, files) {
  const store = baselineStoreLoad();
  baselineStoreCommit(store, dir, baselineSnapshot(files));
}

// baselineUpdateFile(dir, path, mtimeNs, sizeBytes)：保存 / 重载后基线单
// 条目对齐（下次对比不再把本文件报为「修改」——写盘方 = 本 IDE 自己）。
function baselineUpdateFile(dir, path, mtimeNs, sizeBytes) {
  const store = baselineStoreLoad();
  const entry = store[dir];
  if (!entry || !entry.files) return;
  if (!Object.prototype.hasOwnProperty.call(entry.files, path)) {
    entry.files[path] = {};
  }
  entry.files[path].mtime_ns = String(mtimeNs == null ? "" : mtimeNs);
  entry.files[path].size_bytes = sizeBytes == null ? "" : sizeBytes;
  entry.ts = Date.now();
  baselineStoreSave(baselineEvict(store, CODE_BASELINE_MAX_DIRS));
}

// applyDiskChanges(diff)：基线对比命中 → 联动（spec 1）——干净标签自动
// 重载（计数 → toast）；脏标签置「磁盘已变更」徽章（点徽章弹既有三选，绝不
// 静默——脏标签永不推进，留待用户定夺）；未打开的变更文件留树徽章。树徽章
// = 磁盘改动集合（新增「新」/ 修改「变」），**不因自动重载而消失**——重载
// 只是标签跟上磁盘，用户尚未整体审视（spec 用户故事 2）；「清空并确认已
// 看」（工单 03）/保存/树操作才推进基线让集合收敛。removed 文件标签保留旧
// 内容可继续查看（保存时后端既有错误文案兜底；树重拉后条目自然消失）。
async function applyDiskChanges(diff) {
  const changed = diff.added.concat(diff.modified);
  const dirty = new Set(dirtyTabPaths());
  const open = new Set(openTabPaths());
  let reloaded = 0;
  for (const path of changed) {
    if (!open.has(path)) continue;
    if (dirty.has(path)) {
      setDiskChanged([path]);
      continue;
    }
    try {
      if ((await reloadTabFromDisk(path)) === "reloaded") reloaded++;
    } catch (e) {
      // 磁盘文件已不存在 / 读取失败：保留标签旧内容（验收 4），不打断
    }
  }
  const next = {};
  for (const p of diff.modified) next[p] = TREE_CHANGE_MODIFIED;
  for (const p of diff.added) next[p] = TREE_CHANGE_NEW;
  codeTreeChanges = next;
  renderCodeTree();
  // main.c 被外部/AI 改写（含子目录）→ 步骤 8 状态行联动（既有路径）
  if ((diff.modified.concat(diff.added)).some(isMainCPath) && isMainCDiskDir()) {
    refreshMainCDiskState();
  }
  if (reloaded > 0) {
    toast("ok", reloaded + " 个文件已被外部更新，已自动重载");
  }
}

// probeDiskBaseline(dir)：重拉清单 + 基线探测（纯计算不推进基线；无基线先
// 建立）——loadCodeDir 与 checkCodeDiskChanges 共用同一探测序（评审整改：
// 两处同序易漂移）。无基线 → 徽章集合清空（跨目录/首次不残留旧目录徽章——
// spec：目录隔离不串台）。**不渲染**——渲染由调用方统一（无变更一次 /
// 有变更 applyDiskChanges 内一次，评审整改：消灭双次渲染）。
async function probeDiskBaseline(dir) {
  const data = await apiPost("/api/code/open", { dir });
  codeFiles = data.files || [];
  const diff = baselineDiffDisk(dir, codeFiles);
  if (diff === null) {
    baselineCommitDisk(dir, codeFiles);
    codeTreeChanges = {};
  }
  return diff;
}

// checkCodeDiskChanges()：切回「代码」tab / 显式刷新入口——重扫磁盘对比
// 基线，命中 → applyDiskChanges（loadCodeDir 成功与 refreshCodeTreeOnly
// 之外的第三触发点；与 index.html tab 切换钩子接线）。
export async function checkCodeDiskChanges() {
  if (!codeDir) return;
  try {
    const diff = await probeDiskBaseline(codeDir);
    if (diff && baselineHasChanges(diff)) {
      await applyDiskChanges(diff);
    } else {
      codeTreeChanges = {};   // 变更已收敛（无 diff）：不残留旧徽章
      renderCodeTree();
    }
  } catch (e) {
    toastError(e, "刷新文件变化失败");
  }
}

// 跳行/缩放浮标共用闪烁时延（评审整改（工单 code-viewer/09）：1200 三处归拢）
const CODE_FLASH_MS = 1200;

// 树面板拖拽调宽（工单 code-viewer-tree-resize/01）：宽度持久化键——
// localStorage 只进胶水层（fx 无副作用约定，同 firstep.mainc.zoom 先例）。
const CODE_TREE_W_KEY = "firstep.codeTreeWidth";
const CODE_TREE_WIDTH_STEP = 16;  // 键盘 ←/→ 步进（spec：16px 微调）

function codeTabActive() {
  const sec = $("tab-code");
  return !!(sec && sec.classList.contains("active"));
}

// openCodeViewer(dir)：外部桥（最近记录卡「查看代码」/ 探针）——先切到
// 「代码」tab 再加载目录；dir 为空 → toast 中文。
export function openCodeViewer(dir) {
  const btn = document.querySelector('nav button[data-tab="code"]');
  if (btn) btn.click();
  loadCodeDir(dir || "");
}

async function loadCodeDir(dir) {
  if (!dir) { toast("error", "目录为空：无法打开（请从最近记录或「选择文件夹」进入）"); return; }
  codeDir = dir;
  setCodeDir(dir);  // 编辑器上下文切换：清标签/缓存/活动态（code-viewer-editor/02）
  $("code-dir-label").textContent = dir;
  updateGotoGenerateVisibility();
  $("code-tree").innerHTML = '<span class="muted">加载中…</span>';
  try {
    // code-ide-flow/02：基线探测——首次打开建基线（无感知）；已打开过 →
    // 对比旧基线感知（上次会话/外部编辑器改过）→ 联动（干净重载 / 脏标签
    // 徽章 / 树徽章）。基线**不**随打开推进——diff 是待审视变更集，用户
    // 点「清空并确认已看」（工单 03）才整体确认（spec 用户故事 2）。
    const diff = await probeDiskBaseline(codeDir);
    renderOutline();
    renderSearchResults([]);
    $("code-find-input").value = "";
    $("code-find-results").innerHTML = '<span class="muted">在当前文件内查找</span>';
    if (diff && baselineHasChanges(diff)) {
      await applyDiskChanges(diff);   // 内部渲染树（带「新/变」徽章）
    } else {
      codeTreeChanges = {};           // 跨目录/无变更：不残留上一目录徽章
      renderCodeTree();
    }
  } catch (e) {
    codeFiles = [];
    $("code-tree").innerHTML = '<div class="error">加载失败：' + esc(e.message) + "</div>";
    toastError(e, "打开目录失败");
  }
}

// isMainCDiskDir()：当前打开目录 === 生成上下文目录（单源谓词——「去生成页
// 编辑 main.c」可见性、main.c 保存联动与代码栏编译引导共用，防多处漂移；
// code-tab-compile/03 起 export：ui/code-compile.js 直接 import 同一实现）。
export function isMainCDiskDir() {
  return !!codeDir && codeDir === getMainCDiskDir();
}

// updateGotoGenerateVisibility()：当前打开目录 === 生成上下文目录 → 顶栏
// 「去生成页编辑 main.c」可见（mainc-codeview-bridge/03 双向跳转桥——生成页
// 步骤 8 仍是 main.c 编辑入口之一，编辑器与步骤 8 双入口共存）。
function updateGotoGenerateVisibility() {
  const btn = $("btn-code-goto-generate");
  if (!btn) return;
  btn.classList.toggle("hidden", !isMainCDiskDir());
}

function renderCodeTree() {
  const box = $("code-tree");
  const nodes = buildCodeTree(codeFiles, codeTreeChanges);
  box.innerHTML = nodes.length
    ? '<ul class="code-tree">' + codeTreeHTML(nodes) + "</ul>"
    : '<span class="muted">（没有文件）</span>';
}

// refreshCodeTreeOnly()：仅重拉清单 + 重渲染树（工单 code-tree-ops/02）——
// 树操作（新建/重命名/删除）成功后刷新用；**不**碰中栏标签/内容（相对
// loadCodeDir：后者会 setCodeDir 清全部标签，树操作不能丢编辑态）。
// code-ide-flow/02：树操作是用户在本 IDE 内主动改盘——基线整体对齐为当前
// 快照（不视为外部变更，徽章清空），避免下次对比把自己改的报「修改」。
export async function refreshCodeTreeOnly() {
  if (!codeDir) return;
  try {
    const data = await apiPost("/api/code/open", { dir: codeDir });
    codeFiles = data.files || [];
    baselineCommitDisk(codeDir, codeFiles);
    codeTreeChanges = {};
    renderCodeTree();
  } catch (e) {
    toastError(e, "刷新文件树失败");
  }
}

// getCodeTreeDir() / getCodeTreeFiles()：当前目录与清单只读出口（工单
// code-tree-ops/02：树操作判定 is_dir / 组装请求 payload）。
export function getCodeTreeDir() { return codeDir; }
export function getCodeTreeFiles() { return codeFiles; }

// ===== 右侧栏：大纲（活动标签来自 codeeditor） =====
function renderOutline() {
  const box = $("code-outline");
  const tab = getActiveTab();
  if (!tab) {
    box.innerHTML = '<span class="muted">打开 .c/.h / .md 文件后显示函数 / 宏 / include（.md 为标题）</span>';
    return;
  }
  box.innerHTML = tab.outline && tab.outline.length
    ? outlineHTML(tab.outline)
    : outlineEmptyHTML();
}

// ===== 右侧栏：跨文件搜索 =====
async function runProjectSearch(q) {
  const needle = String(q || "").trim();
  if (!needle) { renderSearchResults([]); return; }
  const box = $("code-search-results");
  box.innerHTML = '<span class="muted">搜索中…</span>';
  try {
    const data = await apiGet("/api/code/search?dir=" + encodeURIComponent(codeDir)
      + "&q=" + encodeURIComponent(needle));
    renderSearchResults(data.hits || [], data);
  } catch (e) {
    box.innerHTML = '<div class="error">搜索失败：' + esc(e.message) + "</div>";
    toastError(e, "搜索失败");
  }
}

function renderSearchResults(hits, data) {
  const box = $("code-search-results");
  const active = getActiveTab();
  box.innerHTML = '<ul class="code-side-summary">'
    + `<li><span class="muted">${(hits || []).length} 条命中${data && data.truncated ? "（已达上限）" : ""}${data ? " · 扫描 " + data.files_scanned + " 个文件" : ""}</span></li>`
    + "</ul>" + searchListHTML(hits, active ? active.path : "");
}

// ===== 右侧栏：当前文件 Ctrl+F（数据 = codeeditor 活动标签内容） =====
function renderFindPanel(q, lineHits) {
  const box = $("code-find-results");
  const tab = getActiveTab();
  if (!tab) { box.innerHTML = ""; return; }
  if (!q) { box.innerHTML = '<span class="muted">在当前文件内查找</span>'; return; }
  if (!lineHits.length) { box.innerHTML = '<span class="muted">当前文件没有匹配</span>'; return; }
  box.innerHTML = '<ul class="code-find-list">' + lineHits.map((n) =>
    `<li><button type="button" class="code-find-item" data-find-line="${n}">
        <span class="code-search-path">第 ${esc(n)} 行</span>
        <span class="code-search-text">${esc(String(tab.content.split("\n")[n - 1] || "").trim().slice(0, 80))}</span></button></li>`)
    .join("") + "</ul>";
}

function refreshFindPanel() {
  const input = $("code-find-input");
  const tab = getActiveTab();
  renderFindPanel(input ? input.value || "" : "",
    tab ? fileFindFilter(tab.content.split("\n"), input ? input.value || "" : "") : []);
}

// ===== 代码字号缩放（工单 code-viewer-zoom/01） =====
// Ctrl/Cmd+滚轮缩放（只读视图与编辑器同容器）：上滚放大 / 下滚缩小，
// 80%–200%、每档 10%（codeZoomClamp / parseZoomStored 复用 fx/code.js
// 单源）。机制 = .code-gutter-line / .code-hl / .code-ta 的 font-size 均
// `calc(13px * var(--code-zoom, 1))`（index.html 单源），本层只写
// #code-viewer 容器 inline 变量——重渲染不影响容器自身 style（缩放跟会话
// 不跟文件）；值持久化到 firstep.codeViewZoom；缩放时右上角浮出当前百分比
// （1.2s 淡出）。
const CODE_VIEW_ZOOM_KEY = "firstep.codeViewZoom";
const CODE_VIEW_ZOOM_STEP = 10;
const CODE_VIEW_ZOOM_ACC = 40;   // 滚轮累积阈值：高 DPI 鼠标/触控板多事件档
let codeZoomBadge = null;
let codeZoomBadgeTimer = 0;
let codeZoomAcc = 0;

function currentCodeZoomPct() {
  const view = $("code-viewer");
  const raw = parseFloat(view ? view.style.getPropertyValue("--code-zoom") : "");
  return raw > 0 ? Math.round(raw * 100) : 100;
}

function showCodeZoomBadge(pct) {
  if (!codeZoomBadge) {
    const view = $("code-viewer");
    const pane = view && view.closest(".code-pane-main");
    if (!pane) return;
    codeZoomBadge = document.createElement("div");
    codeZoomBadge.className = "code-zoom-badge";
    codeZoomBadge.setAttribute("aria-hidden", "true");
    pane.appendChild(codeZoomBadge);
  }
  codeZoomBadge.textContent = pct + "%";
  codeZoomBadge.classList.add("show");
  clearTimeout(codeZoomBadgeTimer);
  codeZoomBadgeTimer = setTimeout(() => codeZoomBadge.classList.remove("show"), CODE_FLASH_MS);
}

function applyCodeZoom(pct) {
  const view = $("code-viewer");
  if (!view) return;
  pct = codeZoomClamp(pct);
  view.style.setProperty("--code-zoom", String(pct / 100));
  try { localStorage.setItem(CODE_VIEW_ZOOM_KEY, String(pct)); } catch (e) {}
  showCodeZoomBadge(pct);
}

function initCodeViewZoom() {
  const view = $("code-viewer");
  if (!view) return;
  let pct = 100;
  try { pct = parseZoomStored(localStorage.getItem(CODE_VIEW_ZOOM_KEY)); } catch (e) {}
  view.style.setProperty("--code-zoom", String(pct / 100));
  view.addEventListener("wheel", (e) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    codeZoomAcc += e.deltaY;
    if (Math.abs(codeZoomAcc) < CODE_VIEW_ZOOM_ACC) return;
    const dir = codeZoomAcc < 0 ? CODE_VIEW_ZOOM_STEP : -CODE_VIEW_ZOOM_STEP;  // 上滚放大
    codeZoomAcc = 0;
    applyCodeZoom(currentCodeZoomPct() + dir);
  }, { passive: false });
}

// ===== 树面板拖拽调宽（工单 code-viewer-tree-resize/01） =====
function codeLayoutEl() {
  return document.querySelector(".code-layout");
}

function applyTreeWidth(px, persist) {
  const layout = codeLayoutEl();
  if (!layout) return;
  const w = treeWidthClamp(px, layout.getBoundingClientRect().width);
  layout.style.setProperty("--code-tree-w", w + "px");
  if (persist) {
    try { localStorage.setItem(CODE_TREE_W_KEY, String(w)); } catch (e) { /* 静默 */ }
  }
}

function restoreTreeWidth() {
  const layout = codeLayoutEl();
  if (!layout) return;
  let raw = null;
  try { raw = localStorage.getItem(CODE_TREE_W_KEY); } catch (e) { raw = null; }
  applyTreeWidth(parseTreeWidthStored(raw, layout.getBoundingClientRect().width), false);
}

function currentTreeWidth(layout) {
  return parseInt(layout.style.getPropertyValue("--code-tree-w"), 10)
    || CODE_TREE_WIDTH_DEFAULT;
}

function initCodeTreeResize() {
  const handle = $("code-tree-resize");
  const layout = codeLayoutEl();
  if (!handle || !layout) return;
  let dragging = false;

  handle.addEventListener("pointerdown", (e) => {
    dragging = true;
    try { handle.setPointerCapture(e.pointerId); } catch (e) { /* 合成事件：忽略 */ }
    document.body.classList.add("code-resizing");
  });
  handle.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    applyTreeWidth(e.clientX - layout.getBoundingClientRect().left, false);
  });
  const endDrag = () => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove("code-resizing");
    const cur = layout.style.getPropertyValue("--code-tree-w");
    applyTreeWidth(parseInt(cur, 10) || CODE_TREE_WIDTH_DEFAULT, true);
  };
  handle.addEventListener("pointerup", endDrag);
  handle.addEventListener("pointercancel", endDrag);
  handle.addEventListener("dblclick", () => applyTreeWidth(CODE_TREE_WIDTH_DEFAULT, true));
  handle.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      const cur = layout.style.getPropertyValue("--code-tree-w") || "240px";
      applyTreeWidth((parseInt(cur, 10) || CODE_TREE_WIDTH_DEFAULT)
        + (e.key === "ArrowLeft" ? -16 : 16), true);
    } else if (e.key === "Home") {
      e.preventDefault();
      applyTreeWidth(CODE_TREE_WIDTH_DEFAULT, true);
    } else if (e.key === "End") {
      e.preventDefault();
      applyTreeWidth(CODE_TREE_WIDTH_MAX, true);
    }
  });
}

// ===== 侧栏收起/展开（工单 code-viewer-editor/07）：右侧栏贴右缘 40px
// 竖向轨道（收起）↔ 300px 面板（展开）——点活动页签收起、点轨道条目展开、
// Ctrl+F 强制展开；localStorage 持久化（只进胶水层，fx 无副作用约定同
// firstep.codeTreeWidth 先例）。 =====
const CODE_SIDE_COLLAPSE_KEY = "firstep.codeSideCollapsed";  // "1" = 收起

let activeSide = "outline";

function codeSideLayout() {
  return document.querySelector(".code-layout");
}

// setCodeSideCollapsed(collapsed, persist)：单一路径——.side-collapsed 类
// 驱动 grid 列（--code-side-w 300 ↔ 40），轨道的 on 高亮跟随活动页。
function setCodeSideCollapsed(collapsed, persist) {
  const layout = codeSideLayout();
  if (!layout) return;
  layout.classList.toggle("side-collapsed", !!collapsed);
  document.querySelectorAll(".code-side-rail-btn").forEach((b) =>
    b.classList.toggle("on", b.dataset.codeSide === activeSide));
  if (persist) {
    try { localStorage.setItem(CODE_SIDE_COLLAPSE_KEY, collapsed ? "1" : "0"); } catch (e) { /* 静默 */ }
  }
}

function restoreCodeSideCollapsed() {
  let raw = null;
  try { raw = localStorage.getItem(CODE_SIDE_COLLAPSE_KEY); } catch (e) { raw = null; }
  setCodeSideCollapsed(raw === "1", false);
}

// ===== 侧栏切换（大纲 / 搜索）：按钮与 Ctrl+F 共用同一生效路径
// （评审整改：Ctrl+F 必须可见地切到「搜索」栏，否则聚焦隐藏输入框）。
// 收起态点轨道条目 = 先展开再切换；展开态点活动页签 = 收起。 =====
function setCodeSide(side) {
  activeSide = side;
  document.querySelectorAll("[data-code-side]").forEach((x) =>
    x.classList.toggle("on", x.dataset.codeSide === side));
  document.querySelectorAll("[data-code-side-panel]").forEach((p) =>
    p.classList.toggle("hidden", p.dataset.codeSidePanel !== side));
}

// syncInfoBar()：信息条空态折叠单源——三动作按钮（返回预览/编辑源码/保存）
// 全隐藏 → .empty（display:none，不占 30px 空带）。按钮可见性所有路径
// （openEditorFile/setMdMode/applySavedState/closeTab）均经 notifyActive 汇聚
// onActiveTabChanged 回调调用本函数；**初始空态（未打开目录/无活动 tab）回调
// 从未触发——init 显式调用一次**（用户反馈「中间那行黑的空隙」= 空态信息条）。
function syncInfoBar() {
  const pathBar = document.querySelector(".code-file-path");
  if (!pathBar) return;
  const anyShown = [$("code-back-preview"), $("code-edit-md"), $("btn-code-save")]
    .some((b) => b && !b.classList.contains("hidden"));
  pathBar.classList.toggle("empty", !anyShown);
}

// ===== initCodeViewer：入口绑定（host 启动区调用） =====
export function initCodeViewer() {
  const pick = $("btn-code-pick-dir");
  if (pick) pick.addEventListener("click", async () => {
    try {
      const data = await apiPost("/api/pick-directory");
      if (data && data.path) loadCodeDir(data.path);  // 取消 = path null：静默
    } catch (e) {
      toastError(e, "选择文件夹失败");
    }
  });

  // 双向跳转桥（mainc-codeview-bridge/03）：此目录 = 生成上下文 → 回生成页
  // 步骤 8 编辑磁盘版本 main.c（点击 = 显式意图，加载动作与「从磁盘重新
  // 加载」同源；滚动用 step-nav 统一 scrollToStep(8)）。
  const gotoGen = $("btn-code-goto-generate");
  if (gotoGen) gotoGen.addEventListener("click", async () => {
    const tab = document.querySelector('nav button[data-tab="generate"]');
    if (tab) tab.click();
    scrollToStep(8);
    await loadDiskMainC();
  });

  const tree = $("code-tree");
  if (tree) tree.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-code-file]");
    if (!btn) return;
    openEditorFile(btn.dataset.codeFile);
  });

  // 侧栏切换（大纲 / 搜索）：收起态点轨道条目 = 展开并切换；展开态点活动
  // 页签 = 收起（工单 code-viewer-editor/07）。rail 按钮也带 data-code-side
  // 属性，天然命中同一分支（收起态 = 展开并切换）——不另绑独立监听
  // （评审：避免双重绑定 / 展开态程序化点击先收起再展开的抖动路径）。
  document.querySelectorAll("[data-code-side]").forEach((b) =>
    b.addEventListener("click", () => {
      const layout = codeSideLayout();
      const collapsed = !!(layout && layout.classList.contains("side-collapsed"));
      if (collapsed) {
        setCodeSide(b.dataset.codeSide);
        setCodeSideCollapsed(false, true);
        return;
      }
      if (b.dataset.codeSide === activeSide) {
        setCodeSideCollapsed(true, true);
        return;
      }
      setCodeSide(b.dataset.codeSide);
    }));

  // 显式「收起」按钮（工单 code-viewer-editor/07b）：tab 条右端常驻入口，
  // 不依赖「点活动页签收起」的隐藏捷径（用户反馈无提示太神秘）。
  document.querySelectorAll(".code-side-collapse").forEach((b) =>
    b.addEventListener("click", () => setCodeSideCollapsed(true, true)));

  // 活动标签/内容变化 → 大纲（仅路径变化时重渲——逐键输入不重画大纲）/
  // 文件内查找 / 「返回预览」/「编辑源码」/「保存」按钮可见性联动
  let lastOutlinePath = null;
  onActiveTabChanged(() => {
    const tab = getActiveTab();
    if ((tab ? tab.path : null) !== lastOutlinePath) {
      lastOutlinePath = tab ? tab.path : null;
      renderOutline();
    }
    refreshFindPanel();
    const isMd = !!(tab && tab.lang === "md");
    const btn = $("code-back-preview");
    if (btn) btn.classList.toggle("hidden", !(isMd && tab.mdMode !== "preview"));
    const editMd = $("code-edit-md");
    if (editMd) editMd.classList.toggle("hidden", !(isMd && tab.mdMode === "preview"));
    const save = $("btn-code-save");
    if (save) save.classList.toggle("hidden", !isTabSavable(tab));
    // 信息条空态折叠（工单 code-viewer-editor/07c）：三动作按钮全隐藏 →
    // .empty 不占位（用户反馈「代码第一行上面有一行啥也没有的空行」=
    // 空态信息条占位 30px）。同步点唯一 = 本回调（所有按钮可见性路径
    // openEditorFile/setMdMode/applySavedState 均经 notifyActive 汇聚）。
    syncInfoBar();
  });

  // 保存成功 → 树节点大小刷新 + 大纲重渲（服务端重算 outline 直用——
  // 路径未变，「路径去重」不会自动重画大纲，此处显式刷新）+ main.c 步骤 8
  // 联动（工单 05：此目录 = 生成上下文 → 状态行差异提示立即可见）
  // code-ide-flow/02：**仅保存**推进基线（用户动作 = 确认点；resp 无
  // content——自动重载的 disk 载荷含 content，不推进——变更集保留至
  // 「清空并确认已看」）+ 取消标签徽章（保存后磁盘 = 我的内容，冲突已决）。
  onFileSaved((tab, resp) => {
    const hit = codeFiles.find((f) => f.path === tab.path);
    if (hit && resp && typeof resp.size_bytes === "number") hit.size_bytes = resp.size_bytes;
    renderCodeTree();
    renderOutline();
    if (resp && !("content" in resp)) {
      baselineUpdateFile(codeDir, tab.path, resp.mtime_ns, resp.size_bytes);
      clearDiskChanged(tab.path);
      if (codeTreeChanges[tab.path]) {
        delete codeTreeChanges[tab.path];
        renderCodeTree();
      }
    }
    if (isMainCPath(tab.path) && isMainCDiskDir()) {
      refreshMainCDiskState();
    }
  });

  // 大纲点击跳行（delegation）：.md 预览 / 编辑器/只读源码由 codeeditor 统一
  const outline = $("code-outline");
  if (outline) outline.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-outline-line]");
    if (!btn) return;
    editJumpToLine(parseInt(btn.dataset.outlineLine, 10));
  });

  // 跨文件搜索：按钮 + Enter 提交
  const btnSearch = $("btn-code-search");
  if (btnSearch) btnSearch.addEventListener("click", () =>
    runProjectSearch($("code-search-input").value));
  const searchInput = $("code-search-input");
  if (searchInput) searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); runProjectSearch(searchInput.value); }
  });

  // 当前文件 Ctrl+F：截获浏览器查找框（仅「代码」tab 内）→ 切到「搜索」
  // 侧栏 → 聚焦输入面板即时过滤；.md 预览态先切源码（行语义需要行号）。
  const findInput = $("code-find-input");
  if (findInput) findInput.addEventListener("input", () => {
    const tab = getActiveTab();
    if (tab && tab.lang === "md" && isMdPreviewActive()) setMdMode(tab.path, "edit");
    refreshFindPanel();
  });
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "f") return;
    if (!codeTabActive() || !findInput) return;
    e.preventDefault();
    const tab = getActiveTab();
    if (tab && tab.lang === "md" && isMdPreviewActive()) setMdMode(tab.path, "edit");
    setCodeSide("search");
    setCodeSideCollapsed(false, true);   // 收起态必须展开（否则聚焦隐藏输入框）
    findInput.focus();
    findInput.select();
  });
  const findBox = $("code-find-results");
  if (findBox) findBox.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-find-line]");
    if (btn) editJumpToLine(parseInt(btn.dataset.findLine, 10));
  });
  // 搜索结果点击跳文件 + 行（delegation）；.md 预览态在 codeeditor 内先切
  // 源码（editJumpToFile）。
  const results = $("code-search-results");
  if (results) results.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-search-path]");
    if (!btn) return;
    editJumpToFile(btn.dataset.searchPath, parseInt(btn.dataset.searchLine, 10));
  });

  // 「编辑源码」：.md 预览态 → 编辑态（可修改可保存，工单 05）
  const editMd = $("code-edit-md");
  if (editMd) editMd.addEventListener("click", () => {
    const tab = getActiveTab();
    if (tab && tab.lang === "md") setMdMode(tab.path, "edit");
  });

  // 「返回预览」：.md 编辑态回渲染预览（脏点保留——内容不回滚）
  const backPreview = $("code-back-preview");
  if (backPreview) backPreview.addEventListener("click", () => {
    const tab = getActiveTab();
    if (tab && tab.lang === "md") setMdMode(tab.path, "preview");
  });

  // 树面板拖拽调宽（工单 code-viewer-tree-resize/01）
  initCodeTreeResize();
  restoreTreeWidth();

  // 侧栏收起态恢复（工单 code-viewer-editor/07）：localStorage 持久化
  restoreCodeSideCollapsed();

  // 信息条空态初始折叠（工单 code-viewer-editor/07e）：初始空态（未打开
  // 目录/无活动 tab）onActiveTabChanged 从未触发——显式同步一次，防 30px
  // 黑色空带残留（用户反馈「中间那行黑的空隙不需要留，直接顶满」）。
  syncInfoBar();

  // 代码字号缩放（工单 code-viewer-zoom/01）
  initCodeViewZoom();
}
