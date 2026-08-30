// ui/library.js — 模块库 tab DOM 胶水（阶段 2 工单 07）
//
// 模块库 tab 全部胶水：过滤/排序/统计 chips 渲染、表格行（详情/改简介/编辑/
// 删除事件转发）、加载（state.modules 属性写 + renderModulePool 联动）、简介
// 编辑弹窗、平台级编辑弹窗（硬件身份 / 文件增删）、新建模块载荷与两个入库按钮。
// 纯件在 fx/module.js（libStats / libStatsText / libChipRowHTML / libSortModules /
// libFilterModules / moduleRowHTML / danglingDependencies / editDescStatus /
// libIsValidHttpUrl / libPlatformKits——工单 06 迁）；文件行件在 ui/files.js
// （addFileRow / collectFiles / pickFilesInto——跨簇共用件，工单 06 迁）。
// 跨簇硬边按「工单序调整」（spec.md）从 ui/generate-recommend.js import：
// openModuleInfo（表格详情弹窗）/ renderModulePool（模块池网格——模块库刷新后
// 全量重算）。记录服务（recordLLMUsage）无本簇引用。
// 状态：libUI（过滤/排序条件，模块内）；state.modules 属性写（loadLibrary /
// editDescription / editModule 成功路径——ESM 活绑定合法，12 先例注释一致）。
// host 页签分发器 / 启动区经顶部 import 调 loadLibrary / initLibraryToolbar /
// initAddSections；editModule / deleteModule / newModulePayload 亦导出（后续
// 收尾工单核对使用面）。顶层监听（btn-add-file-row / 模块库两个 bindFilePicker /
// btn-draft-desc / btn-add-module-submit）在 import 时绑定（module 延迟执行，
// DOM 已就绪）。
import { $, apiGet, apiPost, apiPut, apiDelete, toast, toastError, state } from "/js/app.js";
import { confirmModal } from "/js/ui/confirm.js";
import { esc } from "/js/fx/core.js";
import { libStats, libStatsText, libChipRowHTML, libSortModules, libFilterModules, moduleRowHTML, danglingDependencies, editDescStatus, libIsValidHttpUrl, libPlatformKits } from "/js/fx/module.js";
import { addFileRow, collectFiles, pickFilesInto, bindFilePicker } from "/js/ui/files.js";
import { openModuleInfo, renderModulePool } from "/js/ui/generate-recommend.js";

// —— 模块库工具栏状态与渲染（library-toolbar/02）：过滤条件集中于此，
// 事件层只改状态再调 renderLibraryTable()（纯函数转发）
const libUI = { q: "", platform: "", status: "", sortBy: "slug", sortDir: "asc" };

function renderLibraryChips() {
  const stats = libStats(state.modules || []);
  const platOpts = [{ value: "", label: "全部" }];
  for (const name of Object.keys(stats.platforms)) {
    platOpts.push({ value: name, label: String(name).toUpperCase(), count: stats.platforms[name] });
  }
  $("lib-platform-chips").innerHTML = libChipRowHTML(platOpts, libUI.platform);
  $("lib-status-chips").innerHTML = libChipRowHTML([
    { value: "", label: "全部" },
    { value: "verified", label: "已验证", count: stats.verified },
    { value: "unverified", label: "未验证", count: stats.unverified },
    { value: "hardware_bound", label: "硬件绑定", count: stats.hardware_bound },
  ], libUI.status);
}

function renderLibraryStats() {
  const stats = libStats(state.modules || []);
  $("lib-stats").innerHTML = esc(libStatsText(stats))
    + (stats.dangling ? ' <span class="lib-dangling-count" title="依赖未入库的模块，点击详情确认">悬空依赖 ' + stats.dangling + "</span>" : "")
    // 可点击筛选的可见提示（ux-polish-02/08）：问题计数能点，不再靠 title 猜
    + (stats.dangling ? ' <span class="lib-stats-hint">（点击可筛选）</span>' : "");
}

