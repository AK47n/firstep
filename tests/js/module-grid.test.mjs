// 模块选择网格纯函数单测（工单 frontend-es-modules/06）：平台标签 / 状态文本 /
// 过滤（含已选排除与搜索匹配）/ 计数 / 卡片 HTML（置灰、徽章、截断、空态）。
// 直接 import fx/module.js（不再字符串提取）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  moduleGridPlatformLabel, moduleGridStatusText, moduleGridBadgeClass,
  moduleGridFilter, moduleGridCountText, moduleGridHTML,
} from "../../src/contest_generator/static/js/fx/module.js";

const MODULES = [
  {
    slug: "led-sample", description: "LED 闪烁示例模块，用于点亮开发板上的小灯并演示基本 IO",
    dependencies: ["mspm0-driver"], python_artifact: true,
    platforms: { stm32: { verified: true }, mspm0: { verified: false } },
  },
  {
    slug: "motor-driver", description: "电机驱动", dependencies: [], python_artifact: false,
    platforms: { stm32: { verified: true, hardware_bound: true } },
  },
  {
    slug: "oled-display", description: "OLED 显示", dependencies: [],
    platforms: { mspm0: { verified: true } },
  },
];

test("moduleGridPlatformLabel 平台短标签", () => {
  assert.equal(moduleGridPlatformLabel("stm32"), "STM32");
  assert.equal(moduleGridPlatformLabel("stm32f103c8t6"), "STM32");
  assert.equal(moduleGridPlatformLabel("mspm0"), "MSPM0");
  assert.equal(moduleGridPlatformLabel("mspm0g3507"), "MSPM0");
  assert.equal(moduleGridPlatformLabel("nrf52"), "nrf52");
});

test("moduleGridStatusText 状态文本", () => {
  assert.equal(moduleGridStatusText({ hardware_bound: true }), "硬件绑定");
  assert.equal(moduleGridStatusText({ verified: true }), "已验证");
  assert.equal(moduleGridStatusText({ verified: false }), "未验证");
  assert.equal(moduleGridStatusText(undefined), "未验证");
});

test("moduleGridBadgeClass 徽章类名（与 StatusText 单源并列）", () => {
  assert.equal(moduleGridBadgeClass({ hardware_bound: true }), "hw");
  assert.equal(moduleGridBadgeClass({ verified: true }), "ok");
  assert.equal(moduleGridBadgeClass({ verified: false }), "un");
  assert.equal(moduleGridBadgeClass(undefined), "un");
});

test("moduleGridFilter 排除已选 + 搜索匹配", () => {
  // 无查询 = 全部未选
  assert.equal(moduleGridFilter(MODULES, [], "").length, 3);
  // 排除已选
  assert.deepEqual(moduleGridFilter(MODULES, ["led-sample"], "").map((m) => m.slug),
    ["motor-driver", "oled-display"]);
  // 匹配 slug
  assert.equal(moduleGridFilter(MODULES, [], "oled").length, 1);
  // 匹配描述
  assert.equal(moduleGridFilter(MODULES, [], "电机").length, 1);
  // 匹配依赖
  assert.equal(moduleGridFilter(MODULES, [], "driver").length, 2);
  // 匹配平台短标签
  assert.equal(moduleGridFilter(MODULES, [], "stm32").length, 2);
  // 大小写不敏感 + 空白裁剪
  assert.equal(moduleGridFilter(MODULES, [], "  OLED  ").length, 1);
  // 无结果
  assert.equal(moduleGridFilter(MODULES, [], "不存在").length, 0);
  // 容错
  assert.deepEqual(moduleGridFilter(undefined, undefined, undefined), []);
});

test("moduleGridCountText 计数文案", () => {
  assert.equal(moduleGridCountText(MODULES, [], ""), "共 3 个可用模块");
  assert.equal(moduleGridCountText(MODULES, ["led-sample"], ""), "共 2 个可用模块");
  assert.equal(moduleGridCountText(MODULES, [], "oled"), "匹配 1 个可用模块");
});

test("moduleGridHTML 卡片结构 + 平台置灰", () => {
  const out = moduleGridHTML(MODULES, [], "", "stm32");
  assert.equal((out.match(/class="module-card/g) || []).length, 3);
  // oled-display 在 stm32 无平台条目 → off
  assert.equal((out.match(/class="module-card off"/g) || []).length, 1);
  assert.equal(out.includes("data-add=\"oled-display\""), true);
  assert.equal(out.includes("需切换平台"), true);
  const out3 = moduleGridHTML(MODULES, [], "", "mspm0");
  // motor-driver 在 mspm0 无平台条目 → off
  assert.equal((out3.match(/class="module-card off"/g) || []).length, 1);
  assert.equal(out3.includes("需切换平台"), true);
});

test("moduleGridHTML 徽章与描述", () => {
  const out = moduleGridHTML(MODULES, ["oled-display"], "", "stm32");
  // 已选排除后剩 2 张卡
  assert.equal((out.match(/class="module-card/g) || []).length, 2);
  // motor-driver 硬件绑定徽章
  assert.equal(out.includes("STM32·硬件绑定"), true);
  // led-sample 在 stm32 已验证徽章
  assert.equal(out.includes("STM32·已验证"), true);
  // mspm0 未验证徽章（led-sample 的第二个平台）
  assert.equal(out.includes("MSPM0·未验证"), true);
  // 依赖徽章
  assert.equal(out.includes("依赖：mspm0-driver"), true);
  // 副产物徽章
  assert.equal(out.includes("副产物"), true);
  // 内嵌母版标注（无 files 且无副产物的平台条目）
  assert.equal(out.includes("内嵌母版"), true);
  // 描述是截断版（26 字 + …）；title 属性保留全文
  assert.equal(out.includes("…"), true);
});

test("moduleGridHTML 空态两个分支", () => {
  const empty = moduleGridHTML(MODULES, ["led-sample", "motor-driver", "oled-display"], "", "stm32");
  assert.equal(empty.includes("暂无可用模块。"), true);
  const nohit = moduleGridHTML(MODULES, [], "不存在", "stm32");
  assert.equal(nohit.includes("没有匹配的可用模块。"), true);
});
