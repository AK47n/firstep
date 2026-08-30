// ui/reference.js — 参考文件库 tab DOM 胶水（阶段 2 工单 08）
//
// 参考文件库 tab 全部胶水：过滤/排序/统计 chips 渲染、条目表格（详情/编辑/
// 文件直开/删除事件转发）、套件 kit 词表加载、条目加载（含赛题 key 悬空判定
// 数据源）、编辑弹窗（元数据 + 文件勾删/新增，一次 PUT 落盘）、文件详情弹层
// （清单 + 过滤 + 文本内联查看）、录入表单（AI 简介草稿 + 入库）。
// 纯件在 fx/reference.js（refStats / refStatsText / refChipRowHTML /
// refFilterEntries / refSortEntries / refRowHTML / refDetailHTML /
// refEditValidate / refEditFilePlan / refEditPayload / refEditState——工单 03 迁）；
// 文件行件在 ui/files.js（addFileRow / collectFiles / pickFilesInto /
// bindFilePicker——跨簇共用件，工单 06 迁；本条目的两个文件选择绑定在此绑定）。
// 状态（模块内）：refUI（过滤/排序条件）/ refFilterContext（过滤上下文组装）/
// refSearchTimer / kitVocabulary（套件词表）/ refEntryCache（条目缓存）/
// refTopicKeys（赛题 key 清单，悬空判定）。无跨簇 mutable 状态读写（参考
// 选择器在 generate-recommend.js 内经 /api/references 直连，不经本簇缓存）。
// host 页签分发器 / 启动区经顶部 import 调 loadReferences / loadKitVocabulary /
// initReferenceToolbar；deleteReference / editReference / openReferenceFile /
// viewReferenceDetail 亦导出（收尾工单核对使用面）。
// 顶层监听（ref-anchor-kind / btn-ref-add-file-row+初始行 / btn-ref-draft-desc /
// btn-ref-add / 两个 bindFilePicker）在 import 时绑定（module 延迟执行，
// DOM 已就绪）。
import { $, apiGet, apiPost, apiPut, apiDelete, toast } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import { esc, formatSize } from "/js/fx/core.js";
import { refStats, refStatsText, refChipRowHTML, refFilterEntries, refSortEntries, refRowHTML, refDetailHTML, refEditValidate, refEditFilePlan, refEditPayload, refEditState } from "/js/fx/reference.js";
import { addFileRow, collectFiles, pickFilesInto, bindFilePicker } from "/js/ui/files.js";

// —— 参考库工具栏状态与渲染（工单 02）：过滤条件集中于此，事件层只转发 ——
// （工单 04 增 dangling 维度 = 只看悬空条目；refFilterContext 组装过滤上下文：
// 用户条件 + 悬空判定词表——行渲染与统计渲染共用同一定义，防两处漂移）
const refUI = { q: "", platform: "", anchorKind: "", sortBy: "title", sortDir: "asc", dangling: false };
const refFilterContext = () => ({ ...refUI, topicKeys: refTopicKeys, kitVocab: kitVocabulary });
let refSearchTimer = null;

function renderReferenceChips() {
  // chips 计数 = 全量（维度概览）；统计条 = 过滤结果（随过滤联动）
  const stats = refStats(refEntryCache || []);
  $("ref-platform-chips").innerHTML = refChipRowHTML([
    { value: "", label: "全部" },
    { value: "any", label: "ANY", count: stats.platforms.any },
    { value: "stm32", label: "STM32", count: stats.platforms.stm32 },
    { value: "mspm0", label: "MSPM0", count: stats.platforms.mspm0 },
  ], refUI.platform);
  $("ref-anchor-chips").innerHTML = refChipRowHTML([
    { value: "", label: "全部" },
    { value: "topic", label: "赛题", count: stats.anchorKinds.topic },
    { value: "kit", label: "套件", count: stats.anchorKinds.kit },
    { value: "none", label: "未锚定", count: stats.anchorKinds.none },
  ], refUI.anchorKind);
}

function renderReferenceStats() {
  const ctx = refFilterContext();
  const filtered = refFilterEntries(refEntryCache || [], ctx);
  const stats = refStats(filtered, ctx);
  // 悬空计数红段（工单 04）：0 时不渲染红色形态；点击 = 只看悬空（再点取消）
  $("ref-stats").innerHTML = esc(refStatsText(stats)) + (stats.dangling
    ? ` <span class="ref-dangling-count" data-ref-dangling title="锚定值不命中任何库内赛题 / 套件，生成时不会自动关联；点击只看悬空条目，再点取消">悬空 ${stats.dangling}</span>`
    + ' <span class="lib-stats-hint">（点击可筛选）</span>'   // ux-polish-02/08 可见提示
    : "");
}