function renderLibraryTable() {
  const modules = state.modules || [];
  // 排序读 {by, dir}（纯函数约定），libUI 存 sortBy/sortDir——调用点映射，勿直传 libUI
  const rows = libSortModules(libFilterModules(modules, libUI), { by: libUI.sortBy, dir: libUI.sortDir });
  // 悬空依赖映射（工单 04）：行内警示标 + 统计条计数同源
  const dmap = danglingDependencies(modules);
  if (!modules.length) {
    $("lib-rows").innerHTML = '<tr><td colspan="5" class="empty-td"><div class="empty-state"><div class="es-icon">📦</div><div class="es-title">模块库还是空的</div><div class="es-hint">用上方表单添加第一个模块（slug + 平台 + 源文件），AI 校验后入库。</div></div></td></tr>';
  } else if (!rows.length) {
    // 过滤后的空结果 ≠ 库为空：提示「清空过滤」而不是「添加模块」
    $("lib-rows").innerHTML = '<tr><td colspan="5" class="empty-td"><div class="empty-state"><div class="es-icon">🔍</div><div class="es-title">没有匹配的模块</div><div class="es-hint">换一个关键词，或点击「清空过滤」恢复全量。</div></div></td></tr>';
  } else {
    $("lib-rows").innerHTML = rows.map((m) => moduleRowHTML(m, dmap)).join("");
  }
  $("lib-rows").querySelectorAll("[data-edit-desc]").forEach((b) =>
    b.addEventListener("click", () => editDescription(b.dataset.editDesc)));
  $("lib-rows").querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", () => deleteModule(b.dataset.del)));
  // 详情（工单 03）：不带平台上下文 → moduleInfoHTML 展示全部平台分段
  $("lib-rows").querySelectorAll("[data-info]").forEach((b) =>
    b.addEventListener("click", () => openModuleInfo(b.dataset.info, null)));
  // 编辑（工单 06）：平台级编辑弹窗
  $("lib-rows").querySelectorAll("[data-edit-mod]").forEach((b) =>
    b.addEventListener("click", () => editModule(b.dataset.editMod)));
  renderLibraryChips();
  renderLibraryStats();
}

function clearLibraryFilter() {
  libUI.q = ""; libUI.platform = ""; libUI.status = "";
  $("lib-search").value = "";
  renderLibraryTable();
}

// 添加模块分区折叠（library-add-collapse/07）：纯布局交互——分区头点击切换
// collapsed（内容 display:none，DOM 不销毁 → 收起不丢已填内容/文件行）。
export function initAddSections() {
  document.querySelectorAll(".add-section").forEach((sec) => {
    const head = sec.querySelector(".add-section-head");
    if (!head) return;
    head.addEventListener("click", () => {
      const collapsed = sec.classList.toggle("collapsed");
      head.setAttribute("aria-expanded", String(!collapsed));
    });
  });
}

export function initLibraryToolbar() {
  $("lib-search").addEventListener("input", (e) => { libUI.q = e.target.value; renderLibraryTable(); });
  $("lib-search").addEventListener("keydown", (e) => { if (e.key === "Escape") clearLibraryFilter(); });
  $("lib-sort").addEventListener("change", (e) => {
    libUI.sortBy = e.target.value;
    if (e.target.value === "mtime") {   // 最近更新默认降序（最新在前，ux-polish-02/08）
      libUI.sortDir = "desc";
      $("lib-sort-dir").textContent = "↓ 降序";
    }
    renderLibraryTable();
  });
  $("lib-sort-dir").addEventListener("click", () => {
    libUI.sortDir = libUI.sortDir === "asc" ? "desc" : "asc";
    $("lib-sort-dir").textContent = libUI.sortDir === "asc" ? "↑ 升序" : "↓ 降序";
    renderLibraryTable();
  });
  $("lib-filter-clear").addEventListener("click", clearLibraryFilter);
  // chips 事件委托（行内动态渲染）；再点已选中项 = 取消该维度过滤
  $("lib-platform-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-lib-chip]"); if (!b) return;
    libUI.platform = libUI.platform === b.dataset.libChip ? "" : b.dataset.libChip;
    renderLibraryTable();
  });
  $("lib-status-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-lib-chip]"); if (!b) return;
    libUI.status = libUI.status === b.dataset.libChip ? "" : b.dataset.libChip;
    renderLibraryTable();
  });
}

export async function loadLibrary() {
  // 加载态（工单 01）：fetched 前给占位，读盘快也避免旧内容残留
  $("lib-msg").textContent = "";
  $("lib-rows").innerHTML = '<tr><td colspan="5" class="empty-td"><div class="empty-state"><div class="es-icon">⏳</div><div class="es-title">正在读取模块库…</div></div></td></tr>';
  try {
    const modules = await apiGet("/api/modules");
    state.modules = modules;
    renderModulePool();
    // 工单 02：过滤 / 排序 / 统计走统一渲染入口（刷新后保持过滤条件不丢）
    renderLibraryTable();
  } catch (e) {
    $("lib-rows").innerHTML = "";
    $("lib-msg").textContent = e.message;
  }
}

