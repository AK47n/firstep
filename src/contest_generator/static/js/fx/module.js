// fx/module.js — 模块域纯函数（工单 frontend-es-modules/06，迁自 index.html
// module 域纯函数组：模块徽章 / 功能组卡 / 模块网格 / 模块详情 / 多实例 /
// 模块库过滤排序统计 / 行渲染 / 改简介状态机 / 编辑弹窗校验词表）。
// esc 单源取自 fx/core.js；moduleGridHTML / moduleInfoHTML 保留函数体内局部
// escHtml（其 null/undefined 兜底语义与 core esc 不同，照搬不合并，防双源处
// 已在注释标注）；multiInstanceModules / instancePayload / ensureDefaultInstances
// 原引用主体脚本模块级状态（expanded / instances），迁入后改为显式参数传递
//（行为零变化，调用点同步传参）。模块约定见 fx/core.js 头部。
import { esc } from "./core.js";

export function moduleBadges(m) {
  const badges = [];
  for (const [platform, entry] of Object.entries(m.platforms || {})) {
    const cls = entry.hardware_bound ? "hw" : entry.verified ? "ok" : "unverified";
    const status = entry.hardware_bound ? "硬件绑定" : entry.verified ? "已验证" : "未验证";
    badges.push(`<span class="badge plat ${cls}">${esc(platform.toUpperCase())}<br>${esc(status)}</span>`);
    // 母版内嵌标注（2024H 复盘）：平台条目 files 空且无副产物 = 实现内嵌母版
    // （如 stm32 的 delay/led），不复制任何文件——消除"自动带入 = 文件重复"误解
    if (!(entry.files || []).length && !m.python_artifact) {
      badges.push('<span class="badge neutral" title="实现内嵌母版（随母版进工程），不复制文件、不重复">内嵌母版</span>');
    }
  }
  return badges.join("");
}

export function pythonArtifactSummary(m) {
  const pa = m.python_artifact;
  if (!pa || !pa.templates || !pa.templates.length) return "";
  const templates = pa.templates.map((t) =>
    `<div><strong>${esc(t.name || t.id)}</strong>${t.description ? "：" + esc(t.description) : ""}</div>`
  ).join("");
  return `<div class="muted" style="margin-top: var(--space-1)">副产物模板：${templates}</div>`;
}

// ---------------------------------------------------------------------------
// 功能组选择卡（工单 recommend-exclusive-groups/04）：纯函数层——组卡渲染、
// 单选交换/取消、autoAdd 同组去重、同组多选冲突判定。交互逻辑全部下沉为
// 纯函数（不碰 DOM），照 score-points-format 先例喂 node:test 单测。
// 载荷形状（工单 02）：exclusive_groups = [{id, label, hint, members:[{slug,
// role}], recommended:[slug]}]；旧载荷无该键 → 一律 || [] 容错（无卡）。
// ---------------------------------------------------------------------------

export function groupOfSlug(groups, slug) {
  for (const g of (groups || [])) {
    if ((g.members || []).some((m) => m.slug === slug)) return g;
  }
  return null;
}

export function applyGroupRadio(groups, selectedSlugs, groupId, slug) {
  // 单选交互：点击成员 → 从 selectedSlugs 移除同组其他成员后加入该成员；
  // 点击已选成员 = 取消整组（该组全部成员移出）。未知组 id / 旧载荷按无组
  // 处理（只加入，无移除）。
  const group = (groups || []).find((g) => g.id === groupId) || null;
  const members = group ? (group.members || []).map((m) => m.slug) : [slug];
  const without = selectedSlugs.filter((s) => !members.includes(s));
  if (selectedSlugs.includes(slug)) return without;
  return without.concat(slug);
}

export function autoAddDedup(groups, selectedSlugs, modules) {
  // autoAdd 同组去重：data.modules 逐个加入时，若该 slug 属某组且已选里已有
  // 同组任一成员 → 跳过（仅首个推荐成员入集；AI 的其它同组推荐仅以组卡徽标
  // 展示）。非组模块照常加入；旧载荷（无组）行为与现状一致。
  const out = (selectedSlugs || []).slice();
  for (const m of (modules || [])) {
    const slug = m && m.slug;
    if (!slug || out.includes(slug)) continue;
    const g = groupOfSlug(groups, slug);
    if (g && (g.members || []).some((mem) => out.includes(mem.slug))) continue;
    out.push(slug);
  }
  return out;
}

