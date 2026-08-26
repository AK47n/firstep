// 最近生成列表纯函数单测（工单 frontend-es-modules/08）：状态元数据 / 时间与平台
// 标签 / 条目 chip HTML / 列表 HTML / 编译 done → 状态映射。
// 直接 import fx/recent.js（不再字符串提取）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  recentStatusMeta, recentTimeLabel, recentPlatformLabel, recentStatusNow,
  recentChipHTML, recentListHTML,
} from "../../src/contest_generator/static/js/fx/recent.js";

test("recentStatusMeta 四种已知状态 → label/cls", () => {
  assert.deepEqual(recentStatusMeta("generated"), { label: "已生成", cls: "gen" });
  assert.deepEqual(recentStatusMeta("compiled_ok"), { label: "编译成功", cls: "ok" });
  assert.deepEqual(recentStatusMeta("compiled_warn"), { label: "有警告", cls: "warn" });
  assert.deepEqual(recentStatusMeta("compile_failed"), { label: "编译失败", cls: "fail" });
});

test("recentStatusMeta 未知状态 → 未知（灰）", () => {
  assert.deepEqual(recentStatusMeta("whatever"), { label: "未知", cls: "gen" });
});

test("recentTimeLabel 秒级时间戳 → MM-DD HH:mm（本地时区）", () => {
  const d = new Date(2025, 0, 5, 8, 9);
  assert.equal(recentTimeLabel(d.getTime() / 1000), "01-05 08:09");
});

test("recentTimeLabel 非法时间戳 → 空串", () => {
  assert.equal(recentTimeLabel("not-a-number"), "");
  assert.equal(recentTimeLabel(undefined), "");
});

test("recentPlatformLabel 平台 id → 短标签（含长短两种别名），未知原样，空 → 空串", () => {
  assert.equal(recentPlatformLabel("stm32"), "STM32");
  assert.equal(recentPlatformLabel("stm32f103c8t6"), "STM32");
  assert.equal(recentPlatformLabel("mspm0"), "MSPM0");
  assert.equal(recentPlatformLabel("mspm0g3507"), "MSPM0");
  assert.equal(recentPlatformLabel("weird"), "weird");
  assert.equal(recentPlatformLabel(""), "");
  assert.equal(recentPlatformLabel(undefined), "");
});

test("recentChipHTML 完整条目：类/属性/平台/模块数/目录名/删除钮", () => {
  const entry = {
    id: "abc123", ts: "1700000000.123", status: "compiled_ok",
    output_dir: "C:\\Users\\me\\Smart_Car", platform: "mspm0g3507",
    slugs: ["led-sample", "dht11"],
  };
  const chip = recentChipHTML(entry);
  assert.ok(chip.includes('class="recent-chip st-ok"'));
  assert.ok(chip.includes('data-id="abc123"'));
  assert.ok(chip.includes('data-dir="C:\\Users\\me\\Smart_Car"'));
  assert.ok(chip.includes("title=\"点击复制路径：C:\\Users\\me\\Smart_Car\""));
  assert.ok(chip.includes("recent-status-dot"));
  assert.ok(chip.includes("MSPM0"));
  assert.ok(chip.includes("2 个模块"));
  assert.ok(chip.includes(">Smart_Car<"));
  assert.ok(chip.includes('class="recent-del"'));
});

test("recentChipHTML 目录名与 HTML 转义：末段取 basename、特殊字符实体化", () => {
  const chip = recentChipHTML({
    id: "id1", ts: "1.0", status: "generated",
    output_dir: "a/b/<x>\"", platform: undefined, slugs: [],
  });
  assert.ok(chip.includes('data-dir="a/b/&lt;x&gt;&quot;"'));
  assert.ok(chip.includes('title="&lt;x&gt;&quot;">&lt;x&gt;&quot;</span>')); // basename 提取 + 转义
  assert.ok(chip.includes("0 个模块"));
});

test("recentChipHTML 空输出目录 → 占位目录名", () => {
  const chip = recentChipHTML({ id: "id2", ts: "1", status: "compiled_warn", output_dir: "", platform: "x", slugs: [] });
  assert.ok(chip.includes("（未知目录）"));
  assert.ok(chip.includes(" st-warn"));
});

test("recentListHTML 空数组 → 空态文案", () => {
  assert.ok(recentListHTML([]).includes("recent-empty"));
  assert.ok(recentListHTML(null).includes("还没有生成记录"));
});

test("recentListHTML 多条 → 逐条拼接", () => {
  const list = recentListHTML([
    { id: "a", ts: "1", status: "generated", output_dir: "d1", platform: "mspm0g3507", slugs: [] },
    { id: "b", ts: "2", status: "generated", output_dir: "d2", platform: "stm32f103c8t6", slugs: [] },
  ]);
  assert.ok(list.includes('data-id="a"'));
  assert.ok(list.includes('data-id="b"'));
  assert.ok((list.match(/recent-chip/g) || []).length === 2);
});

test("recentStatusNow 编译 done → 状态映射", () => {
  assert.equal(recentStatusNow(null), "generated");
  assert.equal(recentStatusNow({ timed_out: true, passed: false }), "compile_failed");
  assert.equal(recentStatusNow({ timed_out: false, passed: false }), "compile_failed");
  assert.equal(recentStatusNow({ timed_out: false, passed: true, summary: { errors: 2, warnings: 0 } }), "compile_failed");
  assert.equal(recentStatusNow({ timed_out: false, passed: true, summary: { warnings: 3 } }), "compiled_warn");
  assert.equal(recentStatusNow({ timed_out: false, passed: true, summary: { warnings: 0 } }), "compiled_ok");
});

test("recentStatusNow 无 summary 的通过编译 → ok（warnings 缺省 0）", () => {
  assert.equal(recentStatusNow({ passed: true }), "compiled_ok");
});
