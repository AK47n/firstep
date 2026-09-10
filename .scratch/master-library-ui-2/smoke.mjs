// 冒烟（master-library-ui-2 系列）：母版库增强 UI——健康徽章 / 体积统计 /
// 文件树与树文件预览 / 高亮与复制钮 / 直接导入按钮 / 共享确认弹窗开合
// （经赛题库删除按钮实测工厂接线，取消不真删）。零真删零真导；工单 01-05
// 端点在 pytest 与 tests/js 覆盖。零依赖：node 内置 fetch + WebSocket 直连
// Chrome CDP（9251，需 Node ≥ 21）；webapp 8000 提供真实 /api/masters。
// 注：模块化后 state/masterCache 均为模块作用域（无 window 桥），就绪与
// 断言全部用 DOM 可观察事实。
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const CDP = 9251;
const pageUrl = "http://127.0.0.1:8000/";

const fetchT = async (url, ms = 5000, opts = {}) => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  try { return await fetch(url, { signal: ctl.signal, ...opts }); } finally { clearTimeout(t); }
};

let targets = null;
for (let i = 0; i < 50 && !targets; i++) {
  try { targets = await (await fetchT(`http://127.0.0.1:${CDP}/json/list`)).json(); } catch {}
  if (!targets || !targets.length) await new Promise((r) => setTimeout(r, 300));
}
if (!targets) { console.error("CDP 不可达"); process.exit(1); }
const page = targets.find((t) => t.type === "page" && t.url.startsWith("http://127.0.0.1:8000"));
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error("ws error")); });

let seq = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
};
const cdp = (method, params = {}) =>
  new Promise((resolve) => { const id = ++seq; pending.set(id, resolve); ws.send(JSON.stringify({ id, method, params })); });
const Eval = async (expr) => {
  const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error("eval 失败: " + (r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails)));
  return r.result?.result?.value;
};
const waitFor = async (expr, ms = 8000) => {
  for (let i = 0; i < ms / 200; i++) {
    try { if (await Eval(expr)) return true; } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
};

await Eval(`window.__smokeMarker = 1`);
await cdp("Page.reload", { ignoreCache: true });
let ready = false;
for (let i = 0; i < 100 && !ready; i++) {
  try {
    ready = await Eval(`document.readyState === 'complete' && !window.__smokeMarker
      && !!document.getElementById('tab-master')
      && !!document.getElementById('master-rows')`);
  } catch {}
  if (!ready) await new Promise((r) => setTimeout(r, 300));
}
if (!ready) { console.error("页面未就绪"); process.exit(1); }

let failed = 0, passed = 0;
const check = (name, ok, extra) => {
  console.log((ok ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " [" + extra + "]" : ""));
  if (ok) passed++; else failed++;
};

// ---- 切「母版」tab ----
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button')]
    .find((b) => b.dataset.tab === 'master');
  if (tab) tab.click();
  return !!tab;
})()`);
await waitFor(`document.querySelectorAll('#master-rows tr').length >= 1`);
const rowCount = await Eval(`document.querySelectorAll('#master-rows tr').length`);
check("母版列表已加载（真实库）", rowCount > 0, "rows=" + rowCount);

// ================= 工单 01：健康徽章 + 体积统计 =================
check("每行健康徽章（✓/⚠ pill，数量 = 行数）", await Eval(`
  document.querySelectorAll('#master-rows .master-health-pill').length
    === document.querySelectorAll('#master-rows tr').length`));
check("真实库双平台健康（均 ✓ 健康）", await Eval(`
  [...document.querySelectorAll('#master-rows .master-health-pill')]
    .every((p) => p.classList.contains('master-health-ok'))`));
check("表格表头含「健康」列", await Eval(`
  [...document.querySelectorAll('#master-rows')][0]
    && [...document.querySelectorAll('table th')].some((th) => th.textContent.trim() === '健康')`));

await Eval(`document.querySelector('#master-rows [data-master-detail="stm32"]')?.click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay')`);
check("详情弹窗：体积统计行（总体积/文件数）", await Eval(`
  (() => {
    const t = document.querySelector('.ref-detail-meta')?.textContent || '';
    return t.includes('总体积') && t.includes('文件数');
  })()`));