export function groupConflicts(groups, selectedSlugs) {
  // renderSelected 兜底：同组 ≥2 成员在 selectedSlugs → 黄字警告条目（用户
  // 拥有最终选择权，不硬拦）。返回 [{id, label, slugs}]，无冲突 = []。
  const out = [];
  for (const g of (groups || [])) {
    const slugs = (g.members || []).map((m) => m.slug)
      .filter((s) => selectedSlugs.includes(s));
    if (slugs.length >= 2) out.push({ id: g.id, label: g.label, slugs });
  }
  return out;
}

export function renderGroupCards(groups, modules, selectedSlugs) {
  // 组卡渲染：label + (hint 卡)「AI 未推荐，题面疑似需要——请确认」标注 +
  // 成员行（radio + slug + role + 「AI 推荐」徽标与理由）。默认选中 = 组内当前
  // 在 selectedSlugs 的成员，多个按 data.modules 序（AI 推荐序）取第一个；
  // 不在 data.modules 的成员（用户手动加的）按组成员登记序兜底（spec:107 注：
  // AI 首选由 data.modules 顺序决定，不依赖 recommended 字段）。
  const reasons = {};
  for (const m of (modules || [])) reasons[m.slug] = m.reason || "";
  return (groups || []).map((g) => {
    const members = g.members || [];
    const checkedMembers = members.filter((m) => selectedSlugs.includes(m.slug));
    let checked = "";
    if (checkedMembers.length) {
      const firstInModules = (modules || []).find((m) =>
        checkedMembers.some((x) => x.slug === m.slug));
      checked = firstInModules
        ? checkedMembers.find((x) => x.slug === firstInModules.slug).slug
        : checkedMembers[0].slug;
    }
    const rows = members.map((m) => {
      const isRec = (g.recommended || []).includes(m.slug);
      const reason = reasons[m.slug];
      return '<label class="group-member' + (m.slug === checked ? " checked" : "") + '">'
        + '<input type="radio" name="group-' + esc(g.id) + '"'
        + ' data-group-id="' + esc(g.id) + '" data-group-slug="' + esc(m.slug) + '"'
        + (m.slug === checked ? " checked" : "") + '>'
        + '<span class="slug">' + esc(m.slug) + '</span>'
        + '<span class="role">' + esc(m.role || "") + '</span>'
        + (isRec ? '<span class="badge ok">AI 推荐</span>'
            + (reason ? '<span class="reason">' + esc(reason) + '</span>' : "") : "")
        + '</label>';
    }).join("");
    return '<div class="group-card">'
      + '<div class="title">功能组选择 · ' + esc(g.label) + '</div>'
      + (g.hint ? '<div class="hint-note">AI 未推荐，题面疑似需要——请确认</div>' : "")
      + rows + '</div>';
  }).join("");
}

export function groupRequirementNote(groups, slug, reason) {
  // 需求清单灰注：组内成员的 slug 不再渲染成可移除 chip，改为灰注（需求句 / 
  // 理由可见性保留）；非组模块返回 null（调用方走 recommendChip 原逻辑）。
  if (!groupOfSlug(groups, slug)) return null;
  return '<span class="muted">' + esc(slug)
    + '（已在『功能组选择』中' + (reason ? "，" + esc(reason) : "") + '）</span>';
}

