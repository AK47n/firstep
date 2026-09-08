// 模块详情弹窗纯函数单测（工单 frontend-es-modules/06）：
// moduleInfoHTML（模块数据 → 全量信息 HTML）。只测外部行为（渲染结果），
// 不断言完整 HTML 结构（子串断言防脆）。直接 import fx/module.js。
import test from "node:test";
import assert from "node:assert/strict";
import {
  moduleInfoHTML,
  moduleRequiresIdentity,
  identityExemptLabel,
} from "../../src/contest_generator/static/js/fx/module.js";

// 全量 fixture：两平台 + 引脚声明 + 依赖 + 多实例 + 互斥组 + 旧形状副产物
const full = {
  slug: "color_sensor",
  description: "8 路颜色传感器（灰度/颜色双模式）",
  dependencies: ["adc", "i2c"],
  multi_instance: { max: 2, variant: "color" },
  python_artifact: { template: "static/py/main.py.tpl", output: "main.py" },
  exclusive_group: { id: "sensor8", label: "8 路传感器", role: "颜色识别" },
  platforms: {
    stm32: {
      files: ["src/color.c", "include/color.h"],
      verified: true,
      hardware_bound: false,
      notes: "需要 5V 供电",
      kit: "RC-03 颜色传感器",
      source_url: "https://example.com/buy/color",
      pins: [
        { id: "pwm", type: "pwm", label: "PWM 输出", default: "PA0", required: true, macros: ["COLOR_PWM"] },
        { id: "cs", type: "gpio", label: "片选", default: "PA1", required: false, macros: [] },
      ],
    },
    mspm0: { files: [], verified: false, hardware_bound: true, notes: "", kit: "", source_url: "", pins: [] },
  },
};

test("全量渲染：标题/描述/依赖/多实例/互斥组/副产物", () => {
  const out = moduleInfoHTML(full, "stm32");
  assert.ok(out.includes("color_sensor"));
  assert.ok(out.includes("8 路颜色传感器"));
  assert.ok(out.includes("adc"));
  assert.ok(out.includes("i2c"));
  assert.ok(out.includes("可配置 2 个实例，按 color 区分"));
  assert.ok(out.includes("8 路传感器"));
  assert.ok(out.includes("颜色识别"));
  assert.ok(out.includes("同组互斥"));
  assert.ok(out.includes("main.py"));
});

test("全量渲染：每平台区块（文件/备注/套件/链接/引脚表）", () => {
  const out = moduleInfoHTML(full, "stm32");
  assert.ok(out.includes("STM32"));
  assert.ok(out.includes("MSPM0"));
  assert.ok(out.includes("src/color.c"));
  assert.ok(out.includes("include/color.h"));
  assert.ok(out.includes("需要 5V 供电"));
  assert.ok(out.includes("RC-03 颜色传感器"));
  assert.ok(out.includes('href="https://example.com/buy/color"'));
  assert.ok(out.includes('target="_blank" rel="noopener"'));
  assert.ok(out.includes("<table"));
  assert.ok(out.includes("pwm"));
  assert.ok(out.includes("PWM 输出"));
  assert.ok(out.includes("PA0"));
  assert.ok(out.includes("必接"));
  assert.ok(out.includes("COLOR_PWM"));
});

test("来源标签：wiki 原页 → 来源（立创 wiki），非 wiki → 购买链接（lckfb-attribution/03）", () => {
  const wiki = moduleInfoHTML({
    slug: "aht10",
    description: "AHT10 温湿度传感器驱动",
    platforms: { mspm0: {
      files: [], verified: true, hardware_bound: false, notes: "", kit: "AHT10 传感器",
      source_url: "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/aht10-temp-humi-sensor.html",
      pins: [],
    } },
  }, "mspm0");
  assert.ok(wiki.includes("来源（立创 wiki）"));
  assert.ok(!wiki.includes("购买链接"));

  const buy = moduleInfoHTML(full, "stm32");
  assert.ok(buy.includes("购买链接"));
  assert.ok(!buy.includes("来源（立创 wiki）"));
});

// 身份字段语义（工单 identity-fields/05）：器件显示「套件：」/来源行；内部件 /
// 协议切片（kind 经 /api/modules 载荷下发，判据单源 library.MODULE_KIND）不显示
// 两行空内容，改标「无需购买链接」。旧载荷（无 kind / requires_identity）保守按
// 器件处理，与旧行为逐字一致。
const platEntry = (extra) => ({
  files: [], verified: true, hardware_bound: false, notes: "", kit: "", source_url: "", pins: [],
  ...extra,
});

