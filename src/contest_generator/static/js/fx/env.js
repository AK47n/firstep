// fx/env.js — 环境体检纯函数（工单 frontend-es-modules/01，迁自 index.html 9711-9804）
// 行结构 data-env-row 标记；ch 参数 = null（待检查）| {ok:true,data} | {ok:false,msg}。
import { esc } from "./core.js";

export const ENV_BADGE_GLYPH = { "env-ok": "✓", "env-warn": "!", "env-err": "✕" };

export function envRowHTML(key, badgeCls, name, detail) {
  return '<div class="env-row" data-env-row="' + key + '">'
    + '<span class="env-badge ' + badgeCls + '">' + ENV_BADGE_GLYPH[badgeCls] + '</span>'
    + '<span class="env-name">' + name + '</span>'
    + '<span class="env-detail">' + detail + '</span></div>';
}

export function envChannelHTML(key, name, ch) {
  let badge, detail;
  if (ch === "pending") {
    badge = "env-warn";
    detail = '<span class="spinner"></span>检查中…';
  } else if (!ch) {
    badge = "env-warn";
    detail = "待检查（点「一键体检」触发）";
  } else if (ch.ok) {
    badge = "env-ok";
    const d = ch.data || {};
    detail = "正常（模型 " + esc(d.model || "?") + "，耗时 " + (d.elapsed_ms ?? "?") + "ms）"
      + (d.reply ? "，回复：" + esc(d.reply) : "");
  } else {
    badge = "env-err";
    detail = "失败：" + esc(ch.msg || "未知原因");
  }
  return envRowHTML(key, badge, name, detail);
}

export function envCheckStatusHTML(status, textCh, visionCh) {
  if (!status) return "";
  const rows = [];
  if (status.api_configured === true) {
    const llm = status.llm || {};
    const local = llm.local_llm_base_url || "";
    rows.push(envRowHTML("api", "env-ok", "API 配置",
      esc("已保存（模型 " + (llm.model || "?") + "，"
        + (local ? "本地路由 " + local : "端点 " + (llm.base_url || "?")) + "）")));
  } else if (status.api_configured === false) {
    rows.push(envRowHTML("api", "env-err", "API 配置", "未保存主 API key，请到设置页「主 API」填写"));
  }
  rows.push(envChannelHTML("llm-text", "文本通道", textCh));
  rows.push(envChannelHTML("llm-vision", "视觉通道", visionCh));
  const tc = status.toolchains || {};
  const tcMeta = {
    stm32: { name: "Keil UV4（stm32）", miss: "未找到 UV4（可在设置页填 uv4_path 覆盖）" },
    mspm0: { name: "gmake（mspm0）", miss: "未找到 gmake（可在设置页填 gmake_path 覆盖）" },
  };
  for (const [plat, meta] of Object.entries(tcMeta)) {
    const entry = tc[plat];
    if (!entry) continue;
    if (entry.found) {
      rows.push(envRowHTML("toolchain-" + plat, "env-ok", meta.name,
        esc(entry.path || "") + (entry.override ? "（设置页路径覆盖）" : "")));
    } else {
      rows.push(envRowHTML("toolchain-" + plat, "env-err", meta.name, meta.miss));
    }
  }
  for (const p of status.platforms || []) {
    const ready = p.status === "ready";
    rows.push(envRowHTML("platform-" + p.id, ready ? "env-ok" : "env-warn", p.name + " 母版",
      ready ? "已就绪（可生成）" : "未导入母版（生成前需导入）"));
  }
  const lib = status.module_library;
  if (lib !== undefined) {
    if (lib.error) {
      // 模块库异常 = 仅库不可用（其他功能可用）：⚠ 而非 ✗（spec 行 57）
      rows.push(envRowHTML("module-library", "env-warn", "模块库", esc(lib.error)));
    } else if (!lib.exists) {
      rows.push(envRowHTML("module-library", "env-warn", "模块库", "目录不存在：" + esc(lib.dir || "")));
    } else {
      const n = lib.count || 0;
      rows.push(envRowHTML("module-library", n > 0 ? "env-ok" : "env-warn", "模块库",
        esc((String(n) + " 个模块：") + (lib.dir || ""))));
    }
  }
  const md = status.masters_dir;
  if (md !== undefined) {
    if (md.exists) {
      rows.push(envRowHTML("masters-dir", "env-ok", "母版目录", esc(md.dir || "")));
    } else {
      rows.push(envRowHTML("masters-dir", "env-warn", "母版目录", "不存在（首次导入母版时创建）"));
    }
  }
  const out = status.output_dir;
  if (out !== undefined) {
    if (out.exists && out.writable) {
      rows.push(envRowHTML("output-dir", "env-ok", "输出目录", esc(out.dir || "") + "（可写）"));
    } else {
      const why = !out.exists ? "目录不存在：" : "目录不可写：";
      rows.push(envRowHTML("output-dir", "env-err", "输出目录", why + esc(out.dir || "")));
    }
  }
  return rows.join("");
}

if (typeof window !== "undefined") {
  Object.assign(window, { envRowHTML, envChannelHTML, envCheckStatusHTML, ENV_BADGE_GLYPH });
}