// ---------------------------------------------------------------------------
// 生成页：5. 模块清单（增删 + 依赖展开 + 平台警告）—— 模块网格（工单 module-grid/01）
// ---------------------------------------------------------------------------
export function moduleGridPlatformLabel(platform) {
  const map = { stm32: "STM32", stm32f103c8t6: "STM32", mspm0: "MSPM0", mspm0g3507: "MSPM0" };
  return map[platform] || platform;
}
export function moduleGridStatusText(entry) {
  if (!entry) return "未验证";
  if (entry.hardware_bound) return "硬件绑定";
  if (entry.verified) return "已验证";
  return "未验证";
}
// 平台条目 → 徽章类名（hw/ok/un）：与 moduleGridStatusText 并列单源（评审 2026-08-26），
// moduleGridHTML 与 moduleInfoHTML 共用；moduleBadges（推荐区）的 unverified 异形体另属
// 其组件，收敛范围外
export function moduleGridBadgeClass(entry) {
  if (!entry) return "un";
  if (entry.hardware_bound) return "hw";
  if (entry.verified) return "ok";
  return "un";
}
export function moduleGridFilter(modules, selectedSet, query) {
  const q = String(query || "").trim().toLowerCase();
  const selected = selectedSet || [];
  const avail = (modules || []).filter((m) => selected.indexOf(m.slug) === -1);
  if (!q) return avail;
  return avail.filter((m) => {
    const text = (m.slug + " " + (m.description || "") + " " + (m.dependencies || []).join(" ")
      + " " + Object.keys(m.platforms || {}).map((p) => moduleGridPlatformLabel(p)).join(" ")).toLowerCase();
    return text.includes(q);
  });
}
export function moduleGridCountText(modules, selectedSet, query) {
  const q = String(query || "").trim();
  const n = moduleGridFilter(modules, selectedSet, query).length;
  return q ? "匹配 " + n + " 个可用模块" : "共 " + n + " 个可用模块";
}
export function moduleGridHTML(modules, selectedSet, query, platform) {
  // 自包含内联 esc（纯函数抽取范式，同 scoreChecklistItemsHTML）——不依赖全局 esc
  const escHtml = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
  const hits = moduleGridFilter(modules, selectedSet, query);
  if (!hits.length) {
    const q = String(query || "").trim();
    return '<div class="muted" style="padding:6px 2px">' + (q ? "没有匹配的可用模块。" : "暂无可用模块。") + "</div>";
  }
  return hits.map((m) => {
    const off = platform && !(m.platforms || {})[platform];
    const desc = String(m.description || "");
    const short = desc.length > 26 ? desc.slice(0, 26) + "…" : desc;
    const badges = Object.keys(m.platforms || {}).map((p) => {
      const e = (m.platforms || {})[p];
      const cls = moduleGridBadgeClass(e);
      let html = '<span class="mc-plat ' + cls + '">' + escHtml(moduleGridPlatformLabel(p))
        + "·" + escHtml(moduleGridStatusText(e)) + "</span>";
      // 母版内嵌标注（2024H 复盘）：平台条目 files 空且无副产物 = 实现内嵌母版
      if (!(e && e.files && e.files.length) && !m.python_artifact) {
        html += '<span class="mc-plat embed" title="实现内嵌母版（随母版进工程），不复制文件、不重复">内嵌母版</span>';
      }
      return html;
    }).join("");
    const deps = (m.dependencies || []).length
      ? '<span class="mc-deps">依赖：' + escHtml(m.dependencies.join("、")) + "</span>" : "";
    const pa = m.python_artifact ? '<span class="mc-pa">副产物</span>' : "";
    return '<div class="module-card' + (off ? " off" : "") + '" data-add="' + escHtml(m.slug) + '"'
      + ' title="' + escHtml(desc) + '">'
      + '<div class="mc-head"><span class="slug">' + escHtml(m.slug) + "</span>"
      + '<button class="mc-info" data-info="' + escHtml(m.slug) + '" title="查看模块详情">详情</button>'
      + (off ? '<span class="mc-offtag">需切换平台</span>' : "") + "</div>"
      + '<div class="mc-desc">' + escHtml(short) + "</div>"
      + '<div class="mc-meta">' + badges + deps + pa + "</div></div>";
  }).join("");
}

// —— 模块详情弹窗（工单 module-info-dialog/01）：零后端，数据 = /api/modules 全量 ──
// 身份字段语义（工单 identity-fields/05）：模块类别的判据单源在 Python 侧
// `library.MODULE_KIND`，载荷经 /api/modules 投影为 kind / requires_identity
// （本文件不写 slug 名单）。`moduleRequiresIdentity` 对旧载荷（无字段）保守判
// 「器件」——器件空字段语义 = 待补，与旧行为逐字一致。
export const INTERNAL_KINDS = ["internal", "protocol"];

export function moduleRequiresIdentity(m) {
  const kind = String((m && m.kind) || "");
  if (INTERNAL_KINDS.includes(kind)) return false;
  if (kind === "device") return true;
  return (m && m.requires_identity) !== false;
}

// 内部件 / 协议切片的身份字段标注（kind 经载荷下发；空字段 = 「不适用」而非「待补」）
export function identityExemptLabel(kind) {
  return kind === "protocol" ? "无需购买链接（协议切片）" : "无需购买链接（内部件）";
}

