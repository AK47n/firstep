// fx/master.js — 母版库纯函数（工单 frontend-es-modules/05，迁自 index.html
// master 域纯函数组：表格行 / 删除确认 / 详情弹窗 / 关键文件清单行 / 内容
// 端点 URL 拼装）。域内常量无；esc / formatSize 单源取自 fx/core.js。模块约定见 fx/core.js 头部。
import { esc, formatSize } from "./core.js";
import { languageOf, highlightText } from "./highlight.js";

// masterHealthBadgeHTML(h)：健康徽章纯函数（工单 master-library-ui-2/01）——
// h = /api/masters 条目的 health 字段（ok / missing_key_files /
// config_file_ok / artifact_dirs，后端一次算好）。✓ 健康 / ⚠ 需关注，
// title 明细 = 缺失清单 / 配置缺失 / 构建残留三项组合（悬停看明细）。
export function masterHealthBadgeHTML(h) {
  if (!h) return "";
  const parts = [];
  if ((h.missing_key_files || []).length) {
    parts.push("关键文件缺失：" + h.missing_key_files.join("、"));
  }
  if (h.config_file_ok === false) parts.push("缺少工程配置文件");
  if ((h.artifact_dirs || []).length) {
    parts.push("构建产物残留：" + h.artifact_dirs.join("、"));
  }
  const title = h.ok
    ? "健康：关键文件齐全、工程配置文件在、无构建产物残留"
    : parts.join("；");
  return `<span class="master-health-pill ${h.ok ? "master-health-ok" : "master-health-warn"}" title="${esc(title)}">${h.ok ? "✓ 健康" : "⚠ 有缺失或残留"}</span>`;
}

// masterStatsHTML(s)：体积统计行纯函数（工单 master-library-ui-2/01）——
// s = /api/masters 条目的 stats 字段（total_size_bytes / file_count /
// big_files[{path,size_bytes}]）；formatSize 单源取自 fx/core.js，big_files
// 空 = 占位 —。
export function masterStatsHTML(s) {
  if (!s) return "";
  const total = typeof s.total_size_bytes === "number" ? formatSize(s.total_size_bytes) : "—";
  const count = typeof s.file_count === "number" ? s.file_count + " 个" : "—";
  const big = (s.big_files || [])
    .map((b) => `${esc(b.path)}（${formatSize(b.size_bytes)}）`)
    .join("、");
  return `<div class="ref-detail-row"><span class="ref-detail-k">总体积</span><span>${esc(total)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">文件数</span><span>${esc(count)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">大文件</span><span>${big || "—"}</span></div>`;
}

// buildMasterTree(files)：扁平文件清单 → 嵌套节点树（工单 02，按路径逐层
// 聚合）。files = [{path, size_bytes}]（/tree 端点直出，顺序无关）；节点 =
// {name, path, isDir, children?, size_bytes?}。兄弟排序：目录在前、同级内按
// 名字码点序（确定性；跨运行时一致——localeCompare 依 locale 漂移，不用）。
export function buildMasterTree(files) {
  const root = { name: "", path: "", isDir: true, children: [] };
  for (const f of files || []) {
    const parts = f.path.split("/");
    let node = root;
    let prefix = [];
    for (let i = 0; i < parts.length; i++) {
      const name = parts[i];
      prefix.push(name);
      const isFile = i === parts.length - 1;
      let child = node.children.find((c) => c.name === name);
      if (!child) {
        child = { name, path: prefix.join("/"), isDir: !isFile,
          children: isFile ? undefined : [], size_bytes: isFile ? f.size_bytes : undefined };
        node.children.push(child);
      }
      node = child;
    }
  }
  return sortMasterTree(root.children);
}

function sortMasterTree(nodes) {
  for (const n of nodes) if (n.children) sortMasterTree(n.children);
  return nodes.sort((a, b) => (a.isDir === b.isDir
    ? (a.name < b.name ? -1 : a.name > b.name ? 1 : 0)
    : a.isDir ? -1 : 1));
}

