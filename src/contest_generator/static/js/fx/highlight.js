// fx/highlight.js — 轻量语法高亮纯函数（工单 master-library-ui-2/03）
//
// 语言判定 + XML token 化 + 分发（C 复用 fx/code.js 的 cHighlight 单源——
// main.c 工具轮已实现同款 C 高亮，不再复制一份）。约定：先切 token 后逐段
// 转义再拼 HTML（杜绝注入，任何原文进 DOM 前必经 esc）；纯展示、不解释
// 代码；esc 单源取自 fx/core.js。模块约定见 fx/core.js 头部。
import { esc } from "./core.js";
import { cHighlight } from "./code.js";

// 高亮回退上限：超过即整段纯文本（esc）。工单 code-page-vscode-overhaul/09：
// 滚动窗口化（08）后高亮只按窗口行渲染、整段 highlightText 是 O(n) 线性
// （实测 267KB ≈ 0.3ms），阈值从 128KB 放宽到 1MB——5000 行 .c 保持真彩色。
export const HIGHLIGHT_MAX_BYTES = 1024 * 1024;

// languageOf(path)：按扩展名判定语言——.c/.h → C；.md/.markdown → md
// （工单 code-viewer-md-preview/01：预览路由）；.syscfg/.uvprojx/.cproject/
// .xml → XML；其余 plain。扩展名取最后一段（小写比较，大小写不敏感）；
// 无扩展名 / 空路径 → plain。
export function languageOf(path) {
  const ext = String(path == null ? "" : path).toLowerCase().split(".").pop();
  if (ext === "c" || ext === "h") return "c";
  if (ext === "md" || ext === "markdown") return "md";   // 工单 code-viewer-md-preview/01：预览路由
  if (ext === "syscfg" || ext === "uvprojx" || ext === "cproject" || ext === "xml") {
    return "xml";
  }
  return "plain";
}

// highlightXml(text)：XML 家族 token 高亮——注释 / CDATA / 声明与 PI /
// 标签名 / 属性名 / 引号值分类着色（tok-com / tok-str / tok-pre / tok-tag /
// tok-attr / tok-val），文本与符号逐段 esc。轻量实现：不校验合法性，
// 只做确定性 token 化（坏 XML 也不会崩、不会泄漏原文）。
export function highlightXml(text) {
  const src = String(text == null ? "" : text);
  let html = "";
  let i = 0;
  const n = src.length;
  while (i < n) {
    const ch = src[i];
    if (ch !== "<") {
      html += esc(ch);
      i++;
      continue;
    }
    if (src.startsWith("<!--", i)) {                       // 注释
      let j = src.indexOf("-->", i + 4);
      j = j < 0 ? n : j + 3;
      html += '<span class="tok-com">' + esc(src.slice(i, j)) + "</span>";
      i = j;
    } else if (src.startsWith("<![CDATA[", i)) {           // CDATA
      let j = src.indexOf("]]>", i + 9);
      j = j < 0 ? n : j + 3;
      html += '<span class="tok-str">' + esc(src.slice(i, j)) + "</span>";
      i = j;
    } else if (src.startsWith("<?", i)) {                  // 声明 / PI
      let j = src.indexOf("?>", i + 2);
      j = j < 0 ? n : j + 2;
      html += '<span class="tok-pre">' + esc(src.slice(i, j)) + "</span>";
      i = j;
    } else if (src[i + 1] === "!") {                       // DOCTYPE 等声明
      let j = src.indexOf(">", i);
      j = j < 0 ? n : j + 1;
      html += '<span class="tok-pre">' + esc(src.slice(i, j)) + "</span>";
      i = j;
    } else if (src[i + 1] === "/") {                       // 闭标签：整段含 >
      let j = i + 2;
      while (j < n && /[A-Za-z0-9_:\-]/.test(src[j])) j++;
      if (src[j] === ">") j++;
      html += '<span class="tok-tag">' + esc(src.slice(i, j)) + "</span>";
      i = j;
    } else if (/[A-Za-z_]/.test(src[i + 1] || "")) {       // 开标签
      let j = i + 1;
      while (j < n && /[A-Za-z0-9_:\-]/.test(src[j])) j++;
      html += '<span class="tok-tag">' + esc(src.slice(i, j)) + "</span>";
      i = j;
      while (i < n && src[i] !== ">") {                    // 属性区
        if (/\s/.test(src[i])) {
          html += esc(src[i]);
          i++;
          continue;
        }
        let k = i;
        while (k < n && /[A-Za-z0-9_:\-]/.test(src[k])) k++;
        if (k === i) {                                     // 裸符号（/ 等）
          html += esc(src[i]);
          i++;
          continue;
        }
        html += '<span class="tok-attr">' + esc(src.slice(i, k)) + "</span>";
        i = k;
        let m = i;
        while (m < n && /\s/.test(src[m])) m++;
        if (src[m] === "=") {
          html += esc(src.slice(i, m + 1));
          i = m + 1;
          let q = i;
          while (q < n && /\s/.test(src[q])) q++;
          const quote = src[q];
          if (quote === '"' || quote === "'") {
            let e = src.indexOf(quote, q + 1);
            e = e < 0 ? n : e + 1;
            html += '<span class="tok-val">' + esc(src.slice(q, e)) + "</span>";
            i = e;
          }
        }
      }
      if (i < n) {
        html += esc(src[i]);                               // 闭标签 >
        i++;
      }
    } else {
      html += esc(ch);
      i++;
    }
  }
  return html;
}

