// ui/codeview.js — 代码查看器 DOM 胶水（工单 code-viewer/04-05）
//
// 「代码」tab 全部交互：选择文件夹（/api/pick-directory——浏览器拿不到
// 绝对路径，必须服务端原生对话框）→ 打开目录（/api/code/open）→ 树点击
// 懒加载文件（/api/code/file，memo + 三态）→ 右侧栏：大纲点击跳行 /
// 跨文件搜索（/api/code/search）/ 当前文件 Ctrl+F 即时过滤。只读、零写侧。
// 纯件在 fx/codeview.js；host 顶部 import 调 initCodeViewer；最近记录卡经
// openCodeViewer(dir) 桥进入（工单 06）。
import { $, apiGet, apiPost, toast, toastError } from "/js/app.js";
import { esc } from "/js/fx/core.js";
import { languageOf } from "/js/fx/highlight.js";
import { codeZoomClamp, parseZoomStored } from "/js/fx/code.js";
import { parseMarkdownBlocks, markdownPreviewHTML, markdownOutline, hasScheme } from "/js/fx/markdown.js";
import {
  buildCodeTree,
  codeFileTabHTML,
  codeTreeHTML,
  codeViewHTML,
  outlineHTML,
  outlineEmptyHTML,
  searchListHTML,
  fileFindFilter,
  treeWidthClamp,
  parseTreeWidthStored,
  CODE_TREE_WIDTH_MAX,
  CODE_TREE_WIDTH_DEFAULT,
} from "/js/fx/codeview.js";

// 模块态：当前目录 / 扁平清单 / 文件内容 memo / 当前文件与大纲
let codeDir = "";
let codeFiles = [];
const codeFileCache = new Map();  // key = dir + "\u0000" + path → {ok:true, data} | {ok:false, message}
let currentPath = "";
let currentContent = "";
let currentOutline = null;
let currentLang = "plain";
// .md 两态（工单 code-viewer-md-preview/03）：默认预览；搜索结果跳行 / Ctrl+F
// 自动临时切源码（行语义）；「返回预览」按钮回预览；点树内文件也回预览。
let codeViewMode = "preview";
let currentMdBlocks = [];
// 跳行/缩放浮标共用闪烁时延（评审整改：1200 三处归拢）
const CODE_FLASH_MS = 1200;

// 树面板拖拽调宽（工单 code-viewer-tree-resize/01）：宽度持久化键——
// localStorage 只进胶水层（fx 无副作用约定，同 firstep.mainc.zoom 先例）。
const CODE_TREE_W_KEY = "firstep.codeTreeWidth";
const CODE_TREE_WIDTH_STEP = 16;  // 键盘 ←/→ 步进（spec：16px 微调）

function codeFileURL(dir, path) {
  return "/api/code/file?dir=" + encodeURIComponent(dir)
    + "&path=" + encodeURIComponent(path);
}

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
  currentPath = "";
  currentContent = "";
  currentOutline = null;
  resetMdView();
  $("code-dir-label").textContent = dir;
  $("code-current-path").textContent = "";
  updateCodeBackPreview();
  $("code-viewer").innerHTML = '<span class="muted">加载中…</span>';
  $("code-tree").innerHTML = '<span class="muted">加载中…</span>';
  try {
    const data = await apiPost("/api/code/open", { dir });
    codeFiles = data.files || [];
    renderCodeTree();
    $("code-viewer").innerHTML = '<span class="muted">点左侧文件查看内容（只读）</span>';
    renderOutline();
    renderSearchResults([]);
    $("code-find-input").value = "";
    $("code-find-results").innerHTML = '<span class="muted">在当前文件内查找</span>';
  } catch (e) {
    codeFiles = [];
    $("code-tree").innerHTML = '<div class="error">加载失败：' + esc(e.message) + "</div>";
    $("code-viewer").innerHTML = "";
    toastError(e, "打开目录失败");
  }
}

