// fx/env.js — 环境体检纯函数（工单 frontend-es-modules/01，迁自 index.html 9711-9804）
// 行结构 data-env-row 标记；ch 参数 = null（待检查）| {ok:true,data} | {ok:false,msg}。
import { esc } from "./core.js";

export const ENV_BADGE_GLYPH = { "env-ok": "✓", "env-warn": "!", "env-err": "✕" };

// CCS 三件套探测说明（工单 real-acceptance/06）：探测规则 = 三件**逐件独立**（各取
// 目录名排序最大），因此可能来自不同 CCS 安装目录 —— 真机实测「编译器在 ccs2050 +
// SDK/SysConfig 在 ccs2051」这一组合能正常编译，用户按「一个 CCS 版本 = 一套工具链」
// 排查会走偏。文案单源在此（体检说明行与设置页提示共用下面的判据）。
export const CCS_PROBE_NOTE =
  "三件逐件独立探测（各取目录名排序最大），可能来自不同 CCS 安装目录"
  + "——排查时别按「一个 CCS 版本 = 一套工具链」；任一覆盖项留空 = 该件自动探测（各取最新）";

// 三件的中文名（探测说明行 / 来源一句话共用）
export const CCS_PIECE_NAMES = { sdk: "SDK", compiler: "编译器", sysconfig: "SysConfig" };

// 路径最后一段（Windows / POSIX 分隔符都认，尾分隔符容错）：来源根只显示目录名
// （ccs2051 比整条 C:\ti\ccs2051 更适合一眼对照），完整路径仍在各件行里。
function _pathTail(p) {
  const parts = String(p || "").split(/[\\/]+/).filter(Boolean);
  return parts.length ? parts[parts.length - 1] : "";
}

// ccsSourceText(ccs)：三件来源根 → 一句话（工单 real-acceptance/06）。
//   「三件来源：编译器 ccs2050；SDK ccs2051；SysConfig ccs2051（跨安装目录）」
// 判据：来源根取载荷的 root（后端反推，推不出为 null = 不列）；≥2 个不同根 = 跨
// 安装目录；三件都探测到且同根 = 三件同源；一件都没有 root（全自定义路径）→ 空串
// （不显示这半句，不猜）。
export function ccsSourceText(ccs) {
  const listed = [];
  let unknown = 0;
  for (const key of ["compiler", "sdk", "sysconfig"]) {
    const entry = (ccs || {})[key];
    if (!entry || !entry.found) continue;
    const tail = _pathTail(entry.root);
    if (tail) listed.push(CCS_PIECE_NAMES[key] + " " + tail);
    else unknown++;
  }
  if (!listed.length) return "";
  const roots = new Set(listed.map((s) => s.slice(s.indexOf(" ") + 1)));
  const verdict = roots.size > 1
    ? "（跨安装目录）"
    : (listed.length === 3 && unknown === 0 ? "（三件同源）" : "");
  return "三件来源：" + listed.join("；") + verdict;
}

