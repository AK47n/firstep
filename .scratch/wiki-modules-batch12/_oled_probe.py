import sys
from pathlib import Path
sys.path.insert(0, 'src')
from contest_generator.generator import generate
from contest_generator.platforms import PLATFORM_MSPM0
from contest_generator.selection import resolve_selection
REPO = Path('.')
resolved = resolve_selection(REPO / 'library' / 'modules', PLATFORM_MSPM0, ['oled'])
main_c = '#include "oled.h"\nint main(void){OLED_Init(); while(1);}\n'
generate(platform=PLATFORM_MSPM0, manifests=resolved.manifests,
         module_library_dir=REPO / 'library' / 'modules',
         master_project_dir=REPO / 'library' / 'masters' / 'mspm0',
         output_dir=Path('.scratch/wiki-modules-batch12/matrix/_oled_probe'),
         main_c_content=main_c, ccs_tools=None)
t = (Path('.scratch/wiki-modules-batch12/matrix/_oled_probe') / 'mspm0.syscfg').read_text(encoding='utf-8', newline='')
for l in t.splitlines():
    if 'OLED' in l:
        print(repr(l))
