// fx/reference.js — 参考文件库纯函数（工单 frontend-es-modules/03，迁自
// index.html reference 域纯函数组：过滤 / 排序 / 统计 / 行渲染 / 详情 / 编辑弹窗）。
// 域内常量无；esc / formatSize 单源取自 fx/core.js。模块约定见 fx/core.js 头部。
import { esc, formatSize } from "./core.js";

// 平台标注 chip（工单 01 平台属性）：any = 平台无关，不标注；stm32 / mspm0
// 显示"xx 平台"——手动选不过平台过滤，靠标注让用户自判
export function referencePlatformChip(e) {
  return e.platform && e.platform !== "any"
    ? ` <span class="chip out">${esc(e.platform)} 平台</span>` : "";
}

// 题型标注 chip（工单 topic-framework/04）：topic_type 空 = 未标记，不标注；
// 非空显示"<题型> 框架"——标了题型即骨架阶段注入决策框架段（含 framework/main.c）
export function referenceTopicTypeChip(e) {
  return e.topic_type
    ? ` <span class="chip" title="已标记题型：骨架生成时按此题型注入决策框架段（条目目录 framework/main.c）">${esc(e.topic_type)} 框架</span>` : "";
}

// —— 参考库表格精修（reference-library-ui/02）：过滤 / 排序 / 统计 / 行渲染
// 纯函数组（tests/js 可注入，对偶模块库 lib-* 系列）——
// refFilterEntries(entries, f)：f={q, platform, anchorKind, dangling, topicKeys,
// kitVocab}。q 大小写不敏感子串匹配标题 / 类型 / 锚定值 / 简介 / 任一文件名
// （四合一关键字）；platform / anchorKind 空串 = 该维度不过滤；dangling=true =
// 只看悬空条目（与既有维度正交，词表数据来自 f.topicKeys / f.kitVocab）。
export function refFilterEntries(entries, f) {
  const q = String((f && f.q) || "").trim().toLowerCase();
  const platform = (f && f.platform) || "";
  const anchorKind = (f && f.anchorKind) || "";
  let out = (entries || []).filter((e) => {
    if (q) {
      const hay = [e.title, e.type,
        e.anchor_kind === "none" ? "" : e.anchor_value, e.description,
        ...(e.files || [])];
      if (!hay.some((s) => String(s == null ? "" : s).toLowerCase().includes(q))) return false;
    }
    if (platform && e.platform !== platform) return false;
    if (anchorKind && e.anchor_kind !== anchorKind) return false;
    return true;
  });
  if (f && f.dangling) {
    out = refDanglingAnchors(out, f.topicKeys, f.kitVocab);
  }
  return out;
}

// refDanglingAnchors(entries, topicKeys, kitVocab)：悬空锚定体检（工单 04）。
// 悬空 = 锚定值永远不命中和生成侧关联注入的判定（selection.py 按赛题 key /
// 模块库 kit 词表逐值 search_references 子串匹配 + 平台过滤，匹配方向为
// 词表值 in 锚定值）：
// - topic 方向：库内不存在任何赛题 key 是锚定值的子串（key in anchor_value）；
// - kit 方向：词表内不存在任何值是锚定值的子串（与生成侧同为子串语义——
//   锚定值带词表值前后缀（如「ALX-套件-v2」）仍会被自动关联，不算悬空）；
// - none 无此概念；数据集为空 = 对应方向跳过检查（零误报降级）。
export function refDanglingAnchors(entries, topicKeys, kitVocab) {
  // 空 key / 空词表项不参与子串匹配（"" 是任何值的子串会误命中）；过滤后
  // 无有效项 = 该方向数据缺失 → 降级不判定（零误报）
  const tk = (topicKeys || []).filter((k) => String(k || "").length > 0);
  const kv = (kitVocab || []).filter((k) => String(k || "").length > 0);
  return (entries || []).filter((e) => {
    const kind = e.anchor_kind;
    const av = String(e.anchor_value || "");
    if (kind === "topic" && tk.length) {
      return !tk.some((k) => av.indexOf(k) !== -1);
    }
    if (kind === "kit" && kv.length) {
      return !kv.some((k) => av.indexOf(k) !== -1);
    }
    return false;
  });
}