function renderCodeTree() {
  const box = $("code-tree");
  const nodes = buildCodeTree(codeFiles);
  box.innerHTML = nodes.length
    ? '<ul class="code-tree">' + codeTreeHTML(nodes) + "</ul>"
    : '<span class="muted">（没有文件）</span>';
}

// loadCodeFileState(path)：文件内容 memo（key = dir+path）——业务 400 缓存
// （数据现状，重试无意义）；网络 / ≥500 不缓存可重试（对偶母版轮先例）。
async function loadCodeFileState(path) {
  const key = codeDir + "\u0000" + path;
  if (codeFileCache.has(key)) return codeFileCache.get(key);
  try {
    const data = await apiGet(codeFileURL(codeDir, path));
    const cached = { ok: true, data };
    codeFileCache.set(key, cached);
    return cached;
  } catch (e) {
    const cached = { ok: false, message: e.message };
    if (e.status && e.status < 500) codeFileCache.set(key, cached);
    return cached;
  }
}

// openCodeFile(path, mode)：点树文件 → 三态（加载中 / 成功只读视图 / 失败中文
// 原因可重试），仅成功行高亮；当前文件变化 → 大纲 / 文件内过滤面板联动。
// mode（仅 .md 有意义）：缺省 "preview"（VSCode 式渲染预览），"source" =
// 临时源码视图（搜索结果跳行 / Ctrl+F 的行语义入口，工单 code-viewer-md-preview/03）。
async function openCodeFile(path, mode) {
  const box = $("code-viewer");
  if (!codeFileCache.has(codeDir + "\u0000" + path)) {
    box.innerHTML = '<span class="muted">加载中…</span>';
  }
  const cached = await loadCodeFileState(path);
  if (!cached.ok) {
    currentPath = "";
    currentContent = "";
    currentOutline = null;
    resetMdView();
    $("code-current-path").textContent = "";
    updateCodeBackPreview();
    box.innerHTML = '<div class="error">加载失败：' + esc(cached.message)
      + '</div><span class="muted">点击左侧文件可重试。</span>';
    renderOutline();
    renderFindPanel("", []);
    return;
  }
  const data = cached.data;
  currentPath = path;
  currentContent = data.content || "";
  currentLang = languageOf(path);
  if (currentLang === "md") {
    currentMdBlocks = parseMarkdownBlocks(currentContent);
    currentOutline = markdownOutline(currentMdBlocks);
  } else {
    currentMdBlocks = [];
    currentOutline = data.outline || null;
  }
  $("code-current-path").innerHTML = codeFileTabHTML(path, currentLang);
  const findInput = $("code-find-input");
  // .md 默认预览：清掉上一个文件遗留的文件内过滤（预览无行语义，遗留命中
  // 点击会静默落空；「点树回预览」用户故事优先，评审整改）。
  if (currentLang === "md" && mode !== "source" && findInput && findInput.value) {
    findInput.value = "";
  }
  if (currentLang === "md" && mode !== "source") renderMdPreview();
  else renderCodeSource();
  document.querySelectorAll("[data-code-file]").forEach((b) =>
    b.classList.toggle("on", b.dataset.codeFile === path));
  renderOutline();
  renderFindPanel($("code-find-input").value || "", fileFindFilter(currentContent.split("\n"), $("code-find-input").value || ""));
}

// ===== .md 两态视图（工单 code-viewer-md-preview/03）=====

// codeImageUrl(src)：.md 预览图片寻址回调（纯件不感知目录与端点，胶水层
// 负责归一）——相对路径以 .md 所在目录为基准（VSCode 语义），归一后
// ../ 跨出打开根 / 绝对路径 / 非 http(s) 协议 → null（渲染占位不请求）；
// http(s) 直通（spec 测试决策）。渲染器自身还有 isSafeImageSrc 先行防御，
// 这里再归一一次（../ 在子目录场景可被消化）。
function codeImageUrl(src) {
  if (hasScheme(src)) {
    return /^https?:/i.test(src) ? src : null;
  }
  if (src.startsWith("/")) return null;                     // 绝对路径
  const base = currentPath.includes("/")
    ? currentPath.slice(0, currentPath.lastIndexOf("/"))
    : "";
  const norm = normalizeRelPath((base ? base + "/" : "") + src);
  if (norm === null) return null;                           // ../ 跨出打开根
  return "/api/code/raw?dir=" + encodeURIComponent(codeDir)
    + "&path=" + encodeURIComponent(norm);
}

