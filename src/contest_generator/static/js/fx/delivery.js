// fx/delivery.js — 交付卡纯函数（工单 delivery-suite/02）：交付检查结果 /
// 打包结果渲染。检查结果的结构（stats / incomplete / message / ok）由后端
// delivery_check 下发；状态徽章文案复用 fx/task.js 单源（taskStatusLabel /
// taskStatusBadgeClass——避免重新维护一份状态→中文映射）。
import { esc, formatSize } from "./core.js";
import { taskStatusLabel, taskStatusBadgeClass } from "./task.js";

/** 交付卡按钮行（工单 delivery-suite/02）：打开工程 / 交付检查 / 一键打包。
 * busy = 任一交付动作进行中（或任务/参数流程占用共享闸）→ 三按钮全部禁用。
 * 按钮 id 与 index.html 静态占位无关——ui/delivery.js 渲染后重绑事件。 */
export function deliveryActionsHTML(busy) {
  const dis = busy ? " disabled" : "";
  return '<button id="btn-delivery-open" class="primary"' + dis
    + ' title="stm32 优先拉起 Keil（UV4），兜底打开文件夹；mspm0 打开文件夹（CCS 手动导入）">打开工程</button>'
    + ' <button id="btn-delivery-check" class="primary"' + dis + ">交付检查</button>"
    + ' <button id="btn-delivery-package" class="primary"' + dis + ">一键打包</button>";
}

/** 交付检查结果 HTML：完成度统计行 + 结论（✅/⚠）+ 未完成逐条列表。
 * result 空 / 未拆解清单（plan_present False）只有结论行；全部 esc。 */
export function deliveryCheckHTML(result) {
  if (!result) return "";
  const head = result.ok
    ? '<div class="delivery-ok">✅ ' + esc(result.message || "") + "</div>"
    : '<div class="delivery-warn">⚠ ' + esc(result.message || "") + "</div>";
  if (!result.plan_present || !result.stats) return head;  // 未拆解：只有提示
  const s = result.stats || {};
  const unfinished = (s.failed || 0) + (s.pending || 0)
    + (s.doing || 0) + (s.unverified || 0);
  const statRow = '<div class="delivery-stat-row">'
    + '<span class="badge ok">已验证 ' + (s.verified || 0) + "</span>"
    + '<span class="badge same">已跳过 ' + (s.skipped || 0) + "</span>"
    + '<span class="badge del">未完成 ' + unfinished + "</span>"
    + "</div>";
  const rows = (result.incomplete || []).map((item) =>
    '<div class="delivery-incomplete">'
    + '<span class="badge ' + taskStatusBadgeClass(item.status) + '">'
    + taskStatusLabel(item.status) + "</span>"
    + " " + esc(item.title)
    + ' <span class="slug">' + esc(item.id) + "</span></div>"
  ).join("");
  return statRow + head + rows;
}

/** 打包结果 HTML：zip 完整路径 + 大小 + 文件数（全部 esc）。空结果 → ""。 */
export function deliveryPackageHTML(result) {
  if (!result || !result.zip_path) return "";
  return '<div class="delivery-zip">📦 ' + esc(result.zip_path)
    + ' <span class="muted">（' + formatSize(result.size || 0)
    + " · " + (result.files || 0) + " 个文件）</span></div>";
}

if (typeof window !== "undefined") {
  Object.assign(window, { deliveryActionsHTML, deliveryCheckHTML, deliveryPackageHTML });
}
