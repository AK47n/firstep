import { readFileSync } from "node:fs";
const html = readFileSync("src/contest_generator/static/index.html","utf8");
const js = readFileSync("src/contest_generator/static/js/ui/a11y.js","utf8");
const table = {};
for (const m of js.matchAll(/^\s*"([^"]+)":\s*"([^"]+)"/gm)) table[m[1]] = m[2];
const ids = new Set();
for (const m of html.matchAll(/<(input|textarea|select)([^>]*)>/g)) {
  const idm = m[2].match(/id="([^"]+)"/);
  if (!idm) continue;
  ids.add(idm[1]);
}
const labelFors = new Set();
for (const m of html.matchAll(/<label[^>]*for="([^"]+)"/g)) labelFors.add(m[1]);
const bare = [];
for (const id of ids) {
  if (id in table) continue;
  if (labelFors.has(id)) continue;
  const wrapped = new RegExp('<label[^>]*>[\\s\\S]*?id="'+id+'"').test(html) || new RegExp('id="'+id+'"[\\s\\S]*?</label>').test(html);
  if (wrapped) continue;
  const elm = html.match(new RegExp('<(input|textarea|select)[^>]*id="'+id+'"[^>]*>'));
  if (elm && elm[0].includes("aria-label")) continue;
  bare.push(id);
}
console.log("total input ids:", ids.size, "| labels in table:", Object.keys(table).length);
console.log("label[for] count:", labelFors.size);
console.log("=== BARE (no label-for / wrap / aria / not in table): ===");
console.log(bare.join(", ") || "(none)");
console.log("=== table ids with NO matching element (dead key): ===");
for (const id of Object.keys(table)) if (!ids.has(id)) console.log("DEAD: "+id);
console.log("=== table ids that ALSO have label[for] (aria-label overrides visible label): ===");
for (const id of Object.keys(table)) if (labelFors.has(id)) console.log("OVERRIDE: "+id);
