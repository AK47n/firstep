// fx/markdown.js — Markdown 渲染纯件（工单 code-viewer-md-preview/01）
//
// 代码查看器里 .md 的 VSCode 式渲染预览（Ctrl+Shift+V 对齐）：把 .md 文本
// 解析成带 1 基行号的块列表（parseMarkdownBlocks），再从同一份块列表投影
// 「预览 HTML」（markdownPreviewHTML）与「大纲标题清单」（markdownOutline）
// ——不重复解析、行号不漂移。语法子集 = 仓库实际语料 + CommonMark 常用：
// ATX 标题 / 段落（软换行=空格）/ 围栏代码块（语言经 fx/highlight.js
// highlightText 单源着色）/ 引用 / 有序无序列表（嵌套）/ 任务清单 / 管道表 /
// 水平线；行内：code / 粗体 / 斜体 / 删除线 / 链接 / 图片。
//
// 安全立场：任何原文进 DOM 前必经 esc（fx/core.js 单源），不透传原始 HTML；
// URL 协议白名单 http/https/mailto/#/相对路径，javascript:/data:/vbscript:/
// file: → 链接退化为纯文本、图片退化为占位标记；图片 src 经注入的
// imageUrl(原始src) 回调产出（纯件不感知目录与后端端点，../ 与协议路径由
// 回调拒绝）。模块约定见 fx/core.js 头部。
import { esc } from "./core.js";
import { highlightText } from "./highlight.js";

// ---- 块起点判定（单一口径：主循环分派 + 段落续行判断共用，防双份正则漂移）----

const ATX_RE = /^(#{1,6})[ \t]+(.*?)[ \t]*$/;
const FENCE_RE = /^(`{3,})[ \t]*([A-Za-z0-9_+\-.#]*)[ \t]*$/;
const HR_RE = /^[ \t]{0,3}((\*[ \t]*){3,}|(-[ \t]*){3,}|(_[ \t]*){3,})[ \t]*$/;
const QUOTE_RE = /^[ \t]{0,3}>[ \t]?/;

function blockStartType(lines, i, n) {
  const line = lines[i];
  if (ATX_RE.test(line)) return "heading";
  if (FENCE_RE.test(line)) return "fence";
  if (line.includes("|") && i + 1 < n && isTableSeparator(lines[i + 1])) return "table";
  if (HR_RE.test(line)) return "hr";
  if (QUOTE_RE.test(line)) return "quote";
  if (isListLine(line)) return "list";
  return null;
}

function isBlockStart(lines, j, n) {
  if (/^[ \t]*$/.test(lines[j])) return true;
  return blockStartType(lines, j, n) !== null;
}

export function parseMarkdownBlocks(text) {
  const lines = String(text == null ? "" : text).replace(/\r\n?/g, "\n").split("\n");
  const blocks = [];
  let i = 0;
  const n = lines.length;
  while (i < n) {
    const line = lines[i];
    if (/^[ \t]*$/.test(line)) { i++; continue; }               // 空行：跳过

    const kind = blockStartType(lines, i, n);

    // ATX 标题（可闭井号：# 标题 # → 标题）
    if (kind === "heading") {
      const m = ATX_RE.exec(line);
      blocks.push({
        type: "heading",
        level: m[1].length,
        text: m[2].replace(/[ \t]+#+[ \t]*$/, ""),
        line: i + 1,
      });
      i++;
      continue;
    }

    // 围栏代码块（``` 带可选语言；未闭合 → 文末兜底）
    if (kind === "fence") {
      const m = FENCE_RE.exec(line);
      const marker = m[1];
      const closeRe = new RegExp("^" + marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "[ \t]*$");
      const body = [];
      let j = i + 1;
      while (j < n && !closeRe.test(lines[j])) { body.push(lines[j]); j++; }
      blocks.push({ type: "fence", lang: m[2], text: body.join("\n"), line: i + 1 });
      i = j < n ? j + 1 : n;
      continue;
    }

    // 管道表：表头行含 | 且下一行是分隔行（--- 至少 3 连字符 + 至少一个 |）
    if (kind === "table") {
      const header = splitTableRow(line);
      const rows = [];
      let j = i + 2;
      while (j < n && lines[j].includes("|") && !/^[ \t]*$/.test(lines[j])) {
        rows.push(splitTableRow(lines[j]));
        j++;
      }
      blocks.push({ type: "table", header, rows, line: i + 1 });
      i = j;
      continue;
    }

    // 水平线（--- / *** / ___，至少 3 个；先于列表判定，- - - 不误判为列表）
    if (kind === "hr") {
      blocks.push({ type: "hr", line: i + 1 });
      i++;
      continue;
    }

    // 引用（> 连续行，前缀剥离）
    if (kind === "quote") {
      const quote = [];
      let j = i;
      while (j < n && QUOTE_RE.test(lines[j])) {
        quote.push(lines[j].replace(QUOTE_RE, ""));
        j++;
      }
      blocks.push({ type: "blockquote", text: quote.join("\n"), line: i + 1 });
      i = j;
      continue;
    }

    // 列表（含嵌套：缩进 2 空格 = 上一层；任务清单 - [ ] / - [x]）
    if (kind === "list") {
      const itemLines = [];
      let j = i;
      while (j < n && isListLine(lines[j])) {
        itemLines.push(parseListLine(lines[j], j + 1));
        j++;
      }
      const top = buildListTree(itemLines);
      blocks.push({
        type: "list",
        ordered: top.ordered,
        start: top.start,
        items: top.items,
        line: i + 1,
      });
      i = j;
      continue;
    }

    // 段落：连续非空且非块起点，软换行合并为空格
    const para = [line];
    let j = i + 1;
    while (j < n && !isBlockStart(lines, j, n)) { para.push(lines[j]); j++; }
    blocks.push({ type: "paragraph", text: para.join(" "), line: i + 1 });
    i = j;
  }
  return blocks;
}

