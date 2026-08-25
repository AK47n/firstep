// 环境体检纯函数单测（工单 env-check-center/01）：envCheckStatusHTML
// （/api/env/status 数据 → 体检行 HTML）。只测外部行为（渲染结果），
// 子串断言防脆；兄弟函数注入沿用 module-info-dialog.test.mjs 范式。
import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const html = readFileSync(
  new URL("../../src/contest_generator/static/index.html", import.meta.url),
  "utf8"
);

// 括号配平提取（同 module-info-dialog.test.mjs 范式）；deps = 注入的兄弟函数依赖
function extract(name, deps) {
  const start = html.indexOf("function " + name);
  assert.ok(start !== -1, "index.html 中未找到 " + name + " 函数体（改名了？）");
  const open = html.indexOf("{", start);
  assert.ok(open !== -1, name + " 函数体缺少左花括号");
  let depth = 0;
  for (let i = open; i < html.length; i++) {
    if (html[i] === "{") depth++;
    else if (html[i] === "}") {
      depth--;
      if (depth === 0) {
        const fnSrc = html.slice(start, i + 1);
        if (deps && Object.keys(deps).length) {
          return new Function(...Object.keys(deps), "return (" + fnSrc + ")")(
            ...Object.values(deps)
          );
        }
        return new Function("return (" + fnSrc + ")")();
      }
    }
  }
  throw new Error("未找到 " + name + " 函数体结束花括号");
}

const ENV_BADGE_GLYPH = { "env-ok": "✓", "env-warn": "!", "env-err": "✕" };
const esc = extract("esc");
const envRowHTML = extract("envRowHTML", { ENV_BADGE_GLYPH });
const envChannelHTML = extract("envChannelHTML", { envRowHTML, esc });
const envCheckStatusHTML = extract("envCheckStatusHTML", {
  esc,
  envRowHTML,
  envChannelHTML,
});

// fixture：全字段形状（字段名与 /api/env/status 契约一致）
const status = {
  api_configured: true,
  llm: { base_url: "https://api.deepseek.com", model: "deepseek-chat", local_llm_base_url: "" },
  toolchains: {
    stm32: { found: true, path: "C:\\Keil5\\Core\\UV4\\UV4.exe", override: true },
    mspm0: { found: false, path: null, override: false },
  },
  platforms: [
    { id: "stm32", name: "STM32F103C8T6", status: "ready" },
    { id: "mspm0", name: "MSPM0G3507", status: "no-master" },
  ],
  module_library: { dir: "C:\\libs\\modules", exists: true, count: 26, error: null },
  masters_dir: { dir: "C:\\libs\\masters", exists: true },
  output_dir: { dir: "C:\\Users\\me\\Desktop", exists: true, writable: true },
};

test("API 已配置：模型/端点回显 + env-ok", () => {
  const out = envCheckStatusHTML(status, null, null);
  assert.ok(out.includes('data-env-row="api"'));
  assert.ok(out.includes("env-ok"));
  assert.ok(out.includes("已保存"));
  assert.ok(out.includes("deepseek-chat"));
  assert.ok(out.includes("https://api.deepseek.com"));
});

test("API 未配置：env-err + 引导文案", () => {
  const out = envCheckStatusHTML({ ...status, api_configured: false, llm: null }, null, null);
  assert.ok(out.includes('data-env-row="api"'));
  assert.ok(out.includes("env-err"));
  assert.ok(out.includes("未保存主 API key"));
});

test("文本通道三态：待检查 / 正常（模型+耗时+回复） / 失败", () => {
  const pending = envCheckStatusHTML(status, null, null);
  assert.ok(pending.includes('data-env-row="llm-text"'));
  assert.ok(pending.includes("待检查"));
  assert.ok(pending.includes("env-warn"));

  const ok = envCheckStatusHTML(status, { ok: true, data: { model: "deepseek-chat", elapsed_ms: 812, reply: "PONG" } }, null);
  assert.ok(ok.includes("正常（模型 deepseek-chat，耗时 812ms）"));
  assert.ok(ok.includes("PONG"));
  assert.ok(ok.includes("env-ok"));

  const fail = envCheckStatusHTML(status, { ok: false, msg: "文本通道自检失败：连接超时" }, null);
  assert.ok(fail.includes("失败：文本通道自检失败：连接超时"));
  assert.ok(fail.includes("env-err"));
});

test("视觉通道：独立行 + 成功回显", () => {
  const out = envCheckStatusHTML(status, null, { ok: true, data: { model: "deepseek-v4-flash-vision-exp", elapsed_ms: 1500 } });
  assert.ok(out.includes('data-env-row="llm-vision"'));
  assert.ok(out.includes("正常（模型 deepseek-v4-flash-vision-exp，耗时 1500ms）"));
});