export function moduleInfoHTML(module, platform) {
  // 自包含内联 esc（同 moduleGridHTML 范式）
  const escHtml = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
  const m = module || {};
  const plats = m.platforms || {};
  const off = !!(platform && !plats[platform]);
  const rows = [];
  if ((m.dependencies || []).length) {
    rows.push('<li class="mi-row"><span class="mi-k">依赖</span><span>'
      + escHtml(m.dependencies.join("、")) + "</span></li>");
  }
  if (m.multi_instance) {
    rows.push('<li class="mi-row"><span class="mi-k">多实例</span><span>可配置 '
      + escHtml(String(m.multi_instance.max)) + " 个实例，按 "
      + escHtml(m.multi_instance.variant) + " 区分</span></li>");
  }
  if (m.python_artifact) {
    const pa = m.python_artifact;
    let text;
    if (pa.templates && pa.templates.length) {
      // 新形状（k230-multi-template）：default + templates 列表；每模板
      // name（desc）：template → output（spec 契约：箭头左 = 模板源路径）
      const defT = pa.templates.find((t) => t.id === (pa.default || "default")) || pa.templates[0];
      text = "默认：" + escHtml(defT.name || defT.id) + "；" + pa.templates.map((t) =>
        escHtml(t.name) + (t.description ? "（" + escHtml(t.description) + "）" : "")
        + "：" + escHtml(t.template) + " → " + escHtml(t.output)).join("；");
    } else {
      // 旧形状：template → output
      text = escHtml(pa.template || "") + " → " + escHtml(pa.output || "");
    }
    rows.push('<li class="mi-row"><span class="mi-k">副产物</span><span>' + text + "</span></li>");
  }
  if (m.exclusive_group) {
    rows.push('<li class="mi-row"><span class="mi-k">互斥组</span><span>'
      + escHtml(m.exclusive_group.label) + "（" + escHtml(m.exclusive_group.role)
      + "）·同组互斥</span></li>");
  }
  const platHtml = Object.keys(plats).map((p) => {
    const e = plats[p] || {};
    const status = moduleGridStatusText(e);
    const cls = moduleGridBadgeClass(e);
    const files = (e.files && e.files.length)
      ? e.files.map((f) => '<li><button type="button" class="mi-file" data-mi-file="'
        + escHtml(f) + '" title="查看源码（只读）">' + escHtml(f) + "</button></li>").join("")
      : '<li class="muted">实现内嵌母版（随母版进工程，不复制文件、不重复）</li>';
    const notes = e.notes ? '<div class="mi-note">备注：' + escHtml(e.notes) + "</div>" : "";
    // 身份字段（工单 identity-fields/05）：器件 = 有值才显示「套件：」/来源行；
    // 内部件 / 协议切片 = 不显示两行空内容，改标「无需购买链接」（空值语义是
    // 「不适用」而非「待补」，见 library.MODULE_KIND）。判据取自载荷 kind，本文件
    // 不写 slug 名单。
    const needsIdentity = moduleRequiresIdentity(m);
    const kit = needsIdentity && e.kit
      ? '<div class="mi-note">套件：' + escHtml(e.kit) + "</div>" : "";
    // 来源链接标签（工单 lckfb-attribution/03）：wiki 手册原页 → 「来源（立创 wiki）」，
    // 其余（购买链接等）维持「购买链接」——打开链接前即知链接性质。
    // 判据与后端 is_wiki_source_url 同构（单一前缀常量，勿各自定义变体）。
    const isWiki = String(e.source_url || "").startsWith("https://wiki.lckfb.com/");
    const source = needsIdentity && e.source_url
      ? '<div class="mi-note"><a href="' + escHtml(e.source_url)
        + '" target="_blank" rel="noopener">' + (isWiki ? "来源（立创 wiki）" : "购买链接")
        + "</a></div>"
      : "";
    const identityNote = needsIdentity
      ? ""
      : '<div class="mi-note muted">' + escHtml(identityExemptLabel(String(m.kind || "")))
        + "</div>";
    const pins = (e.pins && e.pins.length)
      ? '<table class="mi-pins"><thead><tr><th>角色</th><th>类型</th><th>默认引脚</th>'
        + '<th>必接</th><th>宏名</th></tr></thead><tbody>'
        + e.pins.map((pin) => {
          const label = pin.label || pin.id;
          const idPart = pin.id && pin.id !== label
            ? ' <span class="mi-pin-id">' + escHtml(pin.id) + "</span>" : "";
          return "<tr><td>" + escHtml(label) + idPart + "</td><td>" + escHtml(pin.type)
            + "</td><td>" + escHtml(pin.default) + "</td><td>" + (pin.required ? "必接" : "")
            + "</td><td>" + escHtml((pin.macros || []).join("、")) + "</td></tr>";
        }).join("") + "</tbody></table>"
      : "";
    return '<section class="mi-plat" data-platform="' + escHtml(p) + '">'
      + "<h4>" + escHtml(moduleGridPlatformLabel(p))
      + ' <span class="mc-plat ' + cls + '">' + status + "</span></h4>"
      + '<ul class="mi-files">' + files + "</ul>" + notes + kit + source + identityNote + pins + "</section>";
  }).join("");
  return '<div class="module-info-body">'
    + '<div class="module-info-title"><span class="slug">' + escHtml(m.slug || "") + "</span>"
    + '<div class="desc">' + escHtml(m.description || "") + "</div></div>"
    + (off ? '<div class="module-info-off">当前平台 ' + escHtml(moduleGridPlatformLabel(platform))
      + " 无此模块版本</div>" : "")
    + (rows.length ? '<ul class="module-info-rows">' + rows.join("") + "</ul>" : "")
    + '<div class="module-info-platforms">' + platHtml + "</div>"
    // 源码查看区（工单 mainc-codeview-bridge/05）：点击文件行懒加载（隐藏态，
    // module-source 胶水层填充；弹窗主体仍零写侧只读）
    + '<div class="module-info-source" data-module-source hidden></div></div>';
}

