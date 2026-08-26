// fx/score.js — 评分点展示与核对清单纯函数（工单 frontend-es-modules/10，迁自
// index.html 评分域纯函数组：评分点行文案 / 只读面板 / 核对清单渲染与持久化）。
// scoreChecklistItemsHTML 保留函数体内局部 esc（null→"" 兜底，与 fx/core.js 的
// esc 语义不同，合并会破坏既有断言——保持逐字搬移）；共享件：renderScorePointPanel
// 用 esc（fx/core.js）。无域内常量。模块约定见 fx/core.js 头部。
import { esc } from "./core.js";

export function formatScorePoints(points) {
  if (!points || !points.length) return "（无结构化评分点）";
  const partLabel = (part) => part === "basic" ? "基础" : part === "development" ? "发挥" : "未知";
  const scoreText = (score) => (typeof score === "number" && Number.isFinite(score)) ? score + " 分" : "未标分";
  const refsText = (refs) => (refs && refs.length) ? "句子 " + refs.join("、") : "未关联原文";
  return points.map((p, i) => {
    const id = p.id || ("score-" + (i + 1));
    return "- " + id + "｜" + partLabel(p.part) + "｜" + scoreText(p.score)
      + "｜" + refsText(p.sentence_refs || []) + "｜" + (p.description || "");
  }).join("\n");
}

// ---------------------------------------------------------------------------
// 评分点核对清单（工单 score-checklist/01）：生成结果评分点从只读文本升级为
// 可勾选清单——逐条核对 + 进度 + 复制核对表（☑/□）；勾选进度按工程目录
// 持久化 localStorage（key = score-checklist:<output_dir>）。纯函数自包含
// （tests/js 抽取范式），交互在 initScoreChecklist 事件委托（DOM 部分留内联）。
// ---------------------------------------------------------------------------
export function scoreChecklistPartLabel(part) {
  return part === "basic" ? "基础" : part === "development" ? "发挥" : "未知";
}
export function scoreChecklistScoreText(score) {
  return (typeof score === "number" && Number.isFinite(score)) ? score + " 分" : "未标分";
}
export function scoreChecklistRefsText(refs) {
  return (refs && refs.length) ? "句子 " + refs.join("、") : "未关联原文";
}
export function scoreChecklistId(p, i) {
  return p.id || ("score-" + (i + 1));
}
export function scoreChecklistChecked(checkedSet, id) {
  return (checkedSet && typeof checkedSet.has === "function")
    ? checkedSet.has(id)
    : (checkedSet || []).indexOf(id) !== -1;
}
export function scoreChecklistLineText(p, i) {
  const id = scoreChecklistId(p, i);
  return id + "｜" + scoreChecklistPartLabel(p.part) + "｜"
    + scoreChecklistScoreText(p.score) + "｜" + scoreChecklistRefsText(p.sentence_refs || [])
    + "｜" + (p.description || "");
}
export function scoreChecklistKey(outputDir) {
  return outputDir ? "score-checklist:" + String(outputDir) : "";
}
export function scoreChecklistItemsHTML(points, checkedSet) {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
  if (!points || !points.length) return '<div class="muted">没有可核对的评分点。</div>';
  return points.map((p, i) => {
    const id = scoreChecklistId(p, i);
    const crumb = scoreChecklistChecked(checkedSet, id);
    return '<label class="sp-item' + (crumb ? " done" : "") + '">'
      + '<input type="checkbox" data-idx="' + i + '"' + (crumb ? " checked" : "") + ">"
      + '<span class="sp-line">' + esc(scoreChecklistLineText(p, i)) + "</span></label>";
  }).join("");
}
export function scoreChecklistProgressHTML(checkedCount, total) {
  const n = Number(checkedCount) || 0;
  const m = Number(total) || 0;
  return "已核对 " + n + "/" + m;
}
export function scoreChecklistExportText(points, checkedSet) {
  if (!points || !points.length) return "";
  return points.map((p, i) => {
    const id = scoreChecklistId(p, i);
    const mark = scoreChecklistChecked(checkedSet, id) ? "☑" : "□";
    return mark + " " + scoreChecklistLineText(p, i);
  }).join("\n");
}
export function scoreChecklistParse(storageValue) {
  try {
    const data = JSON.parse(storageValue == null ? "" : String(storageValue));
    return Array.isArray(data) ? new Set(data.filter((x) => typeof x === "string")) : new Set();
  } catch (e) { return new Set(); }
}
export function scoreChecklistLoad(key, storage) {
  if (!key || !storage) return new Set();
  try { return scoreChecklistParse(storage.getItem(key)); }
  catch (e) { return new Set(); }
}
export function scoreChecklistSave(key, ids, storage) {
  if (!key || !storage) return false;
  try { storage.setItem(key, JSON.stringify(Array.from(ids || []))); return true; }
  catch (e) { return false; }
}

export function renderScorePointPanel(points) {
  if (!points || !points.length) return "";
  const rows = formatScorePoints(points).split("\n").map((line) =>
    '<div class="score-row">' + esc(line) + '</div>'
  ).join("");
  return '<div class="score-panel" id="rec-score-points">'
    + '<div class="title">评分点验收清单</div>'
    + rows + '</div>';
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    formatScorePoints, renderScorePointPanel,
    scoreChecklistPartLabel, scoreChecklistScoreText, scoreChecklistRefsText,
    scoreChecklistId, scoreChecklistChecked, scoreChecklistLineText,
    scoreChecklistKey, scoreChecklistItemsHTML, scoreChecklistProgressHTML,
    scoreChecklistExportText, scoreChecklistParse, scoreChecklistLoad,
    scoreChecklistSave,
  });
}