function renderReferences() {
  const list = refEntryCache || [];
  const f = refFilterContext();
  const rows = refSortEntries(refFilterEntries(list, f), { by: refUI.sortBy, dir: refUI.sortDir });
  if (!list.length) {
    $("ref-rows").innerHTML = '<tr><td colspan="7" class="empty-td"><div class="empty-state"><div class="es-icon">📚</div><div class="es-title">参考文件库暂无条目</div><div class="es-hint">用下方表单录入资料；生成时按锚定自动注入为学习素材。</div></div></td></tr>';
  } else if (!rows.length) {
    // 过滤后的空结果 ≠ 库为空：提示「清空过滤」而不是「录入条目」
    $("ref-rows").innerHTML = '<tr><td colspan="7" class="empty-td"><div class="empty-state"><div class="es-icon">🔍</div><div class="es-title">没有匹配的参考条目</div><div class="es-hint">换一个关键词，或点击「清空过滤」恢复全量。</div></div></td></tr>';
  } else {
    $("ref-rows").innerHTML = rows.map((e) => refRowHTML(e, f)).join("");
  }
  $("ref-rows").querySelectorAll("[data-ref-view]").forEach((b) =>
    b.addEventListener("click", () => viewReferenceDetail(b.dataset.refView)));
  $("ref-rows").querySelectorAll("[data-ref-edit]").forEach((b) =>
    b.addEventListener("click", () => editReference(b.dataset.refEdit)));
  $("ref-rows").querySelectorAll("[data-mf]").forEach((a) =>
    a.addEventListener("click", (e) => {
      e.preventDefault();
      openReferenceFile(a.dataset.mf, a.dataset.path);
    }));
  $("ref-rows").querySelectorAll("[data-ref-del]").forEach((b) =>
    b.addEventListener("click", () => deleteReference(b.dataset.refDel)));
  renderReferenceChips();
  renderReferenceStats();
}

function clearReferenceFilter() {
  refUI.q = ""; refUI.platform = ""; refUI.anchorKind = "";
  $("ref-filter").value = "";
  renderReferences();
}

export function initReferenceToolbar() {
  $("ref-filter").addEventListener("input", (e) => {
    clearTimeout(refSearchTimer);
    refSearchTimer = setTimeout(() => { refUI.q = e.target.value; renderReferences(); }, 150);
  });
  $("ref-filter").addEventListener("keydown", (e) => { if (e.key === "Escape") clearReferenceFilter(); });
  $("ref-sort").addEventListener("change", (e) => {
    refUI.sortBy = e.target.value;
    if (e.target.value === "mtime") {   // 最近更新默认降序（最新在前，ux-polish-02/08）
      refUI.sortDir = "desc";
      $("ref-sort-dir").textContent = "↓ 降序";
    }
    renderReferences();
  });
  $("ref-sort-dir").addEventListener("click", () => {
    refUI.sortDir = refUI.sortDir === "asc" ? "desc" : "asc";
    $("ref-sort-dir").textContent = refUI.sortDir === "asc" ? "↑ 升序" : "↓ 降序";
    renderReferences();
  });
  $("ref-filter-clear").addEventListener("click", clearReferenceFilter);
  // chips 事件委托（行内动态渲染）；再点已选中项 = 取消该维度过滤
  $("ref-platform-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-ref-chip]"); if (!b) return;
    refUI.platform = refUI.platform === b.dataset.refChip ? "" : b.dataset.refChip;
    renderReferences();
  });
  $("ref-anchor-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-ref-chip]"); if (!b) return;
    refUI.anchorKind = refUI.anchorKind === b.dataset.refChip ? "" : b.dataset.refChip;
    renderReferences();
  });
  // 统计条悬空红段（工单 04）：点击 = 只看悬空条目，再点取消（与过滤 / 排序正交）
  $("ref-stats").addEventListener("click", (e) => {
    if (!e.target.closest("[data-ref-dangling]")) return;
    refUI.dangling = !refUI.dangling;
    renderReferences();
  });
}