// normalizeRelPath(p)：相对路径段归一（./ 与空段消去、.. 消前段）；越出根
// 返回 null（标记占位）。
function normalizeRelPath(p) {
  const segs = [];
  for (const seg of String(p == null ? "" : p).split("/")) {
    if (!seg || seg === ".") continue;
    if (seg === "..") {
      if (!segs.length) return null;
      segs.pop();
    } else {
      segs.push(seg);
    }
  }
  return segs.join("/");
}

function renderMdPreview() {
  const box = $("code-viewer");
  box.innerHTML = markdownPreviewHTML(currentMdBlocks, { imageUrl: codeImageUrl });
  codeViewMode = "preview";
  updateCodeBackPreview();
}

function renderCodeSource() {
  const box = $("code-viewer");
  box.innerHTML = codeViewHTML(currentContent, currentLang);
  codeViewMode = "source";
  updateCodeBackPreview();
}

// updateCodeBackPreview()：「返回预览」按钮仅 .md 临时源码态可见（顶栏文件
// 标签旁）；预览态 / 非 .md 隐藏。
function updateCodeBackPreview() {
  const btn = $("code-back-preview");
  if (!btn) return;
  btn.classList.toggle("hidden", !(currentLang === "md" && codeViewMode === "source"));
}

// resetMdView()：.md 两态复位（预览向 + 块缓存清空）——loadCodeDir 与
// openCodeFile 失败支共用（评审整改：防第三态漂移）。
function resetMdView() {
  codeViewMode = "preview";
  currentMdBlocks = [];
}

// flashEl(el)：跳行/大纲定位共用闪烁（加 flash → CODE_FLASH_MS 后还原；
// 评审整改：jumpToLine / jumpToMdLine / 缩放浮标三处 1200 归拢）。
function flashEl(el) {
  if (!el) return;
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), CODE_FLASH_MS);
}

// jumpToMdLine(line)：大纲标题点击 → 预览内块级元素（data-md-line）
// scrollIntoView（复用 1 基行号寻址，与源码态 jumpToLine 同轴）+ flash 1.2s。
function jumpToMdLine(line) {
  const box = $("code-viewer");
  if (!box) return;
  const el = box.querySelector('[data-md-line="' + line + '"]');
  if (!el) return;
  el.scrollIntoView({ block: "center" });
  flashEl(el);
}

// setActiveLine(line)：当前行高亮（工单 code-viewer-polish/02）——内容行与
// 行号同 data 键对齐：清旧 active → 设新 active（点击 / 跳行共用同一路径，
// 避免两套状态漂移）。行不存在则不动。
function setActiveLine(line) {
  const box = $("code-viewer");
  if (!box) return;
  const gut = box.querySelectorAll(".code-gutter-line")[line - 1];
  const pre = box.querySelectorAll(".code-pre-line")[line - 1];
  if (!gut && !pre) return;
  box.querySelectorAll(".code-pre-line.active, .code-gutter-line.active").forEach(
    (el) => el.classList.remove("active"));
  [gut, pre].forEach((el) => el && el.classList.add("active"));
}

