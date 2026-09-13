// materials-update.test.mjs — 资料库更新纯函数单测（工单 materials-update/06）：
// materialsCheckCardHTML（baseline-missing / 无更新 / 有更新 + 整批删除提示）、
// aggregateSelection（全选 / 部分 / 空）、materialsPickHTML（勾选行 + 元数据）、
// materialsPickFooterHTML（已选大小）、materialsProgressHTML（进度 / 速度 /
// 剩余时间 / 卷状态）、materialsStateText（六态 + 未知）。
import test from "node:test";
import assert from "node:assert/strict";
import {
  materialsCheckCardHTML,
  aggregateSelection,
  materialsPickHTML,
  materialsPickFooterHTML,
  materialsProgressHTML,
  materialsStateText,
} from "../../src/contest_generator/static/js/fx/materials-update.js";

const CHECK = {
  current_version: "v1.0.0",
  latest_version: "v1.1.0",
  update_available: true,
  total_size_bytes: 300 * 1024 * 1024,
  error: "",
  message: "",
  batches: [
    {
      slug: "k230",
      name: "k230资料",
      add_count: 2, modify_count: 1, del_count: 0,
      size_bytes: 200 * 1024 * 1024,
      parts: [{ zip_url: "https://x/k230.zip", size_bytes: 200 * 1024 * 1024, sha256: "a" }],
    },
    {
      slug: "wireless-uart",
      name: "无线串口模块资料",
      add_count: 0, modify_count: 1, del_count: 1,
      size_bytes: 100 * 1024 * 1024,
      parts: [{ zip_url: "https://x/wireless.zip", size_bytes: 100 * 1024 * 1024, sha256: "b" }],
    },
  ],
  deleted_batches: [],
};

const ERROR_CHECK = {
  ...CHECK,
  update_available: false,
  error: "baseline-missing",
  message: "本地资料库版本未知（缺少基线清单），无法增量更新；请下载完整包",
};

test("check 结果卡：baseline-missing 显示指引", () => {
  const html = materialsCheckCardHTML(ERROR_CHECK);
  assert.match(html, /版本未知/);
  assert.match(html, /完整包/);
});

test("check 结果卡：无更新显示已最新", () => {
  const html = materialsCheckCardHTML({ ...CHECK, update_available: false, error: "", batches: [] });
  assert.match(html, /已是最新版本/);
  assert.match(html, /v1\.1\.0/);
});

test("check 结果卡：有更新显示总大小 + 两个按钮 + 整批删除提示", () => {
  const html = materialsCheckCardHTML({
    ...CHECK,
    deleted_batches: [{ slug: "old", name: "废弃批次", file_count: 3 }],
  });
  assert.match(html, /发现资料库新版本/);
  assert.match(html, /约 300 MB/);
  assert.match(html, /btn-materials-pick/);
  assert.match(html, /btn-materials-apply-all/);
  assert.match(html, /废弃批次/);
});

test("aggregateSelection：部分勾选聚合大小与卷数", () => {
  const agg = aggregateSelection(CHECK, ["k230"]);
  assert.equal(agg.totalSize, 200 * 1024 * 1024);
  assert.equal(agg.partCount, 1);
  assert.deepEqual(agg.slugs, ["k230"]);
});

test("aggregateSelection：全选聚合所有", () => {
  const agg = aggregateSelection(CHECK, ["k230", "wireless-uart"]);
  assert.equal(agg.totalSize, 300 * 1024 * 1024);
  assert.equal(agg.partCount, 2);
});

test("aggregateSelection：空选择", () => {
  const agg = aggregateSelection(CHECK, []);
  assert.equal(agg.totalSize, 0);
  assert.deepEqual(agg.slugs, []);
});

test("materialsPickHTML：勾选行 + 变更数 + 多卷标注", () => {
  const html = materialsPickHTML(CHECK, new Set(["k230"]));
  assert.match(html, /k230资料/);
  assert.match(html, /1 改 2 增 0 删/);
  assert.match(html, /checked/);
  // 多卷不触发（本例单卷）；元数据带 MB
  assert.match(html, /200 MB/);
});

test("materialsPickFooterHTML：已选大小与按钮", () => {
  const html = materialsPickFooterHTML(CHECK, new Set(["k230"]));
  assert.match(html, /已选 1 个批次/);
  assert.match(html, /200 MB/);
  assert.match(html, /btn-materials-start/);
  assert.match(html, /稍后/);
});

test("materialsProgressHTML：进度 / 速度 / 剩余时间 / 卷状态", () => {
  const status = {
    state: "downloading",
    total_bytes: 100,
    total_downloaded_bytes: 50,
    speed_bps: 10,
    current_part_name: "k230.zip",
    parts: [
      { name: "k230.zip", downloaded_bytes: 50, total_bytes: 100, ok: false },
      { name: "wireless.zip", downloaded_bytes: 0, total_bytes: 100, ok: true },
    ],
    error: "",
    message: "",
  };
  const html = materialsProgressHTML(status);
  assert.match(html, /正在下载/);
  assert.match(html, /50%/);
  assert.match(html, /✓/); // ok 卷标记
  assert.match(html, /速度/);
  // 与完整包同一套口径：体积用 formatSize（不再甩原始字节数）
  assert.match(html, /50 B \/ 100 B/);
  assert.doesNotMatch(html, /50 \/ 100 字节/);
});

test("materialsStateText：六态映射 + 未知空串", () => {
  assert.match(materialsStateText("downloading"), /下载/);
  assert.match(materialsStateText("applying"), /应用/);
  assert.match(materialsStateText("done"), /完成/);
  assert.match(materialsStateText("failed"), /失败/);
  assert.match(materialsStateText("cancelled"), /取消/);
  assert.match(materialsStateText("partial"), /部分批次/);
  assert.equal(materialsStateText("unknown"), "");
});