// 套件锚定的合法取值 = 模块库已有 kit 词表（从 /api/modules 各平台条目 kit
// 字段去重收集，不新打字——词表外值后端校验拒绝）
let kitVocabulary = [];

export async function loadKitVocabulary() {
  try {
    const modules = await apiGet("/api/modules");
    kitVocabulary = [...new Set(modules.flatMap((m) =>
      Object.values(m.platforms || {}).map((p) => p.kit).filter(Boolean)))].sort();
  } catch (e) { kitVocabulary = []; }   // 未配置 / 模块库读不到：保留空词表，入库时后端给错误
  $("ref-anchor-kit").innerHTML = kitVocabulary.length
    ? kitVocabulary.map((k) => `<option value="${esc(k)}">${esc(k)}</option>`).join("")
    : '<option value="">（模块库暂无 kit 词表）</option>';
  // 悬空判定（工单 04）依赖 kit 词表：词表到达后重渲染（行内 ⚠ / 统计红段收敛）
  if (refEntryCache && refEntryCache.length) {
    renderReferences();
  }
}

$("ref-anchor-kind").addEventListener("change", () => {
  const kind = $("ref-anchor-kind").value;
  $("ref-anchor-kit").classList.toggle("hidden", kind !== "kit");
  $("ref-anchor-topic").classList.toggle("hidden", kind !== "topic");
});

// 题型词表（工单 topic-framework/04）：选项单源 = GET /api/references/topic-types
// （与后端校验同源——前端不硬编码词表）；失败降级 = 空白选项（前端不阻断，
// 后端校验兜底 400 中文）
let refTopicTypes = [];
export async function loadTopicTypes() {
  try {
    const types = await apiGet("/api/references/topic-types");
    refTopicTypes = Array.isArray(types) ? types : [];
  } catch (e) { refTopicTypes = []; }
  $("ref-topic-type").innerHTML = '<option value="">（未标记）</option>'
    + refTopicTypes.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
}

// 最近一次浏览的条目缓存：删除确认框显示体量（避免删 1630 个文件还不知道多大）
let refEntryCache = [];
// 悬空锚定判定数据源（工单 04）：赛题库 key 清单（/api/topics）——降级 = 空数组
// （数据未就绪 / 拉取失败时 topic 方向不判定不误报，行内 ⚠ 与红段随之不渲染）
let refTopicKeys = [];

export async function loadReferences() {
  try {
    // 加载态占位（对偶模块库先例）：fetched 前给占位，读盘快也避免旧内容残留
    $("ref-msg").textContent = "";
    $("ref-rows").innerHTML = '<tr><td colspan="7" class="empty-td"><div class="empty-state"><div class="es-icon">⏳</div><div class="es-title">正在读取参考文件库…</div></div></td></tr>';
    // 全量在手 → 客户端即时过滤 / 排序 / 统计（工单 02 替换服务端四框筛选）
    const entries = await apiGet("/api/references");
    refEntryCache = entries;
    // 赛题库 key 清单（悬空判定）；失败降级 = 空数组（不阻塞条目渲染）
    try {
      const topics = await apiGet("/api/topics");
      refTopicKeys = Array.isArray(topics) ? topics.map((t) => t.key).filter(Boolean) : [];
    } catch { refTopicKeys = []; }
    renderReferences();
  } catch (e) {
    // 对偶模块库先例：失败清空占位（错误信息留 ref-msg，不留假加载态）
    $("ref-rows").innerHTML = "";
    $("ref-msg").textContent = e.message;
  }
}

export async function deleteReference(entryId) {
  const entry = refEntryCache.find((e) => e.id === entryId);
  const bulk = entry ? `（${entry.file_count} 个文件，${formatSize(entry.size_bytes)}）` : "";
  if (!await confirmModal({
    title: "删除参考文件条目？",
    message: `删除参考文件条目 ${entryId}${bulk} 的整个目录？`,
    danger: true,
    confirmText: "确认删除",
  })) return;
  try {
    await apiDelete(`/api/references/${encodeURIComponent(entryId)}`);
    loadReferences();
  } catch (e) { toast("error", e.message); }
}

