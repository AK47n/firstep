// fx/codeview.js — 代码查看器纯函数（工单 code-viewer/04-05）
//
// 文件树 / 行号 gutter / 只读代码视图 / 大纲 / 跨文件搜索列表 / 文件内过滤。
// 高亮与语言判定走 fx/highlight.js 单源（languageOf / highlightText）；
// esc / formatSize 单源取自 fx/core.js；文件树与母版树（fx/master.js）同构
// 但独立实现——母版语义（详情弹窗 / 关键文件白名单）与本工具无关，不 import
// 耦合。模块约定见 fx/core.js 头部。
import { esc, formatSize } from "./core.js";
import { languageOf, highlightText } from "./highlight.js";

// buildCodeTree(files)：扁平文件清单 → 嵌套节点树（按路径逐层聚合）。
// files = [{path, size_bytes}]（/api/code/open 直出，顺序无关）；节点 =
// {name, path, isDir, children?, size_bytes?}。兄弟排序：目录在前、同级内
// 按名字码点序（确定性；localeCompare 依 locale 漂移，不用）。
export function buildCodeTree(files) {
  const root = { name: "", path: "", isDir: true, children: [] };
  for (const f of files || []) {
    const parts = String(f.path || "").split("/");
    let node = root;
    let prefix = [];
    for (let i = 0; i < parts.length; i++) {
      const name = parts[i];
      prefix.push(name);
      const isFile = i === parts.length - 1;
      let child = node.children.find((c) => c.name === name);
      if (!child) {
        child = {
          name,
          path: prefix.join("/"),
          isDir: !isFile,
          children: isFile ? undefined : [],
          size_bytes: isFile ? f.size_bytes : undefined,
        };
        node.children.push(child);
      }
      node = child;
    }
  }
  return sortCodeTree(root.children);
}

function sortCodeTree(nodes) {
  for (const n of nodes) if (n.children) sortCodeTree(n.children);
  return nodes.sort((a, b) => (a.isDir === b.isDir
    ? (a.name < b.name ? -1 : a.name > b.name ? 1 : 0)
    : a.isDir ? -1 : 1));
}

// codeTreeHTML(nodes)：递归树 HTML——目录 = 原生 <details open>/<summary>
// （零 JS 收起），文件 = 行按钮（data-code-file = 相对路径，交事件层；
// 末尾附 formatSize 大小）。根 <ul class="code-tree"> 由调用方包裹。
export function codeTreeHTML(nodes) {
  return (nodes || []).map((n) => n.isDir
    ? `<li class="code-tree-dir"><details open><summary>${esc(n.name)}</summary>
        <ul>${codeTreeHTML(n.children)}</ul></details></li>`
    : `<li class="code-tree-file">
        <button type="button" class="code-tree-btn" data-code-file="${esc(n.path)}">
          <span class="code-tree-name">${esc(n.name)}</span>
          <span class="muted">${formatSize(n.size_bytes)}</span></button></li>`
  ).join("");
}

// codeLineNumbersHTML(count)：行号 gutter 纯件——1..count 逐行 span
// （与代码行同一 font/line-height 由 CSS 保证对齐；count 下限 1）。
export function codeLineNumbersHTML(count) {
  const n = Math.max(1, Math.floor(count) || 1);
  let out = "";
  for (let i = 1; i <= n; i++) out += '<span class="code-gutter-line">' + i + "</span>";
  return out;
}

// highlightCodeLines(content, lang)：整段高亮 → 逐行 HTML 数组（评审整改：
// .code-pre-line 独立可寻址，供跳行内容行 flash——spec.md:127-128）。跨行
// token（块注释 / 续行字符串）在行界闭合并按同 class 重开，视觉与整段
// 渲染一致——cHighlight 产出的 span 可跨行，单纯按 \n 切会断色。行尾 \n
// 被消费为分隔符；空内容 / 尾 \n 的空行各得一个空串元素（与行号 gutter
// 逐行对齐）。
export function highlightCodeLines(content, lang) {
  const html = highlightText(content, lang);
  const lines = [];
  let line = "";
  let stack = [];            // 当前跨行打开的 tok 类别（最近在后）
  let i = 0;
  const n = html.length;
  while (i < n) {
    const ch = html[i];
    if (ch === "\n") {
      lines.push(line + stack.map(() => "</span>").join(""));
      line = stack.map((cls) => `<span class="${cls}">`).join("");
      i++;
      continue;
    }
    if (ch === "<" && html.startsWith("</span>", i)) {
      if (stack.length) stack.pop();
      line += "</span>";
      i += 7;
      continue;
    }
    if (ch === "<" && html.startsWith("<span class=", i)) {
      const end = html.indexOf(">", i);
      if (end > 0) {
        const m = /class="([^"]*)"/.exec(html.slice(i, end + 1));
        if (m) stack.push(m[1]);
        line += html.slice(i, end + 1);
        i = end + 1;
        continue;
      }
    }
    line += ch;
    i++;
  }
  lines.push(line);
  return lines;
}