// jumpToLine(line)：大纲 / 搜索结果跳行——gutter 行元素 scrollIntoView
// （同一滚动容器，横向不跑）+ 主行号与内容行同 data 键对齐闪 flash 1.2s
// 后还原（spec.md:127-128）；当前行持续高亮随跳行移动（setActiveLine）。
function jumpToLine(line) {
  const box = $("code-viewer");
  if (!box) return;
  const gut = box.querySelectorAll(".code-gutter-line")[line - 1];
  const pre = box.querySelectorAll(".code-pre-line")[line - 1];
  if (!gut && !pre) return;
  (gut || pre).scrollIntoView({ block: "center" });
  setActiveLine(line);
  [gut, pre].filter(Boolean).forEach(flashEl);
}

// setCodeSide(side)：右侧栏切换（outline / search）——侧栏按钮与 Ctrl+F
// 共用同一生效路径（评审整改：Ctrl+F 必须可见地切到「搜索」栏，否则聚焦
// 隐藏输入框、用户故事 6 落空）。
function setCodeSide(side) {
  document.querySelectorAll("[data-code-side]").forEach((x) =>
    x.classList.toggle("on", x.dataset.codeSide === side));
  document.querySelectorAll("[data-code-side-panel]").forEach((p) =>
    p.classList.toggle("hidden", p.dataset.codeSidePanel !== side));
}

// ===== 树面板拖拽调宽（工单 code-viewer-tree-resize/01）=====
function codeLayoutEl() {
  return document.querySelector(".code-layout");
}

// applyTreeWidth(px, persist)：单一路径——纯函数收敛（clamp 到
// [160, min(720, layoutW-480)]）→ 写 CSS 变量（.code-layout 网格列宽
// 随之变化）→ persist 时落 localStorage（try/catch：隐私模式静默）。
function applyTreeWidth(px, persist) {
  const layout = codeLayoutEl();
  if (!layout) return;
  const w = treeWidthClamp(px, layout.getBoundingClientRect().width);
  layout.style.setProperty("--code-tree-w", w + "px");
  if (persist) {
    try { localStorage.setItem(CODE_TREE_W_KEY, String(w)); } catch { /* 静默 */ }
  }
}

// restoreTreeWidth()：init 恢复——读存储（try/catch）→ parse 收敛 →
// 同一 apply 路径；persist=false（值与存储一致，不重复写）。
function restoreTreeWidth() {
  const layout = codeLayoutEl();
  if (!layout) return;
  let raw = null;
  try { raw = localStorage.getItem(CODE_TREE_W_KEY); } catch { raw = null; }
  applyTreeWidth(parseTreeWidthStored(raw, layout.getBoundingClientRect().width), false);
}

// currentTreeWidth(layout)：当前生效树宽（px；未设/非法 → 默认 240）——
// endDrag 落盘与键盘微调共用同一读取（评审整改：去重复 parseInt || 兜底）。
function currentTreeWidth(layout) {
  return parseInt(layout.style.getPropertyValue("--code-tree-w"), 10)
    || CODE_TREE_WIDTH_DEFAULT;
}

