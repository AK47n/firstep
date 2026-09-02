// fx/codeview.js — 代码查看器纯函数（工单 code-viewer/04-05）
//
// 文件树 / 行号 gutter / 只读代码视图 / 大纲 / 跨文件搜索列表 / 文件内过滤。
// 高亮与语言判定走 fx/highlight.js 单源（languageOf / highlightText）；
// esc / formatSize 单源取自 fx/core.js；文件树与母版树（fx/master.js）同构
// 但独立实现——母版语义（详情弹窗 / 关键文件白名单）与本工具无关，不 import
// 耦合。模块约定见 fx/core.js 头部。
import { esc, formatSize } from "./core.js";
import { languageOf, highlightText } from "./highlight.js";

// 树徽章变更类型（code-ide-flow/02 磁盘基线感知）：changes 映射的值单源——
// fx 渲染层与 ui 胶水层共用同一常量（评审整改：裸字符串 "new"/"modified"
// 散落两层易漂移）。
export const TREE_CHANGE_NEW = "new";
export const TREE_CHANGE_MODIFIED = "modified";

// buildCodeTree(files, changes)：扁平清单 → 嵌套节点树（按路径逐层聚合）。
// files = [{path, size_bytes, mtime_ns?} | {path, is_dir: True}]（/api/code/open
// 直出，顺序无关；is_dir 条目 = 目录（含空目录，工单 code-tree-ops/01））；
// 节点 = {name, path, isDir, children?, size_bytes?, change?}。兄弟排序：
// 目录在前、同级内按名字码点序（确定性；localeCompare 依 locale 漂移，不用）。
// changes 可选（code-ide-flow/02 磁盘基线对比结果）：{path → TREE_CHANGE_NEW |
// TREE_CHANGE_MODIFIED}，命中文件节点的 change 字段供 codeTreeHTML 渲染
// 「新/变」徽章；缺省无徽章（与旧行为完全一致）。
export function buildCodeTree(files, changes) {
  const root = { name: "", path: "", isDir: true, children: [] };
  for (const f of files || []) {
    const parts = String(f.path || "").split("/");
    let node = root;
    let prefix = [];
    for (let i = 0; i < parts.length; i++) {
      const name = parts[i];
      prefix.push(name);
      const isFile = !f.is_dir && i === parts.length - 1;
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
      if (isFile && changes && Object.prototype.hasOwnProperty.call(changes, child.path)) {
        child.change = changes[child.path];
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

// ---- 文件树类型图标（工单 code-viewer-polish/01）：内联 stroke SVG 16px，
// 风格照 fx/btn-icon.js 单源约定（fill none / stroke currentColor / 1.5）；
// 按钮图标（btn）与文件树图标（file）语义不同，各自独立不 import 耦合。
const CODE_ICO_ATTRS = ' fill="none" stroke="currentColor" stroke-width="1.5"'
  + ' stroke-linecap="round" stroke-linejoin="round"';
// 文档底形（文件类图标共用）
const CODE_ICO_DOC = '<path d="M4.5 1.5 H10 L12.5 4.2 V14.5 H4.5 Z"/>'
  + '<path d="M10 1.5 V4.2 H12.5"/>';
// 扩展名 → 文档内标记（区分类型；无标记 = 通用文档）
const CODE_ICO_MARKS = {
  c: '<path d="M6.6 7 L5.2 8.6 L6.6 10.2 M9.4 7 L10.8 8.6 L9.4 10.2"/>',
  h: '<path d="M6.2 5.8 V10.6 M6.2 8.4 H9.8 V10.6"/>',
  md: '<path d="M6.3 6.9 L8 8.6 L9.7 6.9 V10.4"/>',
  cfg: '<path d="M6.9 5.8 L5.6 6.8 V9.9 L6.9 10.9 M9.1 5.8 L10.4 6.8 V9.9 L9.1 10.9"/>',
  asm: '<path d="M6.4 10.4 L8 6.4 L9.6 10.4 M7 9.1 H9"/>',
  bin: '<circle cx="6.8" cy="7.5" r="0.9"/><circle cx="9.3" cy="8.9" r="0.9"/>'
    + '<circle cx="9.3" cy="6.6" r="0.9"/>',
  txt: '<path d="M6.2 7.2 H9.8 M6.2 9.4 H9.3"/>',
};
const CODE_ICO_FOLDER = '<path d="M1.5 4 H6.5 L8.2 5.8 H14.5 V12.5 H1.5 Z"/>';

function codeIco(kind, marks) {
  return '<svg class="code-ico" viewBox="0 0 16 16" width="15" height="15"'
    + CODE_ICO_ATTRS + ">" + kind + (marks || "") + "</svg>";
}

// fileIconHTML(path, isDir)：文件树节点图标——文件夹 / C / 头文件 / 文档 /
// 配置（json/syscfg/uvprojx/cproject/xml）/ 汇编 / 产物（o/obj/out/map/hex）/
// 其余通用文档；未知扩展名兜底通用图标。纯展示 aria-hidden。
export function fileIconHTML(path, isDir) {
  const name = String(path == null ? "" : path).toLowerCase();
  if (isDir) return codeIco(CODE_ICO_FOLDER);
  const ext = name.split(".").pop() || "";
  if (ext === "c") return codeIco(CODE_ICO_DOC, CODE_ICO_MARKS.c);
  if (ext === "h" || ext === "hpp" || ext === "hxx") {
    return codeIco(CODE_ICO_DOC, CODE_ICO_MARKS.h);
  }
  if (ext === "md" || ext === "markdown") return codeIco(CODE_ICO_DOC, CODE_ICO_MARKS.md);
  if (ext === "s" || ext === "asm") return codeIco(CODE_ICO_DOC, CODE_ICO_MARKS.asm);
  if (ext === "o" || ext === "obj" || ext === "out" || ext === "map"
    || ext === "hex" || ext === "bin") {
    return codeIco(CODE_ICO_DOC, CODE_ICO_MARKS.bin);
  }
  if (ext === "json" || ext === "xml" || ext === "syscfg" || ext === "uvprojx"
    || ext === "cproject" || ext === "ioc") {
    return codeIco(CODE_ICO_DOC, CODE_ICO_MARKS.cfg);
  }
  if (ext === "txt" || ext === "log" || ext === "csv") {
    return codeIco(CODE_ICO_DOC, CODE_ICO_MARKS.txt);
  }
  return codeIco(CODE_ICO_DOC);
}

// treeActionButtonsHTML(n)：行操作按钮（工单 code-tree-ops/02）——✎/🗑
// 悬浮显示（hover 由 CSS 控制），data-tree-op/data-tree-path/data-tree-kind
// 交事件层；文件与目录行都有（目录删除仅空目录可删，后端 400 兜底）。
function treeActionButtonsHTML(n) {
  const kind = n.isDir ? "dir" : "file";
  return `<span class="code-tree-actions">
    <button type="button" class="code-tree-act" data-tree-op="rename"
      data-tree-path="${esc(n.path)}" data-tree-kind="${kind}"
      title="重命名" aria-label="重命名 ${esc(n.name)}">✎</button>
    <button type="button" class="code-tree-act code-tree-act-del" data-tree-op="delete"
      data-tree-path="${esc(n.path)}" data-tree-kind="${kind}"
      title="删除" aria-label="删除 ${esc(n.name)}">🗑</button>
  </span>`;
}

// codeTreeHTML(nodes)：递归树 HTML——目录 = 原生 <details open>/<summary>
// （零 JS 收起，含文件夹图标），文件 = 行按钮（data-code-file = 相对路径，
// 交事件层；含类型图标 + 末尾 formatSize 大小）。根 <ul class="code-tree">
// 由调用方包裹；每行右侧 ✎/🗑 操作按钮（treeActionButtonsHTML）。
// 节点 change（code-ide-flow/02）：TREE_CHANGE_NEW → 「新」徽章、
// TREE_CHANGE_MODIFIED → 「变」徽章（文件名旁，纯展示——标在文件行，目录
// 自身不标）。
export function codeTreeHTML(nodes) {
  return (nodes || []).map((n) => n.isDir
    ? `<li class="code-tree-dir"><details open data-dir-path="${esc(n.path)}"><summary>`
      + `<span class="code-tree-icon" aria-hidden="true">${fileIconHTML(n.path, true)}</span>`
      + `<span class="code-tree-dir-name">${esc(n.name)}</span></summary>`
      + `<ul>${codeTreeHTML(n.children)}</ul></details>`
      + treeActionButtonsHTML(n) + `</li>`
    : `<li class="code-tree-file">
        <button type="button" class="code-tree-btn" data-code-file="${esc(n.path)}">
          <span class="code-tree-icon" aria-hidden="true">${fileIconHTML(n.path, false)}</span>
          <span class="code-tree-name">${esc(n.name)}</span>`
      + (n.change === TREE_CHANGE_NEW
        ? '<span class="code-tree-badge b-new" title="新增文件" aria-label="新增文件">新</span>'
        : n.change === TREE_CHANGE_MODIFIED
          ? '<span class="code-tree-badge b-mod" title="已修改" aria-label="已修改">变</span>'
          : "")
      + `<span class="muted">${formatSize(n.size_bytes)}</span></button>`
      + treeActionButtonsHTML(n) + `</li>`
  ).join("");
}

// ---- 面包屑（工单 code-page-vscode-overhaul/05）----

// breadcrumbSegments(relPath)：相对路径 → 面包屑分段——每段
// {name, path, isDir}（path = 到该段的累积相对路径；最后一段 isDir=false，
// 其余为目录段）。空路径 / null → []（无面包屑）。
export function breadcrumbSegments(relPath) {
  const p = String(relPath == null ? "" : relPath);
  if (!p) return [];
  const parts = p.split("/").filter((s) => s.length);
  const out = [];
  let acc = "";
  for (let i = 0; i < parts.length; i++) {
    acc = acc ? acc + "/" + parts[i] : parts[i];
    out.push({ name: parts[i], path: acc, isDir: i < parts.length - 1 });
  }
  return out;
}

// breadcrumbHTML(segments)：面包屑 HTML 单源——目录段按钮
// data-breadcrumb-dir=path（点击定位文件树），文件段按钮
// data-breadcrumb-file=path（点击打开）；段间分隔符 ›；name 超长截断
// （>24 字符 → 前 21 + …，title 保留全量路径）；全部 esc 转义。
export function breadcrumbHTML(segments) {
  if (!segments || !segments.length) return "";
  const seg = (s, last) => {
    const name = s.name.length > 24 ? s.name.slice(0, 21) + "…" : s.name;
    const attr = last
      ? `data-breadcrumb-file="${esc(s.path)}"`
      : `data-breadcrumb-dir="${esc(s.path)}"`;
    return `<button type="button" class="code-crumb${last ? " code-crumb-last" : ""}" `
      + attr + ` title="${esc(s.path)}">${esc(name)}</button>`;
  };
  return segments.map((s, i) =>
    (i ? '<span class="code-crumb-sep" aria-hidden="true">›</span>' : "")
    + seg(s, i === segments.length - 1)
  ).join("");
}

// codeGutterLineHTML(n)：单行行号 gutter 纯件（工单 code-page-vscode-overhaul/08
// 窗口化——行号列逐行滑动窗口复用，与 codeLineNumbersHTML 单源）。
export function codeGutterLineHTML(n) {
  return '<span class="code-gutter-line" data-code-line="' + n + '">' + n + "</span>";
}

// codeLineNumbersHTML(count)：行号 gutter 纯件——1..count 逐行 span
// （与代码行同一 font/line-height 由 CSS 保证对齐；count 下限 1；
// data-code-line 与内容行 .code-pre-line 同 data 键——spec.md:127-128
// 主行号与内容行同键，跳行 / 当前行高亮按索引统一寻址）。
export function codeLineNumbersHTML(count) {
  const n = Math.max(1, Math.floor(count) || 1);
  let out = "";
  for (let i = 1; i <= n; i++) {
    out += codeGutterLineHTML(i);
  }
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
// include=<> / heading=H——.md 标题清单，工单 code-viewer-md-preview/01；
// 纯展示文案，其余 ·）。
const OUTLINE_KIND_BADGE = { function: "ƒ", define: "#", include: "<>", heading: "H" };

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

// outlineEmptyHTML()：无条目的大纲空态（「当前文件无大纲」——.c/.h 提供
// 函数 / 顶层宏 / include 清单；.md 提供标题清单，工单 code-viewer-md-preview/03）。
export function outlineEmptyHTML() {
  return '<div class="muted code-side-empty">当前文件无大纲（.c/.h 提供函数 / 顶层宏 / include 清单；.md 提供标题）</div>';
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

// ---- 树面板拖拽调宽（工单 code-viewer-tree-resize/01）：纯函数与常量。
// 宽度区间 [MIN, min(MAX, layoutW-480)]——保右侧大纲栏 300px + 中缝 + 主
// 视图最少 180px 不被挤没；layoutW 非有限或 ≤0（保守防御：tab 未来若走
// display:none，init 取宽为 0）时不收缩上限，待真实布局后再收敛。
// localStorage 只进胶水层（fx 无副作用约定，同 fx/code.js codeZoomClamp
// 先例：clamp / parse 分离 → parse 收敛后交 clamp）。
export const CODE_TREE_WIDTH_MIN = 160;
export const CODE_TREE_WIDTH_MAX = 720;
export const CODE_TREE_WIDTH_DEFAULT = 240;

// treeWidthClamp(px, layoutW)：任意输入 → 合法树宽（非数值 → 默认 240；
// 四舍五入后夹在 [MIN, cap]；cap = min(MAX, round(layoutW)-480)，layoutW
// 非有限或 ≤0 时 cap=MAX——隐藏态恢复不塌到下限）。
export function treeWidthClamp(px, layoutW) {
  const cap = Number.isFinite(layoutW) && layoutW > 0
    ? Math.min(CODE_TREE_WIDTH_MAX, Math.max(CODE_TREE_WIDTH_MIN, Math.round(layoutW) - 480))
    : CODE_TREE_WIDTH_MAX;
  const n = Number(px);
  if (!Number.isFinite(n)) return CODE_TREE_WIDTH_DEFAULT;
  return Math.min(cap, Math.max(CODE_TREE_WIDTH_MIN, Math.round(n)));
}

// parseTreeWidthStored(raw, layoutW)：localStorage 恢复——parseInt 容忍
// 后缀（"320px"），非法/空 → 默认 240，之后走同一 clamp 收敛。
export function parseTreeWidthStored(raw, layoutW) {
  const n = parseInt(raw, 10);
  if (!Number.isFinite(n)) return CODE_TREE_WIDTH_DEFAULT;
  return treeWidthClamp(n, layoutW);
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    buildCodeTree,
    fileIconHTML,
    codeTreeHTML,
    codeGutterLineHTML,
    codeLineNumbersHTML,
    highlightCodeLines,
    codeViewHTML,
    outlineHTML,
    outlineEmptyHTML,
    searchListHTML,
    fileFindFilter,
    treeWidthClamp,
    parseTreeWidthStored,
    CODE_TREE_WIDTH_MIN,
    CODE_TREE_WIDTH_MAX,
    CODE_TREE_WIDTH_DEFAULT,
    TREE_CHANGE_NEW,
    TREE_CHANGE_MODIFIED,
  });
}