// masterTreeNodeHTML(nodes)：递归树 HTML（工单 02）——目录 = 原生
// <details open>/<summary>（零 JS 收起逻辑），文件 = 行按钮
// （data-master-tree-file 交事件层，data 属性 = 相对路径）。目录内子节点
// 渲染为 <ul>；根 <ul class="master-tree"> 由调用方包裹。
export function masterTreeNodeHTML(nodes) {
  return (nodes || []).map((n) => n.isDir
    ? `<li class="master-tree-dir"><details open><summary>${esc(n.name)}</summary>
        <ul>${masterTreeNodeHTML(n.children)}</ul></details></li>`
    : `<li class="master-tree-file">
        <button type="button" class="master-tree-btn" data-master-tree-file="${esc(n.path)}">
          <span class="master-tree-name">${esc(n.name)}</span>
          <span class="muted">${formatSize(n.size_bytes)}</span></button></li>`
  ).join("");
}

// masterTableRowHTML(m)：母版库表格行纯函数——平台展示名（platform_label，
// 缺省回退 platform）、提炼来源 join("、")、入库警告 join("；")、健康徽章列
// （带 health 字段时，工单 master-library-ui-2/01）、详情 + 删除按钮
// （data-master-detail / data-master-del）。m = /api/masters 条目。
export function masterTableRowHTML(m) {
  const healthCell = m.health ? `<td>${masterHealthBadgeHTML(m.health)}</td>` : "";
  return `<tr>
    <td class="slug">${esc(m.platform_label || m.platform)}</td>
    <td class="muted">${esc(m.sources.join("、") || "—")}</td>
    <td class="muted">${esc(m.warnings.join("；") || "—")}</td>
    ${healthCell}
    <td>
      <button data-master-detail="${esc(m.platform)}">详情</button>
      <button class="danger" data-master-del="${esc(m.platform)}">删除</button>
    </td>
  </tr>`;
}

// masterDeleteConfirmHTML(m)：删除确认弹窗内容纯函数——平台展示名 + 元数据
// （平台标识 / 提炼来源 / 关键文件数）+ 不可恢复警告 + 确认/取消双钮。
export function masterDeleteConfirmHTML(m) {
  const files = (m.key_files || []).length;
  return `<div class="ref-detail-meta">
    <div class="ref-detail-title">${esc(m.platform_label || m.platform)}</div>
    <div class="ref-detail-row"><span class="ref-detail-k">平台标识</span><span class="mono">${esc(m.platform)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">提炼来源</span><span>${esc(m.sources.join("、") || "—")}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">关键文件</span><span>${files} 项预览清单</span></div>
    <div class="ref-detail-note">删除后该平台母版目录与元数据一并移除，<strong>不可恢复</strong>——该平台的生成将找不到母版。确认删除？</div>
  </div>
  <div class="pdf-detail-actions">
    <button type="button" class="danger" data-master-del-confirm>确认删除</button>
    <button type="button" data-master-del-cancel>取消</button>
  </div>`;
}

// _masterFileURL(platform, endpoint, path)：母版文件内容端点 URL 拼装——
// platform 与 path 逐段 encodeURIComponent（对偶 ref 轮 href 先例，路径经
// 编码不进 URL 面）；endpoint = "files"（关键文件白名单）| "tree"（树文件），
// 仅此一处有差异（评审去重：masterFileURL 与 masterTreeFileURL 共形）。
function _masterFileURL(platform, endpoint, path) {
  return "/api/masters/" + encodeURIComponent(platform) + "/" + endpoint + "/"
    + path.split("/").map(encodeURIComponent).join("/");
}

// masterFileURL(platform, path)：关键文件内容端点 URL。
export function masterFileURL(platform, path) {
  return _masterFileURL(platform, "files", path);
}

// masterTreeFileURL(platform, path)：树文件内容端点 URL（工单 02）。
export function masterTreeFileURL(platform, path) {
  return _masterFileURL(platform, "tree", path);
}

// masterContentHTML(cached, path)：内容箱渲染纯件（工单 03）——关键文件与
// 树文件共用的「复制按钮 + 语法高亮 + 加载三态」统一收口。cached = null
// （加载中）| {ok:true, content} | {ok:false, message}；path 仅用于语言判定
// （高亮纯前端展示，content 后端契约原样）。失败 = 中文原因 + 可重试提示；
// 成功 = 复制按钮（data-master-copy 交事件层）+ pre（>128KB / plain 回退纯文本）。
export function masterContentHTML(cached, path) {
  if (!cached) {
    return '<span class="muted">加载中…</span>';
  }
  if (!cached.ok) {
    return '<div class="error">加载失败：' + esc(cached.message || "未知错误")
      + '</div><span class="muted">点击上方文件可重试。</span>';
  }
  const content = cached.content || "";
  const body = highlightText(content, languageOf(path));
  return '<div class="master-content-bar"><button type="button" class="master-copy-btn" data-master-copy>复制</button></div>'
    + '<pre class="master-file-pre">' + body + "</pre>";
}