// ===== 参考库编辑弹窗（工单 03）：改元数据 + 文件增删，一次 PUT 落盘 =====
// 骨架对偶模块库编辑弹窗（.lib-edit-*）；字段照录入表单；文件管理 = 勾选
// 删除清单（磁盘实况） + 新增文本行（addFileRow / pickFilesInto 共用）。
// 校验与后端同源（原生中文 400 原因保留弹窗）；成功 = 关窗 + 表格即时刷新。
export async function editReference(entryId) {
  const entry = (refEntryCache || []).find((e) => e.id === entryId);
  if (!entry) { toast("error", "未找到参考条目 " + entryId); return; }
  document.querySelectorAll(".lib-edit-overlay").forEach((o) => o.remove());
  const overlay = document.createElement("div");
  overlay.className = "lib-edit-overlay";
  const modal = document.createElement("div");
  modal.className = "lib-edit-modal";
  modal.style.maxWidth = "720px";
  modal.innerHTML = '<div class="lib-edit-head"><strong>编辑参考条目：<span class="ref-edit-id"></span></strong>'
    + '<button class="ref-files-close" title="关闭">×</button></div>'
    + '<div class="lib-edit-body">'
    + '<div class="row"><div style="flex:1"><label>标题</label><input class="ref-edit-title" type="text"></div>'
    + '<div style="flex:1"><label>类型</label><input class="ref-edit-type" type="text"></div>'
    + '<div style="flex:1"><label>题型（未标记 = 不注入决策框架）</label><select class="ref-edit-topic-type"><option value="">（未标记）</option></select></div></div>'
    + '<label>锚定（套件型号只能从模块库已有 kit 词表选，不能自由输入）</label>'
    + '<div class="row"><select class="ref-edit-kind" style="width:130px">'
    + '<option value="topic">赛题编号</option><option value="kit">套件型号</option>'
    + '<option value="none">未锚定</option></select>'
    + '<input class="ref-edit-topic" type="text" placeholder="如 2026C" style="flex:1;max-width:200px">'
    + '<select class="ref-edit-kit hidden" style="flex:1;max-width:280px"></select></div>'
    + '<label>平台属性（any = 不限平台；stm32 / mspm0 = 只注入对应平台工程）</label>'
    + '<div class="row"><label style="cursor:pointer"><input type="radio" name="ref-edit-platform" value="any"> any（不限平台）</label>'
    + '<label style="cursor:pointer"><input type="radio" name="ref-edit-platform" value="stm32"> stm32</label>'
    + '<label style="cursor:pointer"><input type="radio" name="ref-edit-platform" value="mspm0"> mspm0</label></div>'
    + '<label>简介</label><textarea class="ref-edit-desc" rows="3"></textarea>'
    + '<h3>素材文件 <span class="muted">（勾选 = 删除；支持增，不支持改内容——替换请先勾删保存，再回来添加）</span></h3>'
    + '<ul class="lib-mod-files ref-edit-files"></ul>'
    + '<div class="ref-edit-newfiles"></div>'
    + '<div class="row" style="margin-top:4px"><button class="ref-edit-addrow">+ 文件</button>'
    + '<button class="ref-edit-pick">选择文件…</button>'
    + '<button class="ref-edit-pickdir">选择文件夹…</button>'
    + '<input type="file" class="ref-edit-pick-input" multiple accept=".c,.h,.cpp,.hpp,.txt,.md,.py,.s,.asm,.inc,.json,.xml,.yml,.yaml,.ini,.cfg,.lua,.sh,.bat,.csv,.html,.js,.ts,.v,.sv,.f" style="display:none">'
    + '<input type="file" class="ref-edit-pickdir-input" webkitdirectory multiple style="display:none"></div>'
    + '<div class="lib-edit-msg"></div></div>'
    + '<div class="lib-edit-foot"><button class="ref-edit-cancel">取消</button>'
    + '<button class="primary ref-edit-save">保存</button></div>';
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  modal.querySelector(".ref-edit-id").textContent = entry.id;
  const titleEl = modal.querySelector(".ref-edit-title");
  const typeEl = modal.querySelector(".ref-edit-type");
  const kindEl = modal.querySelector(".ref-edit-kind");
  const topicEl = modal.querySelector(".ref-edit-topic");
  const kitEl = modal.querySelector(".ref-edit-kit");
  const descEl = modal.querySelector(".ref-edit-desc");
  const filesUl = modal.querySelector(".ref-edit-files");
  const newfilesBox = modal.querySelector(".ref-edit-newfiles");
  const msgEl = modal.querySelector(".lib-edit-msg");
  const saveBtn = modal.querySelector(".ref-edit-save");
  // 保存三态（refEditState 状态机驱动按钮渲染：saving → 禁用 + 「保存中…」）
  let saveState = "idle";
  const renderSaveBtn = () => {
    const saving = saveState === "saving";
    saveBtn.disabled = saving;
    saveBtn.textContent = saving ? "保存中…" : "保存";
  };
  const close = () => overlay.remove();
  const setMsg = (text, ok) => {
    msgEl.textContent = text || "";
    msgEl.classList.toggle("ok", !!ok);
  };
  // 预填元数据（id / 目录名不变；锚定/平台按当前值落位）
  titleEl.value = entry.title || "";
  typeEl.value = entry.type || "";
  descEl.value = entry.description || "";
  const topicTypeEl = modal.querySelector(".ref-edit-topic-type");
  topicTypeEl.innerHTML = '<option value="">（未标记）</option>'
    + refTopicTypes.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("")
    + (entry.topic_type && !refTopicTypes.includes(entry.topic_type)
      ? `<option value="${esc(entry.topic_type)}">${esc(entry.topic_type)}（词表外，保存时后端拒绝）</option>` : "");
  topicTypeEl.value = entry.topic_type || "";
  kindEl.value = ["topic", "kit", "none"].includes(entry.anchor_kind) ? entry.anchor_kind : "none";
  topicEl.value = kindEl.value === "topic" ? (entry.anchor_value || "") : "";
  const kits = kitVocabulary.includes(entry.anchor_value)
    ? kitVocabulary
    : (entry.anchor_value ? [entry.anchor_value, ...kitVocabulary] : kitVocabulary);
  kitEl.innerHTML = kits.length
    ? kits.map((k) => `<option value="${esc(k)}">${esc(k)}</option>`).join("")
    : '<option value="">（模块库暂无 kit 词表）</option>';
  kitEl.value = entry.anchor_value || "";
  (modal.querySelector(`input[name="ref-edit-platform"][value="${esc(entry.platform || "any")}"]`)
    || modal.querySelector('input[name="ref-edit-platform"][value="any"]')).checked = true;
  const syncKind = () => {
    const kind = kindEl.value;
    kitEl.classList.toggle("hidden", kind !== "kit");
    topicEl.classList.toggle("hidden", kind !== "topic");
  };
  syncKind();
  kindEl.addEventListener("change", syncKind);
  // 文件清单（磁盘实况端点：逐路径 + 大小）；读取失败降级 = 只改元数据
  let files = [];
  try {
    files = await apiGet(`/api/references/${encodeURIComponent(entryId)}/files`);
  } catch (e) { setMsg("文件清单读取失败：" + e.message + "（仍可保存元数据）"); }
  const renderFiles = () => {
    filesUl.innerHTML = files.length
      ? files.map((f) => `<li><label style="cursor:pointer;display:flex;gap:10px;align-items:baseline">`
          + `<input type="checkbox" data-edit-rm="${esc(f.path)}" style="flex:none">`
          + `<span class="fname">${esc(f.path)}</span>`
          + `<span class="muted">${formatSize(f.size_bytes)}</span></label></li>`).join("")
      : '<li class="muted">无文件（素材清单缺失）。</li>';
  };
  renderFiles();
  const doSave = async () => {
    const kind = kindEl.value;
    const fields = {
      title: titleEl.value,
      type: typeEl.value,
      description: descEl.value,
      anchor_kind: kind,
      anchor_value: kind === "topic" ? topicEl.value : kind === "kit" ? kitEl.value : "",
      platform: (modal.querySelector('input[name="ref-edit-platform"]:checked') || {}).value || "any",
      topic_type: modal.querySelector(".ref-edit-topic-type").value,
    };
    const v = refEditValidate(fields);
    if (!v.ok) { setMsg(v.message); return; }
    const added = collectFiles(newfilesBox);
    if (added === null) return;   // collectFiles 已 alert 重名
    const removed = Array.from(modal.querySelectorAll("[data-edit-rm]:checked"))
      .map((c) => c.dataset.editRm);
    const plan = refEditFilePlan(files.map((f) => f.path), removed, added);
    if (!plan.ok) { setMsg(plan.message); return; }
    const payload = refEditPayload(fields, plan);
    // 保存三态由 refEditState 状态机驱动（idle→saving→ok/rejected；reset 回收）
    saveState = refEditState(saveState, "save");
    renderSaveBtn();
    try {
      await apiPut(`/api/references/${encodeURIComponent(entryId)}`, payload);
      saveState = refEditState(saveState, "saved");
      if (!overlay.isConnected) return;
      close();
      loadReferences();   // 行 / 统计即时刷新（体量、锚定、平台可见变化）
    } catch (e) {
      saveState = refEditState(saveState, "error");
      if (!overlay.isConnected) return;
      setMsg(e.message);   // 后端 400 中文原因（校验同源）
    } finally {
      saveState = refEditState(saveState, "reset");
      renderSaveBtn();
    }
  };
  saveBtn.addEventListener("click", doSave);
  modal.querySelector(".ref-edit-cancel").addEventListener("click", close);
  modal.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  modal.querySelector(".ref-edit-addrow").addEventListener("click", () => addFileRow(newfilesBox));
  modal.querySelector(".ref-edit-pick").addEventListener("click", () => modal.querySelector(".ref-edit-pick-input").click());
  modal.querySelector(".ref-edit-pickdir").addEventListener("click", () => modal.querySelector(".ref-edit-pickdir-input").click());
  modal.querySelector(".ref-edit-pick-input").addEventListener("change", (e) => pickFilesInto(e.target, newfilesBox, msgEl));
  modal.querySelector(".ref-edit-pickdir-input").addEventListener("change", (e) => pickFilesInto(e.target, newfilesBox, msgEl));
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  titleEl.focus();
}

