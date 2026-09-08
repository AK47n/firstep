import { readFileSync } from "node:fs";
const spec = readFileSync("C:/Users/luoji/Desktop/firstep/.scratch/newcomer-glossary/spec.md", "utf8").replace(/\r/g, "");
const lines = spec.split("\n");
let start = -1;
for (let i = 0; i < lines.length; i++) if (lines[i].startsWith("### 卡片副标题")) { start = i; break; }
const specs = [];
for (let i = start + 1; i < lines.length; i++) {
  const t = lines[i].trim();
  if (!t) continue;
  const m = t.match(/^\d+\.\s*(.+)$/);
  if (!m) break;
  const body = m[1].includes("：") ? m[1].split("：").slice(1).join("：") : m[1];
  specs.push(body);
}
console.log("spec 12句 count:", specs.length);
const html = readFileSync("C:/Users/luoji/Desktop/firstep/src/contest_generator/static/index.html", "utf8");
const RE = /<span class="step-no">(\d+)<\/span>[^<]*<\/h2>\s*<p class="card-purpose">([^<]+)<\/p>/g;
const htmls = [];
let m;
while ((m = RE.exec(html))) htmls.push([parseInt(m[1]), m[2]]);
console.log("html card-purpose count:", htmls.length, " order:", htmls.map((x) => x[0]).join(","));
let ok = true;
for (let i = 0; i < Math.max(specs.length, htmls.length); i++) {
  const exp = specs[i];
  const got = (htmls[i] || [])[1];
  const match = exp === got;
  if (!match) ok = false;
  console.log((match ? "OK   " : "DIFF ") + (i + 1) + "  slen=" + (exp ? exp.length : "-") + " hlen=" + (got ? got.length : "-"));
  if (!match) { console.log("     spec:" + JSON.stringify(exp)); console.log("     html:" + JSON.stringify(got)); }
}
console.log("VERBATIM ALL MATCH:", ok);
