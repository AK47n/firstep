# -*- coding: utf-8 -*-
"""探针：ir_remote_tx（GPIO OUTPUT 默认 PA0）单选 SysConfig CLI 是否仍可过。"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from contest_generator.compile_runner import (  # noqa: E402
    collect_build_log, find_ccs_tools, find_make,
)
from contest_generator.generator import generate  # noqa: E402
from contest_generator.platforms import PLATFORM_MSPM0  # noqa: E402
from contest_generator.selection import resolve_selection  # noqa: E402

GMAKE = r"C:/ti/ccs2050/ccs/utils/bin/gmake.exe"
MAIN_C = (
    '#include "ti_msp_dl_config.h"\n'
    '#include "ir_remote_tx.h"\n'
    "int main(void) { ir_tx_init(); while (1); }\n"
)

out = REPO / ".scratch" / "wiki-modules-batch8" / "matrix" / "probe_ir_tx"
if out.exists():
    import shutil
    shutil.rmtree(out)
out.mkdir(parents=True)

resolved = resolve_selection(REPO / "library" / "modules", PLATFORM_MSPM0, ["ir_remote_tx"])
generate(
    platform=PLATFORM_MSPM0,
    manifests=resolved.manifests,
    module_library_dir=REPO / "library" / "modules",
    master_project_dir=REPO / "library" / "masters" / "mspm0",
    output_dir=out,
    main_c_content=MAIN_C,
    ccs_tools=find_ccs_tools(),
)
log = collect_build_log(PLATFORM_MSPM0, out, make=find_make(GMAKE), timeout=240)
import re
print("exit_code:", log.run.exit_code)
m = re.search(r"Error: cannot set[^\n]*", log.run.output)
print("assign_error:", m.group(0) if m else "(none)")
print("target_built:", "Finished building target" in log.run.output)