// refSortEntries(entries, s)：s={by:'title'|'type'|'size'|'files'|'platform',
// dir:'asc'|'desc'}；返回新数组（不改原数组）；Array.sort 稳定 → 同键保持入库序。
// by 分派集中在 key() 一处（数值键按数值、文本键按 localeCompare）。
export function refSortEntries(entries, s) {
  const by = (s && s.by) || "title";
  const dir = (s && s.dir) === "desc" ? -1 : 1;
  const key = (e) => {
    if (by === "size") return Number(e.size_bytes || 0);
    if (by === "files") return Number(e.file_count != null ? e.file_count : (e.files || []).length);
    if (by === "type") return String(e.type || "");
    if (by === "platform") return String(e.platform || "");
    return String(e.title || "");
  };
  const out = (entries || []).slice();
  out.sort((a, b) => {
    const av = key(a), bv = key(b);
    const cmp = (typeof av === "number" && typeof bv === "number")
      ? (av === bv ? 0 : (av < bv ? -1 : 1))
      : String(av).localeCompare(String(bv));
    return cmp * dir;
  });
  return out;
}

// refStats(entries, ctx?)：统计（对传入集合计算——统计条随过滤结果联动）。
// platforms / anchorKinds 三键恒显（统计条固定口径）；totalBytes 求和；
// ctx={topicKeys,kitVocab} 可选——传入时按悬空锚定语义补 dangling 计数
// （spec 契约：统计输出含悬空数；无 ctx / 词表缺失 = dangling 0，不误报）。
export function refStats(entries, ctx) {
  const list = entries || [];
  const platforms = { any: 0, stm32: 0, mspm0: 0 };
  const anchorKinds = { topic: 0, kit: 0, none: 0 };
  let totalBytes = 0;
  for (const e of list) {
    if (platforms[e.platform] != null) platforms[e.platform] += 1;
    if (anchorKinds[e.anchor_kind] != null) anchorKinds[e.anchor_kind] += 1;
    totalBytes += Number(e.size_bytes || 0);
  }
  const dangling = ctx
    ? refDanglingAnchors(list, ctx.topicKeys, ctx.kitVocab).length : 0;
  return { total: list.length, platforms, anchorKinds, unanchored: anchorKinds.none, totalBytes, dangling };
}

// refStatsText(stats)：统计条文案（平台名沿用徽章惯例 toUpperCase 显示）。
export function refStatsText(stats) {
  const parts = ["共 " + stats.total + " 条参考"];
  for (const name of ["any", "stm32", "mspm0"]) {
    parts.push(String(name).toUpperCase() + " " + (stats.platforms[name] || 0));
  }
  parts.push("赛题 " + (stats.anchorKinds.topic || 0));
  parts.push("套件 " + (stats.anchorKinds.kit || 0));
  parts.push("未锚定 " + (stats.unanchored || 0));
  if (stats.totalBytes) parts.push("总体积 " + formatSize(stats.totalBytes));
  return parts.join(" · ");
}

// refMatchFiles(entry, q)：文件名命中清单（客户端版 matched_files）。
// 从条目 files 元数据清单按子串（大小写不敏感）计算；空关键字 = 无命中。
export function refMatchFiles(entry, q) {
  const needle = String(q || "").trim().toLowerCase();
  if (!needle) return [];
  return (entry.files || []).filter((p) => String(p).toLowerCase().includes(needle));
}

// refAnchorBadge(entry)：锚定三色徽章（赛题 = ref-topic / 套件 = ref-kit /
// 未锚定 = ref-none），复用 .badge 基础样式。
export function refAnchorBadge(entry) {
  if (entry.anchor_kind === "topic") return `<span class="badge ref-topic">赛题 ${esc(entry.anchor_value)}</span>`;
  if (entry.anchor_kind === "kit") return `<span class="badge ref-kit">套件 ${esc(entry.anchor_value)}</span>`;
  return `<span class="badge ref-none">未锚定</span>`;
}