// markdownPreviewHTML(blocks, opts)：块列表 → VSCode 式预览 HTML（外层
// <div class="code-md-preview">，块级元素带 data-md-line 供预览内滚动）。
// opts.imageUrl(原始src) → 最终 url 或 null/空串（图片占位）；省略回调时
// 相对路径原样透出（仍过协议白名单）。所有原文先 esc，不透传原始 HTML。
export function markdownPreviewHTML(blocks, opts) {
  const imageUrl = opts && typeof opts.imageUrl === "function" ? opts.imageUrl : null;
  const body = (blocks || []).map((b) => renderBlock(b, imageUrl)).join("");
  return '<div class="code-md-preview">' + body + "</div>";
}

// markdownOutline(blocks)：从同一块列表投影标题清单 ——
// [{kind:"heading", name, line, level}]（预览内滚动与右栏大纲共用）。
export function markdownOutline(blocks) {
  return (blocks || [])
    .filter((b) => b.type === "heading")
    .map((b) => ({ kind: "heading", name: b.text, line: b.line, level: b.level }));
}

// ---- 块级渲染 ----

function renderBlock(b, imageUrl) {
  switch (b.type) {
    case "heading": {
      return `<h${b.level} data-md-line="${b.line}">` + renderInline(b.text, imageUrl) + `</h${b.level}>`;
    }
    case "paragraph":
      return '<p data-md-line="' + b.line + '">' + renderInline(b.text, imageUrl) + "</p>";
    case "fence":
      // 语言经既有高亮单源着色（超限/未知语言自动回退纯文本 esc）
      return '<pre data-md-line="' + b.line + '"><code>'
        + highlightText(b.text, b.lang || "plain") + "</code></pre>";
    case "blockquote":
      return '<blockquote data-md-line="' + b.line + '"><p>'
        + renderInline(b.text, imageUrl) + "</p></blockquote>";
    case "list": {
      const tag = b.ordered ? "ol" : "ul";
      const start = b.ordered && b.start !== 1 ? ' start="' + b.start + '"' : "";
      return '<' + tag + ' data-md-line="' + b.line + '"' + start + ">"
        + renderListItems(b.items, imageUrl) + "</" + tag + ">";
    }
    case "table":
      return '<table data-md-line="' + b.line + '"><thead><tr>'
        + b.header.map((c) => "<th>" + renderInline(c, imageUrl) + "</th>").join("")
        + "</tr></thead><tbody>"
        + b.rows.map((r) => "<tr>" + r.map((c) => "<td>" + renderInline(c, imageUrl) + "</td>").join("") + "</tr>").join("")
        + "</tbody></table>";
    case "hr":
      return '<hr data-md-line="' + b.line + '">';
    default:
      return "";
  }
}

function renderListItems(items, imageUrl) {
  return items.map((it) => {
    const content = renderInline(it.text, imageUrl);
    const body = it.task
      ? '<input type="checkbox" disabled' + (it.checked ? " checked" : "") + "> " + content
      : content;
    const kidTag = it.ordered ? "ol" : "ul";
    const kidStart = it.ordered && it.start !== 1 ? ' start="' + it.start + '"' : "";
    const kids = it.items.length
      ? "<" + kidTag + kidStart + ">" + renderListItems(it.items, imageUrl) + "</" + kidTag + ">"
      : "";
    return '<li' + (it.task ? ' class="md-task"' : "") + ">" + body + kids + "</li>";
  }).join("");
}

