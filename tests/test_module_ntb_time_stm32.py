"""ntb_time stm32 补双平台（module-functionalize/03）：get_time_stamp_ms 对偶。"""

from pathlib import Path

LIBRARY_ROOT = Path(__file__).resolve().parents[1] / "library"
MODULES = LIBRARY_ROOT / "modules"


def test_ntb_time_manifest_has_stm32_files():
    import json

    m = json.loads((MODULES / "ntb_time" / "manifest.json").read_text(encoding="utf-8"))
    assert "stm32" in m["platforms"]
    for rel in m["platforms"]["stm32"]["files"]:
        assert (MODULES / "ntb_time" / rel).is_file(), rel


def test_ntb_time_stm32_uses_master_systick():
    c = (MODULES / "ntb_time" / "code" / "ntb_time_stm32.c").read_text(
        encoding="utf-8", errors="replace"
    )
    h = (MODULES / "ntb_time" / "code" / "ntb_time_stm32.h").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "get_time_stamp_ms" in h
    assert "systick_init" in c and "g_systick" in c
    assert "int64_t get_time_stamp_ms" in c