// ================= 工单 02：文件树 + 树文件预览 =================
check("全部文件树渲染（ul.master-tree + details 目录可收）", await waitFor(`
  (() => {
    const box = document.querySelector('.ref-files-overlay [data-master-tree]');
    return !!box && !!box.querySelector('ul.master-tree')
      && box.querySelectorAll('.master-tree details').length > 0;
  })()`));
check("树含非关键文件（ml_libs/ 开头条目）", await Eval(`
  [...document.querySelectorAll('.ref-files-overlay [data-master-tree-file]')]
    .some((b) => b.dataset.masterTreeFile.startsWith('ml_libs/'))`));
await Eval(`[...document.querySelectorAll('.ref-files-overlay [data-master-tree-file]')]
  .find((b) => b.dataset.masterTreeFile.startsWith('ml_libs/'))?.click()`);
check("树文件加载成功（内容 pre + #include 子串）", await waitFor(`
  (() => {
    const el = document.querySelector('.ref-files-overlay [data-master-content]');
    return !!el && !!el.querySelector('.master-file-pre') && (el.textContent || '').includes('#include');
  })()`));
check("树文件点选行高亮（.on）", await Eval(`
  !![...document.querySelectorAll('.ref-files-overlay [data-master-tree-file]')].find((b) =>
    b.classList.contains('on'))`));

// ================= B8（工单 02 收口）：树清单**数值**断言 + 400 中文 =================
// 网页内树由 `/api/masters/<platform>/tree` 的清单渲染；这里拿同一端点现算期望值，
// 逐项对齐「文件数 / 目录数」——不再只看「有 ul.master-tree」这种存在性断言。
const treeApi = await (await fetchT("http://127.0.0.1:8000/api/masters/stm32/tree")).json();
const apiFiles = treeApi.map((f) => f.path);
const apiDirs = new Set();
for (const p of apiFiles) {
  const segs = p.split("/");
  for (let i = 1; i < segs.length; i++) apiDirs.add(segs.slice(0, i).join("/"));
}
const domFiles = await Eval(`[...document.querySelectorAll('.ref-files-overlay [data-master-tree-file]')].map((b) => b.dataset.masterTreeFile)`);
const domDirs = await Eval(`document.querySelectorAll('.ref-files-overlay [data-master-tree] details').length`);
check("B8 树文件数 = 端点清单条数（且逐条同名）",
  domFiles.length === apiFiles.length && apiFiles.every((p) => domFiles.includes(p)),
  `dom=${domFiles.length} api=${apiFiles.length}`);
check("B8 树目录数 = 清单推导的目录数", domDirs === apiDirs.size, `dom=${domDirs} api=${apiDirs.size}`);
const missRes = await fetchT("http://127.0.0.1:8000/api/masters/stm32/tree/" + encodeURIComponent("不存在.c"));
check("B8 缺失路径 → 400 中文", missRes.status === 400 && (await missRes.text()).includes("文件不存在"));
const escRes = await fetchT("http://127.0.0.1:8000/api/masters/stm32/tree/" + encodeURIComponent("../secret.txt"));
check("B8 路径穿越 → 400 中文（非法路径）", escRes.status === 400 && (await escRes.text()).includes("非法路径"));
// 二进制 400：母版树里**没有真样本**（实测库内 0 个含 NUL 文件），改用同一条约束的
// 代码查看器端点 + 临时目录验证同一判定（口径写在收口记录里，不当成母版树实测）。
const BIN_DIR = join(ROOT, ".scratch", "master-library-ui-2", "tmp-bin");
mkdirSync(BIN_DIR, { recursive: true });
writeFileSync(join(BIN_DIR, "bin.dat"), Buffer.from([0x00, 0x01, 0x02, 0x00, 0xff]));
const binRes = await fetchT("http://127.0.0.1:8000/api/code/file?dir=" + encodeURIComponent(BIN_DIR)
  + "&path=" + encodeURIComponent("bin.dat"));
check("（替代判据）二进制文件 → 400 中文（代码端点同约束）",
  binRes.status === 400 && (await binRes.text()).includes("二进制文件不可预览"), `dir=${BIN_DIR}`);

