"""一次性探针：资料库文件后缀分布（决定完整包排除规则，不进版本库）。"""

from __future__ import annotations

import collections
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
exts: collections.Counter[str] = collections.Counter()
sizes: collections.Counter[str] = collections.Counter()
for path in repo.joinpath("sources", "materials").rglob("*"):
    if not path.is_file():
        continue
    ext = path.suffix.lower() or "(无后缀)"
    exts[ext] += 1
    sizes[ext] += path.stat().st_size

for ext, count in exts.most_common(30):
    print(f"{ext:14} {count:6} 个  {sizes[ext] / 1024 / 1024:9.1f} MB")
