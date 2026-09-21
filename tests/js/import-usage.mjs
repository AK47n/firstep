// import-usage.mjs — 「零未使用具名 import」判据共享件
// （工单 frontend-import-fossils/01；frontend-boot-module/02 收敛解析器并重定取数面；
//   module-import-usage/01 把口径修对、取数面从装载根扩到**每个模块**）。
//
// 为什么单独一个文件（照 nav-tabs-shared.mjs 先例）：判据要被**多处**用——
//   1. tests/js/import-usage-guard.test.mjs（守卫本体；**工单 03 起**连全模块一起守）
//   2. .scratch/module-import-usage/synthetic-cases.mjs（合成红证）
//   3. .scratch/frontend-import-fossils/guard-red-proof.mjs（旧版 index.html 那一代）
//   4. .scratch/module-import-usage/probe-0{0d,0e,0f}-*.mjs（取数 / 模拟清点）
//   5. **工单 02 交付的** .scratch/module-import-usage/probe-02-base-red-proof.mjs（真红证）
// 放在 .test.mjs 里会让 import 方顺带注册并运行那批用例。
//
// 本文件是**这条不变量的单源**：
//   不变量 = 「import 语句里具名的符号，必须在宿主正文里**被用到**」
//
// ## 口径（工单 module-import-usage/01 定死；改动前请连同 spec 一起读）
//
//   · **「被使用」= 该 import 的本地名出现在宿主的代码里**，或**经再导出链被消费**
//     （`export { x };` / `export { x as y };` 的清单里出现——那本身就是一条消费边）。
//   · **注释 / 字符串 / 正则字面量 / 模板串的文本段里的同名词不算用过**——
//     正文走 `boot-contract.mjs::maskNonCode`（**模板表达式感知**：`${esc(x)}` 里的 `esc` 算用过）。
//     用 `maskCommentsAndStrings` 会把 `${…}` 里的真使用判成死的（假红，实测 33 处）；
//     不掩码则满屏假绿（注释/字符串把一个死 import 喂绿）。
//   · **按本地名判**（`locals`）：`import { A as B } from "M"` 里正文该出现的是 `B`。
//     按**源名** A 判会误报——实测 5 处 `WRITE_GUARD_ACTIONS as WG` 全被旧口径判成死的（假红）。
//   · **裸装载（`import "./x.js"`，零具名）永远合法**：判据不碰它。
//   · **模板替换的 `$` 不算使用**：`${` 那两个字符是语法、不是标识符，正文里一并掩掉——
//     不掩的话，任何含模板串的模块里名为 `$` 的 import 都会被喂绿（本轮实测过的假绿）。
//   · 取数面：宿主可以是**装载根**（`boot.js`）也可以是**任意模块**——同一核心，根不再特殊。
//
// ## 解析器不在本文件
//
// `parseImports` 现在是 `tests/js/boot-contract.mjs` 的 `parseModuleImports`（唯一一份，
// 注释感知）的薄适配器——它多给 `locals`（本地名）与 `raw`（语句原文切片，供剥语句用）。
import { parseModuleImports, maskNonCode } from "./boot-contract.mjs";

/** 切出 index.html 里 `<script type="module">` 块（读旧版源码用；找不到返回空串）。 */
export function hostScript(source) {
  const start = source.indexOf('<script type="module">');
  if (start < 0) return "";
  const end = source.indexOf("</script>", start);
  return source.slice(start, end < 0 ? source.length : end);
}

/** 抽 import（含多行具名清单）→ [{ spec, names, locals, raw }]；裸 import 的 names = []。 */
export function parseImports(script) {
  return parseModuleImports(script).map((e) => ({ spec: e.spec, names: e.names, locals: e.locals, raw: e.raw }));
}

/**
 * **旧口径**正文：原文 − import 语句 − **整行** `//` 注释。
 *
 * 已经**不是**判据正文（工单 module-import-usage/01 换成了 `criterionBody`）：它留着两个用处——
 * ① 红证脚本读**旧版源码**（`<script type="module">` 那一代）时对照口径；
 * ② 合成红证里当"旧口径会被注释喂绿"的**反面样本**（`synthetic-cases.mjs`）。
 */
export function hostBody(script, imports) {
  let stripped = script;
  for (const imp of imports) stripped = stripped.replace(imp.raw, " ");
  return stripped
    .split("\n")
    .filter((line) => !line.trim().startsWith("//"))
    .join("\n");
}

// 标识符边界：不能用 \b —— `$` 不是 word 字符，`\b$\b` 恒假，
// 会把真正在用的 `$`（app.js 的 getElementById 别名）误判成未使用（工单 01 实测的坑）。
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** 该标识符是否出现在文本里（按 JS 标识符边界，不按 \b）。 */
export function identRe(name) {
  return new RegExp("(?<![\\w$])" + escapeRe(name) + "(?![\\w$])");
}

/**
 * 判据正文：宿主**代码**（`maskNonCode`：注释/字符串/正则/模板文本段掩掉、`${…}` 保留）
 * 再剥掉 import 语句切片。掩码保长度，所以按原文里那条语句的区间抹同一段即可。
 *
 * 找不到切片 = 解析器与原文不一致 —— **大声失败**，不许静默少剥一条（少剥会让那条 import
 * 的名字在正文里"自己算用过"，判据当场变瞎）。
 */
function criterionBody(script, imports) {
  let out = maskNonCode(script);
  let cursor = 0;
  for (const imp of imports) {
    const at = script.indexOf(imp.raw, cursor);
    if (at < 0) {
      throw new Error(`import-usage：解析出的 import 切片在原文里找不到（${imp.spec}）—— 判据取数面失效`);
    }
    cursor = at + imp.raw.length;
    out = out.slice(0, at) + out.slice(at, cursor).replace(/[^\n]/g, " ") + out.slice(cursor);
  }
  return out;
}

/** 判据本体：→ [{ spec, unused }]；空数组 = 不变量成立。宿主可以是装载根，也可以是任意模块。 */
export function unusedImports(script) {
  const imports = parseImports(script);
  const body = criterionBody(script, imports);
  const problems = [];
  for (const { spec, names, locals } of imports) {
    if (!names.length) continue;                       // 裸装载：零具名，永远合法
    if (locals.length !== names.length) {
      // 两个平行数组不等长 = 解析器破了；**大声失败**（退回按源名判会静默误报，见文件头第 3 条口径）
      throw new Error(`import-usage：${spec} 的 names/locals 不等长（${names.length}/${locals.length}）`);
    }
    const unused = names.filter((n, i) => !identRe(locals[i]).test(body));
    if (unused.length) problems.push({ spec, unused });
  }
  return problems;
}
