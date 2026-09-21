// import-usage.mjs — 装载清单判据共享件（工单 frontend-import-fossils/01；
// 工单 frontend-boot-module/02 收敛解析器并重定取数面）。
//
// 为什么单独一个文件（照 nav-tabs-shared.mjs 先例）：判据要被**两处**用——
//   1. tests/js/import-usage-guard.test.mjs（守卫本体）
//   2. .scratch/frontend-import-fossils/guard-red-proof.mjs（红证：同一套判据作用在旧版文件上）
// 放在 .test.mjs 里会让 import 方顺带注册并运行那批用例。
//
// 本文件是**装载清单判据的单源**：
//   不变量 = 「import 语句里具名的符号，必须在宿主正文里出现」
//   正文   = 宿主脚本去掉 import 语句与整行注释。
//
// **取数面（工单 frontend-boot-module/02 起）**：宿主 = `static/js/boot.js`（装载根）。
// 此前是 index.html 的 `<script type="module">` 块；`hostScript()` 保留下来，用于
// **读旧版源码**（红证按 `git show <base>` 取那一代）与夹具的静态锚点回退。
//
// **解析器不在本文件**：`parseImports` 现在是 `tests/js/boot-contract.mjs` 的
// `parseModuleImports`（唯一一份，注释感知）的薄适配器——它多给一个 `raw`（语句原文切片），
// 供 `hostBody` 把 import 整条剥掉。
import { parseModuleImports } from "./boot-contract.mjs";

/** 切出 index.html 里 `<script type="module">` 块（读旧版源码用；找不到返回空串）。 */
export function hostScript(source) {
  const start = source.indexOf('<script type="module">');
  if (start < 0) return "";
  const end = source.indexOf("</script>", start);
  return source.slice(start, end < 0 ? source.length : end);
}

/** 抽 import（含多行具名清单）→ [{ spec, names, raw }]；裸 import 的 names = []。 */
export function parseImports(script) {
  return parseModuleImports(script).map((e) => ({ spec: e.spec, names: e.names, raw: e.raw }));
}

/** 宿主正文：去掉 import 语句与整行注释。 */
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

/** 判据本体：→ [{ spec, unused }]；空数组 = 不变量成立。 */
export function unusedImports(script) {
  const imports = parseImports(script);
  const body = hostBody(script, imports);
  const problems = [];
  for (const { spec, names } of imports) {
    const unused = names.filter((n) => !identRe(n).test(body));
    if (unused.length) problems.push({ spec, unused });
  }
  return problems;
}