// highlightText(text, lang)：按语言分发高亮并回退——C = cHighlight（单源）
// / XML = highlightXml / 其余 = esc 纯文本；超过 HIGHLIGHT_MAX_BYTES 一律
// 纯文本（先测字节数，避免为超限文件做无谓着色；中文注释按 UTF-8 字节计）。
export function highlightText(text, lang) {
  const src = String(text == null ? "" : text);
  if (utf8Bytes(src) > HIGHLIGHT_MAX_BYTES) return esc(src);
  if (lang === "c") return cHighlight(src);
  if (lang === "xml") return highlightXml(src);
  return esc(src);
}

// ---- 行级跨行态（窗口化编辑器逐行惰性高亮的上下文）----
// 窗口化代码编辑器逐行惰性高亮（工单 code-editor-opt/06）不能感知跨行 token
// ——块注释 / 跨行字符串 / XML 注释 CDATA 的承接行被当普通代码着色（用户现场：
// 多行 /* */ 注释只有首行生效）。本组纯件补上行级上下文：
//   lineStatesOf：一次 O(n) 扫出每行「起始跨行态」（行 i 的起始态 = 行 0..i-1
//   的跨行段延续结果；行自身内容不影响自身起始态）；
//   highlightLineHTML：按起始态渲染单行——行内新开的跨行段由单行完整高亮器
//   承接（cHighlight/highlightXml 对未闭合段一直渲染到输入尾），与整段渲染
//   「在行界闭合并重开」等价（highlightCodeLines 全量语义），逐行结果应与
//   highlightCodeLines(全文) 严格一致（单测对拍）。
// 跨行态形状：C = {comment, quote}（quote = null | '"' | "'"）；XML =
// {comment, cdata, pi, doctype}；plain/md 恒 null。

function _cLineEndState(line, st) {
  const src = String(line == null ? "" : line);
  const n = src.length;
  let comment = !!(st && st.comment);
  let quote = st && st.quote ? st.quote : null;
  let i = 0;
  while (i < n) {
    if (comment) {
      const j = src.indexOf("*/", i);       // 与 cHighlight 同语义：不嵌套
      if (j < 0) break;                     // 行内未闭合 → 跨行态保持
      comment = false;
      i = j + 2;
      continue;
    }
    if (quote) {
      const ch = src[i];
      if (ch === "\\") { i += 2; continue; }   // 转义跳过下一字符（同 cHighlight）
      if (ch === quote) { quote = null; i++; continue; }
      i++;
      continue;
    }
    const ch = src[i];
    if (ch === "/" && src[i + 1] === "/") break;    // 行注释：余下无跨行态
    if (ch === "/" && src[i + 1] === "*") { comment = true; i += 2; continue; }
    if (ch === '"' || ch === "'") { quote = ch; i++; continue; }
    i++;
  }
  return { comment, quote };
}

