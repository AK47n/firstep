// PDF 疑似重复判据的守卫（2026-09-13 库去重盘点的结论固化）。
//
// 背景：库里曾有一类「内容逐字节相同、但文件名不同」的重复（如
// ESP32技术参考手册(中文).pdf 与 esp32_technical_reference_manual_cn.pdf），
// 应用自身的判据（同名 + 同大小）抓不到，靠离线 SHA256 盘点才清掉那 7 个文件。
// 于是有了「要不要把判据升级成读内容哈希」的动议——**实测后否决**：
// 对真实库（97 个 PDF / 208 MB）全量 SHA256 只需 1.4s，但算出来的重复组
// 100% 都已被「同名 + 同大小」覆盖（组内大小全部一致，多抓 0 组）。
// 也就是说该判据在本库上是完备的，加内容哈希只有维护成本、没有收益。
//
// 本文件把两件事钉住：
//   ① 判据的**形态**——同名不同大小 = 版本差异，不判重复（否则纯属误报）；
//   ② 判据的**健全性**——对真实库的形态（同名同大小 / 内容同但名与大小都不同）
//      必须给出正确结论。若哪天有人改判据，这两条会先红。
// 数据来源与复跑命令：.scratch/library-dedup-audit/report.md
import test from "node:test";
import assert from "node:assert/strict";
import { pdfDupGroups, pdfHealth } from "../../src/contest_generator/static/js/fx/pdf.js";

const mk = (rel_path, name, size_bytes, mtime = 1700000000) => ({
  rel_path,
  name,
  batch: rel_path.split("/")[0],
  size_bytes,
  mtime,
});

test("判据形态：同名同大小成组；同名不同大小 = 版本差异不判", () => {
  const groups = pdfDupGroups([
    mk("a/手册.pdf", "手册.pdf", 1024),
    mk("b/手册.pdf", "手册.pdf", 1024),
    mk("c/手册.pdf", "手册.pdf", 2048), // 同名不同大小 → 不该进组
  ]);
  assert.equal(groups.length, 1);
  assert.deepEqual(groups[0].paths, ["a/手册.pdf", "b/手册.pdf"]);
  assert.equal(groups[0].count, 2);
  assert.equal(groups[0].size, 1024);
});

test("改名重复（内容同、大小也同）：判据按名分组，故**不会**标出——清理由离线盘点负责", () => {
  // 这就是那 7 个文件的形态：同一份内容存了两个名字。
  const groups = pdfDupGroups([
    mk("x/ESP32技术参考手册(中文).pdf", "ESP32技术参考手册(中文).pdf", 8779264),
    mk("x/esp32_technical_reference_manual_cn.pdf", "esp32_technical_reference_manual_cn.pdf", 8779264),
  ]);
  assert.deepEqual(groups, [], "按名分组 → 不同名不成组（本判据的已知边界，非缺陷）");

  // 反证：名字一改回去就成组 —— 证明差异只来自「同名」这一条
  const same = pdfDupGroups([
    mk("x/手册.pdf", "手册.pdf", 8779264),
    mk("y/手册.pdf", "手册.pdf", 8779264),
  ]);
  assert.equal(same.length, 1);
});

test("健壮性：0 字节归损坏不参与重复；缺字段不炸；大小比较不串类型", () => {
  assert.deepEqual(
    pdfDupGroups([mk("a/空.pdf", "空.pdf", 0), mk("b/空.pdf", "空.pdf", 0)]),
    [],
    "0 字节 = 损坏，不进重复组（由 pdfBroken 单独标）",
  );
  assert.deepEqual(pdfDupGroups([null, undefined, {}, mk("a/手册.pdf", "手册.pdf", 10)]), []);
  assert.equal(pdfDupGroups([]).length, 0);
  assert.equal(pdfDupGroups(null).length, 0);

  // 大小 > 0 才参与；字符串数字 "0" 与 0 同判（后端 int，防御宽口径已由 pdfBroken 承担）
  assert.equal(pdfDupGroups([mk("a/x.pdf", "x.pdf", "0"), mk("b/x.pdf", "x.pdf", "0")]).length, 0);
});

test("健康派生与分组同源：dupPaths 恰为组内成员并集", () => {
  const pdfs = [
    mk("a/手册.pdf", "手册.pdf", 1024),
    mk("b/手册.pdf", "手册.pdf", 1024),
    mk("c/独有.pdf", "独有.pdf", 999),
    mk("d/空.pdf", "空.pdf", 0),
  ];
  const health = pdfHealth(pdfs);
  assert.deepEqual([...health.dupPaths].sort(), ["a/手册.pdf", "b/手册.pdf"]);
  assert.deepEqual([...health.broken], ["d/空.pdf"]);
  assert.equal(health.dupGroups.length, 1);
});
