# -*- coding: utf-8 -*-
"""冒烟：真实生成 aht10 mspm0，检查 README 来源行/声明段与工程内模块头（lckfb-attribution/02）。"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contest_generator.generator import generate
from contest_generator.platforms import PLATFORM_MSPM0
from contest_generator.selection import resolve_selection

LIB = Path(__file__).resolve().parents[2] / "library" / "modules"
MASTER = Path(__file__).resolve().parents[2] / "library" / "masters" / "mspm0"

MAIN_C = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "aht10.h"\n'
    "\n"
    "int main(void)\n"
    "{\n"
    "    aht10_init();\n"
    "    while (1)\n"
    "    {\n"
    "    }\n"
    "}\n"
)

resolved = resolve_selection(LIB, PLATFORM_MSPM0, ["aht10"])
out = Path(tempfile.mkdtemp()) / "out"
generate(
    platform=PLATFORM_MSPM0,
    manifests=resolved.manifests,
    module_library_dir=LIB,
    master_project_dir=MASTER,
    output_dir=out,
    main_c_content=MAIN_C,
)
readme = (out / "README.md").read_text(encoding="utf-8")
checks = {
    "README 声明段": "第三方素材来源" in readme,
    "README 来源行": (
        "https://wiki.lckfb.com/zh-hans/dmx/module/sensor/aht10-temp-humi-sensor.html"
        in readme
    ),
    "工程内模块头含 URL": "wiki.lckfb.com" in (out / "modules/aht10/code/aht10.c").read_text(
        encoding="utf-8"
    )[:300],
}
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + name)
assert all(checks.values())