test("内部件：空身份字段不显示空行，改标「无需购买链接（内部件）」", () => {
  const out = moduleInfoHTML({
    slug: "delay",
    description: "软件延时工具",
    kind: "internal",
    requires_identity: false,
    platforms: { stm32: platEntry() },
  }, "stm32");
  assert.ok(out.includes("无需购买链接（内部件）"));
  assert.ok(!out.includes("套件："));
  assert.ok(!out.includes("购买链接</a>"));
  assert.ok(!out.includes("来源（立创 wiki）"));
});

test("协议切片：标注措辞按 kind 区分（协议切片）", () => {
  const out = moduleInfoHTML({
    slug: "coord_detect",
    description: "K230 视觉帧解析",
    kind: "protocol",
    requires_identity: false,
    platforms: { stm32: platEntry() },
  }, "stm32");
  assert.ok(out.includes("无需购买链接（协议切片）"));
  assert.ok(!out.includes("无需购买链接（内部件）"));
});

test("真实内部件 slug（delay，单源登记）：空身份字段渲染豁免标注", () => {
  // 与 /api/modules 的真实载荷同形（kind/requires_identity 由后端投影）
  const out = moduleInfoHTML({
    slug: "delay",
    description: "软件延时工具",
    kind: "internal",
    requires_identity: false,
    platforms: { stm32: platEntry() },
  }, "stm32");
  assert.ok(out.includes("无需购买链接（内部件）"));
  assert.ok(!out.includes("套件："));
});

test("器件：有身份字段照旧显示套件与链接，不出现豁免标注", () => {
  const out = moduleInfoHTML({
    slug: "dht11",
    description: "DHT11 温湿度传感器",
    kind: "device",
    requires_identity: true,
    platforms: { stm32: platEntry({ kit: "DHT11 模块", source_url: "https://example.com/buy/dht11" }) },
  }, "stm32");
  assert.ok(out.includes("套件：DHT11 模块"));
  assert.ok(out.includes('href="https://example.com/buy/dht11"'));
  assert.ok(!out.includes("无需购买链接"));
});

test("器件：缺身份字段（待补）仍不渲染空行，也不误标豁免", () => {
  const out = moduleInfoHTML({
    slug: "beep",
    description: "蜂鸣器驱动",
    kind: "device",
    requires_identity: true,
    platforms: { stm32: platEntry() },
  }, "stm32");
  assert.ok(!out.includes("套件："));
  assert.ok(!out.includes("无需购买链接"));
});

test("旧载荷（无 kind 字段）：按器件处理，有值照旧显示", () => {
  const out = moduleInfoHTML({
    slug: "oled",
    description: "OLED 驱动",
    platforms: { stm32: platEntry({ kit: "0.96 寸 OLED", source_url: "https://example.com/buy/oled" }) },
  }, "stm32");
  assert.ok(out.includes("套件：0.96 寸 OLED"));
  assert.ok(out.includes("购买链接"));
  assert.ok(!out.includes("无需购买链接"));
  assert.equal(moduleRequiresIdentity({ slug: "x" }), true);
  assert.equal(moduleRequiresIdentity({ slug: "x", kind: "internal" }), false);
  assert.equal(moduleRequiresIdentity({ slug: "x", kind: "protocol" }), false);
  assert.equal(moduleRequiresIdentity({ slug: "x", kind: "device" }), true);
  // 未知 kind 但载荷显式说不需要 → 尊重载荷
  assert.equal(moduleRequiresIdentity({ slug: "x", kind: "future", requires_identity: false }), false);
  assert.equal(identityExemptLabel("protocol"), "无需购买链接（协议切片）");
  assert.equal(identityExemptLabel("internal"), "无需购买链接（内部件）");
});

test("转义：描述与字段含 HTML 字符被转义", () => {
  const out = moduleInfoHTML({
    slug: "x",
    description: '颜色 <传感器> & "双模式"',
    platforms: { stm32: { files: ["a< b.c"], verified: false, hardware_bound: false, notes: "", kit: "", source_url: "", pins: [] } },
  }, "stm32");
  assert.ok(out.includes("&lt;传感器&gt;"));
  assert.ok(out.includes("&amp;"));
  assert.ok(out.includes("&quot;双模式&quot;"));
});

test("缺省字段不渲染行（依赖/多实例/副产物/互斥组）", () => {
  const bare = {
    slug: "bare",
    description: "无附加信息",
    platforms: { stm32: { files: [], verified: false, hardware_bound: false, notes: "", kit: "", source_url: "", pins: [] } },
  };
  const out = moduleInfoHTML(bare, "stm32");
  assert.ok(!out.includes("可配置"));
  assert.ok(!out.includes("副产物"));
  assert.ok(!out.includes("互斥"));
  // 依赖行不渲染：行标记为 >依赖</span>（评审 2026-08-26：原 "依赖：" 断言恒真属假置信）
  assert.ok(!out.includes(">依赖</span>"));
  assert.ok(!out.includes("mi-row"));
});

