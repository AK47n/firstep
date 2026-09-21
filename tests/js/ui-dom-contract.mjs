// ui-dom-contract.mjs — ui 层 DOM 契约的**静态判据单源**（工单 ui-dom-contract-gate/02）。
//
// 为什么单独一个文件（照 tests/js/import-usage.mjs 先例）：判据要被两处用——
//   1. tests/js/ui-dom-contract.test.mjs（守卫本体）
//   2. 红证 / 探针脚本（同一套判据作用在被打回原状的源码上）
// 放在 .test.mjs 里会让 import 方顺带注册并运行那批用例。
//
// ## 这条缝回答什么
//
// `ui/` 模块的 interface 就是 **DOM**：它绑哪些选择器、绑上之后用户做什么会看到什么
// （选件口径与行为契约在 tests/browser/ui-contract.spec.mjs）。本文件管**静态那一半**：
//
//   ① **id 存在性**：ui 源码里写死的 id，必须在"页面真正会出现的声明集合"里找得到。
//      声明集合 = 全前端源码（index.html ∪ js/**）里 `id="…"` / `.id = "…"` / `id: "…"`
//      的**字符串字面量**——检测页的 `#hwcheck-compile-status`、欢迎卡的
//      `#btn-welcome-dismiss` 都是 JS 现生成的，只查 index.html 会误报。
//      游离的 id 就是"点了没反应"的来源（`$("outpt-dir")` 静默 null，`?.` 一挂全静默）。
//   ② **装载可达性**：每个 `ui/*.js` 都必须从 index.html 走 import 图**到得了**
//      （`ui/a.js` → `ui/b.js` 也算——b 靠 a 装载是正当结构）；导出 `init*` 的模块，
//      该 init 必须**有人具名导入、且有人调用**。"写了却从没生效"就是这么来的。
//
// ## 判据**不绑写法**
//
// 判的是事实，不是源码形状：改名变量、两步取元素、可选链、`import { a as b }` 都算通过。
// 唯一被认可的选择器形态是**字符串字面量**里的 id——模板串拼出来的选择器
// （`$("tab-" + x)`）静态看不出来，不进判据（那靠行为契约那一层）。

import { readFileSync, readdirSync } from "node:fs";
import { parseModuleImports, listJs, ownInitExports, hasCallSite } from "./boot-contract.mjs";

// 这三个通用取件现在归 tests/js/boot-contract.mjs（唯一一份实现），本文件**转发**它们，
// 好让既有消费方（守卫、红证探针）不用改 import 路径。
export { listJs, ownInitExports, hasCallSite };

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * declaredIds(sources) → Set<id>：全前端源码里"声明过"的 id。
 *
 * sources = [{ path, text }]。三种声明形态都收：`id="…"`（静态标记与模板串里的元素）、
 * `.id = "…"`（createElement 之后赋值）、`id: "…"`（对象字面量）。只认字符串字面量。
 */
export function declaredIds(sources) {
  const ids = new Set();
  const patterns = [
    /\bid="([A-Za-z][\w:.-]*)"/g,
    /\.id\s*=\s*"([A-Za-z][\w:.-]*)"/g,
    /\bid:\s*"([A-Za-z][\w:.-]*)"/g,
  ];
  for (const { text } of sources) {
    for (const re of patterns) {
      for (const m of text.matchAll(re)) ids.add(m[1]);
    }
  }
  return ids;
}

/**
 * referencedIds(path, text) → [{ id, line }]：该文件里**静态引用**的 id。
 *
 * 三种选择器形态：`$("x")` / `getElementById("x")` / `querySelector("#x…")`
 * （含 `querySelectorAll`）。`#rrggbb` 这类颜色字面量按形态排除。
 */