function _xmlLineEndState(line, st) {
  const src = String(line == null ? "" : line);
  const n = src.length;
  let comment = !!(st && st.comment);
  let cdata = !!(st && st.cdata);
  let pi = !!(st && st.pi);
  let doctype = !!(st && st.doctype);
  let i = 0;
  while (i < n) {
    if (comment) {
      const j = src.indexOf("-->", i);
      if (j < 0) break;
      comment = false;
      i = j + 3;
      continue;
    }
    if (cdata) {
      const j = src.indexOf("]]>", i);
      if (j < 0) break;
      cdata = false;
      i = j + 3;
      continue;
    }
    if (pi) {
      const j = src.indexOf("?>", i);
      if (j < 0) break;
      pi = false;
      i = j + 2;
      continue;
    }
    if (doctype) {
      const j = src.indexOf(">", i);
      if (j < 0) break;
      doctype = false;
      i = j + 1;
      continue;
    }
    const ch = src[i];
    if (ch === "<" && src.startsWith("<!--", i)) { comment = true; i += 4; continue; }
    if (ch === "<" && src.startsWith("<![CDATA[", i)) { cdata = true; i += 9; continue; }
    if (ch === "<" && src.startsWith("<?", i)) { pi = true; i += 2; continue; }
    if (ch === "<" && src[i + 1] === "!") { doctype = true; i += 2; continue; }
    i++;
  }
  return { comment, cdata, pi, doctype };
}

export function lineEndState(line, state, lang) {
  if (lang === "c") return _cLineEndState(line, state);
  if (lang === "xml") return _xmlLineEndState(line, state);
  return null;
}

export function lineStatesOf(lines, lang) {
  const src = lines || [];
  const out = new Array(src.length);
  let st = null;
  for (let i = 0; i < src.length; i++) {
    out[i] = st;
    st = lineEndState(src[i], st, lang);
  }
  return out;
}

// stateEq(a, b)：跨行态浅比较（null 与 {…} 两种形态）——lineStatesRefresh
// 早停判定；导出供单测复用同一判定（单源，防测试与实现判定漂移）。
export function stateEq(a, b) {
  if (a === b) return true;
  if (!a || !b) return false;
  const ka = Object.keys(a);
  const kb = Object.keys(b);
  return ka.length === kb.length && ka.every((k) => a[k] === b[k]);
}

// lineStatesRefresh(lines, states, fromIdx, lang, changedEndIdx?)：编辑后**增量
// 续算**逐行起始跨行态（工单 editor-line-state-opt/01）。约定：lines[fromIdx,
// changedEndIdx) 行文本已按新内容落位（行数不变；changedEndIdx 缺省 = n，即
// 保守到文末——正确但无早停），states 仍是编辑前的旧起始态（fromIdx 行自身的
// 起始态由前面行决定，不受本行编辑影响；其后每行起始态 = 上一行新文本的终止态）。
// 原地写 states[k+1]（k ≥ fromIdx），返回**首个起始态变化的行索引**
// （0 基；-1 = 无变化）——调用方据此作废该行起的惰性高亮缓存。
// 早停论据（归纳）：行 k+1 的起始态是「行 k 文本 + 行 k 起始态」的唯一函数；
// 若某行新终止态与旧起始态相等，则该行起始态未变；**且 k+1 已越过变更区**
// （k+1 ≥ changedEndIdx——其后各行文本又未变），故其后所有起始态必与旧值
// 全等——继续扫描只会重复写相同值。变更区内部不得早停：区内行文本已变，
// 即使某行起始态碰巧未变，其**终止态**也可能改变后续行（评审实测案例：
// 多行替换 [2,4) 中第 3 行新开 `/*`，若在区内收敛会漏掉其后注释承接行）。
// 常见输入（单行字符增删不碰注释/字符串跨行结构）changedEndIdx = fromIdx+1，
// 第 1 行即收敛：成本 O(受影响跨行段行数) 而非 O(剩余行数)。fromIdx 越界 /
// 空数组 → -1 不改动。
export function lineStatesRefresh(lines, states, fromIdx, lang, changedEndIdx) {
  const src = lines || [];
  const st = states || [];
  const n = src.length;
  if (!n || fromIdx < 0 || fromIdx >= n) return -1;
  const to = changedEndIdx == null
    ? n
    : Math.max(fromIdx + 1, Math.min(n, changedEndIdx | 0));
  let changed = -1;
  for (let k = fromIdx; k < n - 1; k++) {
    const next = lineEndState(src[k], st[k], lang);
    const old = st[k + 1];
    st[k + 1] = next;
    if (k + 1 >= to && stateEq(old, next)) break;   // 越区且收敛：其后全等
    if (changed < 0 && !stateEq(old, next)) changed = k + 1;
  }
  return changed;
}