function initCodeTreeResize() {
  const handle = $("code-tree-resize");
  const layout = codeLayoutEl();
  if (!handle || !layout) return;
  let dragging = false;

  // 拖拽：pointer capture（移出窗口/松手外仍收到 move）→ clientX 相对
  // 布局左缘即目标树宽；body.code-resizing 禁文本选中。pointercancel 与
  // pointerup 同路径（落盘当前值）。
  handle.addEventListener("pointerdown", (e) => {
    dragging = true;
    // setPointerCapture 对合成事件（PointerEvent 无活动指针）会抛
    // NotFoundError——捕获失败不阻断拖拽（move/up 仍绑在 handle 上），
    // 仅作防御性包装（真指针事件正常生效）。
    try { handle.setPointerCapture(e.pointerId); } catch { /* 合成事件：忽略 */ }
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
  // 双击复位默认 240 并持久化
  handle.addEventListener("dblclick", () => applyTreeWidth(CODE_TREE_WIDTH_DEFAULT, true));
  // 键盘（role=separator 焦点可达）：←/→ 16px 步进、Home 默认、End 上限，
  // 与拖拽同一 applyTreeWidth 路径（含持久化）。
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

// ===== 右侧栏：大纲 =====
function renderOutline() {
  const box = $("code-outline");
  if (!currentPath) {
    box.innerHTML = '<span class="muted">打开 .c/.h / .md 文件后显示函数 / 宏 / include（.md 为标题）</span>';
    return;
  }
  box.innerHTML = currentOutline && currentOutline.length
    ? outlineHTML(currentOutline)
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
  box.innerHTML = '<ul class="code-side-summary">'
    + `<li><span class="muted">${(hits || []).length} 条命中${data && data.truncated ? "（已达上限）" : ""}${data ? " · 扫描 " + data.files_scanned + " 个文件" : ""}</span></li>`
    + "</ul>" + searchListHTML(hits, currentPath);
}

// ===== 右侧栏：当前文件 Ctrl+F =====
function renderFindPanel(q, lineHits) {
  const box = $("code-find-results");
  if (!currentPath) { box.innerHTML = ""; return; }
  if (!q) { box.innerHTML = '<span class="muted">在当前文件内查找</span>'; return; }
  if (!lineHits.length) { box.innerHTML = '<span class="muted">当前文件没有匹配</span>'; return; }
  box.innerHTML = '<ul class="code-find-list">' + lineHits.map((n) =>
    `<li><button type="button" class="code-find-item" data-find-line="${n}">
        <span class="code-search-path">第 ${esc(n)} 行</span>
        <span class="code-search-text">${esc(String(currentContent.split("\n")[n - 1] || "").trim().slice(0, 80))}</span></button></li>`)
    .join("") + "</ul>";
}

// ===== 代码字号缩放（工单 code-viewer-zoom/01） =====
// Ctrl/Cmd+滚轮缩放只读代码字体：上滚放大 / 下滚缩小，80%–200%、每档 10%
// （codeZoomClamp / parseZoomStored 复用 fx/code.js 单源，不新增重复实现）。
// 机制 = .code-gutter-line 与 .code-pre 的 font-size 均 `calc(13px * var(--code-zoom, 1))`
// （index.html 单源），本层只写 #code-viewer 容器 inline 变量——openCodeFile
// 的 innerHTML 重渲染不影响容器自身 style（缩放跟会话不跟文件）；值持久化
// 到 firstep.codeViewZoom；缩放时右上角浮出当前百分比（1.2s 淡出）。
const CODE_VIEW_ZOOM_KEY = "firstep.codeViewZoom";
const CODE_VIEW_ZOOM_STEP = 10;
const CODE_VIEW_ZOOM_ACC = 40;   // 滚轮累积阈值：高 DPI 鼠标/触控板多事件档
let codeZoomBadge = null;
let codeZoomBadgeTimer = 0;
let codeZoomAcc = 0;

// currentCodeZoomPct()：反算当前档位（读 container inline --code-zoom，
// 非法/未设 → 100）。
function currentCodeZoomPct() {
  const view = $("code-viewer");
  const raw = parseFloat(view ? view.style.getPropertyValue("--code-zoom") : "");
  return raw > 0 ? Math.round(raw * 100) : 100;
}

// showCodeZoomBadge(pct)：右上角浮标（首次懒建，挂 .code-pane-main——
// 不随 .code-view 内容滚动；重复缩放重置 1.2s 淡出计时）。
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

// applyCodeZoom(pct)：单一路径——clamp → 写 --code-zoom → 持久化 → 浮标。
function applyCodeZoom(pct) {
  const view = $("code-viewer");
  if (!view) return;
  pct = codeZoomClamp(pct);
  view.style.setProperty("--code-zoom", String(pct / 100));
  try { localStorage.setItem(CODE_VIEW_ZOOM_KEY, String(pct)); } catch (e) {}
  showCodeZoomBadge(pct);
}

// initCodeViewZoom()：恢复持久化档位（静默，不弹浮标）+ wheel 监听
// （passive:false 才可 preventDefault；仅 Ctrl/Cmd 接管——普通滚动交还原生；
// 累积 |Δ| ≥ 40 才触发一步）。
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

  const tree = $("code-tree");
  if (tree) tree.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-code-file]");
    if (!btn) return;
    openCodeFile(btn.dataset.codeFile);
  });

  // 当前行：点击代码行 → 持续淡色高亮（delegation，渲染后无需重绑）
  const view = $("code-viewer");
  if (view) view.addEventListener("click", (e) => {
    const el = e.target.closest(".code-pre-line");
    if (!el) return;
    setActiveLine(parseInt(el.dataset.codeLine, 10));
  });

  // 侧栏切换（大纲 / 搜索）
  document.querySelectorAll("[data-code-side]").forEach((b) =>
    b.addEventListener("click", () => setCodeSide(b.dataset.codeSide)));

  // 大纲点击跳行（delegation：渲染后条目存在）；.md 预览态走块级元素
  // data-md-line 滚动定位（工单 code-viewer-md-preview/03），源码态与
  // 非 .md 走既有 gutter 跳行（flash + 当前行移动）。
  const outline = $("code-outline");
  if (outline) outline.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-outline-line]");
    if (!btn) return;
    const line = parseInt(btn.dataset.outlineLine, 10);
    if (currentLang === "md" && codeViewMode === "preview") jumpToMdLine(line);
    else jumpToLine(line);
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
  // 侧栏（查找输入 / 命中列表所在，评审整改：不切则聚焦隐藏框无界面反馈）
  // → 聚焦输入面板即时过滤。
  const findInput = $("code-find-input");
  if (findInput) findInput.addEventListener("input", () => {
    // .md 预览态经侧栏「搜索」tab 直输（非 Ctrl+F）时同样先切源码——
    // 行语义需要行号（评审整改：预览态点命中无 gutter 会静默落空）。
    if (currentLang === "md" && codeViewMode === "preview") renderCodeSource();
    renderFindPanel(findInput.value, fileFindFilter(currentContent.split("\n"), findInput.value));
  });
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "f") return;
    if (!codeTabActive() || !findInput) return;
    e.preventDefault();
    // .md 预览态先切临时源码（行语义需要行号，工单 code-viewer-md-preview/03）
    if (currentLang === "md" && codeViewMode === "preview") renderCodeSource();
    setCodeSide("search");
    findInput.focus();
    findInput.select();
  });
  // 文件内命中点击跳行（delegation）
  const findBox = $("code-find-results");
  if (findBox) findBox.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-find-line]");
    if (btn) jumpToLine(parseInt(btn.dataset.findLine, 10));
  });
  // 搜索结果点击跳文件 + 行（delegation）；命中 .md → 临时源码视图定位
  // （行语义，工单 code-viewer-md-preview/03），非 .md 行为不变。
  const results = $("code-search-results");
  if (results) results.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-search-path]");
    if (!btn) return;
    const path = btn.dataset.searchPath;
    const line = parseInt(btn.dataset.searchLine, 10);
    await openCodeFile(path, "source");
    jumpToLine(line);
  });

  // 「返回预览」（.md 临时源码态）：只读视图回预览排版；重新点树内文件也
  // 回预览（openCodeFile 缺省 mode=preview）。
  const backPreview = $("code-back-preview");
  if (backPreview) backPreview.addEventListener("click", () => {
    if (currentLang === "md") renderMdPreview();
  });

  // 树面板拖拽调宽（工单 code-viewer-tree-resize/01）：绑定手柄 + 恢复
  // localStorage 宽度（DOM 已就绪；无布局/手柄时静默跳过——不阻断其他绑定）。
  initCodeTreeResize();
  restoreTreeWidth();

  // 代码字号缩放（工单 code-viewer-zoom/01）：恢复持久化档位 + Ctrl/Cmd+滚轮。
  initCodeViewZoom();
}
