"""apply-07-unmark.py — 工单 hwcheck-hygiene/07 的**第二处数据面**：把本单新写的那几句
里的 `**粗体**` 标记去掉（评审整改）。

为什么要去（不是洁癖）：配方 note 走的是 `fx/hwcheck.js` 的 `hwcheckSectionNoteHTML`
→ `esc()` → `innerHTML`——**前端不解释 markdown**，`**` 到了页面上就是两个字面星号
（工单 02 立的口径，`tests/js/hwcheck.test.mjs` 有断言钉住"产品串里不许带标记"）。
本单新写的这句正是学生要读的那句，不能自己带标记。

存量 354 条 note 里的标记**不在本单范围**（那是另一张单的账，记在 07 的票尾）；
本脚本只改本单新写的四处。

用法（幂等）：`python .scratch/hwcheck-hygiene/apply-07-unmark.py`
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from patch_bytes import patch  # noqa: E402  （本目录的小工具，两份脚本共用）

REPO = pathlib.Path(__file__).resolve().parents[2]
TARGET = REPO / "library/hwcheck_recipes.json"

MARKED = "多实例只验**第一路**"
PLAIN = "多实例只验第一路"


def main() -> int:
    blob = TARGET.read_bytes()
    before = hashlib.sha256(blob).hexdigest()
    text = blob.decode("utf-8")
    hits = text.count(MARKED)
    if hits == 0:
        print(f"已就位（没有带标记的那句）；sha256 = {before}")
        return 0
    if PLAIN in text:
        print(f"✗ 带标记与不带标记两种形态同时存在（{hits} 处标记）——先人工核一遍",
              file=sys.stderr)
        return 1
    patch(TARGET, [(MARKED, PLAIN, hits)])
    after = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    raw = TARGET.read_bytes()
    print(f"去掉 {hits} 处 markdown 标记；换行形态："
          f"{'CRLF' if b'\\r\\n' in raw else 'LF'}；字节数 {len(blob)} → {len(raw)}")
    print(f"sha256：{before} → {after}")
    data = json.loads(TARGET.read_text(encoding="utf-8"))
    for slug in ("led", "key"):
        for platform, cell in data[slug].items():
            line = "\n".join(cell["note"]["lines"])
            assert PLAIN in line, f"{slug} × {platform} 的实话说没了"
            assert "第一路**" not in line, f"{slug} × {platform} 还有标记"
    print("复核：JSON 合法、四格都含「多实例只验第一路」且不带标记 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