test("工具链：找到+覆盖标注 env-ok / 未找到 env-err；缺 platform 键不渲染行", () => {
  const out = envCheckStatusHTML(status, null, null);
  assert.ok(out.includes('data-env-row="toolchain-stm32"'));
  assert.ok(out.includes("C:\\Keil5\\Core\\UV4\\UV4.exe"));
  assert.ok(out.includes("设置页路径覆盖"));
  assert.ok(out.includes('data-env-row="toolchain-mspm0"'));
  assert.ok(out.includes("未找到 gmake"));

  const sparse = envCheckStatusHTML({ ...status, toolchains: {} }, null, null);
  assert.ok(!sparse.includes("toolchain-stm32"));
  assert.ok(!sparse.includes("toolchain-mspm0"));
});

test("平台母版：ready env-ok / no-master env-warn", () => {
  const out = envCheckStatusHTML(status, null, null);
  assert.ok(out.includes('data-env-row="platform-stm32"'));
  assert.ok(out.includes("已就绪（可生成）"));
  assert.ok(out.includes('data-env-row="platform-mspm0"'));
  assert.ok(out.includes("未导入母版（生成前需导入）"));
});

test("模块库四态：错误 / 目录不存在 / 有模块 / 空目录", () => {
  const err = envCheckStatusHTML(
    { ...status, module_library: { dir: "C:\\libs\\modules", exists: true, count: 0, error: "模块库加载失败：x" } },
    null, null);
  assert.ok(err.includes("模块库加载失败：x"));
  assert.ok(err.includes("env-err"));

  const missing = envCheckStatusHTML(
    { ...status, module_library: { dir: "C:\\libs\\modules", exists: false, count: 0, error: null } },
    null, null);
  assert.ok(missing.includes("目录不存在：C:\\libs\\modules"));

  const ok = envCheckStatusHTML(status, null, null);
  assert.ok(ok.includes("26 个模块：C:\\libs\\modules"));
  assert.ok(ok.includes("env-ok"));

  const empty = envCheckStatusHTML(
    { ...status, module_library: { dir: "C:\\libs\\modules", exists: true, count: 0, error: null } },
    null, null);
  assert.ok(empty.includes("0 个模块"));
  assert.ok(empty.includes("env-warn"));
});

test("母版目录：存在 env-ok / 不存在 env-warn 提示首次创建", () => {
  const ok = envCheckStatusHTML(status, null, null);
  assert.ok(ok.includes('data-env-row="masters-dir"'));
  assert.ok(ok.includes("C:\\libs\\masters"));
  const missing = envCheckStatusHTML(
    { ...status, masters_dir: { dir: "C:\\libs\\masters", exists: false } },
    null, null);
  assert.ok(missing.includes("不存在（首次导入母版时创建）"));
  assert.ok(missing.includes("env-warn"));
});

test("输出目录：可写 env-ok / 不存在 env-err / 不可写 env-err", () => {
  const ok = envCheckStatusHTML(status, null, null);
  assert.ok(ok.includes("C:\\Users\\me\\Desktop"));
  assert.ok(ok.includes("可写"));
  const missing = envCheckStatusHTML(
    { ...status, output_dir: { dir: "C:\\nope", exists: false, writable: false } },
    null, null);
  assert.ok(missing.includes("目录不存在：C:\\nope"));
  assert.ok(missing.includes("env-err"));
  const ro = envCheckStatusHTML(
    { ...status, output_dir: { dir: "C:\\Users\\me\\Desktop", exists: true, writable: false } },
    null, null);
  assert.ok(ro.includes("目录不可写：C:\\Users\\me\\Desktop"));
});

test("转义：路径/错误文本中的 HTML 字符不直出", () => {
  const evil = { ...status, module_library: { dir: "C:\\<x>", exists: false, count: 0, error: null } };
  const out = envCheckStatusHTML(evil, null, null);
  assert.ok(!out.includes("<x>"));
  assert.ok(out.includes("&lt;x&gt;"));
});

test("status 为 null/空 → 空串", () => {
  assert.equal(envCheckStatusHTML(null, null, null), "");
  assert.equal(envCheckStatusHTML(undefined, null, null), "");
});

test("本地路由配置回显（local_llm_base_url 非空）", () => {
  const out = envCheckStatusHTML(
    { ...status, llm: { base_url: "", model: "qwen3-coder:30b-local", local_llm_base_url: "http://localhost:11434/v1" } },
    null, null);
  assert.ok(out.includes("本地路由 http://localhost:11434/v1"));
});