test("空 platforms：不渲染平台区块", () => {
  const out = moduleInfoHTML({ slug: "empty", description: "无平台", platforms: {} }, "stm32");
  assert.ok(!out.includes("mi-plat"));
});

test("空 files = 内嵌母版文案；空 pins 不渲染表", () => {
  const out = moduleInfoHTML(full, "stm32");
  assert.ok(out.includes("实现内嵌母版"));
  const out2 = moduleInfoHTML({ slug: "a", description: "d", platforms: { stm32: { files: ["f.c"], verified: false, hardware_bound: false, notes: "", kit: "", source_url: "", pins: [] } } }, "stm32");
  assert.ok(!out2.includes("<table"));
  assert.ok(out2.includes("f.c"));
});

test("文件行可点击（data-mi-file）+ 源码区槽位含隐藏初始态（mainc-codeview-bridge/05）", () => {
  const out = moduleInfoHTML(full, "stm32");
  assert.ok(out.includes('data-mi-file="src/color.c"'));
  assert.ok(out.includes('data-mi-file="include/color.h"'));
  assert.ok(out.includes('data-module-source hidden'));
  // 无文件平台 = 内嵌母版文案，不渲染伪文件行
  const mspm0 = moduleInfoHTML(full, null);
  assert.ok(!mspm0.includes('data-mi-file=""'));
});

test("副产物两形状：旧 template/output 与新 default/templates", () => {
  const old = moduleInfoHTML({ slug: "a", description: "d", python_artifact: { template: "t.py", output: "main.py" }, platforms: {} }, null);
  assert.ok(old.includes("main.py"));
  assert.ok(!old.includes("templates"));
  const newShape = moduleInfoHTML({
    slug: "b",
    description: "d",
    python_artifact: {
      default: "dual",
      templates: [
        { id: "dual", name: "双目", description: "双摄像头", template: "t/dual.py", output: "main.py" },
        { id: "mono", name: "单目", description: "单摄像头", template: "t/mono.py", output: "main_mono.py" },
      ],
    },
    platforms: {},
  }, null);
  assert.ok(newShape.includes("双目"));
  assert.ok(newShape.includes("单摄像头"));
  assert.ok(newShape.includes("main_mono.py"));
  // spec 契约：每模板 template → output（评审 2026-08-26：原实现箭头左为 name 漏源路径）
  assert.ok(newShape.includes("t/dual.py → main.py"));
  assert.ok(newShape.includes("t/mono.py → main_mono.py"));
  // 默认模板展示 name（可读性），缺省回退 id
  assert.ok(newShape.includes("默认：双目"));
});

test("off 提示：platform 无版本才提示，不传/命中不提示", () => {
  const off = moduleInfoHTML({ slug: "a", description: "d", platforms: { stm32: { files: [], verified: false, hardware_bound: false, notes: "", kit: "", source_url: "", pins: [] } } }, "mspm0");
  assert.ok(off.includes("当前平台 MSPM0 无此模块版本"));
  const hit = moduleInfoHTML(full, "stm32");
  assert.ok(!hit.includes("无此模块版本"));
  const noPlatform = moduleInfoHTML(full, null);
  assert.ok(!noPlatform.includes("无此模块版本"));
});

test("状态徽章三态：硬件绑定/已验证/未验证", () => {
  const hw = moduleInfoHTML({ slug: "a", description: "d", platforms: { stm32: { files: [], verified: false, hardware_bound: true, notes: "", kit: "", source_url: "", pins: [] } } }, "stm32");
  assert.ok(hw.includes("硬件绑定"));
  const ok = moduleInfoHTML({ slug: "b", description: "d", platforms: { stm32: { files: [], verified: true, hardware_bound: false, notes: "", kit: "", source_url: "", pins: [] } } }, "stm32");
  assert.ok(ok.includes("已验证"));
  const un = moduleInfoHTML({ slug: "c", description: "d", platforms: { stm32: { files: [], verified: false, hardware_bound: false, notes: "", kit: "", source_url: "", pins: [] } } }, "stm32");
  assert.ok(un.includes("未验证"));
});

test("徽章语境不误报：未验证字样在无平台区块时也可出现（空 platforms 无未验证）", () => {
  const out = moduleInfoHTML({ slug: "e", description: "d", platforms: {} }, "stm32");
  assert.ok(!out.includes("未验证"));
});