async function editDescription(slug) {
  const module = (state.modules || []).find((mo) => mo.slug === slug);
  if (!module) { toast("info", "未找到模块 " + slug); return; }
  // 替换式打开（同 openModuleInfo 先例）；全字段 textContent 填充免转义
  document.querySelectorAll(".lib-edit-overlay").forEach((o) => o.remove());
  const overlay = document.createElement("div");
  overlay.className = "lib-edit-overlay";
  const modal = document.createElement("div");
  modal.className = "lib-edit-modal";
  modal.innerHTML = '<div class="lib-edit-head"><strong>修改简介：<span class="lib-edit-slug"></span></strong>'
    + '<button class="ref-files-close" title="关闭">×</button></div>'
    + '<div class="lib-edit-body">'
    + '<label>原简介（只读对照）</label><div class="lib-edit-old"></div>'
    + '<label>新简介（AI 校验与代码一致后写入）</label><textarea class="lib-edit-text"></textarea>'
    + '<div class="lib-edit-msg"></div></div>'
    + '<div class="lib-edit-foot"><button class="lib-edit-cancel">取消</button>'
    + '<button class="primary lib-edit-save">保存</button></div>';
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  modal.querySelector(".lib-edit-slug").textContent = module.slug;
  modal.querySelector(".lib-edit-old").textContent = String(module.description || "");
  const textEl = modal.querySelector(".lib-edit-text");
  textEl.value = String(module.description || "");
  const msgEl = modal.querySelector(".lib-edit-msg");
  const saveBtn = modal.querySelector(".lib-edit-save");
  let status = "idle";
  const close = () => overlay.remove();
  const doSave = async () => {
    status = editDescStatus(status, "save");
    saveBtn.disabled = true;
    saveBtn.textContent = "保存中…";
    msgEl.textContent = "";
    try {
      const data = await apiPut(`/api/modules/${encodeURIComponent(module.slug)}/description`,
        { description: textEl.value.trim() });
      status = editDescStatus(status, "saved");
      // 端点返回新 manifest：本地替换 + 全量重算（零额外请求）。数据始终更新；
      // saving 中被取消/关闭则跳过 DOM 渲染（对已移除节点是安全 no-op）
      state.modules = (state.modules || []).map((m) => (m.slug === module.slug ? data : m));
      if (!overlay.isConnected) return;
      renderModulePool();
      renderLibraryTable();
      close();
    } catch (e) {
      status = editDescStatus(status, "error");
      if (!overlay.isConnected) return;
      saveBtn.disabled = false;
      saveBtn.textContent = "保存";
      msgEl.textContent = e.message;
    }
  };
  saveBtn.addEventListener("click", doSave);
  modal.querySelector(".lib-edit-cancel").addEventListener("click", close);
  modal.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  textEl.focus();
}

