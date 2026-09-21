// static-import-guard.test.mjs — 装载根契约守卫（工单 frontend-boot-module/02 重定根）。
//
// 现场（2026-09-12 落盘、2026-09-13 真机复现）：commit 165665e5 从 fx/module.js 删掉了
// applyGroupRadio，而 index.html 的 import 清单漏删了这一项 —— 浏览器解析 import 时抛
//   SyntaxError: The requested module '/js/fx/module.js' does not provide an export named …
// **整页脚本全灭**：模块网格 0 张卡、导航点了没反应，而服务端 /api/* 全部 200、静态资源
// 也一一 200（所以"看起来像卡住"，强刷也没用——坏的是磁盘上的文件）。
//
// 那时候装载清单写在 index.html 里，本文件判的是"HTML 导入的名字，模块里到底有没有"。
// **2026-09-21 起清单搬进 static/js/boot.js**（工单 frontend-boot-module/02），所以本文件
// 重定根，判四件：
//   ① `index.html` **零 import**（装载根不再住在 HTML 里——"漏删一个导出"再也无法从 HTML
//      打崩整页）；
//   ② 装载标签唯一且指向装载根；清单里每条路径都指向真实存在的模块文件；
//   ③ **清单里每个名字都真的被对应模块导出**（同一类事故的现行形态：boot.js 与模块导出不一致）；
//   ④ **全图 import↔export 对账**（工单 05）：不止装载根那一层——**每个前端模块**的每条具名
//      import 都必须是目标模块真导出的名字。2026-09-12 那类事故（改一个导出 → SyntaxError）
//      在图的任何一处都可能发生，而 fx-guard 的 337 行名字表已退化成结构不变量，这一条是它的替代：
//      不挑名字、对整张图成立；
//   ⑤ **分层禁环**：boot 可 import ui/app，**任何 ui/app 不得 import boot**（否则成环）；
//   ⑥ 抽取器不静默失效（清单条数与具名数下限）。
//
// 判据单源 = tests/js/boot-contract.mjs（红证脚本 import 同一份）。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  indexHtmlImports, loadRootTag, parseModuleImports, parseModuleExports, readLoadRoot, listJs,
  graphBreaks, readJsModules, modulesImportingLoadRoot,
} from "./boot-contract.mjs";

const STATIC = fileURLToPath(new URL("../../src/contest_generator/static/", import.meta.url));
const html = readFileSync(STATIC + "index.html", "utf8");
const ROOT = readLoadRoot(STATIC);
const IMPORTS = ROOT === null ? [] : parseModuleImports(ROOT);

test("① index.html 零 import（装载根住在模块图里，不在 HTML 里）", () => {
  const found = indexHtmlImports(html);
  assert.deepEqual(
    found.map((f) => `${f.line}: ${f.text}`),
    [],
    "index.html 里出现 import —— 装载清单必须住在 static/js/boot.js：\n"
    + found.map((f) => `  ${f.line}: ${f.text}`).join("\n")
  );
});

test("② 装载标签唯一且指向装载根；清单路径都真实存在", () => {
  const tag = loadRootTag(html);
  assert.equal(tag.count, 1, `index.html 的 type="module" 标签应有且仅有一条（实际 ${tag.count}）`);
  assert.equal(tag.src, "/js/boot.js", `装载标签 src 应为 /js/boot.js（实际 ${tag.src}）`);
  assert.ok(ROOT !== null, "static/js/boot.js 不存在——装载根丢了？");
  const files = new Set(listJs(STATIC + "js")
    .map((p) => p.slice(STATIC.length + 3).split("\\").join("/")));
  const missing = IMPORTS
    .map((i) => i.spec)
    .filter((spec) => spec.startsWith("/js/") && !files.has(spec.slice(4)));
  assert.deepEqual(missing, [], `装载清单指向不存在的模块文件：${missing.join(", ")}`);
});

test("③ 全图 import↔export 对账：每个前端模块的每条具名 import 都真有出处（工单 05）", () => {
  // 这一条**包含**"装载根清单 ↔ 导出对账"（load root 也是图里的一个 entry），
  // 故不再单列一条弱副本（工单 05 评审：「缝越少越好」）。
  const modules = readJsModules(STATIC);
  const breaks = graphBreaks([{ key: "boot.js", text: ROOT }, ...modules]);
  const detail = breaks.map((b) =>
    `  ${b.from} → ${b.spec}：${b.why}${b.missing.length ? " " + b.missing.join(", ") : ""}`);
  assert.deepEqual(
    detail,
    [],
    "模块图里有死导入（浏览器会抛 SyntaxError 且整页不初始化——2026-09-12 的形态）：\n"
    + detail.join("\n")
  );
});

test("⑤ 装载根不被任何 ui/app 模块 import（分层禁环：boot 可 import ui/app，不许反过来）", () => {
  const back = modulesImportingLoadRoot(readJsModules(STATIC))
    .map((m) => `  ${m.key}:${m.line} → ${m.spec}`);
  assert.deepEqual(back, [],
    "有模块 import 了装载根 boot.js —— 分层成环（谁先求值会变成隐式约定）：\n" + back.join("\n"));
});

test("⑥ 抽取器不静默失效：装载根抽得到清单、且有具名导入", () => {
  assert.ok(IMPORTS.length >= 30, `只抽到 ${IMPORTS.length} 条 import（boot.js 结构变了？）`);
  const names = IMPORTS.reduce((n, i) => n + i.names.length, 0);
  assert.ok(names >= 50, `具名导入只抽到 ${names} 个（抽取器或清单形态变了）`);
});
