// fx/topic-preread.js — 步骤 2「赛题预读」展示层纯函数（工单 topic-preread/02）
//
// 数据契约（后端 /api/topic/preread 返回形状，机械校验已在后端 topic_preread
// 域完成）：{overview: string, reminders: [{steps: number[], text, quote}]}。
// 本模块只做展示组装：
//   prereadReminderGroups — 按步骤分组（一条提醒影响多步则每组同现；
//                           steps 为空的提醒归「其他限定」组放最后，组内保序）；
//   prereadGroupLabel     — 组标题（步骤名不硬编码：调用方经 stepNavTitles
//                           从 DOM h2 单源读取传入查表）；
//   prereadHTML           — 总览 + 分组提醒 + 题面引用小字的整段 HTML。
// 模块约定见 fx/core.js 头部。
import { esc } from "./core.js";

export const OTHER_GROUP_LABEL = "其他限定";

export function prereadReminderGroups(reminders) {
  const byStep = new Map();
  const other = [];
  for (const r of Array.isArray(reminders) ? reminders : []) {
    const item = { text: String((r && r.text) || ""), quote: String((r && r.quote) || "") };
    const steps = Array.isArray(r && r.steps)
      ? [...new Set(r.steps.filter((s) => Number.isInteger(s)))].sort((a, b) => a - b)
      : [];
    if (!steps.length) { other.push(item); continue; }
    for (const s of steps) {
      if (!byStep.has(s)) byStep.set(s, []);
      byStep.get(s).push(item);
    }
  }
  const groups = [...byStep.entries()].sort((a, b) => a[0] - b[0])
    .map(([step, items]) => ({ step, items }));
  if (other.length) groups.push({ step: null, items: other });
  return groups;
}

export function prereadGroupLabel(group, stepTitles) {
  if (group.step === null) return OTHER_GROUP_LABEL;
  const title = (stepTitles && stepTitles[group.step]) || "";
  return title ? `步骤 ${group.step} · ${title}` : `步骤 ${group.step}`;
}

export function prereadHTML(payload, stepTitles) {
  const overview = String((payload && payload.overview) || "");
  const out = [];
  if (overview) out.push(`<div class="preread-overview">${esc(overview)}</div>`);
  for (const group of prereadReminderGroups(payload && payload.reminders)) {
    out.push(`<div class="preread-group"><div class="preread-group-title">${esc(prereadGroupLabel(group, stepTitles))}</div>`);
    for (const item of group.items) {
      out.push(`<div class="preread-item"><div class="preread-text">${esc(item.text)}</div>`);
      if (item.quote) out.push(`<div class="preread-quote">题面原文：${esc(item.quote)}</div>`);
      out.push("</div>");
    }
    out.push("</div>");
  }
  return out.join("");
}

// 钉到步骤卡的提醒横幅（工单 topic-preread/03）：每卡只显该卡相关条目，
// 一条 = 提醒文本 + 题面引用小字（无引用省略）。样式见 index.html .preread-slot。
export function prereadSlotHTML(items) {
  const out = [];
  for (const item of Array.isArray(items) ? items : []) {
    const text = String((item && item.text) || "");
    if (!text) continue;
    out.push(`<div class="preread-slot-line">${esc(text)}`
      + (item && item.quote ? `<span class="preread-slot-quote">题面原文：${esc(String(item.quote))}</span>` : "")
      + "</div>");
  }
  return out.join("");
}

if (typeof window !== "undefined") {
  Object.assign(window, { prereadReminderGroups, prereadGroupLabel, prereadHTML, prereadSlotHTML, OTHER_GROUP_LABEL });
}
