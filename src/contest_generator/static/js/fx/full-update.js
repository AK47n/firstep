// fx/full-update.js — 完整包（整份 firstep）更新纯函数（工单 full-download/05）
//
// 展示层单源：设置页「完整包」区结果卡（未知版本 / 有新版本 / 已是最新 /
// 各类降级）、确认弹窗、下载进度（总进度条 + 当前卷 + 速度 + 剩余时间 + 分卷
// 列表）、终态文案（完成提示重启 / 取消说明已完成卷保留 / 失败可重试）。
// 后端契约见 src/contest_generator/full_update.py 与 full_task.py。
//
// 下载抗断的状态面（工单 resumable-download/05）：三种「进度条不动」必须长得不一样——
// **慢**（速度低 → 明写「网络较慢」）／**在重试**（`retrying` → 明写第几次、从多少接着下）
// ／**真失败**（`error_kind` 选话术）。分类只认 `error_kind` 字段，**不许解析 error 文案**。
import {
  esc, formatSize, fmtEta, downloadedPercent,
  downloadFailureText, retryProgressText, retryNoteText, SLOW_SPEED_BPS,
} from "./core.js";

/** 体积 + 卷数的中文描述（下载前估算用；0 = 未知）。 */
export function fullPlanText(totalBytes, partCount) {
  const total = Number(totalBytes) || 0;
  const count = Number(partCount) || 0;
  if (total <= 0) return "体积未知";
  const sizeText = total >= 1024 * 1024 * 1024
    ? (total / 1024 / 1024 / 1024).toFixed(1) + " GB"
    : Math.round(total / 1024 / 1024) + " MB";
  return count > 0 ? `${sizeText} · ${count} 卷` : sizeText;
}

/** 检查结果 → 设置页「完整包」区 HTML（无更新也保留主动重下入口）。 */
export function fullCheckCardHTML(check) {
  const plan = fullPlanText(check && check.total_bytes, (check && check.parts || []).length);
  if (check && check.error) {
    const fallback = "检查完整包更新失败，请稍后重试";
    return `<div class="error">${esc(check.message || fallback)}</div>`;
  }
  const latest = (check && check.latest_version) || "?";
  const current = (check && check.current_version) || "";
  const anchor = `<button id="btn-full-download" type="button" class="primary breathe" data-ico="download">下载完整 firstep</button>`;
  if (check && check.update_available) {
    const from = current ? `当前 ${esc(current)} → ` : "";
    return `<div class="update-result">
      <div>发现完整包：<b>${esc(latest)}</b>（${from}${esc(plan)}）
        ${anchor}
      </div>
      <div class="muted" style="margin-top:var(--space-1)">${esc((check && check.message) || "")}</div>
      <div class="muted" style="margin-top:var(--space-1)">完整包 = 工具本体 + 五个库 + 电赛资料库内容（不含装机用的第三方安装包）；下载完成后工具会自动替换并重启，配置与已生成工程保留。</div>
    </div>`;
  }
  return `<div class="update-result">
    <div class="ok">已是最新完整包（${esc(current || latest)}）</div>
    <div class="muted" style="margin-top:var(--space-1)">如需修复损坏或换机器，可重新下载完整包（${esc(plan)}）：
      ${anchor}
    </div>
  </div>`;
}

/** 确认弹窗内容（extra 传给弹窗骨架）：说明体积 / 卷数 / 重启语义。 */
export function fullConfirmHTML(check) {
  const version = (check && check.latest_version) || "";
  const plan = fullPlanText(check && check.total_bytes, (check && check.parts || []).length);
  return `<div class="full-confirm">
    <div>将下载完整 firstep${version ? ` <b>${esc(version)}</b>` : ""}：<b>${esc(plan)}</b></div>
    <div class="muted" style="margin-top:var(--space-1)">下载完成后工具会停止、替换到新版本并自动重启（DeepSeek key、任务状态、对话记录、已生成工程与电赛资料库都保留）。</div>
    <div class="muted" style="margin-top:var(--space-1)">中途可取消或关掉页面：已下载校验通过的卷不会重下。</div>
    <div class="row" style="margin-top:var(--space-2)">
      <button type="button" class="primary breathe" id="btn-full-start" data-ico="download">开始下载</button>
    </div>
  </div>`;
}

/** 状态文案（无对应 = 空串）。 */
export function fullStateText(state) {
  return {
    idle: "等待开始…",
    downloading: "正在下载完整包…",
    applying: "下载完成，正在替换并重启工具…",
    done: "完整包已应用，工具即将重启",
    failed: "完整包下载失败",
    cancelled: "已取消",
  }[state] || "";
}

