// fx/topic.js — 赛题库纯函数（工单 frontend-es-modules/04，迁自 index.html
// topic 域纯函数组：图注 / 词表 / 悬空体检 / 健康 / 过滤 / 排序 / 统计 /
// 卡片 / 详情 / 页图 / 编辑弹窗）。域内常量无；esc 单源取自 fx/core.js
// （topicCardHTML 保留局部 esc：其 null 兜底语义与 core esc 不同且有测试
// 断言「空字段兜底不抛错」，照搬不合并）。模块约定见 fx/core.js 头部。
import { esc } from "./core.js";

// topicHasNotes(text)：题面是否已含图注段（[示意图N：…] / [图N 标注] /
// [图N 标注：…]——与后端 enrich 幂等判定同前缀，前端仅作展示徽章）。
export function topicHasNotes(text) {
  const s = String(text == null ? "" : text);
  return s.indexOf("[示意图") !== -1 || /\[图\s*\d+\s*标注/.test(s);
}

// topicGroupVocabulary(modules)：/api/modules → 功能组 id→label 唯一表
//（模块序保序去重；无 exclusive_group 的模块跳过——对偶 kitVocabulary
// 派生先例，不新设词表端点）。
export function topicGroupVocabulary(modules) {
  const out = {};
  for (const m of (modules || [])) {
    const g = m && m.exclusive_group;
    if (g && g.id) out[g.id] = g.label || "";
  }
  return out;
}

// topicDanglingGroups(entry, groupIds)：hint 组悬空体检（对偶
// refDanglingAnchors 降级语义）——组 id 不在模块库词表 = 推荐链路静默
// 忽略；词表空（模块库未配置 / 拉取失败）= 空结果降级不判定（零误报）。
export function topicDanglingGroups(entry, groupIds) {
  const ids = (groupIds || []).filter((g) => String(g || "").length > 0);
  if (!ids.length) return [];
  return (((entry || {}).hint_module_groups) || []).filter((g) => !ids.includes(g));
}

// topicHealthText(entry, vocab)：数据问题中文描述（空数组 = 健康）。
// 三类：原 PDF 缺失 / 附带程序目录悬空 / 功能组 hint 悬空；vocab = 组词表
// 对象（{id: label}，缺省 = 不判定 hint 方向）。
export function topicHealthText(entry, vocab) {
  const out = [];
  const health = (entry && entry.health) || {};
  if (health.original_pdf_missing) {
    out.push("原 PDF 缺失（" + String((entry || {}).original_pdf || "?") + " 不在条目目录）");
  }
  for (const p of (health.programs_missing || [])) {
    out.push("附带程序目录不存在：" + String(p));
  }
  const dangling = topicDanglingGroups(entry, vocab ? Object.keys(vocab) : []);
  for (const g of dangling) {
    out.push("功能组 " + g + " 库内无此组（推荐链路会忽略）");
  }
  return out;
}

// topicFilterEntries(entries, f)：f={q, year, health, groupIds}——关键字
// （编号 / 年份 / 题面全文，大小写不敏感）× 年份 × 健康状态正交过滤；
// 空条件 = 全量（对偶 refFilterEntries）。
export function topicFilterEntries(entries, f) {
  const q = String((f && f.q) || "").trim().toLowerCase();
  const year = (f && f.year) || "";
  const groupIds = (f && f.groupIds) || [];
  return (entries || []).filter((t) => {
    if (q) {
      const hay = [t.key, t.year, t.problem_text];
      if (!hay.some((s) => String(s == null ? "" : s).toLowerCase().includes(q))) return false;
    }
    if (year && t.year !== year) return false;
    if (f && f.health) {
      const health = t.health || {};
      const dangling = topicDanglingGroups(t, groupIds);
      if (!(health.original_pdf_missing
        || (health.programs_missing || []).length || dangling.length)) return false;
    }
    return true;
  });
}

// topicSortEntries(entries, s)：s={by:'key'|'chars'|'mtime', dir:'asc'|'desc'}；
// 返回新数组（不改原数组）；Array.sort 稳定 → 同键保持全量序。
export function topicSortEntries(entries, s) {
  const by = (s && s.by) || "key";
  const dir = (s && s.dir) === "desc" ? -1 : 1;
  const key = (t) => {
    if (by === "chars") return Number((t.problem_text || "").length);
    if (by === "mtime") return Number(t.mtime || 0);   // 最近更新（ux-polish-02/08）
    return String(t.key || "");
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

// topicStats(entries, groupIds)：统计（对传入集合计算——统计条随过滤联动）。
// issues = 任一健康缺项（PDF 缺失 / 程序悬空 / hint 悬空）的条目数。
export function topicStats(entries, groupIds) {
  const list = entries || [];
  let withPrograms = 0, withNotes = 0, totalChars = 0, issues = 0;
  for (const t of list) {
    if ((t.programs || []).length) withPrograms += 1;
    if (topicHasNotes(t.problem_text)) withNotes += 1;
    totalChars += Number((t.problem_text || "").length);
    const health = t.health || {};
    if (health.original_pdf_missing
      || (health.programs_missing || []).length
      || topicDanglingGroups(t, groupIds).length) issues += 1;
  }
  return { total: list.length, withPrograms, withNotes, totalChars, issues };
}

// topicStatsText(stats)：统计条文案（字数 K 缩写；0 项不显）。
export function topicStatsText(stats) {
  const chars = Number(stats.totalChars || 0);
  const charsText = chars >= 1000 ? (chars / 1000).toFixed(1) + "K" : String(chars);
  const parts = ["共 " + Number(stats.total || 0) + " 题"];
  if (stats.withPrograms) parts.push("含附带程序 " + Number(stats.withPrograms || 0));
  if (stats.withNotes) parts.push("含图注 " + Number(stats.withNotes || 0));
  if (chars) parts.push("题面合计 ~" + charsText + " 字");
  return parts.join(" · ");
}

// topicChipRowHTML(options, selected)：年份筛选 chips 纯函数（对偶
// refChipRowHTML，换 data-topic-chip 属性）；selected 命中项加 on 类。
export function topicChipRowHTML(options, selected) {
  return (options || []).map((o) =>
    '<button type="button" class="lib-chip' + (o.value === selected ? " on" : "")
      + '" data-topic-chip="' + esc(o.value) + '">' + esc(o.label)
      + (o.count != null ? "（" + o.count + "）" : "") + '</button>'
  ).join("");
}

// 详情弹窗（工单 topic-library-ui/04）：元数据段（复用 ref-detail-* 布局
// 令牌）+ 题面全文段 + 页图懒加载容器 + 操作段。数据 = 浏览列表同源
// （entry 含 health），hint 悬空判定与卡片同词表、同一判定（topicDanglingGroups
// ——词表空 = 不判定，防空词表误报；vocab 缺省 = 降级）。
export function topicDetailHTML(entry, vocab) {
  const health = (entry && entry.health) || {};
  const groupIds = vocab ? Object.keys(vocab) : [];
  const danglingGroups = topicDanglingGroups(entry, groupIds);
  const problems = topicHealthText(entry, vocab);
  const missingPrograms = (health.programs_missing || []);
  const programs = ((entry && entry.programs) || []).map((p) =>
    '<span class="topic-detail-prog mono">' + esc(p) + '</span>'
    + (missingPrograms.includes(p)
      ? ' <span class="topic-warn" title="附带程序目录不存在">⚠</span>' : '')
  ).join("");
  const groups = ((entry && entry.hint_module_groups) || []).map((g) => {
    const label = vocab ? vocab[g] : "";
    const dangling = danglingGroups.includes(g);
    return label
      ? '<span class="badge">' + esc(label) + '</span> <span class="mono muted">' + esc(g) + '</span>'
      : '<span>' + esc(g) + '</span>' + (dangling
        ? ' <span class="topic-warn" title="库内无此组，推荐链路会忽略">⚠ 库内无此组</span>' : "");
  }).join(" ");
  const pdfLine = (entry && entry.original_pdf)
    ? '<span class="mono">' + esc(entry.original_pdf) + '</span>'
      + (health.original_pdf_missing
        ? ' <span class="topic-warn" title="原 PDF 文件不在条目目录，页图端点不可用">⚠ 缺失</span>'
        : (health.original_pdf_size ? ' <span class="muted">' + Number(health.original_pdf_size) + ' B</span>' : ""))
    : '<span class="muted">无</span>';
  const row = (k, v) => '<div class="ref-detail-row"><span class="ref-detail-k">' + k
    + '</span><span>' + v + '</span></div>';
  return '<div class="ref-detail-meta topic-detail-meta">'
    + row('编号', '<span class="mono">' + esc((entry && entry.key) || '') + '</span>')
    + row('年份', esc((entry && entry.year) || ''))
    + row('题面字数', String(String((entry && entry.problem_text) || '').length) + ' 字')
    + row('原 PDF', pdfLine)
    + row('附带程序', programs || '<span class="muted">无</span>')
    + row('功能组', groups || '<span class="muted">无</span>')
    + row('图注', topicHasNotes(entry && entry.problem_text)
      ? '<span class="badge ok">✓ 已含图注段</span>' : '<span class="muted">无</span>')
    + (problems.length
      ? row('数据问题', '<span class="topic-warn">⚠ ' + esc(problems.join('；')) + '</span>') : '')
    + '</div>'
    + '<div class="topic-detail-problem-title"><span>题面全文</span>'
    + '<span class="topic-detail-count">'
    + String(String((entry && entry.problem_text) || '').length) + ' 字</span>'
    + '<button class="topic-detail-toggle" data-topic-expand>展开全文</button></div>'
    + '<pre class="topic-detail-problem">' + esc((entry && entry.problem_text) || '') + '</pre>'
    + '<div class="topic-detail-pages-title">题面页图（懒加载）</div>'
    + '<div class="topic-pages" data-topic-pages></div>'
    + '<div class="topic-detail-actions">'
    + '<button data-topic-use="' + esc((entry && entry.key) || '') + '">用此题生成</button>'
    + '<button data-topic-edit="' + esc((entry && entry.key) || '') + '">编辑</button>'
    + '<button class="danger" data-topic-del="' + esc((entry && entry.key) || '') + '">删除</button>'
    + '</div>';
}

// topicPagesHTML(pages)：页图成功列表（data_url 叠放 + 页码标注）。
export function topicPagesHTML(pages) {
  return (pages || []).map((p) => {
    const pageNo = Number(p.page_no || 0);
    return '<figure class="topic-page"><figcaption>第 ' + pageNo + ' 页</figcaption>'
      + '<img src="' + String(p.data_url || '') + '" alt="题面页 ' + pageNo
      + '" loading="lazy"></figure>';
  }).join("");
}

// topicPagesErrorHTML(message)：页图失败态（后端 400 中文原因原样展示）。
export function topicPagesErrorHTML(message) {
  return '<p class="muted">页图不可用：' + esc(message) + '</p>';
}

// ===========================================================================
// 编辑弹窗（工单 topic-library-ui/05）：题面全文 / 附带程序 / 功能组勾选，
// 一次保存调 PUT（年份 + 编号只读 = 目录身份不可改）。交互逻辑下沉纯函数
// （topicEditHTML / topicEditValidate / topicEditPayload），DOM 只转发。
// ===========================================================================

// topicEditHTML(entry, vocab)：编辑表单渲染。功能组选项 = 词表组 + 词表外
// 当前值兜底（标注「库内无此组」——勾选保留或取消，不静默丢弃）。
export function topicEditHTML(entry, vocab) {
  const current = ((entry && entry.hint_module_groups) || []);
  const groupIds = vocab ? Object.keys(vocab) : [];
  const groupOptions = groupIds.map((id) => ({ id, label: vocab[id], dangling: false }));
  for (const g of current) {
    if (!groupIds.includes(g)) groupOptions.push({ id: g, label: g, dangling: true });
  }
  const groupBox = groupOptions.map((o) =>
    '<label class="topic-edit-group">'
    + '<input type="checkbox" data-topic-group="' + esc(o.id) + '"'
    + (current.includes(o.id) ? " checked" : "") + '><span>'
    + esc(o.label) + '</span>'
    + (o.dangling ? '<span class="topic-warn" title="库内无此组，推荐链路会忽略">⚠ 库内无此组</span>' : "")
    + '</label>'
  ).join("");
  return '<div class="ref-detail-meta">'
    + '<div class="ref-detail-row"><span class="ref-detail-k">编号</span>'
    + '<span class="mono">' + esc((entry && entry.key) || '') + '</span>'
    + ' <span class="muted">（年份 + 编号不可改 = 目录身份，已有引用不失效）</span></div>'
    + '<div class="ref-detail-row"><span class="ref-detail-k">年份</span>'
    + '<span>' + esc((entry && entry.year) || '') + '</span></div>'
    + '</div>'
    + '<div class="topic-edit-field"><label>题面全文（可改，含图注段原样可编辑）</label>'
    + '<textarea class="topic-edit-problem" rows="12">' + esc((entry && entry.problem_text) || '') + '</textarea></div>'
    + '<div class="topic-edit-field"><label>附带程序目录（每行一个绝对路径，留空 = 无）</label>'
    + '<textarea class="topic-edit-programs" rows="3">'
    + esc((((entry && entry.programs) || [])).join('\n')) + '</textarea></div>'
    + '<div class="topic-edit-field"><label>功能组（勾选；AI 未命中模块时出兜底选择卡）</label>'
    + '<div class="topic-edit-groups">' + (groupBox || '<span class="muted">模块库暂无功能组</span>')
    + '</div></div>'
    + '<div class="topic-edit-foot"><button data-topic-save>保存</button>'
    + ' <span class="muted">保存后题面 / 程序 / 功能组一次生效；校验失败不改数据</span></div>';
}

// topicEditValidate(fields)：保存前本地校验（与后端同口径的轻量前置）。
// 题面非空；程序路径存在性由后端兜底（目录可能在保存前被删，服务端为准）。
export function topicEditValidate(fields) {
  if (!String((fields && fields.problem_text) || "").trim()) {
    return { ok: false, message: "题面不能为空" };
  }
  return { ok: true, message: "" };
}

// topicEditPayload(fields)：组装 PUT body（全量三字段）。programs 逐行拆分
// （空行忽略 + 逐行 trim）；hint_module_groups = 勾选值清单。
export function topicEditPayload(fields) {
  const programs = String((fields && fields.programs) || "").split("\n")
    .map((s) => s.trim()).filter((s) => s.length > 0);
  return {
    problem_text: String((fields && fields.problem_text) || ""),
    programs,
    hint_module_groups: ((fields && fields.hint_module_groups) || []).slice(),
  };
}

// 赛题卡片 HTML（工单 ui-polish-9/02 + topic-library-ui/03 增强）：编号徽章
// + 年份 chip + 元数据小行（题面字数 / 程序数 / 图注 ✓）+ 健康 ⚠ + 题面预览
// + 操作（详情 / 用此题生成 / 删除）。自包含纯函数（内联 esc 与截断，deps
// 注入 topicDanglingGroups / topicHealthText / topicHasNotes——tests/js
// 括号配平抽取）；vocab 缺省 = 不判定 hint 悬空（旧调用兼容，零 ⚠）。
export function topicCardHTML(t, vocab) {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
  const trunc = (s, n) => {
    const str = String(s == null ? "" : s);
    return str.length > n ? str.slice(0, n) + "…" : str;
  };
  const key = esc(t && t.key);
  const year = esc(t && t.year);
  const preview = esc(trunc(t && t.problem_text, 80));
  const full = esc(trunc(t && t.problem_text, 200));
  const chars = String((t && t.problem_text) || "").length;
  const programs = ((t && t.programs) || []).length;
  const notes = topicHasNotes(t && t.problem_text);
  const problems = topicHealthText(t, vocab);
  return '<div class="topic-card">'
    + '<div class="topic-head"><span class="topic-key">' + key + '</span>'
    + '<span class="topic-year">' + year + '</span></div>'
    + '<div class="topic-meta"><span class="topic-meta-item">' + chars + ' 字</span>'
    + '<span class="topic-meta-item">程序 ' + programs + '</span>'
    + (notes ? '<span class="badge ok">图注 ✓</span>' : "")
    + '</div>'
    + (problems.length
      ? '<div class="topic-warn" title="' + esc(problems.join("；")) + '">⚠ 数据问题</div>' : "")
    + '<div class="topic-preview" title="' + full + '">' + preview + '</div>'
    + '<div class="topic-actions">'
    + '<button data-topic-view="' + key + '">详情</button>'
    + '<button data-topic-use="' + key + '">用此题生成</button>'
    + '<button class="danger" data-topic-del="' + key + '">删除</button>'
    + '</div></div>';
}

if (typeof window !== "undefined") {
  Object.assign(window, { topicHasNotes, topicGroupVocabulary, topicDanglingGroups, topicHealthText, topicFilterEntries, topicSortEntries, topicStats, topicStatsText, topicChipRowHTML, topicDetailHTML, topicPagesHTML, topicPagesErrorHTML, topicEditHTML, topicEditValidate, topicEditPayload, topicCardHTML });
}