function _cLineHTML(line, st) {
  const src = String(line == null ? "" : line);
  const n = src.length;
  if (st && st.quote) {
    // 行首在未闭合字符串中：前缀（到闭引号或行尾）整体 tok-str，
    // 其余交给 cHighlight 正常 token 化（其未闭合段渲染到行尾 = 本行正确）
    let i = 0;
    while (i < n) {
      const ch = src[i];
      if (ch === "\\") { i += 2; continue; }
      if (ch === st.quote) { i++; break; }
      i++;
    }
    const head = src.slice(0, i);
    return '<span class="tok-str">' + esc(head) + "</span>" + cHighlight(src.slice(i));
  }
  if (st && st.comment) {
    const j = src.indexOf("*/");
    const head = j < 0 ? src : src.slice(0, j + 2);
    const rest = j < 0 ? "" : src.slice(j + 2);
    return '<span class="tok-com">' + esc(head) + "</span>" + cHighlight(rest);
  }
  return cHighlight(src);
}

function _xmlLineHTML(line, st) {
  const src = String(line == null ? "" : line);
  if (st && st.comment) {
    const j = src.indexOf("-->");
    const head = j < 0 ? src : src.slice(0, j + 3);
    const rest = j < 0 ? "" : src.slice(j + 3);
    return '<span class="tok-com">' + esc(head) + "</span>" + highlightXml(rest);
  }
  if (st && st.cdata) {
    const j = src.indexOf("]]>");
    const head = j < 0 ? src : src.slice(0, j + 3);
    const rest = j < 0 ? "" : src.slice(j + 3);
    return '<span class="tok-str">' + esc(head) + "</span>" + highlightXml(rest);
  }
  if (st && st.pi) {
    const j = src.indexOf("?>");
    const head = j < 0 ? src : src.slice(0, j + 2);
    const rest = j < 0 ? "" : src.slice(j + 2);
    return '<span class="tok-pre">' + esc(head) + "</span>" + highlightXml(rest);
  }
  if (st && st.doctype) {
    const j = src.indexOf(">");
    const head = j < 0 ? src : src.slice(0, j + 1);
    const rest = j < 0 ? "" : src.slice(j + 1);
    return '<span class="tok-pre">' + esc(head) + "</span>" + highlightXml(rest);
  }
  return highlightXml(src);
}

export function highlightLineHTML(line, state, lang) {
  const src = String(line == null ? "" : line);
  if (lang === "c") return _cLineHTML(src, state);
  if (lang === "xml") return _xmlLineHTML(src, state);
  return highlightText(src, lang);
}

function utf8Bytes(text) {
  try {
    return new TextEncoder().encode(text).length;
  } catch {
    return text.length;  // 无 TextEncoder 的环境退化为码元数（仅影响边界）
  }
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    languageOf, highlightXml, highlightText, HIGHLIGHT_MAX_BYTES,
    lineEndState, lineStatesOf, lineStatesRefresh, highlightLineHTML,
  });
}
