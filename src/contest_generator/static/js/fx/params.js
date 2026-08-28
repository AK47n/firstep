// fx/params.js — 参数速调展示纯函数（工单 param-tune/02）：main.c 可调参数
// 表（识别结果）+ 改值应用结果面板（编译徽章 / diff / 备份回滚 / 烧录）。
// 数据形状 = 后端 /api/tasks/params/scan|apply|read 载荷（ParamItem{name,
// label, old_value, anchor, unit, range_hint, valid}）。共享件用 esc /
// truncate（fx/core.js）；diff 与烧录行复用时下模块（参数应用结果面板与
// 任务执行结果面板同构——diff 展示、备份回滚、烧录三者一致）。模块约定
// 见 fx/core.js 头部。
import { esc, truncate } from "./core.js";
import { mainDiffHTML } from "./diff.js";
import { flashPanelHTML } from "./flash.js";
import { verifyStatusMarkup } from "./task.js";

/** 参数表（spec 故事 2：参数一行一个，当前值可改、建议范围给参考）：
 * 每行 = 名称（slug）+ 含义 + 当前值输入框（默认值 = old_value）+ 建议范围
 * 提示；valid=false 行输入框禁用 + 「锚已失效」标记（main.c 已被改动，旧锚
 * 不再可靠——重新识别才有意义）；running = 一轮流程进行中（全部禁用）。
 * 空态两分支（opts.emptyScan，spec 轴评审整改）：未识别（false）→ 引导
 * 点「识别 main.c 参数」；已识别但无参数（true）→ 「未发现可调参数」。
 * 空态都带 data-param-empty 标记供胶水层查状态。
 *
 * id 契约（评审提示）：输入框 id = "params-input-<name>"——ui/params.js
 * 用 `$("params-input-" + name)` 重建（$ = getElementById，契约稳定）；
 * 改动 id 公式必须两处同步（fx 写 / ui 查）。
 */
export function paramListHTML(params, opts = {}) {
  const running = !!(opts && opts.running);
  if (!Array.isArray(params) || !params.length) {
    const scanned = !!(opts && opts.emptyScan);
    return '<div class="muted" data-param-empty="1">' + (scanned
      ? '已识别：未发现可调数值参数（当前 main.c 全是结构代码 / 字符串常量）'
        + '——如需调整请改代码后重新识别。'
      : '尚未识别参数——点上方「识别 main.c 参数」让 AI 扫描可调数值'
        + '（阈值 / 速度 / PID 系数 / 延时 / 占空比…）。')
      + "</div>";
  }
  const rows = params.map((p) => {
    const name = p && p.name ? String(p.name) : "";
    const label = p && p.label ? String(p.label) : "";
    const oldValue = p && p.old_value !== undefined && p.old_value !== null
      ? String(p.old_value) : "";
    const rangeHint = p && p.range_hint ? String(p.range_hint) : "";
    const unit = p && p.unit ? String(p.unit) : "";
    const valid = p && p.valid !== false;
    const disabled = running || !valid;
    const inputId = "params-input-" + name;
    const hint = [rangeHint, unit].filter(Boolean).map((s) => esc(s)).join("　");
    return '<div class="param-row' + (valid ? "" : " param-stale") + '">'
      + '<span class="slug">' + esc(name || "?") + "</span>"
      + '<span class="param-label">' + esc(label || oldValue || "—") + "</span>"
      + '<input class="param-input" id="' + esc(inputId) + '" type="text"'
      + ' value="' + esc(oldValue) + '"' + (disabled ? " disabled" : "")
      + ' title="当前值：' + esc(oldValue) + '" />'
      + (hint ? '<span class="muted param-hint">' + hint + "</span>" : "")
      + (valid
        ? '<button class="btn-params-apply" data-param-name="' + esc(name)
          + '"' + (running ? " disabled" : "") + ">改这个并验证</button>"
        : '<span class="badge param-stale-badge">锚已失效</span>')
      + "</div>";
  }).join("");
  return '<div class="param-table">' + rows + "</div>";
}

/** 应用结果面板（spec 故事 3/4：改值 → 备份 → 编译验证 → 可回滚 / 可烧录）：
 * 徽章 + 说明（verifyStatusMarkup 与任务结果面板同源）+ 备份回滚行 +
 * 烧录行（uid="params" 独立于任务卡与结果面板烧录容器）+ diff。
 * result 空 = 空串（防御）。 */
export function paramResultHTML(result, dir) {
  if (!result) return "";
  const markup = verifyStatusMarkup(result, {
    unverified: "未检测到编译工具链：参数已写入 main.c，但未经编译验证——请配置工具链后手动编译，或上板后人工确认。",
    failed: "编译验证未通过，参数已写入 main.c（已备份，可回滚）。",
  });
  const backupId = result.backup_id || "";
  return '<div class="item" style="margin-top:4px">'
    + '<div class="head"><span class="slug">⚙️ 参数修改结果</span> ' + markup.badge + "</div>"
    + '<div class="reason">' + markup.detail + "</div>"
    + (backupId
      ? '<div class="reason">备份：<span class="slug">' + esc(backupId)
        + '</span> · <button class="btn-params-rollback danger" data-backup="'
        + esc(backupId) + '">回滚本次参数修改</button></div>'
      : "")
    + flashPanelHTML(dir, "params")
    + mainDiffHTML(result.main_diff, "参数")
    + "</div>";
}

if (typeof window !== "undefined") {
  Object.assign(window, { paramListHTML, paramResultHTML });
}