export function referencedIds(path, text) {
  const out = [];
  const patterns = [
    /\$\(\s*"([A-Za-z][\w:.-]*)"\s*\)/g,
    /getElementById\(\s*"([A-Za-z][\w:.-]*)"\s*\)/g,
    /querySelector(?:All)?\(\s*"#([A-Za-z][\w-]*)(?:[\s"'.>[:\]]|$)/g,
  ];
  for (const re of patterns) {
    for (const m of text.matchAll(re)) {
      if (/^[0-9a-fA-F]{3,8}$/.test(m[1])) continue;   // 颜色字面量，不是 id
      out.push({ id: m[1], line: text.slice(0, m.index).split("\n").length, path });
    }
  }
  return out;
}

/** 判据①：→ [{ id, refs: [{ path, line }] }]；空数组 = 不变量成立。 */
export function danglingIds(uiSources, declared) {
  const byId = new Map();
  for (const { path, text } of uiSources) {
    for (const ref of referencedIds(path, text)) {
      if (declared.has(ref.id)) continue;
      if (!byId.has(ref.id)) byId.set(ref.id, []);
      byId.get(ref.id).push({ path, line: ref.line });
    }
  }
  return [...byId].sort(([a], [b]) => a.localeCompare(b))
    .map(([id, refs]) => ({ id, refs }));
}

// ---------------------------------------------------------------------------
// 装载图：从**装载根**（static/js/boot.js；工单 frontend-boot-module/02 起，此前是
// index.html 的宿主脚本块）出发，沿 import 边走到得了哪些 ui 模块
//
// 解析器**不在本文件**：`parseModuleImports` / `listJs` / `ownInitExports` / `hasCallSite`
// 都来自 `tests/js/boot-contract.mjs`（唯一一份 ESM 解析器，注释感知）。此前这里、那里、
// import-usage.mjs 各有一份，工单 02 的双轴评审把"判据抄两份必然分叉"挑出来后收敛了。
// ---------------------------------------------------------------------------

/** 该文本里的 import 边 → [{ spec, names, bare }]（names = **本地名**，`a as b` 收 b）。 */
export function importEdges(text) {
  return parseModuleImports(text).map((e) => ({ spec: e.spec, bare: e.bare, names: e.locals }));
}

/** 把说明符归一成 `js/…` 仓库内相对键；不是仓内前端模块则返回 null。 */
export function resolveSpec(spec, importerKey) {
  if (spec.startsWith("/js/")) return spec.slice(1);
  if (!spec.startsWith(".")) return null;          // 裸说明符（node: / 外部包）
  const base = importerKey ? importerKey.split("/").slice(0, -1) : [];
  for (const part of spec.split("/")) {
    if (part === "." || part === "") continue;
    if (part === "..") base.pop();
    else base.push(part);
  }
  return base.join("/");
}

// 标识符边界不能用 \b：`$` 不是 word 字符（import-usage.mjs 记着同一个坑）
export function identRe(name) {
  return new RegExp("(?<![\\w$])" + escapeRe(name) + "(?![\\w$])");
}

/**
 * reachableFromHost(hostText, modules) → { reachable, importedNames, bodies }。
 *
 * hostText = **装载根原文**（static/js/boot.js 全文；要带 import 语句——装载图的边在那里）。
 * modules = Map<key, text>，key 形如 `js/ui/guide.js`（**不含** static/ 前缀）。
 * 广度优先走 import 边；走不到的键就是"从没被装载"。
 */
export function reachableFromHost(hostText, modules) {
  const reachable = new Set();
  const importedNames = new Set();
  const bodies = [hostText];
  const queue = [];
  for (const edge of importEdges(hostText)) {
    const key = resolveSpec(edge.spec, "index.html");
    if (key) queue.push(key);
    for (const name of edge.names) importedNames.add(name);
  }
  while (queue.length) {
    const key = queue.shift();
    if (reachable.has(key) || !modules.has(key)) continue;
    reachable.add(key);
    const text = modules.get(key);
    bodies.push(text);
    for (const edge of importEdges(text)) {
      const next = resolveSpec(edge.spec, key);
      if (next) queue.push(next);
      for (const name of edge.names) importedNames.add(name);
    }
  }
  return { reachable, importedNames, bodies };
}

/**
 * 判据②：→ [{ path, why }]；空数组 = 不变量成立。
 *
 * 两种失效形态（**只判"本该生效却没生效"**，不逼所有 init 都公开——见下）：
 *   · **孤立模块**：从装载根沿 import 图走不到它（写了却从没进页面）；
 *   · **导入的 init 没人调**：有人从装载根或可达模块里**具名导入了**某个 `init*`，
 *     但可达的全部正文里没有它的**调用点**（"import 了却忘调"）——这是本轮要防的
 *     真实事故形态：导出与 import 都写了，忘了在启动区调用，页面安安静静什么都不发生。
 *     「调用点」的判据 = `名字(` **且那一行不是定义行**（定义本身也含 `名字(`，
 *     留在正文里会让"忘了调用"永远看不出来——本工单红证实测踩到过这个假绿）。
 *
 * 为什么**不**要求"每个 init* 导出都必须被外部具名导入"：ui 里 legit 地存在
 * 「模块顶部自己调」的写法和「导出给别的 ui 模块调」的写法，前者（如 ui/topic.js 的
 * `initTopicToolbar` 在模块底部自调）本来就不该出现在装载根的清单里——
 * 一刀切会逼出一批为过守卫而加的假导出。可达性由上面那条「孤立模块」保证。
 */
export function unreachableModules(uiModules, hostText, allModules) {
  const modules = new Map(allModules.map((m) => [m.key, m.text]));
  const { reachable, importedNames, bodies } = reachableFromHost(hostText, modules);
  const bodyText = bodies.join("\n");
  const problems = [];
  for (const { path, text } of uiModules) {
    const key = `js/${path}`;
    if (!reachable.has(key)) {
      problems.push({ path, why: "孤立模块：从装载根走 import 图到不了它" });
      continue;
    }
    for (const name of ownInitExports(text)) {
      if (importedNames.has(name) && !hasCallSite(bodyText, name)) {
        problems.push({
          path,
          why: `${name} 被 import 了却没人调用：可达正文里找不到 ${name}( 的调用点`,
        });
      }
    }
  }
  return problems.sort((a, b) => a.path.localeCompare(b.path));
}