// —— 编辑弹窗（library-edit-dialog/06）：平台级编辑——硬件身份（kit/链接）+ 文件增删。
// 复用 05 模态骨架（.lib-edit-*）、文件行（addFileRow/collectFiles/pickFilesInto）。
export function editModule(slug) {
  const module = (state.modules || []).find((mo) => mo.slug === slug);
  if (!module) { toast("info", "未找到模块 " + slug); return; }
  document.querySelectorAll(".lib-edit-overlay").forEach((o) => o.remove());
  const overlay = document.createElement("div");
  overlay.className = "lib-edit-overlay";
  const modal = document.createElement("div");
  modal.className = "lib-edit-modal";
  modal.style.maxWidth = "640px";
  modal.innerHTML = '<div class="lib-edit-head"><strong>编辑模块：<span class="lib-edit-slug"></span></strong>'
    + '<button class="ref-files-close" title="关闭">×</button></div>'
    + '<div class="lib-edit-body">'
    + '<label>平台版本</label><select class="lib-mod-platform"></select>'
    + '<div class="lib-mod-status"></div>'
    + '<label>套件型号（词表提示）</label><input class="lib-mod-kit" list="lib-mod-kit-list" placeholder="例如 LaunchPad / 最小系统板">'
    + '<datalist id="lib-mod-kit-list"></datalist>'
    + '<label>购买链接（留空 = 保留原值）</label><input class="lib-mod-url" placeholder="https://…">'
    + '<h3>平台文件</h3><ul class="lib-mod-files"></ul>'
    + '<div class="lib-mod-newfiles"></div>'
    + '<div class="row" style="margin-top:4px"><button class="lib-mod-addrow">+ 文件</button>'
    + '<button class="lib-mod-pick">选择文件…</button>'
    + '<input type="file" class="lib-mod-pick-input" multiple accept=".c,.h,.cpp,.hpp,.txt,.md,.py,.inc,.s,.asm" style="display:none"></div>'
    + '<div class="lib-mod-msg"></div></div>'
    + '<div class="lib-edit-foot"><button class="lib-mod-cancel">取消</button>'
    + '<span class="lib-mod-pending muted hidden"></span>'
    + '<button class="primary lib-mod-save">保存</button></div>';
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  modal.querySelector(".lib-edit-slug").textContent = module.slug;
  const platSel = modal.querySelector(".lib-mod-platform");
  const statusEl = modal.querySelector(".lib-mod-status");
  const kitEl = modal.querySelector(".lib-mod-kit");
  const urlEl = modal.querySelector(".lib-mod-url");
  const filesUl = modal.querySelector(".lib-mod-files");
  const newfilesBox = modal.querySelector(".lib-mod-newfiles");
  const msgEl = modal.querySelector(".lib-mod-msg");
  const saveBtn = modal.querySelector(".lib-mod-save");
  const pendingBadge = modal.querySelector(".lib-mod-pending");
  const kitList = modal.querySelector("#lib-mod-kit-list");
  const close = () => overlay.remove();
  const setMsg = (text, ok) => {
    msgEl.textContent = text || "";
    msgEl.classList.toggle("ok", !!ok);
  };
  // 平台下拉（首见序）
  const platNames = Object.keys(module.platforms || {});
  platSel.innerHTML = platNames.map((p) =>
    `<option value="${esc(p)}">${esc(String(p).toUpperCase())}</option>`).join("");
  let curPlatform = platNames[0] || "";
  const curEntry = () => (module.platforms || {})[curPlatform] || {};
  // 删除后平台集合可能变化（最后一个文件删除 → 该平台条目移除）：重建下拉并落位
  const rebuildPlatSelect = () => {
    const names = Object.keys(module.platforms || {});
    platSel.innerHTML = names.map((p) =>
      `<option value="${esc(p)}">${esc(String(p).toUpperCase())}</option>`).join("");
    if (!names.includes(curPlatform)) curPlatform = names[0] || "";
    platSel.value = curPlatform;
    renderPlat();
  };
  // 词表：库内全部 kit 去重
  kitList.innerHTML = libPlatformKits(state.modules || []).map((k) =>
    `<option value="${esc(k)}"></option>`).join("");
  const renderPlat = () => {
    if (!curPlatform) {
      statusEl.textContent = "该模块暂无平台版本（先到「添加模块」录入源文件）";
      kitEl.value = ""; urlEl.value = "";
      filesUl.innerHTML = "";
      return;
    }
    const entry = curEntry();
    statusEl.textContent = "验证状态：" + (entry.verified ? "已验证" : "未验证")
      + " · 硬件绑定：" + (entry.hardware_bound ? "是" : "否")
      + "（只读；信息走「详情」，简介走「改简介」）";
    kitEl.value = entry.kit || "";
    urlEl.value = entry.source_url || "";
    if (entry.files && entry.files.length) {
      filesUl.innerHTML = entry.files.map((f) =>
        `<li><span class="fname">${esc(f)}</span><button class="danger file-del" title="从该平台移除文件">✕</button></li>`).join("");
    } else {
      filesUl.innerHTML = '<li class="muted">实现内嵌母版（随母版进工程，不复制文件、不重复）</li>';
    }
  };
  platSel.addEventListener("change", () => { curPlatform = platSel.value; renderPlat(); });
  const refresh = (data) => {
    // 端点返回新 manifest：本地替换 + 全量重算（同 05 成功路径）
    state.modules = (state.modules || []).map((m) => (m.slug === module.slug ? data : m));
    Object.assign(module, data);
    renderLibraryTable();
  };
  const doSave = async () => {
    // 单「保存」按钮（工单 ux-walkthrough-02/09）：顺序提交身份 → 推送新文件，
    // 失败提示是哪一步；保存中禁用防连点；全部成功后一次反馈。
    const resetSaveBtn = () => {
      saveBtn.disabled = false; saveBtn.textContent = "保存";
      platSel.disabled = false;   // 保存中禁平台下拉：防止切换后渲染误导（评审整改）
    };
    if (!curPlatform) { setMsg("该模块暂无平台版本（先到「添加模块」录入源文件）"); return; }
    saveBtn.disabled = true; saveBtn.textContent = "保存中…";
    platSel.disabled = true;
    const kit = kitEl.value.trim();
    const url = urlEl.value.trim();
    if (url && !libIsValidHttpUrl(url)) {
      setMsg("购买链接格式不正确（须 http/https 开头）");
      resetSaveBtn();
      return;
    }
    // ① 身份（kit / 链接）
    try {
      const data = await apiPut(`/api/modules/${encodeURIComponent(module.slug)}/platform-identity`, {
        platform: curPlatform,
        kit: kit || undefined,      // 空 = 未提供 = 后端保留原值
        source_url: url || undefined,
      });
      refresh(data);   // 数据始终更新（后端已写库）
      if (!overlay.isConnected) return;
      renderPlat();
    } catch (e) {
      if (!overlay.isConnected) return;
      setMsg("身份保存失败：" + (e.message || String(e)));
      resetSaveBtn();
      return;
    }
    // ② 推送新文件（无待推送 = 跳过）
    const files = collectFiles(newfilesBox);
    if (files === null) { resetSaveBtn(); return; }
    const names = Object.keys(files);
    if (names.length) {
      try {
        const data = await apiPost(`/api/modules/${encodeURIComponent(module.slug)}/platform-files`, {
          platform: curPlatform,
          files,
          hardware_bound: !!curEntry().hardware_bound,
          kit: curEntry().kit || undefined,
          source_url: curEntry().source_url || undefined,
        });
        refresh(data);
        if (!overlay.isConnected) return;
        newfilesBox.innerHTML = "";
        renderPlat();
      } catch (e) {
        if (!overlay.isConnected) return;
        setMsg("文件推送失败：" + (e.message || String(e)));
        resetSaveBtn();
        return;
      }
    }
    setMsg(names.length ? "已保存（含 " + names.length + " 个新文件推送）" : "已保存");
    updatePendingBadge();
    resetSaveBtn();
  };
  // 未推送文件计数角标（工单 ux-walkthrough-02/09）：按「有文件名的行」计数
  // （近似值——同名行会由保存时的 collectFiles 拦截并提示；推送成功后角标消失）
  const pendingFileCount = () => {
    let n = 0;
    for (const row of newfilesBox.children) {
      const name = row.querySelector("input").value.trim();
      if (name) n++;
    }
    return n;
  };
  const updatePendingBadge = () => {
    const n = pendingFileCount();
    pendingBadge.textContent = n ? n + " 个文件未推送" : "";
    pendingBadge.classList.toggle("hidden", !n);
  };
  newfilesBox.addEventListener("input", updatePendingBadge);
  new MutationObserver(updatePendingBadge).observe(newfilesBox, { childList: true });
  updatePendingBadge();
  const doRemoveFile = async (fname) => {
    if (!await confirmModal({
      title: "移除平台文件？",
      message: "从平台 " + curPlatform + " 移除文件 " + fname + "？（共享文件只移出条目，磁盘保留）",
      danger: true,
      confirmText: "确认移除",
    })) return;
    try {
      const data = await apiDelete(`/api/modules/${encodeURIComponent(module.slug)}/platform-files`, {
        platform: curPlatform, filenames: [fname],
      });
      refresh(data);
      if (!overlay.isConnected) return;
      // 最后一个文件删除 → 后端移除该平台条目：重建下拉并落位到剩余平台
      rebuildPlatSelect();
      setMsg("已移除 " + fname);
    } catch (e) {
      if (!overlay.isConnected) return;
      setMsg(e.message);
    }
  };
  saveBtn.addEventListener("click", doSave);
  modal.querySelector(".lib-mod-cancel").addEventListener("click", close);
  modal.querySelector(".ref-files-close").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
  filesUl.addEventListener("click", (e) => {
    const b = e.target.closest(".file-del");
    if (b) doRemoveFile(b.closest("li").querySelector(".fname").textContent);
  });
  modal.querySelector(".lib-mod-addrow").addEventListener("click", () => addFileRow(newfilesBox));
  modal.querySelector(".lib-mod-pick").addEventListener("click", () => modal.querySelector(".lib-mod-pick-input").click());
  modal.querySelector(".lib-mod-pick-input").addEventListener("change", (e) =>
    pickFilesInto(e.target, newfilesBox, msgEl));
  const onKey = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  overlay.addEventListener("remove", () => document.removeEventListener("keydown", onKey));
  renderPlat();
  platSel.focus();
}