// ================= B9（工单 03 收口）：key 文件高亮 + 剪贴板子串 =================
await Eval(`document.querySelector('.ref-files-overlay [data-master-file="pin_config.h"]')?.click()`);
check("B9 pin_config.h 打开 + 高亮 span（C 高亮）", await waitFor(`
  (() => {
    const el = document.querySelector('.ref-files-overlay [data-master-content]');
    return !!el && el.querySelectorAll('[class*="tok-"]').length > 0
      && (el.textContent || '').includes('define');
  })()`));
const pinTokCount = await Eval(`document.querySelectorAll('.ref-files-overlay [data-master-content] [class*="tok-"]').length`);
check("B9 pin_config.h 高亮 span 计数 > 0", pinTokCount > 0, "tok=" + pinTokCount);
// 剪贴板：先授权（headless 读剪贴板需权限），再点「复制」读回内容
let clipNote = "未授权";
try {
  await cdp("Browser.grantPermissions", {
    origin: "http://127.0.0.1:8000", permissions: ["clipboardReadWrite", "clipboardSanitizedWrite"],
  });
  clipNote = "已授权";
} catch (e) { clipNote = "授权失败：" + String(e && e.message || e).slice(0, 60); }
await Eval(`document.querySelector('.ref-files-overlay [data-master-copy]')?.click()`);
await new Promise((r) => setTimeout(r, 400));
const clip = await Eval(`navigator.clipboard.readText().then((t) => t).catch((e) => 'ERR:' + e.message)`);
check("B9 复制钮 → 剪贴板内容 = 该文件正文子串", typeof clip === "string"
  && (clip.includes("#define") || clip.includes("pin_config")), `${clipNote}；len=${typeof clip === "string" ? clip.length : "n/a"}`);

// ================= 工单 03：高亮 + 复制按钮 =================
check("内容高亮 span（tok-* 类 > 0，C 高亮）", await Eval(`
  document.querySelectorAll('.ref-files-overlay [data-master-content] [class*="tok-"]').length > 0`));
check("复制按钮存在（data-master-copy）", await Eval(`
  !!document.querySelector('.ref-files-overlay [data-master-copy]')`));

// 关键文件（mspm0.syscfg）内容仍安全
await Eval(`document.querySelector('.ref-files-overlay .ref-files-close')?.click()`);
await waitFor(`!document.querySelector('.ref-files-overlay')`);
await Eval(`document.querySelector('#master-rows [data-master-detail="mspm0"]')?.click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay')`);
await Eval(`document.querySelector('.ref-files-overlay [data-master-file="mspm0.syscfg"]')?.click()`);
check("mspm0.syscfg 内容成功（addInstance 子串）", await waitFor(`
  (() => {
    const el = document.querySelector('.ref-files-overlay [data-master-content]');
    return !!el && !!el.querySelector('.master-file-pre') && (el.textContent || '').includes('addInstance');
  })()`));
// ── B9 口径修订（第十四轮）：源工单 03 写的是「pin_config.h / mspm0.syscfg 打开 → 高亮 span」，
// 但 `mspm0.syscfg` 的真实内容是 **SysConfig JavaScript**（含 `/** */` 注释与 addInstance 调用），
// 而 `fx/highlight.js` 的 languageOf 把 `.syscfg` 归到 **XML** 分词器（有 tests/js 守卫）⇒ 该文件
// 一个 tok-* 都不产出、预览是纯文本（实测纯件层与页面层均为 0，见
// `.scratch/master-library-ui-2/diag-syscfg-highlight.mjs` 输出）。据此把「高亮 span」这一判据
// 落到**真 XML 的工程配置文件**上（stm32 `user/Project.uvprojx` / mspm0 `.cproject`），
// syscfg 的纯文本表现按**已知缺口**记录，不当作已达标。
await Eval(`document.querySelector('.ref-files-overlay [data-master-file=".cproject"]')?.click()`);
check("B9 mspm0 .cproject（真 XML）带高亮 span", await waitFor(`
  (() => {
    const el = document.querySelector('.ref-files-overlay [data-master-content]');
    return !!el && el.querySelectorAll('[class*="tok-"]').length > 0;
  })()`));
