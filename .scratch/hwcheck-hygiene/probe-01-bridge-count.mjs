// probe-01-bridge-count.mjs — 只读量具：桥的**名字清单**两处口径对账（工单 hwcheck-hygiene/01）。
//
// 为什么要对这一次账：spec / 工单里写的「609 个名字 / 66 个模块」是立项探针
// `.scratch/hwcheck-hygiene/probe-bridge-callsites.mjs` 的读数，而它的切分用的是**未掩码原文**
// 按逗号 split —— 桥块里带**行尾注释**的条目会被整段吞掉（`fx/task.js` 的
// `taskPhaseHTML,   // …` 之后那两行）。本量具把两处口径并排跑出来，差值逐名打印。
//
// 用法：`node .scratch/hwcheck-hygiene/probe-01-bridge-count.mjs`
import { fileURLToPath } from "node:url";
import { readJsModules, windowBridgeNames } from "../../tests/js/boot-contract.mjs";

const REPO = fileURLToPath(new URL("../../", import.meta.url));
const MODULES = readJsModules(`${REPO}src/contest_generator/static`);

/** 立项探针那一版：原文切分，未掩码（**已知低估**，保留只为对账）。 */
function probeNames(text) {
  const names = new Set();
  const re = /Object\.assign\(\s*window\s*,\s*\{/g;
  let m;
  while ((m = re.exec(text))) {
    let i = m.index + m[0].length;
    let depth = 1;
    while (i < text.length && depth > 0) {
      const c = text[i];
      if (c === "{") depth++;
      else if (c === "}") depth--;
      if (depth === 0) break;
      i++;
    }
    const body = text.slice(m.index + m[0].length, i);
    for (const part of body.split(",")) {
      const t = part.trim();
      const kv = t.match(/^([A-Za-z_$][\w$]*)\s*:/);
      const shorthand = t.match(/^([A-Za-z_$][\w$]*)$/);
      if (kv) names.add(kv[1]);
      else if (shorthand) names.add(shorthand[1]);
    }
  }
  return names;
}

const guard = new Map();
const probe = new Map();
for (const mod of MODULES) {
  for (const n of windowBridgeNames(mod.text)) if (!guard.has(n)) guard.set(n, mod.key);
  for (const n of probeNames(mod.text)) if (!probe.has(n)) probe.set(n, mod.key);
}

const guardOnly = [...guard.keys()].filter((n) => !probe.has(n)).sort();
const probeOnly = [...probe.keys()].filter((n) => !guard.has(n)).sort();
console.log(`守卫（掩码口径）：${guard.size} 个名字 / ${new Set(guard.values()).size} 个模块发布`);
console.log(`立项探针（原文口径）：${probe.size} 个名字 / ${new Set(probe.values()).size} 个模块发布`);
console.log(`只被守卫抽到的（${guardOnly.length}）：`
  + guardOnly.map((n) => `${n}（${guard.get(n)}）`).join(", "));
console.log(`只被探针抽到的（${probeOnly.length}）：${probeOnly.join(", ")}`);
