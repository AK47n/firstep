"""复用 `contrast-residue/probe-09` 的口径，把输入指到本轮新拍的 JSON。

**为什么要这一层**：`probe-09-cant-readings.py` 把输入写死成
`.scratch/contrast-residue/probe-08-shots-cant.json`；本轮用
`node .scratch/code-contrast/probe-08-disabled-state.mjs --tag cant --out .scratch/release-v1.4.3`
**重新拍了一份同名 JSON 在新目录**（上一轮的 PNG/JSON 原地不动、零覆盖）。

所以这里只做一件事：按路径载入 probe-09，把它的 `SHOTS` 常量换成新目录那一份，再调它的
`main()` —— **判据、取数、比值算法仍是同一份代码**，不另造第二套口径（本仓最怕"腿绿而读数红"）。

跑法（仓库根）：`python .scratch\\release-v1.4.3\\run-probe-09.py`
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / ".scratch" / "contrast-residue" / "probe-09-cant-readings.py"
SHOTS = HERE / "probe-08-shots-cant.json"


def main() -> int:
    if not SHOTS.is_file():
        print(f"缺输入：{SHOTS}（先把 probe-08-disabled-state.mjs 拍到本目录）")
        return 2
    spec = importlib.util.spec_from_file_location("_probe09", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SHOTS = SHOTS          # ← 只换输入路径，其余原样
    module.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
