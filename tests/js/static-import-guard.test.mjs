// static-import-guard.test.mjs — index.html 的 import 清单与 fx/ui 模块导出对账
// （工单 exclusive-group-gap-audit/01 尾巴：真机「firstep 一打开就卡死、强刷也不行」的根因守卫）。
//
// 现场（2026-09-12 落盘、2026-09-13 真机复现）：commit 165665e5 从 fx/module.js 删掉了
// applyGroupRadio（单选交互改用 applyGroupChoices/recordGroupChoice），但 index.html 的
// import 清单漏删了这一项 —— 浏览器解析 import 时抛
//   SyntaxError: The requested module '/js/fx/module.js' does not provide an export named 'applyGroupRadio'
// **整页脚本全灭**：模块网格 0 张卡、导航点了没反应，而服务端 /api/* 全部 200、静态资源
// 也一一 200（所以「看起来像卡住」，强刷也没用——坏的是磁盘上的文件）。
//
// 为什么既有守卫没拦住：fx-guard.test.mjs 只做单向检查（「模块是否导出 DOMAINS 登记的名字」
// + 「index.html 不得重复定义」），没有任何用例问「index.html 导入的名字，模块里到底有没有」。
// 本文件补这个方向：抽 index.html 的 import 清单 → 与模块源码的导出集合对账。
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";

const STATIC = new URL("../../src/contest_generator/static/", import.meta.url);
const html = readFileSync(new URL("index.html", STATIC), "utf8");

/** 抽 `import { a, b as c } from "/js/...";`（含多行）→ [{spec, names}] */
export function parseImports(source) {
  const out = [];
  const re = /import\s*\{([^}]*)\}\s*from\s*["']([^"']+)["']/g;
  let m;
  while ((m = re.exec(source)) !== null) {
    const names = m[1]
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .map((s) => s.split(/\s+as\s+/)[0].trim()); // 本地别名不影响「模块里要有谁」
    out.push({ spec: m[2], names });
  }
  return out;
}

/** 抽模块源码的导出名集合（static 声明形态；本项目 fx/ui 全用 static export） */
export function parseExports(source) {
  const names = new Set();
  const patterns = [
    /export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/g,
    /export\s+(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g,
    /export\s+class\s+([A-Za-z_$][\w$]*)/g,
    /export\s*\{([^}]*)\}/g, // export { a, b as c }
  ];
  for (const re of patterns) {
    let m;
    while ((m = re.exec(source)) !== null) {
      if (m[1] === undefined) continue;
      for (const part of m[1].split(",")) {
        const name = part.split(/\s+as\s+/)[0].trim();
        if (name) names.add(name);
      }
    }
  }
  return names;
}

const IMPORTS = parseImports(html);

test("抽取器不静默失效：index.html 至少抽到 30 条 import、每条至少 1 个名字", () => {
  assert.ok(IMPORTS.length >= 30, `只抽到 ${IMPORTS.length} 条 import（index.html 结构变了？）`);
  const empty = IMPORTS.filter((i) => i.names.length === 0);
  assert.deepEqual(empty, [], `有空 import 清单：${JSON.stringify(empty)}`);
});

test("每条 import 路径都指向 static/ 下真实存在的模块文件", () => {
  const missing = IMPORTS.filter(
    (i) => i.spec.startsWith("/js/") && !existsSync(new URL("." + i.spec, STATIC))
  ).map((i) => i.spec);
  assert.deepEqual(missing, [], `import 路径不存在：${missing.join(", ")}`);
});

test("index.html 导入的每个名字都真的被对应模块导出（防死导入打崩整页）", () => {
  const problems = [];
  for (const { spec, names } of IMPORTS) {
    if (!spec.startsWith("/js/")) continue;
    const url = new URL("." + spec, STATIC);
    if (!existsSync(url)) continue; // 上一用例报路径问题
    const source = readFileSync(url, "utf8");
    const exported = parseExports(source);
    assert.ok(exported.size > 0, `${spec} 抽不到任何导出（抽取器或模块形态变了）`);
    for (const name of names) {
      if (!exported.has(name)) problems.push(`${spec} 未导出 ${name}`);
    }
  }
  assert.deepEqual(
    problems,
    [],
    "index.html 与模块导出不一致（浏览器会抛 SyntaxError 且整页不初始化）：\n" + problems.join("\n")
  );
});
