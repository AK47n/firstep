// 阶段 2 工单 07：模块库 tab 迁 ui/library.js（12 函数 + libUI + 模块库侧
// btn-add-file-row / addFileRow() / 两个 bindFilePicker mod 绑定 / 入库按钮监听；
// 跨簇硬边 openModuleInfo / renderModulePool 从 ui/generate-recommend.js import——12 交付后成立）。
// 删除段（物理升序，内容锚点寻址）：库工具栏状态+渲染+编辑弹窗簇（4898-5262 一带）/
// 选择文件注记+mod 绑定（5264-5268）/ 新建载荷+两按钮监听（5272-5323 一带）。
// host 改造：顶部 import 行 + generate-recommend 代理行裁 openModuleInfo（host 不再用）。
// 参考库两个 bindFilePicker 绑定点留 host（工单 08 迁）。全程 CRLF 感知。
import { readFileSync, writeFileSync } from "node:fs";

const p = "src/contest_generator/static/index.html";
let txt = readFileSync(p, "utf8");
if (!txt.includes("\r\n")) throw new Error("not CRLF?");
const eol = "\r\n";
const lines = txt.split(eol);
const must = (i, what) => { if (i < 0) throw new Error("anchor not found: " + what); return i; };

if (lines.some((l) => l.includes('from "/js/ui/library.js"'))) throw new Error("library import already present");

// ---- 1) host import：step-state import 之后追加；generate-recommend 代理行裁 openModuleInfo
{
  const ss = must(lines.findIndex((l) => l.includes('from "/js/ui/step-state.js"')), "step-state import");
  lines.splice(ss + 1, 0,
    'import { loadLibrary, initLibraryToolbar, initAddSections, editModule, deleteModule, newModulePayload } from "/js/ui/library.js";');
}
{
  const gi = must(lines.findIndex((l) => l.includes('from "/js/ui/generate-recommend.js"')), "recommend import");
  if (!lines[gi].includes("openModuleInfo")) throw new Error("openModuleInfo not in recommend import?");
  lines[gi] = lines[gi].replace("openModuleInfo, ", "").replace(", openModuleInfo", "");
  if (lines[gi].includes("openModuleInfo")) throw new Error("openModuleInfo still in import");
}

// ---- 2) 段 A：库工具栏状态 + 渲染 + 编辑弹窗簇（libUI → addFileRow() 初始行）→ 注记
{
  const a = must(lines.findIndex((l) => l === "// —— 模块库工具栏状态与渲染（library-toolbar/02）：过滤条件集中于此，"), "libUI header");
  const b = must(lines.findIndex((l) => l.startsWith("function newModulePayload() {")), "newModulePayload");
  // 段 A 结束于 addFileRow() 行（在 newModulePayload 之前），把 06 注记 + btn-add-file-row + 初始行一并带走
  let e = b;
  while (e > a && lines[e] !== "addFileRow();") e--;
  if (e === a) throw new Error("addFileRow() anchor not before newModulePayload");
  const removed = lines.slice(a, e + 1).join(eol);
  for (const n of ["libUI", "renderLibraryChips", "renderLibraryStats", "renderLibraryTable", "clearLibraryFilter", "initAddSections", "initLibraryToolbar", "loadLibrary", "editDescription", "editModule", "deleteModule"]) {
    if (!new RegExp("(function|const)\\s+" + n + "\\b").test(removed)) throw new Error("missing " + n);
  }
  if (!removed.includes('$("btn-add-file-row")')) throw new Error("btn-add-file-row listener missing");
  const note = [
    "// ===== 模块库 tab：过滤 / 排序 / 表格 / 加载 / 简介与平台级编辑 / 新建入库 =====",
    "// 已迁至 static/js/ui/library.js（阶段 2 工单 07）：libUI 状态 + renderLibraryChips /",
    "// renderLibraryStats / renderLibraryTable / clearLibraryFilter / initAddSections /",
    "// initLibraryToolbar / loadLibrary / editDescription / editModule / deleteModule /",
    "// newModulePayload + 添加模块表单行监听（btn-add-file-row / btn-draft-desc /",
    "// btn-add-module-submit / 两个 mod 文件选择绑定）。跨簇硬边 openModuleInfo /",
    "// renderModulePool 从 ui/generate-recommend.js import（12 交付后成立）；",
    "// host 页签分发器 / 启动区经顶部 import 调 loadLibrary / initLibraryToolbar /",
    "// initAddSections（见 import 行与启动区）。",
    "",
  ];
  lines.splice(a, e - a + 1, ...note);
}