// ---------------------------------------------------------------------------
// 多实例（工单 module-multi-instance/04-06）：复刻实例卡的状态逻辑纯函数。
// 原引用主体脚本模块级状态（expanded / instances），迁入后显式参数传递——
// 测试直接传参，调用点（renderInstanceConfig / generate 载荷）同步传参。
// ---------------------------------------------------------------------------

export function multiInstanceModules(expanded) {
  // 依赖带入的多实例模块（如 led_beep 依赖 led）也显示实例卡（工单
  // instance-config-deps/01）：实例清单随 instancePayload 走 expanded 全集，
  // 后端 parse_instances 认"选中 ∪ 依赖"——不再是加了没反应的死按钮。
  // 未展开（expanded 空）时本函数为空 → 卡隐藏（旧行为）。
  return expanded.filter((m) => m.multi_instance);
}

export function instancePayload(expanded, instances) {
  // 只带仍在最终工程集（expanded = 选中 ∪ 依赖）内且配了 ≥1 实例的模块；
  // 空清单 = 不发 instances（旧行为）。依赖带入的多实例模块同样能发——
  // 未展开时 expanded 空 → 空对象（旧行为零变化）。
  const out = {};
  for (const m of expanded) {
    if (!m.multi_instance) continue;
    const list = instances[m.slug] || [];
    if (list.length) {
      out[m.slug] = list.map((i) => ({ name: i.name, variant: i.variant, pin: i.pin }));
    }
  }
  return out;
}

export function ensureDefaultInstances(expanded, instances) {
  // 实例卡首次呈现即预填平台默认（expand 端点 default_instances，工单
  // instance-config-defaults/01）：AI 未猜 / 依赖带入（led_beep → led）的多实例
  // 模块也有「第一版」可改，而不是空卡。键已存在不覆盖——AI 猜过 / 用户配过 /
  // 用户删空（键在、清单空 = 用户明确要默认单实例）都不复活。
  for (const m of expanded) {
    if (!m.multi_instance) continue;
    if (m.slug in instances) continue;
    if (!m.default_instances || !m.default_instances.length) continue;
    instances[m.slug] = m.default_instances.map((i) => ({
      name: String(i.name || ""), variant: i.variant || "", pin: i.pin || "",
    }));
  }
}

// 实例缺口（工单 ux-walkthrough-02/02）：多实例模块中当前没有任何实例配置的
// 个数（列表存在且非空即不算缺口）。6.5 卡「还差 N 个实例」徽章与导航点
// 完成态的唯一计数口径；expanded 未展开（空）→ 0（无模块可数）。
export function instanceGapCount(expanded, instances) {
  const inst = instances || {};
  return (expanded || []).filter((m) => {
    if (!m.multi_instance) return false;
    const list = inst[m.slug];
    return !list || !list.length;
  }).length;
}