export async function deleteModule(slug) {
  if (!await confirmModal({
    title: "删除模块？",
    message: "删除模块 " + slug + " 的整个目录？",
    danger: true,
    confirmText: "确认删除",
  })) return;
  try {
    await apiDelete(`/api/modules/${encodeURIComponent(slug)}`);
    loadLibrary();
  } catch (e) { toastError(e); }
}

// 动态文件行（模块库 / 参考文件库共用）已迁至 static/js/ui/files.js（阶段 2 工单 06）；
// 添加模块表单的初始行与 + 文件 按钮（本簇）在此绑定；参考库簇的绑定留 host（工单 08 迁）。
$("btn-add-file-row").addEventListener("click", () => addFileRow());
addFileRow();

// ===== 选择文件 / 文件夹 → 读为文本填入文件行（模块库 / 参考库共用）=====
// 已迁至 static/js/ui/files.js（阶段 2 工单 06）：collectFiles / readPickedText /
// pickFilesInto / bindFilePicker / MAX_PICK_BYTES。
bindFilePicker("btn-pick-mod-files", "pick-mod-files", "new-files", "add-msg");
bindFilePicker("btn-pick-mod-dir", "pick-mod-dir", "new-files", "add-msg");

export function newModulePayload() {
  const files = collectFiles();
  if (files === null) return null;
  if (!Object.keys(files).length) { toast("error", "至少需要一个源文件"); return null; }
  return {
    slug: $("new-slug").value.trim(),
    platform: $("new-platform").value,
    description: $("new-desc").value.trim(),
    dependencies: $("new-deps").value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
    hardware_bound: $("new-hw").checked,
    verified: $("new-verified").checked,
    notes: $("new-notes").value.trim(),
    files,
  };
}

