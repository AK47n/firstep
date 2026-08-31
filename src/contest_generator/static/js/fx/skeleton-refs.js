// fx/skeleton-refs.js — 骨架引用模块锚定纯函数（工单 mainc-codeview-bridge/04）
//
// 从骨架文本静态提取「模块风格调用」（<slug>_init / <slug>_read / <slug>_update…
// 形态 = ident( 且 ident === slug 或 slug + "_" 前缀）并与已选模块匹配——
// 让步骤 8 的骨架调用与模块库建立可点击的锚定（生成前上下文的一环）。
// best-effort：注释 / 字符串 / 关键字不误收；无命中返回空（宁少标不错标）。
// 模块约定见 fx/core.js 头部。
import { esc } from "./core.js";

// C 控制关键字：后随 ( 但不构成调用的词（if/for/while/switch…）
const KEYWORDS = new Set([
  "if", "for", "while", "switch", "sizeof", "return",
  "do", "else", "case", "default", "goto", "catch",
]);

const isIdentStart = (c) => /[A-Za-z_]/.test(c);
const isIdentChar = (c) => /[A-Za-z0-9_]/.test(c);

// skeletonModuleRefs(mainC, slugs)：扫描 mainC 文本，返回 [{slug, ident}]
// 命中列表——每 slug 只保留首次命中（去重、按骨架出现顺序）；slugs 非数组 /
// 含非字符串自动过滤；mainC 为 null/undefined 防御为空串（返回 []）。
export function skeletonModuleRefs(mainC, slugs) {
  const slugList = Array.isArray(slugs)
    ? slugs.filter((s) => typeof s === "string" && s)
    : [];
  if (!slugList.length) return [];
  const text = String(mainC || "");
  const n = text.length;
  const hits = [];
  const seen = new Set();
  let state = "code";  // code | line | block | str | chr（注释/字符串状态机）
  let i = 0;
  while (i < n) {
    const c = text[i];
    const d = i + 1 < n ? text[i + 1] : "";
    if (state === "code") {
      if (c === "/" && d === "/") { state = "line"; i += 2; continue; }
      if (c === "/" && d === "*") { state = "block"; i += 2; continue; }
      if (c === '"') { state = "str"; i += 1; continue; }
      if (c === "'") { state = "chr"; i += 1; continue; }
      if (isIdentStart(c)) {
        let j = i + 1;
        while (j < n && isIdentChar(text[j])) j += 1;
        const ident = text.slice(i, j);
        if (text[j] === "(" && !KEYWORDS.has(ident)) {
          for (const slug of slugList) {
            if (seen.has(slug)) continue;
            if (ident === slug || ident.startsWith(slug + "_")) {
              seen.add(slug);
              hits.push({ slug, ident });
              break;
            }
          }
        }
        i = j;
        continue;
      }
      i += 1;
      continue;
    }
    if (state === "line") {
      if (c === "\n") state = "code";
      i += 1;
      continue;
    }
    if (state === "block") {
      if (c === "*" && d === "/") { state = "code"; i += 2; }
      else i += 1;
      continue;
    }
    // str / chr
    const quote = state === "str" ? '"' : "'";
    if (c === "\\") { i += 2; continue; }   // 转义跳过下一字符
    if (c === quote) state = "code";
    i += 1;
  }
  return hits;
}

// skeletonRefsHTML(refs)：chips 标记（slug 主标签 + 首个命中调用作 reason 副文）；
// 空 → 空串（调用方隐藏容器）。data-skeleton-ref 供点击委托开模块详情弹窗。
export function skeletonRefsHTML(refs) {
  if (!Array.isArray(refs) || !refs.length) return "";
  return '<span class="muted skeleton-refs-label">骨架引用的模块：</span>'
    + refs.map((r) =>
      '<button type="button" class="chip rec skeleton-ref-chip" data-skeleton-ref="'
      + esc(r.slug) + '" title="查看模块 ' + esc(r.slug) + ' 详情（元数据 + 源码）">'
      + esc(r.slug) + '<span class="reason">' + esc(r.ident) + "</span></button>"
    ).join("");
}
