import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const html = readFileSync(resolve(root, "src/contest_generator/static/index.html"), "utf8");

function extract(name) {
  const m = html.match(new RegExp("function " + name + "[\\s\\S]*?\\n\\}"));
  assert.ok(m, "function " + name + " not found in index.html");
  return new Function(m[0] + "; return " + name + ";")();
}

const btnIcon = extract("btnIcon");

const NAMES = ["rocket", "code", "sparkles", "doc", "clipboard", "wrench",
  "search", "save", "copy", "check", "upload", "wand"];

test("12 个图标名均返回 SVG 且为 btn-ico 类", () => {
  for (const n of NAMES) {
    const out = btnIcon(n);
    assert.ok(out.startsWith('<svg class="btn-ico"'), n + " 前缀错误: " + out.slice(0, 30));
    assert.ok(out.endsWith("</svg>"), n + " 未闭合");
    assert.ok(out.includes('viewBox="0 0 16 16"'), n + " 缺 viewBox");
    assert.ok(out.includes('stroke="currentColor"'), n + " 缺 stroke");
    assert.ok(!out.includes("undefined"), n + " 含 undefined");
  }
});

test("未知图标名返回空字符串（安全兜底）", () => {
  assert.equal(btnIcon("nope"), "");
  assert.equal(btnIcon(""), "");
});

test("HTML 中 data-ico 按钮均已注入图标映射内", () => {
  const used = [...html.matchAll(/data-ico="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(used.length >= 12, "data-ico 数量不足: " + used.length);
  for (const n of used) {
    assert.ok(NAMES.includes(n), "未注册图标: " + n);
  }
});

test("注入逻辑存在：initBtnIcons 遍历 [data-ico] 前置插入", () => {
  assert.ok(html.includes("function initBtnIcons()"));
  assert.ok(html.includes('document.querySelectorAll("[data-ico]")'));
  assert.ok(html.includes('insertAdjacentHTML("afterbegin", btnIcon(b.dataset.ico))'));
});

test("关键高频按钮已带 data-ico", () => {
  for (const id of ["btn-generate", "btn-skeleton", "btn-recommend", "btn-fix-center",
    "btn-handoff", "btn-save-settings", "btn-topic-search",
    "btn-topic-split", "btn-topic-confirm", "btn-confirm"]) {
    const m = html.match(new RegExp('<button id="' + id + '"[^>]*data-ico="[^"]+"'));
    assert.ok(m, id + " 缺 data-ico");
  }
});

test("按钮文本保留（图标注入不改文案）", () => {
  assert.ok(html.includes('data-ico="rocket">生成工程</button>'));
  assert.ok(html.includes('data-ico="save">保存设置</button>'));
  assert.ok(html.includes('data-ico="check">确认并入库</button>'));
});
