// 模块库表格行渲染纯函数单测（工单 module-library-ui/01）：
// moduleRowHTML（模块数据 → 表格行 HTML）。只测外部行为（渲染结果），
// 子串断言防脆。后续工单（详情 / 编辑 / 悬空警示）在本文件扩展。
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

const esc = extract("esc");
const moduleBadges = extract("moduleBadges", { esc });
const pythonArtifactSummary = extract("pythonArtifactSummary", { esc });
const moduleRowHTML = extract("moduleRowHTML", { esc, moduleBadges, pythonArtifactSummary });

const base = {
  slug: "ultrasonic",
  description: "超声波测距模块，返回厘米距离",
  dependencies: ["delay"],
  platforms: { stm32: { files: ["src/ultra.c"], verified: true, hardware_bound: false } },
};

test("moduleRowHTML 骨干结构：slug 等宽类、简介截断类 + title 全文、操作按钮", () => {
  const out = moduleRowHTML(base);
  assert.ok(out.includes('<td class="slug">ultrasonic</td>'));
  assert.ok(out.includes('<td class="desc-cell" title="超声波测距模块，返回厘米距离">'));
  assert.ok(out.includes("超声波测距模块，返回厘米距离"));
  assert.ok(out.includes('<button data-info="ultrasonic" title="查看模块详情">详情</button>'));
  assert.ok(out.includes('<button data-edit-desc="ultrasonic">改简介</button>'));
  assert.ok(out.includes('<button data-del="ultrasonic" class="danger">删除</button>'));
});

test("moduleRowHTML 操作列三按钮并存且 slug 转义（工单 03 详情入口）", () => {
  const out = moduleRowHTML({ ...base, slug: 'a"b' });
  assert.ok(out.includes('data-info="a&quot;b"'));
  assert.ok(out.includes('data-edit-desc="a&quot;b"'));
  assert.ok(out.includes('data-del="a&quot;b"'));
  assert.ok(out.indexOf("data-info") < out.indexOf("data-edit-desc"));
  assert.ok(out.indexOf("data-edit-desc") < out.indexOf("data-del"));
});

test("moduleRowHTML 简介含特殊字符：单元格与 title 双转义", () => {
  const out = moduleRowHTML({ ...base, description: 'a<b>&"c\'' });
  assert.ok(out.includes('title="a&lt;b&gt;&amp;&quot;c&#39;"'));
  assert.ok(out.includes("a&lt;b&gt;&amp;&quot;c&#39;"));
  assert.ok(!out.includes("<b>&"));
});

test("moduleRowHTML 依赖列：有依赖按顿号连接，无依赖回退 —", () => {
  assert.ok(moduleRowHTML(base).includes('<td class="muted">delay</td>'));
  const noDep = moduleRowHTML({ ...base, dependencies: [] });
  assert.ok(noDep.includes('<td class="muted">—</td>'));
});

test("moduleRowHTML 副产物摘要嵌入依赖列（python_artifact 模块）", () => {
  const out = moduleRowHTML({
    ...base,
    python_artifact: { templates: [{ id: "default", name: "CanMV", description: "K230 侧脚本", template: "py/main.py.tpl", output: "main.py" }], default: "default" },
  });
  assert.ok(out.includes("副产物模板"));
  assert.ok(out.includes("CanMV"));
});

test("moduleRowHTML 平台徽章：已验证 / 硬件绑定 / 未验证 / 内嵌母版", () => {
  const ok = moduleRowHTML({ ...base, platforms: { stm32: { files: ["a.c"], verified: true, hardware_bound: false } } });
  assert.ok(ok.includes("badge plat ok"));
  const hw = moduleRowHTML({ ...base, platforms: { stm32: { files: ["a.c"], verified: false, hardware_bound: true } } });
  assert.ok(hw.includes("badge plat hw"));
  const un = moduleRowHTML({ ...base, platforms: { stm32: { files: ["a.c"], verified: false, hardware_bound: false } } });
  assert.ok(un.includes("badge plat unverified"));
  const master = moduleRowHTML({ ...base, platforms: { stm32: { files: [], verified: true, hardware_bound: false } } });
  assert.ok(master.includes("内嵌母版"));
});

test("moduleRowHTML 无平台：徽章区为空、行仍完整", () => {
  const out = moduleRowHTML({ slug: "empty", description: "无平台模块", platforms: {} });
  assert.ok(out.includes('<td class="slug">empty</td>'));
  assert.ok(!out.includes("badge"));
});

// ================= 工单 02：工具栏与统计条纯函数 =================
// libFilterModules / libSortModules / libStats / libStatsText / libChipRowHTML。
// danglingDependencies（工单 04）定义在前：libStats 引用它（extract 注入依赖）。