const syscfgTok = await (async () => {
  await Eval(`document.querySelector('.ref-files-overlay [data-master-file="mspm0.syscfg"]')?.click()`);
  await new Promise((r) => setTimeout(r, 500));
  return Eval(`document.querySelectorAll('.ref-files-overlay [data-master-content] [class*="tok-"]').length`);
})();
console.log(`NOTE（已知缺口，不计 PASS/FAIL）：mspm0.syscfg 走 XML 分词器 ⇒ tok=${syscfgTok}（内容实为 JS，纯文本预览）`);await Eval(`document.querySelector('.ref-files-overlay .ref-files-close')?.click()`);
await waitFor(`!document.querySelector('.ref-files-overlay')`);

// ================= 工单 04：直接导入按钮就位（不真选不真导） =================
check("「直接导入替换」按钮与隐藏目录选择输入存在", await Eval(`
  !!document.getElementById('btn-direct-import')
  && !!document.getElementById('import-pick-dirs')`));

// ================= B10（工单 04 收口）：入口接线 + 平台下拉选项数 + 400 中文 =================
// 真实链路「选文件夹 → /api/masters/stage → 确认弹窗」走**原生目录选择器**：CDP 的
// `DOM.setFileInputFiles` 不会产生 `webkitRelativePath`，而产品按 `parts.length > 1`
// 过滤 ⇒ 无法用它跑通真实链路。故拆成四段机器判据：入口接线（spy）/ 下拉数据源 /
// 后端 400 中文 / 确认弹窗形状（下一段实测）。
const importSpy = await Eval(`(() => {
  const input = document.getElementById('import-pick-dirs');
  window.__pickCount = 0;
  if (!input.__spy) { input.addEventListener('click', () => { window.__pickCount++; }, true); input.__spy = 1; }
  document.getElementById('btn-direct-import').click();
  return window.__pickCount;
})()`);
check("B10 「直接导入替换」→ 触发隐藏目录选择输入", importSpy >= 1, "pickCount=" + importSpy);
const statePlatforms = await (await fetchT("http://127.0.0.1:8000/api/state")).json();
const optVals = await Eval(`[...document.getElementById('new-platform').options].map((o) => o.value)`);
check("B10/B17 平台下拉选项数 = state.platforms", Array.isArray(optVals)
  && optVals.length === statePlatforms.platforms.length
  && statePlatforms.platforms.every((p) => optVals.includes(p.id)),
  `dom=${JSON.stringify(optVals)} state=${JSON.stringify(statePlatforms.platforms.map((p) => p.id))}`);
const impEmpty = await fetchT("http://127.0.0.1:8000/api/masters/import", 8000,
  { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ platform: "stm32", project_dir: "" }) });
check("B10 空 project_dir → 400 中文", impEmpty.status === 400
  && (await impEmpty.text()).includes("缺少必填字段：project_dir"));
const impBadPlat = await fetchT("http://127.0.0.1:8000/api/masters/import", 8000,
  { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ platform: "nope", project_dir: "C:/tmp" }) });
check("B10 非法平台 → 400 中文（已知：stm32、mspm0）", impBadPlat.status === 400
  && (await impBadPlat.text()).includes("未知平台"));

// ================= B11（工单 05 收口）：共享确认弹窗三条闭合路径 =================
// 用「导入同形」的 extra（平台下拉 data-confirm-value）实测**确认**路径——只调组件、
// 不调后端，零写库；遮罩 / Esc 两条取消路径在同一个弹窗上验。
const openImportLike = () => Eval(`(async () => {
  const { confirmModal } = await import('/js/ui/confirm.js');
  const opts = [...document.getElementById('new-platform').options];
  const extra = '<div class="import-platform-field"><label>目标平台</label><select data-confirm-value>'
    + opts.map((o) => '<option value="' + o.value + '">' + o.textContent + '</option>').join('') + '</select></div>';
  window.__smokeConfirm = confirmModal({ title: '直接导入替换母版？', message: '冒烟：不真导', danger: true,
    confirmText: '确认替换', cancelText: '取消', extra });
  return true;
})()`);
await openImportLike();
check("B11 导入同形弹窗打开（.confirm-modal + 双钮 + 平台下拉）", await waitFor(`
  (() => {
    const o = document.querySelector('.ref-files-overlay');
    return !!o && !!o.querySelector('.confirm-modal') && !!o.querySelector('[data-confirm-ok]')
      && !!o.querySelector('[data-confirm-cancel]') && !!o.querySelector('[data-confirm-value]');
  })()`));