// 参考文件查看（文件名搜索 + 文件打开工单）：清单弹层 + 按扩展名分流
// （.pdf 新窗口预览 / 文本 fetch 内联 / 其余触发下载）。路径按段编码
// （含中文和斜杠，服务端 :path 转换器接收）。
const REF_TEXT_EXTENSIONS = ["txt", "md", "c", "h", "cpp", "hpp", "ino", "py", "json", "cfg", "ini"];

export function referenceFileUrl(entryId, path) {
  const segments = path.split("/").map(encodeURIComponent).join("/");
  return `/api/references/${encodeURIComponent(entryId)}/files/${segments}`;
}

// 打开参考文件（行内直开 / 弹层共用）：PDF 新窗口预览 / 文本 fetch 内联 /
// 其余新窗口下载。viewer 缺省 = 行内直开（文本也新窗口，服务端给 Content-Type）。
export async function openReferenceFile(entryId, path, viewer, viewerPre) {
  const url = referenceFileUrl(entryId, path);
  const lower = path.toLowerCase();
  if (lower.endsWith(".pdf")) { window.open(url, "_blank"); return; } // PDF 浏览器预览
  if (viewer && REF_TEXT_EXTENSIONS.some((ext) => lower.endsWith("." + ext))) {
    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(await resp.text().catch(() => "HTTP " + resp.status));
      viewerPre.textContent = `${path}\n\n${await resp.text()}`;
      viewer.classList.remove("hidden");
    } catch (err) { toast("error", err.message); }
    return;
  }
  window.open(url, "_blank"); // 其余类型：服务端按扩展名给 Content-Type，浏览器转下载
}