// ---------------------------------------------------------------------------
// 模块库页 —— 工具栏纯函数（library-toolbar/02）：过滤 / 排序 / 统计 / chips
// 均为顶层纯函数（tests/js 可注入）；DOM 层只做转发，交互逻辑不散落事件里。
// ---------------------------------------------------------------------------
// libFilterModules(modules, f)：f={q, platform, status}。
// q 大小写不敏感子串，匹配 slug / 简介 / 依赖串 / 任一平台条目 kit 或 notes；
// platform='' 全平台，否则要求存在该平台条目；
// status=''|'verified'|'unverified'|'hardware_bound'，任选平台条目满足即命中
// （unverified 语义 = 该平台无 verified===true 的条目）。
export function libFilterModules(modules, f) {
  const q = String((f && f.q) || "").trim().toLowerCase();
  const platform = (f && f.platform) || "";
  const status = (f && f.status) || "";
  return (modules || []).filter((m) => {
    if (q) {
      const hay = [m.slug || "", m.description || "", (m.dependencies || []).join("、")];
      for (const p of Object.values(m.platforms || {})) if (p) hay.push(p.kit || "", p.notes || "");
      if (!hay.some((s) => String(s).toLowerCase().includes(q))) return false;
    }
    if (platform && !(m.platforms || {})[platform]) return false;
    if (status) {
      const any = (m.platforms && Object.values(m.platforms).some((p) => p && (
        status === "verified" ? p.verified === true :
        status === "unverified" ? p.verified !== true :
        status === "hardware_bound" ? p.hardware_bound === true : false)));
      if (!any) return false;
    }
    return true;
  });
}

// libSortModules(modules, s)：s={by:'slug'|'platforms'|'deps'|'mtime', dir:'asc'|'desc'}；
// 返回新数组（不改原数组）；Array.sort 稳定 → 同键保持入库序。
export function libSortModules(modules, s) {
  const by = (s && s.by) || "slug";
  const dir = (s && s.dir) === "desc" ? -1 : 1;
  const count = (m) => by === "platforms" ? Object.keys(m.platforms || {}).length
    : by === "deps" ? (m.dependencies || []).length
    : by === "mtime" ? Number(m.mtime || 0)   // 最近更新（ux-polish-02/08）
    : 0;
  const out = (modules || []).slice();
  out.sort((a, b) => {
    const cmp = by === "slug"
      ? String(a.slug || "").localeCompare(String(b.slug || ""))
      : (count(a) === count(b) ? 0 : (count(a) < count(b) ? -1 : 1));
    return cmp * dir;
  });
  return out;
}

// danglingDependencies(modules)：悬空依赖体检（工单 04 纯函数）。
// 返回 { 缺失依赖slug: [引用方模块slug...] }；空对象 = 无悬空。
// 同模块重复声明只记一次引用方；不同模块引用同一缺失依赖合并引用方列表。
export function danglingDependencies(modules) {
  const slugs = new Set((modules || []).map((m) => m.slug));
  const map = {};
  for (const m of modules || []) {
    for (const dep of m.dependencies || []) {
      if (slugs.has(dep)) continue;
      if (!map[dep]) map[dep] = [];
      if (!map[dep].includes(m.slug)) map[dep].push(m.slug);
    }
  }
  return map;
}

// libStats(modules)：全量统计（不过滤）。verified / hardware_bound / unverified 为
// 模块级计数（存在任一平台条目满足即计 1，平台间可重叠）；exclusiveGroups 按 id 去重；
// dangling = 悬空依赖数（依赖不在库内 slug 集合）。
export function libStats(modules) {
  const platforms = {};
  let verified = 0, unverified = 0, hardware_bound = 0;
  const groups = new Set();
  for (const m of modules || []) {
    const ps = Object.values(m.platforms || {});
    // 与 libFilterModules 语义一致：null/缺失条目视作「无该平台」，不计数
    for (const [name, p] of Object.entries(m.platforms || {})) {
      if (p) platforms[name] = (platforms[name] || 0) + 1;
    }
    if (ps.some((p) => p && p.verified === true)) verified += 1;
    if (ps.some((p) => p && p.verified !== true)) unverified += 1;
    if (ps.some((p) => p && p.hardware_bound === true)) hardware_bound += 1;
    if (m.exclusive_group && m.exclusive_group.id) groups.add(m.exclusive_group.id);
  }
  return { total: (modules || []).length, platforms, verified, unverified,
           hardware_bound, exclusiveGroups: groups.size,
           dangling: Object.keys(danglingDependencies(modules)).length };
}