// ---- 行内渲染（原文先 esc；软换行 → 空格）----

function renderInline(text, imageUrl) {
  const src = String(text == null ? "" : text);
  let html = "";
  let i = 0;
  const n = src.length;
  while (i < n) {
    const ch = src[i];
    if (ch === "\n") { html += " "; i++; continue; }
    if (ch === "\\" && i + 1 < n) { html += esc(src[i + 1]); i += 2; continue; }  // 反斜杠转义
    if (ch === "`") {                                                             // 行内 code
      const end = src.indexOf("`", i + 1);
      if (end > i) { html += "<code>" + esc(src.slice(i + 1, end)) + "</code>"; i = end + 1; continue; }
    }
    if (ch === "!" && src[i + 1] === "[") {                                       // 图片
      const p = parseLinkish(src, i + 1);
      if (p) { html += renderImage(p, imageUrl); i = p.end; continue; }
    }
    if (ch === "[") {                                                             // 链接
      const p = parseLinkish(src, i);
      if (p) { html += renderLink(p, imageUrl); i = p.end; continue; }
    }
    if (ch === "*") {                                                             // 粗体/斜体
      if (src.startsWith("**", i)) {
        const end = src.indexOf("**", i + 2);
        if (end > i + 1) { html += "<strong>" + renderInline(src.slice(i + 2, end), imageUrl) + "</strong>"; i = end + 2; continue; }
      }
      const end = src.indexOf("*", i + 1);
      if (end > i + 1 && !isIntraword(src, i, end)) {
        html += "<em>" + renderInline(src.slice(i + 1, end), imageUrl) + "</em>"; i = end + 1; continue;
      }
    }
    if (ch === "_") {                                                             // 斜体（词内不强调）
      const end = src.indexOf("_", i + 1);
      if (end > i + 1 && !isIntraword(src, i, end)) {
        html += "<em>" + renderInline(src.slice(i + 1, end), imageUrl) + "</em>"; i = end + 1; continue;
      }
    }
    if (ch === "~" && src.startsWith("~~", i)) {                                  // 删除线
      const end = src.indexOf("~~", i + 2);
      if (end > i + 1) { html += "<del>" + renderInline(src.slice(i + 2, end), imageUrl) + "</del>"; i = end + 2; continue; }
    }
    html += esc(ch);
    i++;
  }
  return html;
}

// [label](url "title") / ![alt](url "title") → {text, url, title, end, isImage}
function parseLinkish(src, start) {
  const closeB = src.indexOf("]", start + 1);
  if (closeB < 0 || src[closeB + 1] !== "(") return null;
  let j = closeB + 2;
  while (j < src.length && /\s/.test(src[j])) j++;
  const uStart = j;
  let depth = 0;                    // URL 内平衡括号（CommonMark：一层嵌套）
  while (j < src.length) {
    const c = src[j];
    if (c === "(") depth++;
    else if (c === ")") { if (depth > 0) depth--; else break; }
    else if (/\s/.test(c) && depth === 0) break;
    j++;
  }
  const url = src.slice(uStart, j);
  let title = "";
  while (j < src.length && /\s/.test(src[j])) j++;
  if (j < src.length && (src[j] === '"' || src[j] === "'")) {
    const q = src[j];
    const qEnd = src.indexOf(q, j + 1);
    if (qEnd > j && src[qEnd + 1] === ")") { title = src.slice(j + 1, qEnd); j = qEnd + 1; }
  }
  if (src[j] !== ")") return null;
  return { text: src.slice(start + 1, closeB), url, title, end: j + 1 };
}

function renderLink(p, imageUrl) {
  const label = renderInline(p.text, imageUrl);
  if (!isSafeUrl(p.url)) return label;                     // 非法协议 → 纯文本兜底
  let a = '<a href="' + esc(p.url) + '"';
  if (p.title) a += ' title="' + esc(p.title) + '"';
  return a + ">" + label + "</a>";
}

function renderImage(p, imageUrl) {
  // 原始 src 的引用面判定先行（纯件独立防御）：../ 跨出基准目录 / 绝对路径 /
  // 协议相对 / 非 http(s) 协议 → 直接占位，不调回调、不产生可请求引用；
  // 后续回调输出再过 isSafeUrl（防回调放毒）。
  if (!isSafeImageSrc(p.url)) return imageFallback(p.text);
  const mapped = imageUrl ? imageUrl(p.url) : p.url;       // 回调拒绝 → null/空串
  const url = mapped == null || mapped === "" ? "" : String(mapped);
  if (!url || !isSafeUrl(url)) return imageFallback(p.text);  // 放毒 → 占位
  let img = '<img src="' + esc(url) + '" alt="' + esc(p.text) + '"';
  if (p.title) img += ' title="' + esc(p.title) + '"';
  return img + ">";
}

