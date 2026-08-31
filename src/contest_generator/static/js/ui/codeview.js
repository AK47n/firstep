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
import {
  buildCodeTree,
  codeFileTabHTML,
  codeTreeHTML,
  codeViewHTML,
  outlineHTML,
  outlineEmptyHTML,
  searchListHTML,
  fileFindFilter,
} from "/js/fx/codeview.js";

// 模块态：当前目录 / 扁平清单 / 文件内容 memo / 当前文件与大纲
let codeDir = "";
let codeFiles = [];
const codeFileCache = new Map();  // key = dir + "\u0000" + path → {ok:true, data} | {ok:false, message}
let currentPath = "";
let currentContent = "";
let currentOutline = null;
let currentLang = "plain";

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
  $("code-dir-label").textContent = dir;
  $("code-current-path").textContent = "";
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

// openCodeFile(path)：点树文件 → 三态（加载中 / 成功只读视图 / 失败中文
// 原因可重试），仅成功行高亮；当前文件变化 → 大纲 / 文件内过滤面板联动。
async function openCodeFile(path) {
  const box = $("code-viewer");
  if (!codeFileCache.has(codeDir + "\u0000" + path)) {
    box.innerHTML = '<span class="muted">加载中…</span>';
  }
  const cached = await loadCodeFileState(path);
  if (!cached.ok) {
    currentPath = "";
    currentContent = "";
    currentOutline = null;
    $("code-current-path").textContent = "";
    box.innerHTML = '<div class="error">加载失败：' + esc(cached.message)
      + '</div><span class="muted">点击左侧文件可重试。</span>';
    renderOutline();
    renderFindPanel("", []);
    return;
  }
  const data = cached.data;
  currentPath = path;
  currentContent = data.content || "";
  currentOutline = data.outline || null;
  currentLang = languageOf(path);
  $("code-current-path").innerHTML = codeFileTabHTML(path, currentLang);
  box.innerHTML = codeViewHTML(currentContent, currentLang);
  document.querySelectorAll("[data-code-file]").forEach((b) =>
    b.classList.toggle("on", b.dataset.codeFile === path));
  renderOutline();
  renderFindPanel($("code-find-input").value || "", fileFindFilter(currentContent.split("\n"), $("code-find-input").value || ""));
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
  const targets = [gut, pre].filter(Boolean);
  targets.forEach((el) => el.classList.add("flash"));
  setTimeout(() => targets.forEach((el) => el.classList.remove("flash")), 1200);
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

// ===== 右侧栏：大纲 =====
function renderOutline() {
  const box = $("code-outline");
  if (!currentPath) {
    box.innerHTML = '<span class="muted">打开 .c/.h 文件后显示函数 / 宏 / include</span>';
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

  // 大纲点击跳行（delegation：渲染后条目存在）
  const outline = $("code-outline");
  if (outline) outline.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-outline-line]");
    if (btn) jumpToLine(parseInt(btn.dataset.outlineLine, 10));
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
  if (findInput) findInput.addEventListener("input", () =>
    renderFindPanel(findInput.value, fileFindFilter(currentContent.split("\n"), findInput.value)));
  document.addEventListener("keydown", (e) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "f") return;
    if (!codeTabActive() || !findInput) return;
    e.preventDefault();
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
  // 搜索结果点击跳文件 + 行（delegation）
  const results = $("code-search-results");
  if (results) results.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-search-path]");
    if (!btn) return;
    const path = btn.dataset.searchPath;
    const line = parseInt(btn.dataset.searchLine, 10);
    await openCodeFile(path);
    jumpToLine(line);
  });
}