const libFilterModules = extract("libFilterModules");
const libSortModules = extract("libSortModules");
const danglingDependencies = extract("danglingDependencies");
const libStats = extract("libStats", { danglingDependencies });
const libStatsText = extract("libStatsText");
const libChipRowHTML = extract("libChipRowHTML", { esc });

const libMods = [
  {
    slug: "ultrasonic",
    description: "超声波测距模块",
    dependencies: ["delay"],
    platforms: {
      stm32: { verified: true, hardware_bound: false, kit: "LaunchPad", notes: "接 PA1" },
      mspm0: { verified: false, hardware_bound: true },
    },
  },
  {
    slug: "delay",
    description: "阻塞延时",
    dependencies: [],
    platforms: { stm32: { verified: true, hardware_bound: false } },
  },
  {
    slug: "servo",
    description: "PWM 舵机驱动",
    dependencies: ["delay"],
    platforms: { mspm0: { verified: false, hardware_bound: true } },
    exclusive_group: { id: "pwm", label: "PWM 输出" },
  },
  {
    slug: "oled",
    description: "I2C 屏幕",
    dependencies: [],
    platforms: {},
    exclusive_group: { id: "display", label: "显示" },
  },
];

test("libFilterModules 关键字：大小写不敏感匹配 slug / 简介 / 依赖 / 套件 / 备注", () => {
  assert.deepEqual(libFilterModules(libMods, { q: "ULTRA", platform: "", status: "" }).map((m) => m.slug), ["ultrasonic"]);
  assert.deepEqual(libFilterModules(libMods, { q: "舵机", platform: "", status: "" }).map((m) => m.slug), ["servo"]);
  assert.deepEqual(libFilterModules(libMods, { q: "delay", platform: "", status: "" }).map((m) => m.slug), ["ultrasonic", "delay", "servo"]);
  assert.deepEqual(libFilterModules(libMods, { q: "launchpad", platform: "", status: "" }).map((m) => m.slug), ["ultrasonic"]);
  assert.deepEqual(libFilterModules(libMods, { q: "pa1", platform: "", status: "" }).map((m) => m.slug), ["ultrasonic"]);
});

test("libFilterModules 空条件：全量返回（同一数组内容，不修改原数组）", () => {
  const before = libMods.map((m) => m.slug);
  const out = libFilterModules(libMods, { q: "", platform: "", status: "" });
  assert.deepEqual(out.map((m) => m.slug), before);
  assert.equal(libMods.length, 4);
});

test("libFilterModules 平台过滤：存在该平台条目即命中", () => {
  assert.deepEqual(libFilterModules(libMods, { q: "", platform: "stm32", status: "" }).map((m) => m.slug), ["ultrasonic", "delay"]);
  assert.deepEqual(libFilterModules(libMods, { q: "", platform: "mspm0", status: "" }).map((m) => m.slug), ["ultrasonic", "servo"]);
  assert.deepEqual(libFilterModules(libMods, { q: "", platform: "mega", status: "" }).map((m) => m.slug), []);
});

test("libFilterModules 状态过滤：任一平台条目满足即命中（verified / unverified / hardware_bound）", () => {
  assert.deepEqual(libFilterModules(libMods, { q: "", platform: "", status: "verified" }).map((m) => m.slug), ["ultrasonic", "delay"]);
  assert.deepEqual(libFilterModules(libMods, { q: "", platform: "", status: "unverified" }).map((m) => m.slug), ["ultrasonic", "servo"]);
  assert.deepEqual(libFilterModules(libMods, { q: "", platform: "", status: "hardware_bound" }).map((m) => m.slug), ["ultrasonic", "servo"]);
  assert.deepEqual(libFilterModules(libMods, { q: "", platform: "", status: "verified2" }).map((m) => m.slug), []);
});

test("libFilterModules 条件叠加：关键字 + 平台 + 状态同时生效", () => {
  assert.deepEqual(libFilterModules(libMods, { q: "delay", platform: "stm32", status: "" }).map((m) => m.slug), ["ultrasonic", "delay"]);
  // unverified = 任一平台条目未验证：ultrasonic 的 mspm0 未验证 → 仍命中
  assert.deepEqual(libFilterModules(libMods, { q: "delay", platform: "stm32", status: "unverified" }).map((m) => m.slug), ["ultrasonic"]);
  // hardware_bound = 任一平台条目硬件绑定：ultrasonic 的 mspm0 绑定 → 命中
  assert.deepEqual(libFilterModules(libMods, { q: "delay", platform: "stm32", status: "hardware_bound" }).map((m) => m.slug), ["ultrasonic"]);
});

