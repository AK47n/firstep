// fx/fix-rows.js —— 修复结果行 HTML（工单 code-ide-ai/06）。
// 纯函数无副作用：apply_result / 最终列表共用同一行结构（此前生成页 onApply
// 与 fixRenderResults 各建一次——抽共享后两壳层复用；行内文案与 .fix-row /
// .fix-tag / .fix-file / .fix-msg 结构保持与既有 CSS 一致）。
import { esc } from "./core.js";

/** fixRowHTML({file, line, status, reason}) → 修复结果行 HTML 字符串。
 * 直接 innerHTML 插入（内容已 esc）；行点击跳转由调用方绑定（fx 不碰 DOM）。
 * status: "applied" → 已修复/fixed；其他 → 跳过/skipped。 */
export function fixRowHTML(item) {
  const applied = item && item.status === "applied";
  const file = (item && (item.file || item.path)) || "?";
  const line = item && item.line ? ":" + item.line : "";
  return '<div class="fix-row"><span class="fix-tag ' + (applied ? "fixed" : "skipped")
    + '">' + (applied ? "已修复" : "跳过")
    + '</span><span class="fix-file">' + esc(file + line)
    + '</span><span class="fix-msg">' + esc((item && item.reason) || "") + "</span></div>";
}

// window 同名桥（fx/*.js 模块约定兼容层——探针/devtools 取用）
if (typeof window !== "undefined") Object.assign(window, { fixRowHTML });