// codeViewHTML(content, lang)：只读代码视图纯件——gutter（sticky 左栏，
// 同一滚动容器内不随横向滚动跑）+ pre（white-space:pre 不换行，行号与
// 代码同一行高；每行独立 .code-pre-line[data-code-line]，与 gutter 同
// 索引对齐）；高亮走 highlightText 单源（超 128KB 或 plain 自动回退
// 纯文本）。调用方把返回体放进 .code-view 滚动容器。
export function codeViewHTML(content, lang) {
  const src = String(content == null ? "" : content);
  const lines = highlightCodeLines(src, lang);
  return '<div class="code-gutter" aria-hidden="true">' + codeLineNumbersHTML(lines.length) + "</div>"
    + '<pre class="code-pre">' + lines.map((h, idx) =>
        `<span class="code-pre-line" data-code-line="${idx + 1}">${h}</span>`).join("") + "</pre>";
}

// outlineKindBadge(kind)：大纲条目类型徽标（function=ƒ / define=# /
// include=<>——纯展示文案，其余 ·）。
const OUTLINE_KIND_BADGE = { function: "ƒ", define: "#", include: "<>" };

// outlineHTML(outline)：大纲列表纯件——[{kind, name, line}]（/api/code/file
// 的 outline 字段直出）；条目 = 按钮（data-outline-line 交事件层跳行）。
export function outlineHTML(outline) {
  const items = outline || [];
  return items.length ? '<ul class="code-outline">' + items.map((o) =>
    `<li><button type="button" class="code-outline-item" data-outline-line="${esc(o.line)}"
        data-outline-kind="${esc(o.kind)}">
        <span class="code-outline-kind k-${esc(o.kind)}">${OUTLINE_KIND_BADGE[o.kind] || "·"}</span>
        <span class="code-outline-name">${esc(o.name)}</span>
        <span class="muted">${esc(o.line)}</span></button></li>`).join("")
    + "</ul>" : "";
}

// outlineEmptyHTML()：非 C 文件 / 无条目的大纲空态（「当前文件无大纲」）。
export function outlineEmptyHTML() {
  return '<div class="muted code-side-empty">当前文件无大纲（仅 .c/.h 提供函数 / 顶层宏 / include 清单）</div>';
}

// searchListHTML(hits, activeFile)：跨文件搜索结果列表纯件——
// hits = [{path, line, text}]（/api/code/search 直出）；条目 = 按钮
// （data-search-path / data-search-line 交事件层跳转）；activeFile 命中行加
// .on 高亮。
export function searchListHTML(hits, activeFile) {
  const items = hits || [];
  if (!items.length) return '<div class="muted code-side-empty">没有命中</div>';
  return '<ul class="code-search-list">' + items.map((h) =>
    `<li><button type="button" class="code-search-hit${h.path === activeFile ? " on" : ""}"
        data-search-path="${esc(h.path)}" data-search-line="${esc(h.line)}">
        <span class="code-search-path">${esc(h.path)}:${esc(h.line)}</span>
        <span class="code-search-text">${esc(h.text)}</span></button></li>`).join("")
    + "</ul>";
}

// fileFindFilter(lineTexts, q)：当前文件全文客户端过滤（纯函数）——大小写
// 不敏感子串，返回 1 基命中行号数组（空 q → []；与后端搜索同语义轴，
// 前端即时过滤用）。
export function fileFindFilter(lineTexts, q) {
  const needle = String(q == null ? "" : q).trim().toLowerCase();
  if (!needle) return [];
  const lines = lineTexts || [];
  const hits = [];
  for (let i = 0; i < lines.length; i++) {
    if (String(lines[i] == null ? "" : lines[i]).toLowerCase().includes(needle)) {
      hits.push(i + 1);
    }
  }
  return hits;
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    buildCodeTree,
    codeTreeHTML,
    codeLineNumbersHTML,
    highlightCodeLines,
    codeViewHTML,
    outlineHTML,
    outlineEmptyHTML,
    searchListHTML,
    fileFindFilter,
  });
}
