import sys, traceback
from pathlib import Path
sys.path.insert(0, "src")
from contest_generator.hwcheck import HwCheckConfig, render_main_c
from contest_generator.generator import generate_project
from contest_generator.selection import resolve_selection

lib = Path("library/modules")
masters = Path("library/masters")
out = Path(".scratch/_probe_gen/stm32_BOTH")
import shutil
if out.exists(): shutil.rmtree(out.parent, ignore_errors=True)

for platform, channels, slugs in [
    ("stm32", (True, True), ()),
    ("stm32", (True, True), ("led", "delay", "debug_uart", "oled")),
    ("mspm0", (True, True), ("led", "delay", "debug_uart", "oled")),
]:
    cfg = HwCheckConfig(platform=platform, debug_uart=channels[0], oled=channels[1])
    d = out.parent / f"{platform}_{channels[0]}{channels[1]}_{len(slugs)}"
    if d.exists(): shutil.rmtree(d, ignore_errors=True)
    try:
        summary = generate_project(
            platform=platform, slugs=list(slugs), main_c_content=render_main_c(cfg),
            output_dir=d, module_library_dir=lib, masters_dir=masters,
        )
        print(f"OK  {platform} slugs={slugs} -> {summary.output_dir}")
        print("    modules:", [m[0] for m in summary.modules])
    except Exception as e:
        print(f"ERR {platform} slugs={slugs}: {type(e).__name__}: {str(e)[:600]}")
