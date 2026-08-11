"""生成侧跨模块同名文件查重兜底（工单 gen-file-collision-gate/01）。

zigbee_uart / zigbee_uart_key 曾同声明 code/zigbee_uart.c/.h（且都定义
zigbee_uart_init）——双选时五道静态门全数静默通过、UV4 链接期才炸（L6200E
multiply defined）。库内数据已唯一化修复，本文件测生成侧兜底门：用户组合 /
新补录模块再次撞出跨模块同名文件时，生成前大声失败（400 中文），同类冲突
不再等真机编译暴露。

与 test_module_collision.py 的分工：那边守库内数据不变量（全库跨模块重复
路径即红），这边守生成时组合（所选模块集内查重）。门直接吃 manifest 平台
条目声明，不读盘；全链生成路径（真实库 + 真实母版 + 双选照常）由
test_module_collision.py 的双选用例覆盖（同一 generate 接缝）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from contest_generator.errors import error_entry
from contest_generator.generator import (
    DuplicateFilePathError,
    _check_file_path_conflicts,
    generate,
)
from contest_generator.manifest import ModuleManifest, PlatformEntry
from contest_generator.patchers import PLATFORM_STM32
from tests.fakes import _add_module

LIBRARY_MODULES = Path(__file__).resolve().parents[1] / "library" / "modules"


def _manifest(
    slug: str, files: tuple[str, ...], *, platforms: dict[str, PlatformEntry] | None = None
) -> ModuleManifest:
    """内存 manifest：默认只在 stm32 平台声明给定文件。"""
    return ModuleManifest(
        slug=slug,
        description=slug,
        platforms=(
            {PLATFORM_STM32: PlatformEntry(files=files, verified=True)}
            if platforms is None
            else platforms
        ),
    )


# ---------------------------------------------------------------------------
# 门禁本体（内存 manifest 直喂，无盘上夹具）
# ---------------------------------------------------------------------------


def test_gate_rejects_cross_module_duplicate_path():
    """红证：重命名前冲突形态（两模块都声明 code/zigbee_uart.c）→ 大声失败，
    报错点名两模块与路径、点明链接期后果。"""
    with pytest.raises(DuplicateFilePathError) as excinfo:
        _check_file_path_conflicts(
            [_manifest("zigbee_uart", ("code/zigbee_uart.c",)),
             _manifest("zigbee_uart_key", ("code/zigbee_uart.c",))],
            PLATFORM_STM32,
        )

    message = str(excinfo.value)
    assert "zigbee_uart" in message
    assert "zigbee_uart_key" in message
    assert "code/zigbee_uart.c" in message
    assert "L6200E" in message  # 点明后果（链接期 multiply defined）


def test_gate_accepts_unique_paths():
    """修复后形态（zigbee_uart_key 文件已唯一化）→ 双选不报。"""
    _check_file_path_conflicts(
        [_manifest("zigbee_uart", ("code/zigbee_uart.c",)),
         _manifest("zigbee_uart_key", ("code/zigbee_uart_key.c",))],
        PLATFORM_STM32,
    )  # 不抛


def test_gate_accepts_single_module():
    """单选照旧：单模块文件列表不触发跨模块查重。"""
    _check_file_path_conflicts(
        [_manifest("zigbee_uart", ("code/zigbee_uart.c", "code/zigbee_uart.h"))],
        PLATFORM_STM32,
    )  # 不抛


def test_gate_skips_empty_files_embedded_in_master():
    """files 空（实现内嵌母版）→ 跳过：无文件可撞，两个内嵌模块不报。"""
    _check_file_path_conflicts(
        [_manifest("a", ()), _manifest("b", ())],
        PLATFORM_STM32,
    )  # 不抛


def test_gate_skips_module_without_platform_entry():
    """无该平台版本条目（缺失由 _check_module_files 报）→ 不参与查重。"""
    _check_file_path_conflicts(
        [_manifest("a", ("code/x.c",), platforms={})],
        PLATFORM_STM32,
    )  # 不抛


def test_gate_ignores_other_platform_entries():
    """只查选中平台条目：同一路径在另一平台重复不影响本平台判定。"""
    entry = PlatformEntry(files=("code/x.c",), verified=True)
    manifests = [
        ModuleManifest(slug="a", description="", platforms={"stm32": entry}),
        ModuleManifest(slug="b", description="", platforms={"mspm0": entry}),
    ]
    _check_file_path_conflicts(manifests, PLATFORM_STM32)  # 本平台各一份 → 不抛


def test_gate_rejects_same_module_duplicate_declaration():
    """同一模块内重复声明同查（parse 侧已防，这里防内存构造路径）。"""
    with pytest.raises(DuplicateFilePathError) as excinfo:
        _check_file_path_conflicts(
            [_manifest("a", ("code/x.c", "code/x.c"))],
            PLATFORM_STM32,
        )

    assert "模块 a 重复声明文件 code/x.c" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 全链生成（红证：恢复冲突形态 → 400 中文，不再等 UV4 链接期）
# ---------------------------------------------------------------------------


def test_generate_rejects_cross_module_duplicate_paths(
    fake_module_library, fake_master_project, tmp_path
):
    """恢复重命名前冲突形态（两模块都声明 code/zigbee_uart.c）→ 生成 400 中文
    报错（error_to_http 表映射），输出目录不被创建。"""
    for slug in ("zigbee_uart", "zigbee_uart_key"):
        _add_module(
            fake_module_library,
            {
                "slug": slug,
                "description": f"{slug}（冲突形态）",
                "dependencies": [],
                "platforms": {
                    "stm32": {
                        "files": ["code/zigbee_uart.c"],
                        "verified": False,
                        "hardware_bound": False,
                        "notes": "",
                        "kit": "",
                        "source_url": "",
                    }
                },
            },
            {"code/zigbee_uart.c": "void zigbee_uart_init(void) {}\n"},
        )
    manifests = [
        ModuleManifest.load(fake_module_library / slug)
        for slug in ("zigbee_uart", "zigbee_uart_key")
    ]
    output_dir = tmp_path / "out"

    with pytest.raises(DuplicateFilePathError) as excinfo:
        generate(
            platform=PLATFORM_STM32,
            manifests=manifests,
            module_library_dir=fake_module_library,
            master_project_dir=fake_master_project,
            output_dir=output_dir,
            main_c_content="int main(void) { while (1); }\n",
        )

    message = str(excinfo.value)
    assert "zigbee_uart" in message and "zigbee_uart_key" in message
    assert "code/zigbee_uart.c" in message

    status, mapped = error_entry(excinfo.value)  # 与 /api/generate 同一映射表
    assert status == 400
    assert "同名文件冲突" in mapped
    assert not output_dir.exists()  # 校验在创建输出目录之前


def test_real_zigbee_pair_passes_gate():
    """真实库数据（已唯一化）：zigbee 双选 + config 过新门不报（全链生成
    用例见 test_module_collision.py 双选测试——同一 generate 接缝）。"""
    manifests = [
        ModuleManifest.load(LIBRARY_MODULES / slug)
        for slug in ("config", "zigbee_uart", "zigbee_uart_key")
    ]
    _check_file_path_conflicts(manifests, PLATFORM_STM32)  # 不抛