/** 终态结果文案（非终态 = 空串）。 */
export function fullResultText(status) {
  const state = (status && status.state) || "";
  if (state === "done") {
    const version = (status && status.version) || "";
    // 「它自己扛过去了」这件事要留痕：用户中途看到的失败/重试不是白发生的
    const retryNote = retryNoteText(status && status.retry_count);
    return `完整包更新完成${version ? `（${version}）` : ""}${retryNote}，工具即将重启；若没有自动打开，请双击 start-app.vbs。`;
  }
  if (state === "cancelled") {
    return "已取消下载；已经下载并校验通过的卷会保留，下次重试不用重下。";
  }
  return "";
}

/** 进度视图（status = /api/update/full/status 轮询结果）。 */
export function fullProgressHTML(status) {
  const s = status || {};
  const total = s.total_bytes || 0;
  const done = s.total_downloaded_bytes || 0;
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
  const speed = s.speed_bps || 0;
  const speedText = speed > 0 ? (speed / 1024 / 1024).toFixed(1) + " MB/s" : "—";
  // 剩余时间说人话（「约 12 分钟」），弱网时另加一句「网络较慢」——
  // 让「慢」与「卡死」在界面上长得不一样（两者都是进度条不动）
  const remainText = speed > 0 && total > done
    ? fmtEta((total - done) / speed) : "…";
  const slowNote = speed > 0 && speed < SLOW_SPEED_BPS ? " · 网络较慢" : "";
  const parts = (s.parts || []).map((p) => {
    const pTotal = p.total_bytes || 0;
    const pPct = pTotal > 0 ? Math.min(100, Math.round(((p.downloaded_bytes || 0) / pTotal) * 100)) : 0;
    const mark = p.ok ? " ✓" : "";
    return `<div class="materials-part-row">
      <span class="materials-part-name">${esc(p.name)}${mark}</span>
      <span class="materials-part-meta">${pPct}%</span>
    </div>`;
  }).join("");
  const current = s.current_part_name
    ? `<div class="muted">当前卷：${esc(s.current_part_name)}</div>` : "";
  // 退避等待中：明写「正在自动重试（第 N 次）」，把「等」与「下」分开
  const retryLine = s.retrying
    ? `<div class="warning">${esc(retryProgressText(s.retry_count, s.message, s.resume_percent))}</div>`
    : "";
  const retrying = ["downloading", "applying"].includes(s.state);
  // 校验失败**不给「重试」按钮**：文案刚说完「重下也不会有变化」，再摆一个重试按钮
  // 就是自相矛盾（用户会一直点）。仍可点「检查更新」重新走一遍。
  const canRetry = s.state === "failed" && (s.error_kind || "") !== "verify";
  const actions = retrying
    ? `<div class="row" style="margin-top:var(--space-2)">
        <button id="btn-full-cancel" type="button" data-ico="stop">取消</button>
        <span class="muted">可在后台继续，页面关闭不影响下载</span>
      </div>`
    : canRetry
      ? `<div class="row" style="margin-top:var(--space-2)">
          <button id="btn-full-retry" type="button" data-ico="download">重试（已完成卷跳过）</button>
        </div>`
      : "";
  // 失败：话术按 `error_kind` 分（verify 与网络两类），原始 error 只作补充明细
  const failureLine = s.state === "failed"
    ? `<div class="error">${esc(downloadFailureText(s))}</div>
       ${s.error ? `<div class="muted">${esc(s.error)}</div>` : ""}`
    : "";
  const resultLine = fullResultText(s) ? `<div class="ok">${esc(fullResultText(s))}</div>` : "";
  return `<div class="materials-progress">
    <div class="ok">${esc(fullStateText(s.state))}</div>
    <div class="progress"><div class="progress-fill" style="width:${pct}%"></div></div>
    <div class="muted" style="margin:var(--space-1) 0">${formatSize(done)} / ${formatSize(total)}（${pct}%）· 速度 ${speedText}${slowNote} · ${remainText}</div>
    ${current}
    ${retryLine}
    ${failureLine}
    ${resultLine}
    ${parts}
    ${actions}
  </div>`;
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    fullCheckCardHTML,
    fullConfirmHTML,
    fullProgressHTML,
    fullStateText,
    fullResultText,
    fullPlanText,
  });
}
