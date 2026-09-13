"""本地生成资料库基线清单，并与线上完整包清单里记的那份逐字节对比。

背景：`sources/materials/.materials-manifest.json`（本地基线）**不在完整包里**，
只有走「完整包替换」那一步才由 tools/update-app.py 从完整包清单的
`materials_manifest` 写回工具根。直跑源码 / 普通重启都不会写它 →
工具内「资料库更新」报 baseline-missing。

本脚本做的事（零网络、零下载、只读资料库）：
  1. 用 `materials_pack.scan_as_manifest` 就地扫出当前资料库快照；
  2. 与 `firstep-full-v1.2.0.manifest.json` 里的 `materials_manifest` 做
     「批次 / 文件数 / 逐文件 sha256」三方对比；
  3. 只有三者全等才写基线（默认 dry-run 不写）。

用法：
    python .scratch/materials-baseline-writeback/init-baseline.py            # 只对比，不写
    python .scratch/materials-baseline-writeback/init-baseline.py --write    # 对比通过才写
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from contest_generator.full_pack import materials_excluded  # noqa: E402
from contest_generator.materials_pack import MANIFEST_FILENAME, scan_as_manifest  # noqa: E402

FULL_MANIFEST = Path(r"C:\Users\luoji\Desktop\firstep-pack\firstep-full-v1.2.0.manifest.json")


def _index(manifest: dict) -> dict[str, dict[str, str]]:
    return {
        b["slug"]: {f["path"]: f["sha256"] for f in b.get("files", [])}
        for b in manifest.get("batches", [])
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="对比通过后写入基线")
    ap.add_argument("--version", default="v1.2.0", help="写入清单里的 version 字段")
    args = ap.parse_args()

    tree = ROOT / "sources" / "materials"
    if not tree.is_dir():
        print(f"资料库目录不在：{tree}")
        return 2

    # 关键：用与完整包打包*同一份*排除规则（full_pack.materials_excluded）——
    # 否则会把 36 个「故意不进包」的第三方安装包（CCS / VSCode / *.img / *.rar…）
    # 当成「本地多出」，基线与线上清单就对不上（实测差异 5117 vs 5081）。
    local = scan_as_manifest(tree, args.version, exclude=materials_excluded)
    shipped = json.loads(FULL_MANIFEST.read_text(encoding="utf-8"))["materials_manifest"]

    li, si = _index(local), _index(shipped)
    print(f"本地扫描：{len(li)} 批次 / {sum(len(v) for v in li.values())} 文件")
    print(f"线上包内：{len(si)} 批次 / {sum(len(v) for v in si.values())} 文件")

    ok = True
    if set(li) != set(si):
        ok = False
        print("批次集合不同：")
        print("  仅本地有：", sorted(set(li) - set(si)))
        print("  仅线上有：", sorted(set(si) - set(li)))
    diffs: list[str] = []
    for slug in sorted(set(li) & set(si)):
        only_local = set(li[slug]) - set(si[slug])
        only_shipped = set(si[slug]) - set(li[slug])
        changed = [p for p in set(li[slug]) & set(si[slug]) if li[slug][p] != si[slug][p]]
        for p in sorted(only_local):
            diffs.append(f"  [{slug}] 本地多出：{p}")
        for p in sorted(only_shipped):
            diffs.append(f"  [{slug}] 本地缺少：{p}")
        for p in sorted(changed):
            diffs.append(f"  [{slug}] 内容不同：{p}")
    if diffs:
        ok = False
        print(f"逐文件差异 {len(diffs)} 处：")
        print("\n".join(diffs[:40]))
        if len(diffs) > 40:
            print(f"  …（另有 {len(diffs) - 40} 处）")

    target = tree / MANIFEST_FILENAME
    print(f"目标基线：{target}（现在{'存在' if target.is_file() else '不存在'}）")
    if not ok:
        print("结论：不一致 —— 不写基线（先查清差异来源）")
        return 1

    print("结论：与线上完整包内记录的基线逐文件一致 ✅")
    if not args.write:
        print("（dry-run，未写入；加 --write 落盘）")
        return 0

    payload = {"version": args.version, "published_at": "", "batches": shipped["batches"]}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入：{target}（{target.stat().st_size} 字节）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