// masterKeyFileRowHTML(f)：清单行——相对路径 mono + label + 大小 + 缺失 ⚠。
// f = key_files 条目 {path, label, size_bytes, exists}；缺失项禁用不可点。
export function masterKeyFileRowHTML(f) {
  const size = typeof f.size_bytes === "number" ? formatSize(f.size_bytes) : "—";
  return `<li><button type="button" class="master-file-btn"
      data-master-file="${esc(f.path)}"${f.exists ? "" : " disabled"}>
      <span class="master-file-name">${esc(f.path)}</span>
      <span class="muted">${esc(f.label)} · ${formatSize(f.size_bytes)}${f.exists ? "" : " · ⚠ 缺失"}</span>
    </button></li>`;
}

// masterDetailHTML(m)：详情弹窗内容——元数据段（平台 / 来源 / 警告 / 文件数）
// + 文件清单段 + 内容段（点击行按需加载全文）。
export function masterDetailHTML(m) {
  const files = m.key_files || [];
  return `<div class="ref-detail-meta">
    <div class="ref-detail-row"><span class="ref-detail-k">平台标识</span>
      <span class="mono">${esc(m.platform)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">提炼来源</span>
      <span>${esc((m.sources || []).join("、") || "—")}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">入库警告</span>
      <span>${esc((m.warnings || []).join("；") || "—")}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">关键文件</span>
      <span>${files.length} 项</span></div>
    ${m.stats ? masterStatsHTML(m.stats) : ""}
  </div>
  <div class="topic-detail-problem-title">关键文件清单</div>
  <ul class="master-detail-files">${files.length
    ? files.map(masterKeyFileRowHTML).join("")
    : '<li class="muted">未配置关键文件清单</li>'}</ul>
  <div class="topic-detail-problem-title">全部文件</div>
  <div data-master-tree><span class="muted">加载中…</span></div>
  <div class="topic-detail-problem-title">文件内容</div>
  <div data-master-content><span class="muted">点击上方文件加载全文（纯文本，按需取）。</span></div>`;
}

// decisionItem(d, sourceOptions)：报告"判定行"纯函数——keep 原样 / merge 带
// 来源工程下拉（默认 d.source 选中）/ exclude 剔除；每行附「归档为该题参考
// 文件」按钮（data-archive）+ 判定理由。d = {path, action, source, reason}。
export function decisionItem(d, sourceOptions) {
  const source = d.action === "merge" ? `
    <select data-path="${esc(d.path)}">
      ${sourceOptions.map((s) => `<option value="${esc(s)}" ${s === d.source ? "selected" : ""}>${esc(s)}</option>`).join("")}
    </select>` : "";
  return `<div class="decision"><span class="path">${esc(d.path)}</span>
    <span class="muted">（${d.action === "keep" ? "保留" : d.action === "merge" ? "合并" : "剔除"}${source}）</span>
    <button data-archive="${esc(d.path)}" title="该文件不进母版，复制入库参考文件库并锚定赛题编号">归档为该题参考文件</button>
    <div class="reason">${esc(d.reason)}</div></div>`;
}

// archiveItem(a)：归档行纯函数——路径 + 赛题编号输入（data-topic）+ 移除按钮
// （data-unarchive）+ 理由。a = {path, topic, reason}。
export function archiveItem(a) {
  return `<div class="decision"><span class="path">${esc(a.path)}</span>
    <span class="muted">（归档为该题参考文件，确认时复制入库）</span>
    <input type="text" data-topic="${esc(a.path)}" placeholder="锚定赛题编号，如 2026C" value="${esc(a.topic)}">
    <button data-unarchive="${esc(a.path)}">移除</button>
    <div class="reason">${esc(a.reason || "（无理由）")}</div></div>`;
}

if (typeof window !== "undefined") {
  Object.assign(window, { masterTableRowHTML, masterDeleteConfirmHTML, masterFileURL, masterKeyFileRowHTML, masterDetailHTML, decisionItem, archiveItem, masterHealthBadgeHTML, masterStatsHTML, masterTreeFileURL, buildMasterTree, masterTreeNodeHTML, masterContentHTML });
}