test("libSortModules slug 升/降序；平台数、依赖数排序保持稳定", () => {
  const asc = libSortModules(libMods, { by: "slug", dir: "asc" }).map((m) => m.slug);
  assert.deepEqual(asc, ["delay", "oled", "servo", "ultrasonic"]);
  const desc = libSortModules(libMods, { by: "slug", dir: "desc" }).map((m) => m.slug);
  assert.deepEqual(desc, ["ultrasonic", "servo", "oled", "delay"]);
  // platforms 数：ultrasonic 2、delay/servo 1、oled 0；同 1 的两项保持原相对序（delay 在 servo 前）
  assert.deepEqual(libSortModules(libMods, { by: "platforms", dir: "asc" }).map((m) => m.slug), ["oled", "delay", "servo", "ultrasonic"]);
  // deps 数：delay/oled 0、ultrasonic/servo 1；同 0 保持 delay 在 oled 前、同 1 保持 ultrasonic 在 servo 前
  assert.deepEqual(libSortModules(libMods, { by: "deps", dir: "asc" }).map((m) => m.slug), ["delay", "oled", "ultrasonic", "servo"]);
});

test("libStats 统计：总数 / 平台计数 / 模块级已验证 / 硬件绑定 / 互斥组去重", () => {
  assert.deepEqual(libStats(libMods), {
    total: 4,
    platforms: { stm32: 2, mspm0: 2 },
    verified: 2,
    unverified: 2,
    hardware_bound: 2,
    exclusiveGroups: 2,
    dangling: 0,
  });
  assert.deepEqual(libStats([]), { total: 0, platforms: {}, verified: 0, unverified: 0, hardware_bound: 0, exclusiveGroups: 0, dangling: 0 });
});

test("libStats 与 libFilterModules 一致：null 平台条目不计数也不命中", () => {
  const mods = [{ slug: "x", description: "", dependencies: [], platforms: { stm32: null } }];
  assert.deepEqual(libStats(mods).platforms, {});
  assert.deepEqual(libFilterModules(mods, { q: "", platform: "stm32", status: "" }), []);
});

// ================= 工单 04：悬空依赖检测 =================
// danglingDependencies(modules) → { 缺失依赖: [引用方模块 slug...] }；空对象 = 无悬空。
// （提取已在 02 组完成，libStats 依赖注入。）

test("danglingDependencies：库内依赖不报、缺失依赖报出并附引用方", () => {
  const mods = [
    { slug: "a", description: "", dependencies: ["b"] },
    { slug: "b", description: "", dependencies: [] },
    { slug: "c", description: "", dependencies: ["missing"] },
  ];
  assert.deepEqual(danglingDependencies(mods), { missing: ["c"] });
  assert.deepEqual(danglingDependencies([{ slug: "a", description: "", dependencies: ["b"] }, { slug: "b", description: "", dependencies: [] }]), {});
});

test("danglingDependencies：多缺失合并、多引用方按签名合并、同模块重复声明不重复报", () => {
  const mods = [
    { slug: "a", description: "", dependencies: ["x", "x", "y"] },
    { slug: "b", description: "", dependencies: ["x"] },
  ];
  assert.deepEqual(danglingDependencies(mods), { x: ["a", "b"], y: ["a"] });
});

test("danglingDependencies：空依赖与空库不产生条目", () => {
  assert.deepEqual(danglingDependencies([]), {});
  assert.deepEqual(danglingDependencies([{ slug: "a", description: "", dependencies: [] }]), {});
});

test("moduleRowHTML 悬空依赖警示标：⚠ + title 含缺失清单与引用方；无悬空不渲染", () => {
  const dmap = { delay: ["a", "b"] };
  const out = moduleRowHTML({ slug: "m", description: "", dependencies: ["delay"], platforms: {} }, dmap);
  assert.ok(out.includes('class="dangling-tag"'), out);
  assert.ok(out.includes("依赖未入库：delay"));
  assert.ok(out.includes("被 a、b 引用"));
  // 无悬空（dmap 缺失该依赖或不传）→ 无警示标
  const clean = moduleRowHTML({ slug: "m", description: "", dependencies: ["delay"], platforms: {} }, {});
  assert.ok(!clean.includes("dangling-tag"));
  const noArg = moduleRowHTML({ slug: "m", description: "", dependencies: ["delay"], platforms: {} });
  assert.ok(!noArg.includes("dangling-tag"));
  // 同一依赖重复声明：只渲染一个 ⚠（与 danglingDependencies 不重复报语义一致）
  const dup = moduleRowHTML({ slug: "m", description: "", dependencies: ["x", "x"], platforms: {} }, { x: ["m"] });
  assert.equal((dup.match(/dangling-tag/g) || []).length, 1);
});

