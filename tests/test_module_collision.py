"""跨模块同名文件/符号冲突回归（工单 zigbee-file-collision/01）。

zigbee_uart 与 zigbee_uart_key 曾同声明 code/zigbee_uart.c/.h 且都定义
zigbee_uart_init —— 双车协同模型双选时 UV4 L6200E multiply defined（绿跑
实测，见 .scratch/ball-detect-null-fix/01 验收记录遗留发现）。修复走重命名
路径：key 版文件与符号唯一化（code/zigbee_uart_key.c/.h + zigbee_uart_key_init
/ zigbee_uart_key_send_id），zigbee_uart（锁端接收版）不动。

本文件用仓库内真实模块库 + 真实 stm32 母版断言两条不变量（防回退），并跑
双选/单选生成用例 —— 全程无 LLM、无服务：main.c 手写，直驱 generate()
（与 /api/generate 同一接缝）。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from contest_generator.generator import generate
from contest_generator.library import list_modules
from contest_generator.manifest import ModuleManifest
from contest_generator.patchers import PLATFORM_STM32

LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"
STM32_MASTER = Path(__file__).resolve().parents[1] / "library" / "masters" / "stm32"

ZIGBEE_SLUGS = ("zigbee_uart", "zigbee_uart_key")

# 数据守卫用的保守正则：单行"类型 名字( 参数)"形态的非 static 函数定义。
# 只是防回退哨兵、不是 C 解析器 —— 限定在双选两文件上用（均无原型声明，
# 可靠）；全库扫描会误伤 .c 内的原型声明，不做。
DEF_RE = re.compile(
    r"^\s*(?!static\b)(?:void|int|char|bool|float|double|uint8_t|uint16_t|uint32_t)"
    r"\s+(\w+)\s*\(",
    re.M,
)


def _zigbee_main_c(include_headers: tuple[str, ...], calls: tuple[str, ...]) -> str:
    """手写 main.c：include 指定头 + 按序调用给定初始化函数，其余最小化。

    门禁 _check_main_calls 只认"所选模块头 + 母版头"里存在的调用，main 本身
    按本地定义豁免 —— 最小形态即通过全部静态门禁。
    """
    includes = "\n".join(f'#include "{h}"' for h in ("headfile.h", *include_headers))
    body = "\n".join(f"    {name}();" for name in calls)
    return (
        f"{includes}\n\n"
        "int main(void)\n"
        "{\n"
        f"{body}\n"
        "    while (1)\n"
        "    {\n"
        "    }\n"
        "}\n"
    )


def _load_manifests(slugs: tuple[str, ...]) -> list[ModuleManifest]:
    return [ModuleManifest.load(LIBRARY_MODULES / slug) for slug in slugs]


def test_library_no_cross_module_duplicate_file_paths():
    """库内不得有两个模块声明相同平台相对路径（防回退；zigbee 对曾违反）。

    生成器把模块文件复制到 modules/<slug>/ 命名空间目录，同名文件/符号冲突
    静态门禁不检测、只在 UV4 链接期炸 —— 数据层不变量由本测试守。
    """
    manifests = list_modules(LIBRARY_MODULES)  # 任一 manifest 损坏即 LibraryError
    by_key: dict[tuple[str, str], str] = {}
    for manifest in manifests:
        for platform, entry in manifest.platforms.items():
            for rel in entry.files:
                key = (platform, rel)
                assert key not in by_key, (
                    f"{manifest.slug} 与 {by_key[key]} 声明了相同的平台文件路径"
                    f" {key[0]}:{key[1]} —— 同选会同名冲突（生成侧不检测）"
                )
                by_key[key] = manifest.slug


def test_zigbee_dual_select_generation_files_and_symbols_unique(tmp_path):
    """双选生成（真实库 + 真实母版）：产物文件同名不重叠、定义符号互斥、
    uvprojx 里两个源文件都以各自路径注册。"""
    out, _ = generate(
        platform=PLATFORM_STM32,
        manifests=_load_manifests(("config", *ZIGBEE_SLUGS)),
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=tmp_path / "out",
        main_c_content=_zigbee_main_c(
            ("zigbee_uart.h", "zigbee_uart_key.h"),
            ("zigbee_uart_init", "zigbee_uart_key_init"),
        ),
    )

    # 产物：两模块代码文件不同名（旧数据下此处同为 zigbee_uart.c/.h）
    assert (out / "modules/zigbee_uart/code/zigbee_uart.c").is_file()
    assert (out / "modules/zigbee_uart_key/code/zigbee_uart_key.c").is_file()
    assert (out / "modules/zigbee_uart_key/code/zigbee_uart.c").exists() is False

    # 定义符号互斥（旧数据下两文件都定义 zigbee_uart_init）
    defined_by: dict[str, str] = {}
    for slug in ZIGBEE_SLUGS:
        for c in (out / "modules" / slug / "code").glob("*.c"):
            for name in DEF_RE.findall(c.read_text(encoding="utf-8")):
                assert name not in defined_by, (
                    f"{slug} 与 {defined_by[name]} 都定义了 {name} —— 双选链接必"
                    " L6200E multiply defined"
                )
                defined_by[name] = slug

    # uvprojx：两个源文件都以各自路径注册进 modules 分组
    uvprojx = next(out.rglob("*.uvprojx"))
    root = ET.parse(uvprojx).getroot()
    groups = root.findall("Targets/Target/Groups/Group")
    modules = next(g for g in groups if g.findtext("GroupName") == "modules")
    paths = [f.findtext("FilePath") for f in modules.findall("Files/File")]
    assert any("zigbee_uart_key.c" in p for p in paths)
    assert any(
        "zigbee_uart.c" in p and "zigbee_uart_key" not in p for p in paths
    )


@pytest.mark.parametrize("slug", ZIGBEE_SLUGS)
def test_zigbee_single_select_regression(tmp_path, slug):
    """单选照旧：各模块单独生成全门禁通过、模块文件按 manifest 落盘。"""
    out, _ = generate(
        platform=PLATFORM_STM32,
        manifests=_load_manifests(("config", slug)),
        module_library_dir=LIBRARY_MODULES,
        master_project_dir=STM32_MASTER,
        output_dir=tmp_path / slug,
        main_c_content=_zigbee_main_c((f"{slug}.h",), (f"{slug}_init",)),
    )
    rel = (
        "code/zigbee_uart_key.c"
        if slug == "zigbee_uart_key"
        else "code/zigbee_uart.c"
    )
    assert (out / "modules" / slug / rel).is_file()
