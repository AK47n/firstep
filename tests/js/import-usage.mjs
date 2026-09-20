// import-usage.mjs — 装载清单判据共享件（工单 frontend-import-fossils/01）。
//
// 为什么单独一个文件（照 nav-tabs-shared.mjs 先例）：判据要被**两处**用——
//   1. tests/js/import-usage-guard.test.mjs（守卫本体）
//   2. .scratch/frontend-import-fossils/guard-red-proof.mjs（红证：同一套判据作用在 HEAD 版文件上）
// 放在 .test.mjs 里会让 import 方顺带注册并运行那批用例（红证文件里红绿两段混在一起）。
//
// 本文件是**装载清单判据的单源**：
//   不变量 = 「import 语句里具名的符号，必须在宿主脚本正文里出现」
//   正文 = 宿主脚本块（`<script type="module">` … `</script>`）去掉 import 语句与整行注释。

/** 切出宿主脚本块；找不到返回空串。 */
export function hostScript(source) {
  const start = source.indexOf('<script type="module">');
  if (start < 0) return "";
  const end = source.indexOf("</script>", start);
  return source.slice(start, end < 0 ? source.length : end);
}

/** 抽 import（含多行具名清单）：→ [{ spec, names, raw }]；裸 import 的 names = []。 */
export function parseImports(script) {
  const out = [];
  const re = /^[ \t]*import\s*(?:\{([^}]*)\}\s*from\s*)?["']([^"']+)["'][ \t]*;?/gm;
  let m;
  while ((m = re.exec(script)) !== null) {
    const names = [];
    if (m[1] !== undefined) {
      for (const part of m[1].split(",")) {
        const name = part.trim().split(/\s+as\s+/)[0].trim();
        if (name) names.push(name);
      }
    }
    out.push({ spec: m[2], names, raw: m[0] });
  }
  return out;
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