test("libStats 统计含悬空依赖数（dangling 字段）", () => {
  const stats = libStats([{ slug: "a", description: "", dependencies: ["gone"], platforms: {} }]);
  assert.equal(stats.dangling, 1);
  assert.equal(libStats(libMods).dangling, 0);
  assert.equal(libStats([]).dangling, 0);
});

// ================= 工单 05：改简介模态状态机 =================
// editDescStatus(status, event)：idle → saving → ok / rejected；reset 回 idle；非法事件保持。

const editDescStatus = extract("editDescStatus");

test("editDescStatus 状态机：save/saved/error/reset 流转", () => {
  assert.equal(editDescStatus("idle", "save"), "saving");
  assert.equal(editDescStatus("saving", "saved"), "ok");
  assert.equal(editDescStatus("saving", "error"), "rejected");
  assert.equal(editDescStatus("rejected", "reset"), "idle");
  assert.equal(editDescStatus("saving", "reset"), "idle");
  assert.equal(editDescStatus("ok", "reset"), "idle");
});

test("editDescStatus 非法事件：保持原状态（重入保护由按钮禁用承担）", () => {
  assert.equal(editDescStatus("idle", "bogus"), "idle");
  assert.equal(editDescStatus("saving", "save"), "saving");
  assert.equal(editDescStatus("rejected", "saved"), "rejected");
});

// ================= 工单 06：编辑弹窗纯函数 =================
// libIsValidHttpUrl（URL 格式校验）/ libPlatformKits（库内套件词表去重）。

const libIsValidHttpUrl = extract("libIsValidHttpUrl");
const libPlatformKits = extract("libPlatformKits");

test("libIsValidHttpUrl：http/https 合法，其余协议/非 URL/空串非法", () => {
  assert.equal(libIsValidHttpUrl("https://example.com/buy?a=1"), true);
  assert.equal(libIsValidHttpUrl("http://127.0.0.1:8000/x"), true);
  assert.equal(libIsValidHttpUrl("ftp://example.com"), false);
  assert.equal(libIsValidHttpUrl("not-a-url"), false);
  assert.equal(libIsValidHttpUrl(""), false);
  assert.equal(libIsValidHttpUrl("javascript:alert(1)"), false);
});

test("libPlatformKits：全平台条目 kit 去重（空值忽略），顺序 = 首见序", () => {
  const mods = [
    { slug: "a", description: "", platforms: { stm32: { kit: "LaunchPad" }, mspm0: { kit: "LaunchPad" } } },
    { slug: "b", description: "", platforms: { stm32: { kit: "BluePill" }, mspm0: { kit: "" } } },
  ];
  assert.deepEqual(libPlatformKits(mods), ["LaunchPad", "BluePill"]);
  assert.deepEqual(libPlatformKits([]), []);
});

test("libStatsText 统计条文案：全量分段含互斥组", () => {
  const text = libStatsText(libStats(libMods));
  assert.ok(text.includes("共 4 个模块"));
  assert.ok(text.includes("STM32 2"));
  assert.ok(text.includes("MSPM0 2"));
  assert.ok(text.includes("已验证 2"));
  assert.ok(text.includes("硬件绑定 2"));
  assert.ok(text.includes("互斥组 2"));
  assert.ok(libStatsText(libStats([])).includes("共 0 个模块"));
});

test("libChipRowHTML：每项一个按钮，选中项带 on 类，计数可带可不带", () => {
  const out = libChipRowHTML([{ value: "", label: "全部" }, { value: "stm32", label: "STM32", count: 3 }], "stm32");
  const opts = out.split("<button").slice(1);
  assert.equal(opts.length, 2);
  assert.ok(out.includes('data-lib-chip=""'));
  assert.ok(out.includes('data-lib-chip="stm32"'));
  assert.ok(out.includes("STM32（3）"));
  // 选中项带 on 类，未选中不带
  const sel = opts[1].split(">")[0];
  assert.ok(sel.includes('class="lib-chip on"'), sel);
  const unsel = opts[0].split(">")[0];
  assert.ok(unsel.includes('class="lib-chip"') || unsel.includes('class="lib-chip "'), unsel);
  assert.ok(!unsel.includes(" on"));
  // 带特殊字符的值被转义
  const evil = libChipRowHTML([{ value: 'a"b', label: "x" }], "");
  assert.ok(evil.includes('data-lib-chip="a&quot;b"'));
});