// libStatsText(stats)：统计条文案（平台名沿用徽章惯例 toUpperCase 显示）。
export function libStatsText(stats) {
  const parts = ["共 " + stats.total + " 个模块"];
  for (const name of Object.keys(stats.platforms)) parts.push(String(name).toUpperCase() + " " + stats.platforms[name]);
  parts.push("已验证 " + stats.verified);
  parts.push("硬件绑定 " + stats.hardware_bound);
  parts.push("互斥组 " + stats.exclusiveGroups);
  return parts.join(" · ");
}

// libChipRowHTML(options, selected)：筛选 chips 纯函数。options=[{value,label,count?}]，
// selected 命中项加 on 类（'' = 未选中）；value 经 esc 转义。
export function libChipRowHTML(options, selected) {
  return (options || []).map((o) =>
    `<button type="button" class="lib-chip${o.value === selected ? " on" : ""}" data-lib-chip="${esc(o.value)}">${esc(o.label)}${o.count != null ? "（" + o.count + "）" : ""}</button>`
  ).join("");
}

export function moduleRowHTML(m, dangling) {
  const description = String(m.description || "");
  // 依赖列（工单 04）：悬空依赖名后加 ⚠ 警示标，title = 缺失清单 + 引用方。
  // 重复声明先按名去重（与 danglingDependencies 语义一致：不重复报）
  const depNames = [...new Set(m.dependencies || [])];
  const deps = depNames.map((d) => {
    const refs = dangling && dangling[d];
    return esc(d) + (refs
      ? '<span class="dangling-tag" title="依赖未入库：' + esc(d) + "（被 " + esc(refs.join("、")) + " 引用）\">⚠</span>"
      : "");
  }).join("、") || "—";
  return `<tr>
    <td class="slug">${esc(m.slug || "")}</td>
    <td class="desc-cell" title="${esc(description)}">${esc(description)}</td>
    <td class="muted">${deps}${pythonArtifactSummary(m)}</td>
    <td>${moduleBadges(m)}</td>
    <td>
      <button data-info="${esc(m.slug || "")}" title="查看模块详情">详情</button>
      <button data-edit-mod="${esc(m.slug || "")}" title="编辑平台版本（套件 / 链接 / 文件）">编辑</button>
      <button data-edit-desc="${esc(m.slug || "")}">改简介</button>
      <button data-del="${esc(m.slug || "")}" class="danger">删除</button>
    </td>
  </tr>`;
}

// editDescStatus(status, event)：改简介模态状态机（工单 05 纯函数，可测）。
// idle → saving → ok / rejected；reset 回 idle；非法事件保持原状态（重入由按钮禁用承担）。
export function editDescStatus(status, event) {
  switch (event) {
    case "save": return "saving";
    case "saved": return status === "saving" ? "ok" : status;
    case "error": return status === "saving" ? "rejected" : status;
    case "reset": return "idle";
    default: return status;
  }
}

// libIsValidHttpUrl(s)：编辑弹窗购买链接格式校验（工单 06 纯函数）。
export function libIsValidHttpUrl(s) {
  const text = String(s || "").trim();
  if (!text) return false;
  try {
    const u = new URL(text);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch { return false; }
}

// libPlatformKits(modules)：库内所有平台条目 kit 去重词表（首见序，空值忽略）。
export function libPlatformKits(modules) {
  const seen = new Set();
  const out = [];
  for (const m of modules || []) {
    for (const p of Object.values(m.platforms || {})) {
      const kit = p && p.kit ? String(p.kit).trim() : "";
      if (kit && !seen.has(kit)) { seen.add(kit); out.push(kit); }
    }
  }
  return out;
}

if (typeof window !== "undefined") {
  Object.assign(window, { moduleBadges, pythonArtifactSummary, groupOfSlug, applyGroupRadio, autoAddDedup, groupConflicts, renderGroupCards, groupRequirementNote, moduleGridPlatformLabel, moduleGridStatusText, moduleGridBadgeClass, moduleGridFilter, moduleGridCountText, moduleGridHTML, moduleInfoHTML, moduleRequiresIdentity, identityExemptLabel, INTERNAL_KINDS, multiInstanceModules, instancePayload, ensureDefaultInstances, instanceGapCount, libFilterModules, libSortModules, danglingDependencies, libStats, libStatsText, libChipRowHTML, moduleRowHTML, editDescStatus, libIsValidHttpUrl, libPlatformKits });
}
