// ui/files.js — 动态文件行共用件（阶段 2 工单 06）
//
// 模块库（newModulePayload 弹窗「文件增删」）与参考库（editReference 文件增删）
// 共用的文件行 UI：行增删（addFileRow）/ 收集（collectFiles，重名 alert 返回
// null）/ 选择文件或文件夹读为文本（readPickedText / pickFilesInto）/ 选择器
// 绑定（bindFilePicker）。引用方 import 本模块；文件行绑定时机 = 调用方（弹窗
// 打开时）逐行绑定，顶部无跨域监听。
// 注：「文件名（含相对路径）」语义 + 二进制/超大跳过 + GBK 兜底同前端域约定。
import { $, toast } from "/js/app.js";
import { esc } from "/js/fx/core.js";

// 动态文件行（模块库 / 参考文件库共用；container 缺省为模块库的 #new-files）
export function addFileRow(container, name, content) {
  if (!container) container = $("new-files");
  const row = document.createElement("div");
  row.className = "file-row";
  row.innerHTML = `
    <input type="text" placeholder="文件名（含相对路径）" value="${esc(name || "")}">
    <div class="file-row-body">
      <textarea placeholder="文件内容（.c / .h / .txt / .md）">${esc(content || "")}</textarea>
      <button class="file-row-x danger">✕</button>
    </div>`;
  row.querySelector("button").addEventListener("click", () => row.remove());
  container.appendChild(row);
}

export function collectFiles(container) {
  if (!container) container = $("new-files");
  const files = {};
  for (const row of container.children) {
    const name = row.querySelector("input").value.trim();
    const content = row.querySelector("textarea").value;
    if (!name) continue;
    if (files[name] !== undefined) { toast("error", "文件名重复：" + name); return null; }
    files[name] = content;
  }
  return files;
}

// ===== 选择文件 / 文件夹 → 读为文本填入文件行（模块库 / 参考库共用）=====
// 文件名 = 相对路径（选文件夹时保留子目录，匹配"文件名（含相对路径）"语义）；
// 二进制（文件头含 NUL，与后端扫描同判据）与超大文件跳过不载入；老工程常见的
// GBK 源文件按 gbk 兜底解码。
const MAX_PICK_BYTES = 20 * 1024 * 1024;
export async function readPickedText(file) {
  const buf = await file.arrayBuffer();
  if (new Uint8Array(buf).subarray(0, 8192).includes(0)) return null;   // 二进制
  const text = new TextDecoder("utf-8", { fatal: false }).decode(buf);
  if (!text.includes("�")) return text;
  try { return new TextDecoder("gbk").decode(buf); } catch { return null; }
}
export async function pickFilesInto(input, container, msgEl) {
  const files = Array.from(input.files);
  input.value = "";
  if (!files.length) return;
  let loaded = 0, skipped = 0;
  for (const f of files) {
    if (f.webkitRelativePath && f.webkitRelativePath.split("/").includes(".git")) continue;
    if (f.size > MAX_PICK_BYTES) { skipped++; continue; }
    const text = await readPickedText(f);
    if (text === null) { skipped++; continue; }
    addFileRow(container, f.webkitRelativePath || f.name, text);
    loaded++;
  }
  msgEl.classList.remove("ok");
  msgEl.textContent = loaded
    ? "已载入 " + loaded + " 个文件" + (skipped ? "，跳过 " + skipped + " 个二进制 / 超大文件" : "")
    : "没有可载入的文本文件" + (skipped ? "（跳过 " + skipped + " 个二进制 / 超大文件）" : "");
  if (loaded) msgEl.classList.add("ok");
}
export function bindFilePicker(btnId, inputId, containerId, msgId) {
  const input = $(inputId);
  $(btnId).addEventListener("click", () => input.click());
  input.addEventListener("change", () => pickFilesInto(input, $(containerId), $(msgId)));
}