export function envRowHTML(key, badgeCls, name, detail, jump) {
  const btn = jump
    ? ' <button type="button" class="env-jump" data-env-jump="' + esc(jump.focus) + '"'
      + (jump.collapse ? ' data-env-collapse="' + esc(jump.collapse) + '"' : "") + '>去设置填</button>'
    : "";
  return '<div class="env-row" data-env-row="' + key + '">'
    + '<span class="env-badge ' + badgeCls + '">' + ENV_BADGE_GLYPH[badgeCls] + '</span>'
    + '<span class="env-name">' + name + '</span>'
    + '<span class="env-detail">' + detail + btn + '</span></div>';
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

export function envCheckStatusHTML(status, textCh, visionCh) {  if (!status) return "";
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
    stm32: { name: "Keil UV4（stm32）", miss: "未找到 UV4（可在设置页填 uv4_path 覆盖）", jump: { focus: "set-uv4-path", collapse: "toolchain" } },
    mspm0: { name: "CCS + MSPM0 SDK（mspm0）· gmake", miss: "未找到 gmake / CCS 工具链（可在设置页填 gmake_path 或 CCS 三件套）", jump: { focus: "set-gmake-path", collapse: "toolchain" } },
  };
  for (const [plat, meta] of Object.entries(tcMeta)) {
    const entry = tc[plat];
    if (!entry) continue;
    if (entry.found) {
      rows.push(envRowHTML("toolchain-" + plat, "env-ok", meta.name,
        esc(entry.path || "") + (entry.override ? "（设置页路径覆盖）" : "")));
    } else {
      rows.push(envRowHTML("toolchain-" + plat, "env-err", meta.name, meta.miss + "。", meta.jump));
    }
  }
  // CCS 三件套逐件（工单 ux-walkthrough-02/05-06）：SDK / 编译器 / SysConfig
  const ccs = status.ccs_tools || {};
  const ccsMeta = {
    sdk: { name: "CCS SDK（mspm0）", miss: "未设置（可在设置页填 ccs_sdk_dir）", jump: { focus: "set-ccs-sdk-dir", collapse: "toolchain" } },
    compiler: { name: "CCS 编译器（mspm0）", miss: "未设置（可在设置页填 ccs_compiler_dir）", jump: { focus: "set-ccs-compiler-dir", collapse: "toolchain" } },
    sysconfig: { name: "SysConfig CLI（mspm0）", miss: "未设置（可在设置页填 ccs_sysconfig_cli）", jump: { focus: "set-ccs-sysconfig-cli", collapse: "toolchain" } },
  };
  for (const [piece, meta] of Object.entries(ccsMeta)) {
    const entry = ccs[piece];
    if (!entry) continue;
    if (entry.found) {
      rows.push(envRowHTML("ccs-" + piece, "env-ok", meta.name,
        esc(entry.path || "")
        + (entry.root ? "（安装根 " + esc(entry.root) + "）" : "")
        + (entry.override ? "（设置页路径覆盖）" : "")));
    } else {
      rows.push(envRowHTML("ccs-" + piece, "env-err", meta.name, meta.miss + "。", meta.jump));
    }
  }
  // 探测说明行（工单 real-acceptance/06）：三件逐件独立探测 ⇒ 可能来自不同 CCS
  // 安装目录。有任一件在案就显示（含缺件态——缺件时更要知道探测规则），
  // 「去设置填」按钮不需要（这不是错误，是一条排查提示）。
  if (Object.keys(ccs).length) {
    const source = ccsSourceText(ccs);
    rows.push(envRowHTML("ccs-note", "env-warn", "CCS 探测说明",
      esc(CCS_PROBE_NOTE + "。") + (source ? esc(source) : "")));
  }
  // 派生库目录（工单 ux-walkthrough-02/05-06）：赛题 / 参考 / PDF
  const libDirs = status.library_dirs || {};
  const libMeta = {
    topic: { name: "赛题库目录" },
    reference: { name: "参考文件库目录" },
    pdf: { name: "PDF 资料库目录" },
  };
  for (const [key, meta] of Object.entries(libMeta)) {
    const entry = libDirs[key];
    if (!entry) continue;
    if (entry.exists && entry.writable) {
      rows.push(envRowHTML("lib-dir-" + key, "env-ok", meta.name, esc(entry.dir || "") + "（可写）"));
    } else if (!entry.exists) {
      rows.push(envRowHTML("lib-dir-" + key, "env-warn", meta.name, "目录不存在：" + esc(entry.dir || "")));
    } else {
      rows.push(envRowHTML("lib-dir-" + key, "env-warn", meta.name, "目录不可写：" + esc(entry.dir || "")));
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

// 工具链内联探测文案（工单 ux-walkthrough-02/06）：设置页「已配置值旁显示
// 探测结果」——entry = /api/env/status 的单件 {found, path, override}。
// CCS 三件套专属（工单 real-acceptance/06）：载荷额外带 root（安装根）⇒ 自动
// 探测的语义是「逐件各取目录名最新」，三个 ccs_* 覆盖项下的提示据此点明；
// uv4 / gmake 无 root（按候选顺序 / PATH 探测），不说「各取最新」。
export function toolchainProbeText(entry) {
  if (!entry) return "";
  const isCcs = entry.root !== undefined;
  const hint = isCcs ? "（留空 = 自动探测：三件各取目录名最新）" : "（留空 = 自动）";
  if (entry.override && entry.found) return "已配置：探测命中 " + (entry.path || "") + hint;
  if (entry.override && !entry.found) return "✕ 已填路径未找到（请确认路径正确，或留空自动探测）";
  if (!entry.override && entry.found) return "✓ 自动探测到：" + (entry.path || "") + hint;
  return isCcs
    ? "未探测到（留空 = 自动扫描 C:/ti/ccs*，各取目录名最新；也可填路径覆盖）"
    : "未探测到（留空 = 自动扫描；也可填路径覆盖）";
}

if (typeof window !== "undefined") {
  Object.assign(window, {
    envRowHTML, envChannelHTML, envCheckStatusHTML, toolchainProbeText,
    ccsSourceText, ENV_BADGE_GLYPH, CCS_PROBE_NOTE, CCS_PIECE_NAMES,
  });
}
