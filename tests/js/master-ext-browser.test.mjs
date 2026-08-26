// 母版库增强轮纯函数（工单 master-library-ui-2/01）：健康徽章 + 体积统计行。
// 直接 import fx/master.js；只测外部行为，子串断言防脆。
import test from "node:test";
import assert from "node:assert/strict";
import {
  masterHealthBadgeHTML,
  masterStatsHTML,
  masterTableRowHTML,
  masterDetailHTML,
} from "../../src/contest_generator/static/js/fx/master.js";

const HEALTH_OK = {
  ok: true,
  missing_key_files: [],
  config_file_ok: true,
  artifact_dirs: [],
};
const HEALTH_WARN = {
  ok: false,
  missing_key_files: ["pin_config.h", "user/Project.uvprojx"],
  config_file_ok: false,
  artifact_dirs: ["Debug"],
};

test("masterHealthBadgeHTML：健康 = ✓ 徽章 + title 说明", () => {
  const out = masterHealthBadgeHTML(HEALTH_OK);
  assert.ok(out.includes("✓ 健康"));
  assert.ok(out.includes('class="master-health-pill master-health-ok"'));
  assert.ok(out.includes(
    'title="健康：关键文件齐全、工程配置文件在、无构建产物残留"',
  ));
});

test("masterHealthBadgeHTML：异常 = ⚠ 徽章 + title 明细（缺失/配置/残留）", () => {
  const out = masterHealthBadgeHTML(HEALTH_WARN);
  assert.ok(out.includes("⚠ 有缺失或残留"));
  assert.ok(out.includes(
    'title="关键文件缺失：pin_config.h、user/Project.uvprojx；缺少工程配置文件；构建产物残留：Debug"',
  ));
});

test("masterHealthBadgeHTML：缺失/残留明细转义 title", () => {
  const out = masterHealthBadgeHTML({
    ...HEALTH_WARN,
    missing_key_files: ['<img src=x>'],
  });
  assert.ok(out.includes("&lt;img src=x&gt;"));
  assert.ok(!out.includes('<img src=x>'));
});

test("masterStatsHTML：总体积/文件数/大文件清单（formatSize 可读单位）", () => {
  const out = masterStatsHTML({
    total_size_bytes: 6291456,
    file_count: 42,
    big_files: [
      { path: "ml_libs/oled.c", size_bytes: 1572864 },
      { path: "user/Project.uvprojx", size_bytes: 17606 },
    ],
  });
  assert.ok(out.includes("总体积"));
  assert.ok(out.includes("6.0 MB"));
  assert.ok(out.includes("文件数"));
  assert.ok(out.includes("42 个"));
  assert.ok(out.includes("大文件"));
  assert.ok(out.includes("ml_libs/oled.c（1.5 MB）"));
  assert.ok(out.includes("user/Project.uvprojx（17.2 KB）"));
});

test("masterStatsHTML：无大文件 = — 占位；0 字节 0 文件", () => {
  const out = masterStatsHTML({
    total_size_bytes: 0,
    file_count: 0,
    big_files: [],
  });
  assert.ok(out.includes("0 B"));
  assert.ok(out.includes("0 个"));
  assert.ok(out.includes("—"));

  const empty = masterStatsHTML({ total_size_bytes: 0, file_count: 0, big_files: undefined });
  assert.ok(empty.includes("大文件"));
  assert.ok(empty.includes("—"));
});

test("masterTableRowHTML：带 health = 健康徽章列；不带 = 既有行列不变", () => {
  const base = {
    platform: "stm32",
    platform_label: "STM32 · Keil5",
    sources: ["2026C"],
    warnings: [],
    key_files: [],
  };
  const out = masterTableRowHTML({ ...base, health: HEALTH_OK });
  assert.ok(out.includes('class="master-health-pill master-health-ok"'));
  assert.ok(out.includes("✓ 健康"));
  // 既有列仍渲染
  assert.ok(out.includes("STM32 · Keil5"));
  assert.ok(out.includes('data-master-detail="stm32"'));

  const legacy = masterTableRowHTML(base);
  assert.ok(!legacy.includes("master-health-pill"));
  assert.ok(legacy.includes('data-master-detail="stm32"'));
});

test("masterDetailHTML：带 stats = 元数据段增统计行；不带 = 既有结构不变", () => {
  const base = {
    platform: "stm32",
    sources: ["2026C"],
    warnings: [],
    key_files: [],
  };
  const out = masterDetailHTML({
    ...base,
    stats: { total_size_bytes: 6291456, file_count: 42, big_files: [] },
  });
  assert.ok(out.includes("总体积"));
  assert.ok(out.includes("6.0 MB"));
  assert.ok(out.includes("42 个"));
  assert.ok(out.includes("关键文件清单")); // 清单段仍渲染

  const legacy = masterDetailHTML(base);
  assert.ok(!legacy.includes("总体积"));
  assert.ok(legacy.includes("关键文件清单"));
});