// 参考文件详情（工单 02）：元数据（缓存全量在手）+ 文件清单（磁盘实况端点）
// 合并一窗；文件打开行为沿用（.pdf 预览 / 文本内联 / 其余下载）。
export function viewReferenceDetail(entryId) {
  const entry = (refEntryCache || []).find((e) => e.id === entryId);
  if (!entry) { toast("info", "未找到条目 " + entryId); return; }
  apiGet(`/api/references/${encodeURIComponent(entryId)}/files`).then((files) => {
    showReferenceDetail(entry, files);
  }).catch((e) => toast("error", e.message));
}

function showReferenceDetail(entry, files) {
  const overlay = document.createElement("div");
  overlay.className = "ref-files-overlay";
  overlay.innerHTML = `
    <div class="ref-files-modal">
      <div class="ref-files-head">
        <strong>参考条目详情</strong>
        <button class="ref-files-close" title="关闭">×</button>
      </div>
      <div class="ref-detail-scroll">${refDetailHTML(entry, files)}</div>
      <div class="ref-files-viewer hidden"><pre></pre></div>
    </div>`;
  const close = () => overlay.remove();
  overlay.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const viewer = overlay.querySelector(".ref-files-viewer");
  const viewerPre = viewer.querySelector("pre");
  const filterInput = overlay.querySelector(".ref-files-filter");
  const list = overlay.querySelector(".ref-files-list");
  const applyFilter = () => {
    const needle = filterInput.value.trim().toLowerCase();
    list.querySelectorAll("li[data-path]").forEach((li) => {
      li.style.display = !needle || li.dataset.path.toLowerCase().includes(needle) ? "" : "none";
    });
  };
  filterInput.addEventListener("input", applyFilter);
  overlay.querySelectorAll(".ref-files-list a").forEach((a) =>
    a.addEventListener("click", async (e) => {
      e.preventDefault();
      await openReferenceFile(entry.id, a.dataset.path, viewer, viewerPre);
    }));
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  document.body.appendChild(overlay);
}

