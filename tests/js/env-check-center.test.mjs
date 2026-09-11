// 环境体检纯函数单测（工单 env-check-center/01）：envCheckStatusHTML
// （/api/env/status 数据 → 体检行 HTML）。只测外部行为（渲染结果），
// 子串断言防脆；兄弟函数注入沿用 module-info-dialog.test.mjs 范式。
import test from "node:test";
import assert from "node:assert/strict";
import { esc } from "../../src/contest_generator/static/js/fx/core.js";
import { ENV_BADGE_GLYPH, envRowHTML, envChannelHTML, envCheckStatusHTML, toolchainProbeText, ccsSourceText, CCS_PROBE_NOTE } from "../../src/contest_generator/static/js/fx/env.js";

// fixture：全字段形状（字段名与 /api/env/status 契约一致）；CCS 三件带 root
// （工单 real-acceptance/06：安装根反推，命中件才有）
const status = {
  api_configured: true,
  llm: { base_url: "https://api.deepseek.com", model: "deepseek-chat", local_llm_base_url: "" },
  toolchains: {
    stm32: { found: true, path: "C:\\Keil5\\Core\\UV4\\UV4.exe", override: true },
    mspm0: { found: false, path: null, override: false },
  },
  ccs_tools: {
    sdk: { found: true, path: "C:\\ti\\ccs2051\\mspm0_sdk_2_10_00_04", root: "C:\\ti\\ccs2051", override: false },
    compiler: { found: false, path: null, root: null, override: false },
    sysconfig: { found: true, path: "C:\\ti\\ccs2051\\sysconfig_1.26.2\\sysconfig_cli.bat", root: "C:\\ti\\ccs2051", override: true },
  },
  library_dirs: {
    topic: { dir: "C:\\libs\\topics", exists: true, writable: true },
    reference: { dir: "C:\\libs\\references", exists: false, writable: false },
    pdf: { dir: "C:\\sources\\materials", exists: true, writable: true },
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

test("检查中态：点击后双通道行呈现「检查中…」+ env-warn（spec 行级加载中）", () => {
  const out = envCheckStatusHTML(status, "pending", "pending");
  assert.ok(out.includes("检查中…"));
  assert.ok(!out.includes("待检查"));
  const textRow = out.slice(out.indexOf('data-env-row="llm-text"'), out.indexOf('data-env-row="llm-vision"'));
  assert.ok(textRow.includes("检查中…"));
  assert.ok(textRow.includes("env-warn"));
  const visionRow = out.slice(out.indexOf('data-env-row="llm-vision"'));
  assert.ok(visionRow.includes("检查中…"));
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
  // 叫法统一（工单 ux-walkthrough-02/06）：mspm0 行 = CCS + MSPM0 SDK
  assert.ok(out.includes("CCS + MSPM0 SDK（mspm0）"));
  // 缺失项带「去设置填」跳转
  assert.ok(out.includes('data-env-jump="set-gmake-path"'));
  assert.ok(!out.includes('data-env-jump="set-uv4-path"'));  // stm32 命中态无跳转
  const stmMissing = envCheckStatusHTML(
    { ...status, toolchains: { ...status.toolchains, stm32: { found: false, path: null, override: false } } },
    null, null);
  assert.ok(stmMissing.includes('data-env-jump="set-uv4-path"'));

  const sparse = envCheckStatusHTML({ ...status, toolchains: {} }, null, null);
  assert.ok(!sparse.includes("toolchain-stm32"));
  assert.ok(!sparse.includes("toolchain-mspm0"));
});

test("CCS 三件套逐行：命中 env-ok + 路径 / 未设置 env-err + 跳转；缺键不渲染", () => {
  const out = envCheckStatusHTML(status, null, null);
  assert.ok(out.includes('data-env-row="ccs-sdk"'));
  assert.ok(out.includes("CCS SDK（mspm0）"));
  assert.ok(out.includes("C:\\ti\\ccs2051\\mspm0_sdk_2_10_00_04"));
  // 安装根随行带出（工单 real-acceptance/06）：根不是 path 的可见前缀时（编译器
  // 在 ccs/tools/compiler 下三层）用户才看得出跨目录
  assert.ok(out.includes("（安装根 C:\\ti\\ccs2051）"));
  assert.ok(out.includes('data-env-row="ccs-compiler"'));
  assert.ok(out.includes("未设置（可在设置页填 ccs_compiler_dir）"));
  assert.ok(out.includes('data-env-jump="set-ccs-compiler-dir"'));
  assert.ok(out.includes('data-env-collapse="toolchain"'));
  assert.ok(out.includes('data-env-row="ccs-sysconfig"'));
  assert.ok(out.includes("设置页路径覆盖"));

  const sparse = envCheckStatusHTML({ ...status, ccs_tools: {} }, null, null);
  assert.ok(!sparse.includes('data-env-row="ccs-'));
});

test("CCS 探测说明行：独立探测 / 可能跨安装目录文案 + 三件来源一句话（工单 06）", () => {
  // 本机实况形状（real-acceptance/06 表格）：编译器 ccs2050、SDK + SysConfig ccs2051
  const mixed = {
    ...status,
    ccs_tools: {
      sdk: { found: true, path: "C:\\ti\\ccs2051\\mspm0_sdk_2_10_00_04", root: "C:\\ti\\ccs2051", override: false },
      compiler: { found: true, path: "C:\\ti\\ccs2050\\ccs\\tools\\compiler\\ti-cgt-armllvm_4.0.4.LTS", root: "C:\\ti\\ccs2050", override: false },
      sysconfig: { found: true, path: "C:\\ti\\ccs2051\\sysconfig_1.26.2\\sysconfig_cli.bat", root: "C:\\ti\\ccs2051", override: false },
    },
  };
  const out = envCheckStatusHTML(mixed, null, null);
  const row = out.slice(out.indexOf('data-env-row="ccs-note"'), out.indexOf('data-env-row="ccs-note"') + 700);
  assert.ok(row.includes("三件逐件独立探测"), "说明行含探测规则");
  assert.ok(row.includes("可能来自不同 CCS 安装目录"), "说明行含跨目录提示");
  assert.ok(row.includes("一个 CCS 版本 = 一套工具链"), "说明行点名要打破的直觉");
  assert.ok(row.includes("编译器 ccs2050"), "本机来源逐件列出（编译器）");
  assert.ok(row.includes("SDK ccs2051") && row.includes("SysConfig ccs2051"), "本机来源逐件列出（SDK / SysConfig）");
  assert.ok(row.includes("（跨安装目录）"), "判定为跨安装目录");
  assert.ok(row.includes("env-warn"), "说明行是「注意」而非报错");
  assert.ok(!row.includes("去设置填"), "说明行不带跳转按钮（不是错误）");
  // 说明行排在三条件行之后
  assert.ok(out.indexOf('data-env-row="ccs-sysconfig"') < out.indexOf('data-env-row="ccs-note"'));

  // 三件同源 → 判语换「三件同源」
  const same = {
    ...status,
    ccs_tools: Object.fromEntries(Object.entries(mixed.ccs_tools).map(([k, v]) => [k, { ...v, root: "C:\\ti\\ccs2051" }])),
  };
  assert.ok(envCheckStatusHTML(same, null, null).includes("（三件同源）"));

  // 缺键（旧后端载荷）→ 无说明行，也不炸
  assert.ok(!envCheckStatusHTML({ ...status, ccs_tools: {} }, null, null).includes('data-env-row="ccs-note"'));
});

test("ccsSourceText：跨安装目录 / 三件同源 / 无 root 不猜（工单 06）", () => {
  assert.equal(
    ccsSourceText({
      compiler: { found: true, root: "C:\\ti\\ccs2050" },
      sdk: { found: true, root: "C:\\ti\\ccs2051" },
      sysconfig: { found: true, root: "C:\\ti\\ccs2051\\" },
    }),
    "三件来源：编译器 ccs2050；SDK ccs2051；SysConfig ccs2051（跨安装目录）");
  assert.equal(
    ccsSourceText({
      compiler: { found: true, root: "C:\\ti\\ccs2051" },
      sdk: { found: true, root: "C:\\ti\\ccs2051" },
      sysconfig: { found: true, root: "C:\\ti\\ccs2051" },
    }),
    "三件来源：编译器 ccs2051；SDK ccs2051；SysConfig ccs2051（三件同源）");
  // 自定义路径（root=null）与缺件都不进来源句；全无 root → 空串
  assert.equal(ccsSourceText({
    compiler: { found: true, root: null },
    sdk: { found: false, root: null },
    sysconfig: { found: true, root: "C:\\ti\\ccs2051" },
  }), "三件来源：SysConfig ccs2051");
  assert.equal(ccsSourceText({}), "");
  assert.equal(ccsSourceText(null), "");
  // 文案单源：说明行用的就是这条常量
  assert.ok(CCS_PROBE_NOTE.includes("各取最新"));
});

test("全就绪：工具链 + CCS 三件套 + 派生库目录全部 env-ok（工单 ux-walkthrough-02/06）", () => {
  const all = {
    ...status,
    toolchains: {
      stm32: { found: true, path: "C:\\Keil5\\UV4.exe", override: false },
      mspm0: { found: true, path: "C:\\ti\\gmake.exe", override: false },
    },
    ccs_tools: {
      sdk: { found: true, path: "C:\\ti\\sdk", root: "C:\\ti\\ccs2050", override: false },
      compiler: { found: true, path: "C:\\ti\\compiler", root: "C:\\ti\\ccs2050", override: false },
      sysconfig: { found: true, path: "C:\\ti\\sysconfig_cli.bat", root: "C:\\ti\\ccs2050", override: false },
    },
    library_dirs: {
      topic: { dir: "C:\\libs\\topics", exists: true, writable: true },
      reference: { dir: "C:\\libs\\references", exists: true, writable: true },
      pdf: { dir: "C:\\sources\\materials", exists: true, writable: true },
    },
  };
  const out = envCheckStatusHTML(all, null, null);
  for (const key of ["toolchain-stm32", "toolchain-mspm0", "ccs-sdk", "ccs-compiler", "ccs-sysconfig", "lib-dir-topic", "lib-dir-reference", "lib-dir-pdf"]) {
    const row = out.slice(out.indexOf('data-env-row="' + key + '"'), out.indexOf('data-env-row="' + key + '"') + 400);
    assert.ok(row.includes("env-ok"), key + " 应为 env-ok");
    assert.ok(!row.includes("去设置填"), key + " 就绪态不应有跳转按钮");
  }
});

test("派生库目录行：可写 env-ok / 缺失 env-warn；缺键不渲染", () => {
  const out = envCheckStatusHTML(status, null, null);
  assert.ok(out.includes('data-env-row="lib-dir-topic"'));
  assert.ok(out.includes("赛题库目录"));
  assert.ok(out.includes("C:\\libs\\topics"));
  assert.ok(out.includes("可写"));
  assert.ok(out.includes('data-env-row="lib-dir-reference"'));
  assert.ok(out.includes("目录不存在：C:\\libs\\references"));
  assert.ok(out.includes("env-warn"));
  const ro = envCheckStatusHTML(
    { ...status, library_dirs: { ...status.library_dirs, pdf: { dir: "C:\\sources\\materials", exists: true, writable: false } } },
    null, null);
  assert.ok(ro.includes("目录不可写：C:\\sources\\materials"));

  const sparse = envCheckStatusHTML({ ...status, library_dirs: {} }, null, null);
  assert.ok(!sparse.includes("lib-dir-"));
});

test("toolchainProbeText：四态文案（覆盖命中/覆盖未找到/自动命中/未探测到）", () => {
  assert.match(toolchainProbeText({ found: true, path: "C:\\Keil5\\UV4.exe", override: true }), /已配置：探测命中/);
  assert.match(toolchainProbeText({ found: false, path: null, override: true }), /已填路径未找到/);
  assert.match(toolchainProbeText({ found: true, path: "C:\\ti\\gmake.exe", override: false }), /自动探测到/);
  assert.match(toolchainProbeText({ found: false, path: null, override: false }), /未探测到/);
  assert.equal(toolchainProbeText(undefined), "");
  // 无 root（uv4 / gmake）不出现「各取最新」——那是 CCS 三件套的探测语义
  assert.ok(!toolchainProbeText({ found: true, path: "C:\\ti\\gmake.exe", override: false }).includes("各取最新"));
});

test("toolchainProbeText：CCS 三件（载荷带 root）点明「留空 = 自动探测：各取最新」（工单 06）", () => {
  const piece = { found: true, path: "C:\\ti\\ccs2051\\mspm0_sdk_2_10_00_04", root: "C:\\ti\\ccs2051", override: false };
  assert.match(toolchainProbeText(piece), /自动探测到：C:\\ti\\ccs2051\\mspm0_sdk_2_10_00_04/);
  assert.match(toolchainProbeText(piece), /留空 = 自动探测：三件各取目录名最新/);
  assert.match(toolchainProbeText({ ...piece, override: true }), /已配置：探测命中.*各取目录名最新/);
  const missing = toolchainProbeText({ found: false, path: null, root: null, override: false });
  assert.match(missing, /未探测到/);
  assert.match(missing, /C:\/ti\/ccs\*.*各取目录名最新/);
});

test("平台母版：ready env-ok / no-master env-warn", () => {
  const out = envCheckStatusHTML(status, null, null);
  assert.ok(out.includes('data-env-row="platform-stm32"'));
  assert.ok(out.includes("已就绪（可生成）"));
  assert.ok(out.includes('data-env-row="platform-mspm0"'));
  assert.ok(out.includes("未导入母版（生成前需导入）"));
});

test("模块库四态：错误（⚠ 非 ✗，spec）/ 目录不存在 / 有模块 / 空目录", () => {
  const err = envCheckStatusHTML(
    { ...status, module_library: { dir: "C:\\libs\\modules", exists: true, count: 0, error: "模块库加载失败：x" } },
    null, null);
  assert.ok(err.includes("模块库加载失败：x"));
  // spec 行 57：模块库加载错误 = 仅库异常（其他功能可用）→ ⚠（env-warn）而非 ✗
  assert.ok(err.includes("env-warn"));
  assert.ok(!err.slice(err.indexOf('data-env-row="module-library"'), err.indexOf('data-env-row="masters-dir"')).includes("env-err"));

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

test("缺省字段不渲染行：module_library/masters_dir/output_dir/api/ccs_tools/library_dirs 键缺失 → 无对应行", () => {
  const { module_library, masters_dir, output_dir, api_configured, ccs_tools, library_dirs, ...sparse } = status;
  const out = envCheckStatusHTML(sparse, null, null);
  assert.ok(!out.includes('data-env-row="module-library"'));
  assert.ok(!out.includes('data-env-row="masters-dir"'));
  assert.ok(!out.includes('data-env-row="output-dir"'));
  assert.ok(!out.includes('data-env-row="api"'));
  assert.ok(!out.includes('data-env-row="ccs-'));
  assert.ok(!out.includes("lib-dir-"));
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
