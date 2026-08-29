"""接线快照（工单 task-wiring-diagram/01）：落盘 + 同源一致性 + 无接线退化。

主 seam = generate_project 流程级（照 test_readme 先例）：生成含接线模块的
工程 → 断言 .contest_wiring.json 存在、字段齐全、board 内嵌且与 /api/boards
同平台板一致、rows 与 README「引脚接线表」行逐行一致（含多实例通道行）；
无任何接线模块的工程也落盘（rows 空数组，与 README 空表行为一致）；快照为
纯新增文件（README 内容与直接渲染 render_readme 逐字节一致）。wiring 模块
纯函数直测：行推导 / 快照构建 / 写读往返 / 坏 JSON 与版本不符容错。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contest_generator.boards import board_for_platform
from contest_generator.context_manifest import CONTEXT_MANIFEST_FILENAME as CONTEXT_FILENAME
from contest_generator.generator import generate_project
from contest_generator.manifest import ModuleManifest
from contest_generator.patchers import PLATFORM_STM32
from contest_generator.readme import README_FILENAME, _pin_rows, render_readme
from contest_generator.selection import ModuleInstance
from contest_generator.wiring import (
    WIRING_SNAPSHOT_FILENAME,
    WIRING_SNAPSHOT_VERSION,
    WiringEntry,
    build_wiring_snapshot,
    filter_wiring_entries,
    module_target_names,
    parse_wiring_entries,
    read_wiring_rows,
    read_wiring_snapshot,
    read_wiring_snapshot_legacy,
    wiring_context,
    wiring_rows,
    wiring_summary_text,
    write_wiring_snapshot,
)
from tests.fakes import (
    MAIN_SKELETON,
    _add_module,
    make_fake_master_project,
)


def _add_pin_module(library: Path, slug: str, pins: list[dict]) -> None:
    """给假模块库补一个带 pins 声明的模块（stm32 单平台，files 平铺）。"""
    _add_module(
        library,
        {
            "slug": slug,
            "description": f"{slug} 模块驱动",
            "dependencies": [],
            "platforms": {
                PLATFORM_STM32: {
                    "files": [f"{slug}.c", f"{slug}.h"],
                    "verified": True,
                    "pins": pins,
                },
            },
        },
        {
            f"{slug}.c": f'#include "{slug}.h"\nvoid {slug}_init(void);\n',
            f"{slug}.h": f"#pragma once\nvoid {slug}_init(void);\n",
        },
    )


def _add_key_module(library: Path) -> None:
    """key 模块：stm32 一条按键引脚（label + required，与 test_readme 同构）。"""
    _add_pin_module(
        library,
        "key",
        [
            {
                "id": "KEY_START",
                "type": "gpio_in",
                "default": "PB3",
                "label": "启动按键",
                "required": True,
            }
        ],
    )


def _add_led_multi_module(library: Path) -> None:
    """led 多实例模块：stm32 无 pins 声明（通道宏经实例计划落行）。"""
    _add_module(
        library,
        {
            "slug": "led",
            "description": "状态指示灯",
            "dependencies": [],
            "multi_instance": {"max": 8, "variant": "color"},
            "platforms": {
                PLATFORM_STM32: {"files": ["led.c", "led.h"], "verified": True}
            },
        },
        {
            "led.c": '#include "led.h"\nvoid led_init(unsigned char channel);\n',
            "led.h": "#pragma once\nvoid led_init(unsigned char channel);\n",
        },
    )


def _resolved(fake_module_library: Path, *slugs: str) -> list[ModuleManifest]:
    """假库 resolved 顺序（DFS 后序：依赖先于使用者）。"""
    from contest_generator.selection import resolve_dependencies

    by_slug = {
        m.slug: m
        for m in (ModuleManifest.load(fake_module_library / s) for s in slugs)
    }
    return list(resolve_dependencies(slugs, by_slug))


# ---------------------------------------------------------------------------
# 流程级 seam：generate_project 落盘接线快照（与 README 同批数据）
# ---------------------------------------------------------------------------


def test_generate_project_writes_wiring_snapshot(fake_module_library, tmp_path):
    """生成含接线模块的工程：快照文件出现，字段齐全；board 内嵌与
    /api/boards 同平台板一致；rows 与 README 表行逐行一致（同源）。"""
    _add_key_module(fake_module_library)
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["key", "dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )

    snapshot_path = summary.output_dir / WIRING_SNAPSHOT_FILENAME
    assert snapshot_path.is_file()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    assert snapshot["version"] == WIRING_SNAPSHOT_VERSION
    assert snapshot["platform"] == PLATFORM_STM32
    board = board_for_platform(PLATFORM_STM32)
    assert snapshot["board_id"] == board.board_id
    assert snapshot["board"] == board.to_dict()
    # 内嵌板定义字段齐全（引脚坐标 / 丝印 / 固定资源 / 地标）
    assert snapshot["board"]["pins"]
    assert snapshot["board"]["fixed"]
    assert snapshot["board"]["landmarks"]
    assert all(
        "name" in pin and "x" in pin and "y" in pin
        for pin in snapshot["board"]["pins"]
    )

    # rows 与 README「引脚接线表」行逐行一致（同一输入、同一推导 _pin_row_items）
    manifests = _resolved(fake_module_library, "key", "dht11", "delay")
    expected = [
        (r["slug"], r["role"], r["pin"], r["remark"])
        for r in wiring_rows(PLATFORM_STM32, manifests)
    ]
    assert [(r["slug"], r["role"], r["pin"], r["remark"]) for r in snapshot["rows"]] == expected
    assert expected == _pin_rows(PLATFORM_STM32, manifests)  # 同源防护：两函数同输出
    readme = (summary.output_dir / README_FILENAME).read_text(encoding="utf-8")
    for r in snapshot["rows"]:
        assert f"| {r['slug']} | {r['role']} | {r['pin']} | {r['remark']} |" in readme


def test_generate_project_without_pin_modules_rows_empty(
    fake_module_library, tmp_path
):
    """无任何接线模块的工程也落盘快照：rows 空数组（与 README 空表行为一致）。"""
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["dht11", "delay"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )

    snapshot_path = summary.output_dir / WIRING_SNAPSHOT_FILENAME
    assert snapshot_path.is_file()
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["rows"] == []
    readme = (summary.output_dir / README_FILENAME).read_text(encoding="utf-8")
    assert "本工程所选模块未声明引脚接线。" in readme  # README 空表兜底并存


def test_generate_project_snapshot_multi_instance_rows(
    fake_module_library, tmp_path
):
    """多实例计划：快照 rows 含每实例通道行（role = 通道宏、pin = 实例脚），
    与 README 表行逐行一致。"""
    _add_led_multi_module(fake_module_library)
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["led", "dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
        instances={
            "led": (
                ModuleInstance(name="红灯", variant="red"),
                ModuleInstance(name="黄灯", variant="yellow"),
            )
        },
    )

    snapshot = json.loads(
        (summary.output_dir / WIRING_SNAPSHOT_FILENAME).read_text(encoding="utf-8")
    )
    rows = snapshot["rows"]
    assert [(r["slug"], r["role"], r["pin"], r["remark"]) for r in rows] == [
        ("led", "LED_RED", "PC13", ""),
        ("led", "LED_YELLOW", "PC14", ""),
    ]
    readme = (summary.output_dir / README_FILENAME).read_text(encoding="utf-8")
    for r in rows:
        assert f"| {r['slug']} | {r['role']} | {r['pin']} | {r['remark']} |" in readme


def test_generate_project_readme_byte_identical_to_direct_render(
    fake_module_library, tmp_path
):
    """快照为纯新增文件：README 内容与直接渲染 render_readme 逐字节一致
    （生成路径不因快照引入而扰动既有产物）。"""
    _add_key_module(fake_module_library)
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["key", "dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )
    readme = (summary.output_dir / README_FILENAME).read_text(encoding="utf-8")
    expected = render_readme(
        PLATFORM_STM32,
        board_for_platform(PLATFORM_STM32).name,
        _resolved(fake_module_library, "key", "dht11", "delay"),
    )
    # Windows 文本写盘把 \n 转成 \r\n（write_text 缺省 newline 翻译）——
    # 比较按 LF 归一，断言快照引入不扰动 README 内容
    assert readme.replace("\r\n", "\n") == expected


def test_generate_project_degrades_without_board_skips_snapshot(
    fake_module_library, tmp_path, monkeypatch
):
    """板数据取不到（BoardError）：生成不阻断（README 无板名行），快照不写
    （前端走退化路径——与 README 优雅降级同款）。"""
    from contest_generator import generator as generator_module
    from contest_generator.boards import BoardError

    def _no_board(platform: str):
        raise BoardError(f"平台 {platform!r} 没有板定义")

    monkeypatch.setattr(generator_module, "board_for_platform", _no_board)
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)
    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["delay"],
        main_c_content="int main(void) { while (1); }\n",
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )
    assert not (summary.output_dir / WIRING_SNAPSHOT_FILENAME).exists()


# ---------------------------------------------------------------------------
# wiring 模块纯函数直测：行推导 / 快照构建 / 写读往返 / 容错
# ---------------------------------------------------------------------------


def test_wiring_rows_role_shape_matches_table_derivation(fake_module_library):
    """wiring_rows 与 _pin_rows 同源：(slug, role, pin, remark) 逐条相等；
    role_id / role_label 结构化字段齐全（label 附注形态）。"""
    _add_key_module(fake_module_library)
    manifests = [ModuleManifest.load(fake_module_library / "key")]
    rows = wiring_rows(PLATFORM_STM32, manifests)
    assert [(r["slug"], r["role"], r["pin"], r["remark"]) for r in rows] == [
        ("key", "KEY_START（启动按键）", "PB3", "gpio_in（必接）")
    ]
    assert [(r["slug"], r["role"]) for r in rows] == [("key", "KEY_START（启动按键）")]
    assert rows[0]["role_id"] == "KEY_START"
    assert rows[0]["role_label"] == "启动按键"


def test_build_wiring_snapshot_embeds_board_and_rows(fake_module_library):
    """快照构建：version / platform / board_id / board（to_dict 同形）/ rows。"""
    _add_key_module(fake_module_library)
    manifests = [ModuleManifest.load(fake_module_library / "key")]
    board = board_for_platform(PLATFORM_STM32)
    snapshot = build_wiring_snapshot(PLATFORM_STM32, board, manifests)
    assert snapshot["version"] == WIRING_SNAPSHOT_VERSION
    assert snapshot["platform"] == PLATFORM_STM32
    assert snapshot["board_id"] == board.board_id
    assert snapshot["board"] == board.to_dict()
    assert snapshot["rows"][0]["pin"] == "PB3"


def test_wiring_snapshot_write_file(tmp_path):
    """快照写盘：格式 = ensure_ascii=False + 尾部换行（与既有生成 JSON 一致）。"""
    board = board_for_platform(PLATFORM_STM32)
    snapshot = build_wiring_snapshot(PLATFORM_STM32, board, [], (), {})
    path = write_wiring_snapshot(tmp_path, snapshot)
    assert path.name == WIRING_SNAPSHOT_FILENAME
    text = path.read_text(encoding="utf-8")
    assert "STM32F103C8T6" in text
    assert text.endswith("\n")
    # 往返一致（写盘内容可被 json 读回——读取契约见下节）
    assert json.loads(text) == snapshot


# ---------------------------------------------------------------------------
# wiring 字段校验（工单 02）：形状提取 / 查表校验 / 校验数据源装配
# ---------------------------------------------------------------------------


def test_parse_wiring_entries_shape_only():
    """形状提取：合法条目全收（note 可省）、pin/target 非空字符串、坏条目丢弃、
    非 list / None → 空元组（字段缺省 = 本步无接线引用）。"""
    raw = [
        {"pin": "PA0", "target": "DIO", "note": "注意极性"},
        {"pin": "PB3", "target": "KEY_START"},  # note 缺省
        {"pin": "", "target": "X"},              # pin 空串 → 丢
        {"pin": "PA0", "target": ""},            # target 空串 → 丢
        {"pin": 123, "target": "X"},             # pin 非字符串 → 丢
        "not-a-dict",                            # 非对象 → 丢
        {"pin": "PA0", "target": "DIO", "note": 5},  # note 非字符串 → 空串
    ]
    entries = parse_wiring_entries(raw)
    assert entries == (
        WiringEntry(pin="PA0", target="DIO", note="注意极性"),
        WiringEntry(pin="PB3", target="KEY_START", note=""),
        WiringEntry(pin="PA0", target="DIO", note=""),
    )
    assert parse_wiring_entries(None) == ()
    assert parse_wiring_entries("oops") == ()
    assert parse_wiring_entries([{"pin": "PA0"}]) == ()  # 缺 target


def test_filter_wiring_entries_keeps_valid_drops_invalid():
    """逐条校验：合法全过 / 部分非法丢弃（保序）/ 全非法 → 空元组；
    幻觉引脚名（PA99）/ 幻觉端子名拒绝。"""
    pins = ["PA0", "PB3", "3V3", "GND"]
    targets = ["DIO", "KEY_START", "板载 LED", "PA0"]
    all_valid = [
        WiringEntry(pin="PA0", target="DIO"),
        WiringEntry(pin="3V3", target="板载 LED", note="供电"),
        WiringEntry(pin="GND", target="PA0"),  # 板内直连（引脚名自身作 target）
    ]
    assert filter_wiring_entries(all_valid, pins, targets) == tuple(all_valid)
    mixed = [
        WiringEntry(pin="PA0", target="DIO"),
        WiringEntry(pin="PA99", target="DIO"),      # 幻觉引脚 → 丢
        WiringEntry(pin="PB3", target="KEY_START"),
        WiringEntry(pin="PB3", target="PA99"),      # 幻觉端子 → 丢
    ]
    assert filter_wiring_entries(mixed, pins, targets) == (
        WiringEntry(pin="PA0", target="DIO"),
        WiringEntry(pin="PB3", target="KEY_START"),
    )
    assert filter_wiring_entries(mixed[:1], ["PA99"], targets) == ()
    assert filter_wiring_entries([], pins, targets) == ()


def test_module_target_names_ids_and_labels(fake_module_library):
    """模块端子名集合 = 声明 id ∪ 非空 label（label 缺省 = 只有 id）。"""
    _add_key_module(fake_module_library)
    manifests = [ModuleManifest.load(fake_module_library / "key")]
    names = module_target_names(manifests, PLATFORM_STM32)
    assert "KEY_START" in names
    assert "启动按键" in names


def test_wiring_context_snapshot_preferred(tmp_path):
    """校验数据源：快照内嵌板定义优先（rows 端子名 = role_id/label ∪ 固定 ∪
    引脚名）；无快照回退静态板定义 + manifests 声明（不阻塞）。"""
    board = board_for_platform(PLATFORM_STM32)
    snapshot = build_wiring_snapshot(
        PLATFORM_STM32,
        board,
        [],
        (),
        {},
    )
    snapshot["rows"] = [
        {"slug": "k", "role": "K（键）", "role_id": "K", "role_label": "键",
         "pin": "PA0", "remark": "gpio_out（必接）"}
    ]
    write_wiring_snapshot(tmp_path, snapshot)
    ctx_board, pins, targets = wiring_context(tmp_path, PLATFORM_STM32, [])
    assert ctx_board["name"] == board.name
    assert "PA0" in pins and "GND" in pins
    # rows 端子名（K / 键 / K（键）合成串——评审整改：展示值照抄也放行）
    # + 板载固定资源名 + 引脚名
    assert "K" in targets and "键" in targets and "K（键）" in targets
    assert "板载 LED" in targets and "GND" in targets
    # 评审整改回归：白名单收渲染合成串——AI 照抄 summary 角色列 / 端子标签
    # 展示值进 wiring 也放行（旧实现只收 role_id/label 单独值，会误滤）
    composed = WiringEntry(pin="PA0", target="K（键）")
    assert filter_wiring_entries([composed], pins, targets) == (composed,)

    # 无快照 → 静态板定义回退（不抛异常）
    empty = tmp_path / "empty"
    empty.mkdir()
    ctx_board2, pins2, targets2 = wiring_context(empty, PLATFORM_STM32, [])
    assert ctx_board2["name"] == board.name
    assert len(pins2) > 30


def test_read_wiring_rows_snapshot_priority(fake_module_library):
    """接线行读取：快照行优先（落盘值）；无快照 = manifests 现场推导。"""
    _add_key_module(fake_module_library)
    manifests = [ModuleManifest.load(fake_module_library / "key")]
    derived = read_wiring_rows(fake_module_library / "not-a-dir", manifests, PLATFORM_STM32)
    assert derived and derived[0]["pin"] == "PB3"


def test_wiring_summary_text_lists_rows_and_power():
    """prompt 白名单段：表行（与 README 同源文本）+ 板载供电/固定资源行；
    rows 空 / board 缺失各自退化。"""
    rows = [
        {"slug": "key", "role": "KEY_START（启动按键）", "pin": "PB3",
         "remark": "gpio_in（必接）"}
    ]
    board = board_for_platform(PLATFORM_STM32).to_dict()
    text = wiring_summary_text(rows, board)
    assert "| key | KEY_START（启动按键） | PB3 | gpio_in（必接） |" in text
    assert "板载供电/固定资源（wiring 可引用）：" in text
    assert "3V3" in text and "GND" in text and "板载 LED" in text
    empty_text = wiring_summary_text([], board)
    assert "接线表为空" in empty_text
    bare = wiring_summary_text(rows, None)
    assert "KEY_START" in bare and "板载供电" not in bare


@pytest.mark.parametrize(
    "setup",
    ["missing", "bad_json", "non_object", "wrong_version"],
)
def test_read_wiring_snapshot_corruption_returns_none(tmp_path, setup):
    """读取容错：无文件 / 坏 JSON / 非对象 / 版本不符 → None（不抛异常）。"""
    if setup == "missing":
        pass
    elif setup == "bad_json":
        (tmp_path / WIRING_SNAPSHOT_FILENAME).write_text("{oops", encoding="utf-8")
    elif setup == "non_object":
        (tmp_path / WIRING_SNAPSHOT_FILENAME).write_text("[1, 2]", encoding="utf-8")
    else:
        board = board_for_platform(PLATFORM_STM32)
        snapshot = build_wiring_snapshot(PLATFORM_STM32, board, [], (), {})
        snapshot["version"] = WIRING_SNAPSHOT_VERSION + 1
        write_wiring_snapshot(tmp_path, snapshot)
    assert read_wiring_snapshot(tmp_path) is None


def test_read_wiring_snapshot_legacy_rebuilds_from_readme(
    fake_module_library, tmp_path
):
    """工单 05：无快照目录（README + context platform）→ 兜底重建快照形
    dict——rows 与生成口径逐行一致（README 表同源解析）、board = 静态板定义、
    board_id / platform 与 context 同；快照文件本身缺失不阻断。"""
    _add_key_module(fake_module_library)
    masters_dir = tmp_path / "masters"
    make_fake_master_project(masters_dir / PLATFORM_STM32)

    summary = generate_project(
        platform=PLATFORM_STM32,
        slugs=["key", "dht11"],
        main_c_content=MAIN_SKELETON,
        output_dir=tmp_path / "out",
        module_library_dir=fake_module_library,
        masters_dir=masters_dir,
    )
    out = summary.output_dir
    # 模拟旧工程：删掉快照（其余产物不动，README / context 仍在）
    (out / WIRING_SNAPSHOT_FILENAME).unlink()

    legacy = read_wiring_snapshot_legacy(out)
    assert legacy is not None
    assert legacy["version"] == WIRING_SNAPSHOT_VERSION
    assert legacy["platform"] == PLATFORM_STM32
    board = board_for_platform(PLATFORM_STM32)
    assert legacy["board_id"] == board.board_id
    assert legacy["board"] == board.to_dict()
    manifests = _resolved(fake_module_library, "key", "dht11", "delay")
    expected = wiring_rows(PLATFORM_STM32, manifests)
    assert legacy["rows"] == expected
    # 与快照存在时读到的内容一致（同源恢复，不是新数据）
    write_wiring_snapshot(out, build_wiring_snapshot(PLATFORM_STM32, board, manifests, (), {}))
    assert read_wiring_snapshot(out)["rows"] == expected


def test_read_wiring_snapshot_legacy_degrades_to_none(tmp_path):
    """兜底容错：缺 context / context 无 platform / 无 README / README 无表 /
    坏 JSON / 未知平台 → None（调用方保持空载荷退化，不 500）。"""
    from contest_generator.manifest import ModuleManifest, PinDeclaration, PlatformEntry

    readme = render_readme(
        PLATFORM_STM32,
        None,
        [
            ModuleManifest(
                slug="key",
                description="按键",
                platforms={
                    PLATFORM_STM32: PlatformEntry(
                        files=(),
                        pins=(
                            PinDeclaration(
                                id="KEY_START", type="gpio_in", default="PB3",
                                label="启动按键", required=True,
                            ),
                        ),
                    )
                },
            )
        ],
    )
    # 只有 README，无 context → None
    (tmp_path / README_FILENAME).write_text(readme, encoding="utf-8")
    assert read_wiring_snapshot_legacy(tmp_path) is None

    # context 无 platform / 坏 JSON → None
    (tmp_path / CONTEXT_FILENAME).write_text("{}", encoding="utf-8")
    assert read_wiring_snapshot_legacy(tmp_path) is None
    (tmp_path / CONTEXT_FILENAME).write_text("{oops", encoding="utf-8")
    assert read_wiring_snapshot_legacy(tmp_path) is None

    # platform + README 但无接线表 → None；未知平台 → None
    (tmp_path / CONTEXT_FILENAME).write_text(
        json.dumps({"platform": PLATFORM_STM32}), encoding="utf-8"
    )
    (tmp_path / README_FILENAME).write_text("## 无表格\n", encoding="utf-8")
    assert read_wiring_snapshot_legacy(tmp_path) is None
    (tmp_path / README_FILENAME).write_text(readme, encoding="utf-8")
    (tmp_path / CONTEXT_FILENAME).write_text(
        json.dumps({"platform": "unknown"}), encoding="utf-8"
    )
    assert read_wiring_snapshot_legacy(tmp_path) is None
