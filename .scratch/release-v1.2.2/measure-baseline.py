# -*- coding: utf-8 -*-
"""量具：沙箱资料库基线 vs v1.1.1 完整包内的资料库清单（只读）。

要回答：沙箱那份 `.materials-manifest.json`（重建脚本写回）与「真 v1.1.1 包内该有的」
是否逐文件一致——**差集是什么**。差出来的若是演练标记这类非资料，说明基线把它们当成了
「本地多出的文件」，资料库更新链第一次检查时会把它们算进增量。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SIM_BASELINE = Path(r"C:\Users\luoji\Desktop\firstep-sim\sources\materials\.materials-manifest.json")
PACK_MANIFEST = Path.home() / "Desktop" / "firstep-pack" / "firstep-full-v1.1.1.manifest.json"


def flatten(doc: dict) -> dict[str, str]:
    """资料库清单 → {批次内相对路径: sha256}（两个来源形状相同）。"""
    out: dict[str, str] = {}
    for batch in doc.get("batches") or []:
        for item in batch.get("files") or []:
            out[str(item.get("path"))] = str(item.get("sha256") or "")
    return out


def main() -> int:
    sim_doc = json.loads(SIM_BASELINE.read_bytes().decode("utf-8-sig"))
    pack_doc = json.loads(PACK_MANIFEST.read_bytes().decode("utf-8-sig"))
    pack_mm = pack_doc.get("materials_manifest") or {}
    sim = flatten(sim_doc)
    pack = flatten(pack_mm)
    print(f"沙箱基线：version={sim_doc.get('version')} 文件 {len(sim)}")
    print(f"v1.1.1 包内清单：version={pack_mm.get('version')} 文件 {len(pack)}")

    only_sim = sorted(set(sim) - set(pack))
    only_pack = sorted(set(pack) - set(sim))
    differing = sorted(p for p in set(sim) & set(pack) if sim[p] != pack[p])
    print(f"\n只在沙箱基线里：{len(only_sim)}")
    for path in only_sim[:20]:
        print(f"  + {path}")
    print(f"只在 v1.1.1 包清单里：{len(only_pack)}")
    for path in only_pack[:20]:
        print(f"  - {path}")
    print(f"同名但 sha256 不同：{len(differing)}")
    for path in differing[:20]:
        print(f"  ~ {path}")
    print(f"\n逐文件全等：{'✓' if not (only_sim or only_pack or differing) else '✗'}")
    return 0 if not (only_sim or only_pack or differing) else 1


if __name__ == "__main__":
    raise SystemExit(main())