$("btn-draft-desc").addEventListener("click", async () => {
  // 草稿反馈内联到简介框旁（工单 ux-walkthrough-02/07 评审整改）：不再散落
  // 到卡片底部 #add-msg——结果与反馈都在同区同线
  const box = $("new-desc-msg");
  if (box) { box.textContent = ""; box.classList.remove("ok", "error"); }
  const payload = newModulePayload();
  if (!payload) return;
  if (!$("new-slug").value.trim()) {
    if (box) { box.textContent = "请先填写模块 slug"; box.classList.add("error"); }
    return;
  }
  try {
    const data = await apiPost("/api/modules", { ...payload, description: "" });
    $("new-desc").value = data.draft;
    if (box) {
      box.textContent = "AI 简介草稿已填入，可修改后点击「校验并入库」。";
      box.classList.add("ok");
    }
  } catch (e) {
    if (box) { box.textContent = e.message; box.classList.add("error"); }
  }
});

$("btn-add-module-submit").addEventListener("click", async () => {
  $("add-msg").textContent = "";
  const payload = newModulePayload();
  if (!payload) return;
  if (!$("new-slug").value.trim()) { $("add-msg").textContent = "请先填写模块 slug"; return; }
  if (!$("new-desc").value.trim()) { $("add-msg").textContent = "请填写功能简介（或先让 AI 出草稿）"; return; }
  try {
    const manifest = await apiPost("/api/modules", payload);
    $("add-msg").classList.add("ok");
    $("add-msg").textContent = "模块 " + manifest.slug + " 已入库（简介与代码一致性校验通过）。";
    ["new-slug", "new-desc", "new-deps", "new-notes"].forEach((id) => ($(id).value = ""));
    $("new-hw").checked = $("new-verified").checked = false;
    $("new-files").innerHTML = "";
    addFileRow();
    loadLibrary();
  } catch (e) {
    $("add-msg").classList.remove("ok");
    $("add-msg").textContent = e.message;
  }
});