$("btn-ref-add-file-row").addEventListener("click", () => addFileRow($("ref-files")));
addFileRow($("ref-files"));

function refCollectFiles() { return collectFiles($("ref-files")); }

$("btn-ref-draft-desc").addEventListener("click", async () => {
  // 草稿反馈留在 ② 素材与锚定区（对应按钮就近可见；入库反馈仍走 ③ 的 ref-add-msg）
  $("ref-draft-msg").textContent = "";
  const files = refCollectFiles();
  if (files === null) return;
  if (!Object.keys(files).length) { $("ref-draft-msg").textContent = "至少需要一个素材文件"; return; }
  $("btn-ref-draft-desc").disabled = true;
  $("btn-ref-draft-desc").innerHTML = '<span class="spinner"></span>生成中…';
  try {
    const data = await apiPost("/api/references/draft", { files });
    $("ref-desc").value = data.draft;
    $("ref-draft-msg").classList.add("ok");
    $("ref-draft-msg").textContent = "AI 简介草稿已填入，可修改后点击「入库」。（请求体有大小预算，素材过大后端会报 413）";
  } catch (e) {
    $("ref-draft-msg").classList.remove("ok");
    $("ref-draft-msg").textContent = e.message;
  } finally {
    $("btn-ref-draft-desc").disabled = false;
    $("btn-ref-draft-desc").innerHTML = "AI 生成简介草稿";
  }
});

$("btn-ref-add").addEventListener("click", async () => {
  $("ref-add-msg").textContent = "";
  const files = refCollectFiles();
  if (files === null) return;
  if (!Object.keys(files).length) { $("ref-add-msg").textContent = "至少需要一个素材文件"; return; }
  const title = $("ref-title").value.trim();
  const type = $("ref-type").value.trim();
  const description = $("ref-desc").value.trim();
  if (!title) { $("ref-add-msg").textContent = "请填写标题"; return; }
  if (!type) { $("ref-add-msg").textContent = "请填写类型"; return; }
  if (!description) { $("ref-add-msg").textContent = "请填写简介（或先让 AI 生成草稿）"; return; }
  const anchorKind = $("ref-anchor-kind").value;
  const anchorValue = anchorKind === "kit"
    ? $("ref-anchor-kit").value
    : anchorKind === "none" ? "" : $("ref-anchor-topic").value.trim();
  const platform = document.querySelector('input[name="ref-platform"]:checked').value;
  const topicType = $("ref-topic-type").value;
  $("btn-ref-add").disabled = true;
  $("btn-ref-add").innerHTML = '<span class="spinner"></span>入库中…';
  try {
    const entry = await apiPost("/api/references", {
      title, type, description, anchor_kind: anchorKind, anchor_value: anchorValue, platform, topic_type: topicType, files,
    });
    $("ref-add-msg").classList.add("ok");
    $("ref-add-msg").textContent = "已入库：" + entry.title;
    ["ref-title", "ref-type", "ref-desc", "ref-anchor-topic"].forEach((id) => ($(id).value = ""));
    $("ref-topic-type").value = "";
    $("ref-files").innerHTML = "";
    addFileRow($("ref-files"));
    loadReferences();
  } catch (e) {
    $("ref-add-msg").classList.remove("ok");
    $("ref-add-msg").textContent = e.message;
  } finally {
    $("btn-ref-add").disabled = false;
    $("btn-ref-add").innerHTML = "入库";
  }
});

// 本条目的两个文件选择绑定（与模块库簇同件）：按钮 → 隐藏 input → change 走
// pickFilesInto（readPickedText + MAX_PICK_BYTES 守卫在 files.js 内）。
bindFilePicker("btn-ref-pick-files", "ref-pick-files", "ref-files", "ref-draft-msg");
bindFilePicker("btn-ref-pick-dir", "ref-pick-dir", "ref-files", "ref-draft-msg");