// refChipRowHTML(options, selected)：筛选 chips 纯函数（对偶 libChipRowHTML，
// 换 data-ref-chip 属性）；selected 命中项加 on 类（'' = 未选中）。
export function refChipRowHTML(options, selected) {
  return (options || []).map((o) =>
    `<button type="button" class="lib-chip${o.value === selected ? " on" : ""}" data-ref-chip="${esc(o.value)}">${esc(o.label)}${o.count != null ? "（" + o.count + "）" : ""}</button>`
  ).join("");
}

// refRowHTML(entry, f)：行渲染（标题截断 + 全文 tooltip、文件名命中直出链接、
// 锚定徽章 + 平台 chip、简介截断 + tooltip、体量口径、操作按钮）。
export function refRowHTML(entry, f) {
  const q = (f && f.q) || "";
  const title = String(entry.title || "");
  const desc = String(entry.description || "");
  const matches = refMatchFiles(entry, q);
  // 悬空锚定警示（工单 04）：降级语义集中在 refDanglingAnchors 内部
  // （无词表上下文 = 不判定不渲染 ⚠）
  const dangling = refDanglingAnchors([entry], f && f.topicKeys, f && f.kitVocab).length > 0;
  return `<tr>
    <td class="ref-title-cell" title="${esc(title)}">${esc(title)}
      ${matches.length ? '<div class="ref-matched">' + matches.map((p) =>
        `<a href="#" data-mf="${esc(entry.id)}" data-path="${esc(p)}">▸ ${esc(p)}</a>`).join("") + "</div>" : ""}
    </td>
    <td>${esc(entry.type)}</td>
    <td>${entry.topic_type ? esc(entry.topic_type) : '<span class="muted">—</span>'}</td>
    <td class="muted">${refAnchorBadge(entry)}${referencePlatformChip(entry)}${dangling ? '<span class="ref-dangling-tag" title="锚定值不命中任何库内赛题 / 套件，生成时不会自动关联（点「编辑」改正锚定）">⚠</span>' : ""}</td>
    <td class="desc-cell" title="${esc(desc)}">${esc(desc)}</td>
    <td class="muted" title="${esc(`${(entry.files || []).length} 个素材文件，路径清单见磁盘目录`)}">${esc(entry.file_count)} 个文件 · ${formatSize(entry.size_bytes)}</td>
    <td><button data-ref-view="${esc(entry.id)}" title="查看条目详情">详情</button> <button data-ref-edit="${esc(entry.id)}" title="编辑条目元数据与文件">编辑</button> <button class="danger" data-ref-del="${esc(entry.id)}">删除</button></td>
  </tr>`;
}

// refDetailHTML(entry, files)：详情弹窗内容（元数据段 + 文件过滤输入 +
// 文件清单段；files = 磁盘实况端点结果，逐路径大小 + 打开链接）。
export function refDetailHTML(entry, files) {
  return `<div class="ref-detail-meta">
    <div class="ref-detail-title">${esc(entry.title)}</div>
    <div class="ref-detail-row"><span class="ref-detail-k">编号</span><span class="mono">${esc(entry.id)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">类型</span><span>${esc(entry.type)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">锚定</span><span>${refAnchorBadge(entry)}${referencePlatformChip(entry)}${referenceTopicTypeChip(entry)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">简介</span><span class="ref-detail-desc">${esc(entry.description)}</span></div>
    <div class="ref-detail-row"><span class="ref-detail-k">体量</span><span>${esc(entry.file_count)} 个文件 · ${formatSize(entry.size_bytes)}</span></div>
  </div>
  <input class="ref-files-filter" placeholder="过滤文件名…">
  <ul class="ref-files-list">
    ${files.length ? files.map((f) => `
    <li data-path="${esc(f.path)}"><a href="#" data-path="${esc(f.path)}">${esc(f.path)}</a>
        <span class="muted">${formatSize(f.size_bytes)}</span></li>`).join("")
      : '<li class="muted">无文件（素材清单缺失）。</li>'}
  </ul>`;
}