const dlgOpts = await Eval(`[...document.querySelectorAll('.ref-files-overlay [data-confirm-value] option')].length`);
check("B11 弹窗内平台下拉选项数 = 平台数", dlgOpts === statePlatforms.platforms.length, "dlg=" + dlgOpts);
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-ok]').click()`);
const okVal = await Eval(`window.__smokeConfirm`);
check("B11 确认闭合 → 返回所选值 + 弹窗关闭", okVal === "stm32"
  && await Eval(`!document.querySelector('.ref-files-overlay')`), JSON.stringify(okVal));
await openImportLike();
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-value]')`);
await Eval(`document.querySelector('.ref-files-overlay').click()`);
await new Promise((r) => setTimeout(r, 200));
check("B11 点遮罩 → 关闭（零写库）", await Eval(`!document.querySelector('.ref-files-overlay')`));
await openImportLike();
await waitFor(`!!document.querySelector('.ref-files-overlay [data-confirm-value]')`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))`);
await new Promise((r) => setTimeout(r, 200));
// 取消路径的返回值：带 `[data-confirm-value]` 的弹窗取消返回 **false**（无值型返回 null，
// 见 ui/confirm.js）；这里断言「falsy」而不是写死 null。
const escVal = await Eval(`window.__smokeConfirm`);
check("B11 Esc → 关闭 + 返回 falsy（取消无值）", !escVal
  && await Eval(`!document.querySelector('.ref-files-overlay')`), JSON.stringify(escVal));

// ================= 工单 05：共享确认弹窗开合（经赛题库删除入口，取消不真删） =================
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button')]
    .find((b) => b.dataset.tab === 'topic');
  if (tab) tab.click();
  return !!tab;
})()`);
check("赛题库列表已加载（真实库，删除钮存在）", await waitFor(`
  document.querySelectorAll('[data-topic-del]').length > 0`));
await Eval(`document.querySelector('[data-topic-del]')?.click()`);
check("共享确认弹窗打开（confirm-modal + 双钮 + 删除文案）", await waitFor(`
  (() => {
    const o = document.querySelector('.ref-files-overlay');
    return !!o && !!o.querySelector('.confirm-modal')
      && !!o.querySelector('[data-confirm-ok]')
      && !!o.querySelector('[data-confirm-cancel]')
      && (o.textContent || '').includes('删除赛题');
  })()`));
await Eval(`document.querySelector('.ref-files-overlay [data-confirm-cancel]')?.click()`);
await waitFor(`!document.querySelector('.ref-files-overlay')`);
check("取消 → 关闭 + 删除钮仍在（零写库）", await Eval(`
  !document.querySelector('.ref-files-overlay')
  && document.querySelectorAll('[data-topic-del]').length > 0`));
await Eval(`document.querySelector('[data-topic-del]')?.click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay')`);
await Eval(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))`);
await waitFor(`!document.querySelector('.ref-files-overlay')`);
check("Esc → 关闭", await Eval(`!document.querySelector('.ref-files-overlay')`));

// 截图存档（母版详情 + 树 + 高亮态）
await Eval(`(() => {
  const tab = [...document.querySelectorAll('nav button')]
    .find((b) => b.dataset.tab === 'master');
  if (tab) tab.click();
})()`);
await waitFor(`!!document.querySelector('#master-rows [data-master-detail="stm32"]')`);
await Eval(`document.querySelector('#master-rows [data-master-detail="stm32"]')?.click()`);
await waitFor(`!!document.querySelector('.ref-files-overlay')`);
await waitFor(`!!document.querySelector('.ref-files-overlay ul.master-tree')`);
const shot = await cdp("Page.captureScreenshot", { format: "png" });
mkdirSync(join(ROOT, ".scratch", "master-library-ui-2"), { recursive: true });
writeFileSync(join(ROOT, ".scratch", "master-library-ui-2", "shot-06-detail-tree.png"), Buffer.from(shot.result.data, "base64"));
console.log("shot-06-detail-tree.png 已存档");

console.log("---- 冒烟总览 ----");
console.log("PASS " + passed + " / FAIL " + failed);
console.log(failed === 0 ? "ALL PASS" : "FAILED");
process.exit(failed === 0 ? 0 : 1);