// ---- 3) 段 B：选择文件注记 + mod 两个绑定 → 一行注记（ref 两个绑定留 host）
{
  const a = must(lines.findIndex((l) => l === "// ===== 选择文件 / 文件夹 → 读为文本填入文件行（模块库 / 参考库共用）====="), "picker note");
  const b = must(lines.findIndex((l) => l === 'bindFilePicker("btn-pick-mod-dir", "pick-mod-dir", "new-files", "add-msg");'), "mod dir binding");
  const removed = lines.slice(a, b + 1).join(eol);
  if (!removed.includes("btn-pick-mod-files")) throw new Error("mod files binding not in span");
  const refLine = must(lines.findIndex((l) => l === 'bindFilePicker("btn-ref-pick-files", "ref-pick-files", "ref-files", "ref-draft-msg");'), "ref files binding");
  if (refLine !== b + 1) throw new Error("ref binding must follow mod dir binding directly: " + refLine + " vs " + (b + 1));
  const note = [
    "// 模块库两个文件选择绑定已随簇迁至 ui/library.js（阶段 2 工单 07）；",
    "// 参考库两个绑定留 host（工单 08 迁簇时带走）。",
  ];
  lines.splice(a, b - a + 1, ...note);
}

// ---- 4) 段 C：newModulePayload + 两个入库按钮监听 → 注记
{
  const a = must(lines.findIndex((l) => l.startsWith("function newModulePayload() {")), "newModulePayload");
  const b = must(lines.findIndex((l) => l.startsWith('$("btn-add-module-submit").addEventListener("click"')), "submit listener");
  let e = b;
  while (e < lines.length && lines[e] !== "});") e++;
  if (e >= lines.length) throw new Error("submit listener end not found");
  const removed = lines.slice(a, e + 1).join(eol);
  if (!removed.includes("newModulePayload")) throw new Error("newModulePayload missing");
  if (!removed.includes("btn-draft-desc") || !removed.includes("btn-add-module-submit")) throw new Error("listeners missing");
  // 边界：下一行应为参考库区段头（dashes 或注释）
  const next = lines[e + 1];
  if (!/^\/\/ -+$/.test(next) && !next.startsWith("//") && next !== "") {
    throw new Error("unexpected boundary after submit listener: " + JSON.stringify(next));
  }
  const note = [
    "// 新建模块载荷（newModulePayload）与「AI 简介草稿 / 校验并入库」两个按钮监听",
    "// 已随簇迁至 static/js/ui/library.js（阶段 2 工单 07）。",
    "",
  ];
  lines.splice(a, e - a + 1, ...note);
}

// ---- 校验
const out = lines.join(eol);
for (const n of ["renderLibraryChips", "renderLibraryStats", "renderLibraryTable", "clearLibraryFilter", "initAddSections", "initLibraryToolbar", "loadLibrary", "editDescription", "editModule", "deleteModule", "newModulePayload"]) {
  if (new RegExp("(function|const)\\s+" + n + "\\b").test(out)) throw new Error("residual definition of " + n);
}
if (/^const libUI\b/m.test(out)) throw new Error("residual libUI");
for (const frag of ['loadLibrary();', 'initLibraryToolbar();', 'initAddSections();', 'bindFilePicker("btn-ref-pick-files"', 'bindFilePicker("btn-ref-pick-dir"', 'from "/js/ui/library.js"']) {
  if (!out.includes(frag)) throw new Error("host call site / import vanished: " + frag);
}
if (out.includes('bindFilePicker("btn-pick-mod-files"')) throw new Error("mod binding still in host");
if (out.includes("openModuleInfo(b.dataset.info")) throw new Error("openModuleInfo call still in host (moved to library.js)");
if (out.includes("function moduleRowHTML")) throw new Error("fx single-source drift");

writeFileSync(p, out, "utf8");
console.log("OK: library cluster moved; host rewired; lines now", lines.length);
