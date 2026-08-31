// fx/highlight.js — 轻量语法高亮纯函数（工单 master-library-ui-2/03）
//
// 语言判定 + XML token 化 + 分发（C 复用 fx/code.js 的 cHighlight 单源——
// main.c 工具轮已实现同款 C 高亮，不再复制一份）。约定：先切 token 后逐段
// 转义再拼 HTML（杜绝注入，任何原文进 DOM 前必经 esc）；纯展示、不解释
// 代码；esc 单源取自 fx/core.js。模块约定见 fx/core.js 头部。
import { esc } from "./core.js";
import { cHighlight } from "./code.js";

// 高亮回退上限：超过即整段纯文本（esc）——大文件不浪费着色与转义
export const HIGHLIGHT_MAX_BYTES = 128 * 1024;

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

function utf8Bytes(text) {
  try {
    return new TextEncoder().encode(text).length;
  } catch {
    return text.length;  // 无 TextEncoder 的环境退化为码元数（仅影响边界）
  }
}

if (typeof window !== "undefined") {
  Object.assign(window, { languageOf, highlightXml, highlightText, HIGHLIGHT_MAX_BYTES });
}
