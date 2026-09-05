// fx/update.js — 应用内一键更新纯函数（工单 auto-update/06）
//
// 展示层单源：检查更新结果卡（有新版 / 已最新 / 网络失败 / 无资产）与
// 更新状态卡（applying / failed / done）都从这里出 HTML，ui/update.js
// 只做 fetch 与事件接线。后端契约见 src/contest_generator/update.py 与
// webapp.py 的 /api/update/check、/api/update/status。
import { esc } from "./core.js";

/** 状态 → 短文案（轮询与结果卡通用）。 */
const UPDATE_STATE_TEXT = {
  idle: "",
  applying: "更新进行中，完成后工具将自动重启",
  failed: "上次更新未完成",
  done: "更新完成",
};

export function updateStateText(state) {
  return UPDATE_STATE_TEXT[state] || "";
}

/** 检查更新结果卡（check = /api/update/check 契约）。
 *  error=network / no-asset → 中文提示（200 级，不弹错）；有新版 → 版本 /
 *  大小 / 说明 + 「一键更新」按钮；无新版 → 已是最新。 */
export function updateCheckCardHTML(check) {
  if (check.error === "network") {
    return `<div class="error">${esc(check.message || "检查更新失败（网络原因）")}</div>`;
  }
  if (check.error === "no-asset") {
    return `<div class="muted">${esc(check.message || "最新版本没有发布更新包")}（最新：${esc(check.latest_version || "?")}）</div>`;
  }
  const latest = check.latest_version || "?";
  if (!check.update_available) {
    return `<div class="ok">已是最新版本 v${esc(latest)}</div>`;
  }
  const mb = Math.round((check.size_bytes || 0) / 1024 / 1024);
  const notes = (check.release_notes || "").trim().split(/\n+/)
    .filter(Boolean).slice(0, 3)
    .map((line) => `<div>${esc(line)}</div>`).join("");
  return `<div class="update-result">
    <div>发现新版本：<b>v${esc(latest)}</b>（当前 v${esc(check.current_version || "?")}，更新包约 ${mb} MB）</div>
    ${notes ? `<div class="muted" style="margin-top:var(--space-1)">${notes}</div>` : ""}
    <div class="row" style="margin-top:var(--space-2);align-items:center">
      <button id="btn-update-apply" type="button" class="primary breathe" data-ico="download">一键更新</button>
      <span class="muted">下载约 ${mb} MB；配置与资料库自动保留，完成后自动重启</span>
    </div>
  </div>`;
}

/** 更新状态卡（status = /api/update/status 契约轮询结果）。 */
export function updateStatusHTML(status) {
  const state = status.state || "idle";
  if (state === "applying") {
    return `<div class="ok">更新进行中，完成后工具将自动重启…</div>`;
  }
  if (state === "failed") {
    const err = (status.result && status.result.error) || status.message || "更新失败";
    return `<div class="error">更新失败：${esc(err)}（备份已保留，可重新下载更新包）</div>`;
  }
  if (state === "done") {
    const result = status.result || {};
    if (result.status === "ok") {
      return `<div class="ok">已更新到 ${esc(result.version || "")}，浏览器将自动重新打开</div>`;
    }
    return `<div class="error">上次更新失败：${esc(result.error || "未知原因")}（备份：${esc(result.backup_dir || "")}）</div>`;
  }
  return "";
}
