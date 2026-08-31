// ui/module-source.js — 模块详情弹窗源码区胶水（工单 mainc-codeview-bridge/05）
//
// 弹窗文件清单行（data-mi-file，moduleInfoHTML 渲染）点击 → GET
// /api/modules/{slug}/files/{path} 懒加载 → 渲染行号 + 高亮源码（codeViewHTML
// 与代码查看器同观感）+ 大小+只读标注；memo 缓存（业务 400 缓存、网络/≥500
// 不缓存可重试——对偶代码查看器 loadCodeFileState 先例）。弹窗主体零写侧。
// 纯函数在 fx/codeview.js（codeViewHTML）/ fx/highlight.js（languageOf）。
// 状态：cache 模块私有（Map，会话级）；每次绑定独立监听（重复打开替换弹窗）。
import { apiGet } from "/js/app.js";
import { esc, formatSize } from "/js/fx/core.js";
import { languageOf } from "/js/fx/highlight.js";
import { codeViewHTML } from "/js/fx/codeview.js";

const cache = new Map();  // key = slug + "\u0000" + path → HTML 字符串（含错误态；与代码查看器同缓存口径）

function moduleFileURL(slug, path) {
  return "/api/modules/" + encodeURIComponent(slug) + "/files/"
    + String(path).split("/").map(encodeURIComponent).join("/");
}

function sourceHTML(data) {
  const path = data.path || "";
  const content = (data.content != null) ? String(data.content) : "";
  return '<div class="module-source-head">' + esc(path)
    + '<span class="muted"> · ' + formatSize(data.size_bytes) + "（只读）</span></div>"
    + '<div class="code-view">' + codeViewHTML(content, languageOf(path)) + "</div>";
}

async function loadModuleSource(slot, slug, path) {
  const key = slug + "\u0000" + path;
  slot.hidden = false;
  if (cache.has(key)) { slot.innerHTML = cache.get(key); return; }
  slot.innerHTML = '<div class="module-source-head">' + esc(path)
    + '<span class="muted"> 加载中…</span></div>';
  try {
    const data = await apiGet(moduleFileURL(slug, path));
    const html = sourceHTML(data);
    cache.set(key, html);
    slot.innerHTML = html;
  } catch (e) {
    const errHtml = '<div class="module-source-head">' + esc(path) + "</div>"
      + '<div class="module-source-error error">加载失败：' + esc(e.message)
      + '</div><span class="muted">点击文件可重试。</span>';
    if (e.status && e.status < 500) cache.set(key, errHtml);
    slot.innerHTML = errHtml;
  }
}

// bindModuleSource(modal, slug)：绑定弹窗内全部平台段的文件清单点击委托
//（多平台各段自己的 .mi-files）+ 共享源码槽；槽缺失静默跳过。
export function bindModuleSource(modal, slug) {
  const slot = modal.querySelector("[data-module-source]");
  if (!slot) return;
  modal.querySelectorAll(".mi-files").forEach((filesBox) => {
    filesBox.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-mi-file]");
      if (btn) loadModuleSource(slot, slug, btn.dataset.miFile);
    });
  });
}