// ===== 参考库编辑弹窗纯函数（工单 03，tests/js 可注入）=====

// refEditState(status, event)：编辑保存状态机（对偶 editDescStatus）。
// idle → saving → ok / rejected；reset 回 idle；非法事件保持原状态
// （重入由保存按钮禁用承担）。
export function refEditState(status, event) {
  switch (event) {
    case "save": return "saving";
    case "saved": return status === "saving" ? "ok" : status;
    case "error": return status === "saving" ? "rejected" : status;
    case "reset": return "idle";
    default: return status;
  }
}

// refEditValidate(fields)：保存前本地校验（与后端同源口径的轻量前置）。
// 必填：标题 / 类型 / 简介非空（strip 后）；topic / kit 锚定必须给出值。
// 返回 {ok, message}；合法 message 为空串。返回值语义与后端校验一致，
// 后端仍全量校验（失败 = 400 中文原因，保留弹窗）。
export function refEditValidate(fields) {
  const need = (v) => String(v || "").trim().length > 0;
  if (!need(fields.title)) return { ok: false, message: "标题不能为空" };
  if (!need(fields.type)) return { ok: false, message: "类型不能为空" };
  if (!need(fields.description)) return { ok: false, message: "简介不能为空（留空让 AI 出草稿仅限录入时）" };
  if ((fields.anchor_kind === "topic" || fields.anchor_kind === "kit")
      && !need(fields.anchor_value)) {
    return { ok: false, message: fields.anchor_kind === "topic" ? "赛题锚定必须填写赛题号" : "套件锚定必须选择套件" };
  }
  return { ok: true, message: "" };
}

// refEditFilePlan(existing, removeChecked, added)：文件增减计划。
// existing = 磁盘实况路径清单；removeChecked = 用户勾选删除的既有路径；
// added = 新增行 {文件名: 内容}。规则与后端（工单 01）一致：
// ① 同名既删又增 = 拒绝（后端「同一文件既添加又删除」——不支持替换内容）；
// ② 新增名已存在于既有清单且未勾删 = 拒绝（后端「文件已存在…请先删除再添加」）；
// ③ 勾删的路径不在既有清单（外部已删）也透传，存在性由后端裁决。
// 返回 {ok, add_files, remove_files} 或 {ok:false, message}。
export function refEditFilePlan(existing, removeChecked, added) {
  const addNames = Object.keys(added || {});
  const remove = (removeChecked || []).slice();
  for (const name of addNames) {
    if (remove.includes(name)) {
      return { ok: false, message: "文件 " + name + " 既勾选了删除又新增同名：不支持修改内容，请取消勾选或改新增文件名" };
    }
    if ((existing || []).includes(name)) {
      return { ok: false, message: "文件 " + name + " 已存在：不支持修改内容，请先勾选删除（保存一次）后再添加新文件" };
    }
  }
  return { ok: true, add_files: { ...(added || {}) }, remove_files: remove };
}

// refEditPayload(fields, plan)：组装 PUT 元数据全量（照录入表单语义：
// none 锚定强制空值；topic / kit 取对应输入；全部 trim）。
export function refEditPayload(fields, plan) {
  const anchor_value = fields.anchor_kind === "topic" ? String(fields.anchor_value || "").trim()
    : fields.anchor_kind === "kit" ? String(fields.anchor_value || "").trim() : "";
  return {
    title: String(fields.title || "").trim(),
    type: String(fields.type || "").trim(),
    description: String(fields.description || "").trim(),
    anchor_kind: fields.anchor_kind,
    anchor_value,
    platform: fields.platform || "any",
    topic_type: String(fields.topic_type || "").trim(),
    add_files: plan.add_files,
    remove_files: plan.remove_files,
  };
}

if (typeof window !== "undefined") {
  Object.assign(window, { referencePlatformChip, referenceTopicTypeChip, refFilterEntries, refDanglingAnchors, refSortEntries, refStats, refStatsText, refMatchFiles, refAnchorBadge, refChipRowHTML, refRowHTML, refDetailHTML, refEditState, refEditValidate, refEditFilePlan, refEditPayload });
}