function imageFallback(alt) {
  return '<span class="md-img-fallback">[图片：' + renderInline(alt) + "]</span>";
}

// hasScheme(s)：是否带 URL 协议前缀（scheme:，如 http:/https:/mailto:/javascript:/
// C:/）——isSafeUrl / isSafeImageSrc 与胶水层 codeImageUrl 共用同一判定单源
// （评审整改：三处正则去重）。
export function hasScheme(s) {
  return /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(String(s == null ? "" : s).trim());
}

// isSafeUrl(url)：协议白名单——http/https/mailto/# 与相对路径放行；
// javascript:/data:/vbscript:/file: 与协议相对（//）拒绝。
function isSafeUrl(url) {
  const s = String(url == null ? "" : url).trim();
  if (!s) return false;
  if (hasScheme(s)) {
    return /^(https?|mailto):/i.test(s);
  }
  return !s.startsWith("//");
}

// isSafeImageSrc(raw)：图片原始 src 的引用面判定（不含回调结果）——相对路径 /
// ./ 前缀 / 子目录 / http(s) 放行；../ 跨出基准目录、绝对路径（/ 开头 / 盘符）、
// 协议相对（//）与非 http(s) 协议 → 拒绝（渲染占位）。胶水层回调仍负责
// 「相对路径按 .md 所在目录归一、../ 出根再拒」；这里是纯件自己的防御面
// （无回调时也不产出可请求的 ../ 或绝对引用，对齐 spec 用户故事 10）。
function isSafeImageSrc(raw) {
  const s = String(raw == null ? "" : raw).trim();
  if (!s || s.startsWith("/")) return false;                  // 空 / 绝对路径（含 // 协议相对）
  if (hasScheme(s)) return /^https?:/i.test(s);
  if (/(^|\/)\.\.(\/|$)/.test(s)) return false;
  return true;
}

// isIntraword(src, open, close)：词内标记（a*b*c / foo_bar_baz）不强调
function isIntraword(src, open, close) {
  const before = open > 0 ? src[open - 1] : "";
  const after = close + 1 < src.length ? src[close + 1] : "";
  return /[A-Za-z0-9]/.test(before) && /[A-Za-z0-9]/.test(after);
}

// ---- 列表解析 ----

const LIST_RE = /^([ \t]*)([-*+]|\d+[.)])[ \t]+(.*)$/;

function isListLine(line) {
  return LIST_RE.test(line);
}

function parseListLine(line, lineNo) {
  const m = LIST_RE.exec(line);
  const spaces = m[1].replace(/\t/g, "  ").length;
  const ordered = /^[1-9]/.test(m[2]);
  let text = m[3];
  let task = false;
  let checked = false;
  const t = /^\[([ xX])\][ \t]+(.*)$/.exec(text);
  if (t) { task = true; checked = t[1] !== " "; text = t[2]; }
  return {
    level: Math.floor(spaces / 2),   // 2 空格 = 下一层
    ordered,
    start: ordered ? parseInt(m[2], 10) : 1,
    text,
    task,
    checked,
    line: lineNo,
  };
}

// buildListTree(itemLines)：平铺的列表行 → 嵌套树。顶层为
// {ordered, start, items}；每个条目 {text, task, checked, items, ordered,
// start, line}，条目自带的 ordered/start 描述其子列表类型（无子项为默认值）。
function buildListTree(itemLines) {
  const top = { ordered: itemLines[0].ordered, start: itemLines[0].start, items: [] };
  const stack = [{ level: -1, list: top }];
  for (const it of itemLines) {
    while (stack.length > 1 && stack[stack.length - 1].level >= it.level) stack.pop();
    const list = stack[stack.length - 1].list;
    // 列表类型/起始号 = 该列表首个条目（同层同型，首条定型）
    if (list.items.length === 0) {
      list.ordered = it.ordered;
      list.start = it.start;
    }
    const node = { text: it.text, task: it.task, checked: it.checked, items: [], ordered: false, start: 1, line: it.line };
    list.items.push(node);
    stack.push({ level: it.level, list: node });
  }
  return top;
}

// ---- 表格解析 ----

function isTableSeparator(line) {
  const s = line.trim();
  if (!s.includes("|")) return false;
  const core = s.replace(/[|\s:]/g, "");
  return core.length >= 3 && /^-+$/.test(core);
}

function splitTableRow(line) {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split("|").map((c) => c.trim());
}

if (typeof window !== "undefined") {
  Object.assign(window, { parseMarkdownBlocks, markdownPreviewHTML, markdownOutline, hasScheme });
}
