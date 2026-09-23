# -*- coding: utf-8 -*-
"""硬件检测：检测工程的**落点与回读**（工单 module-hwcheck/02）。

为什么单独一个文件：`hwcheck.py` 的模块边界是纯函数（字符串进 / 字符串出、
不碰盘），而「目录怎么命名 / 扫最近几次 / 把一个已有目录读回检测配置」是盘侧
的事，归 `hwcheck_store.py`。判据分开写，后来的人就不容易顺手往纯函数模块里
塞目录遍历。

判据重点（都是"不覆盖"与"不误认"这类会静默出错的地方）：
① 目录名形态 `hwcheck-<平台>-<YYYYMMDD-HHMMSS>`，同秒撞车顺延一秒；
② 只认得出自己人——赛题工程目录 / 名字像但平台瞎写 / 日期非法，一律不当检测工程；
③ 父目录不存在 = 大声报错（拼错路径不许静默建树），父目录为空 = 空列表（还没检测过是正常的）。
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from contest_generator.context_manifest import CONTEXT_MANIFEST_FILENAME
from contest_generator.hwcheck import HwCheckError
from contest_generator.hwcheck_store import (
    HWCHECK_DIR_PREFIX,
    hwcheck_output_name,
    list_hwcheck_projects,
    parse_hwcheck_dir_name,
    read_hwcheck_project,
    resolve_hwcheck_output_dir,
)
from contest_generator.platforms import PLATFORM_MSPM0, PLATFORM_STM32

# 固定时刻（判据里不出现"现在几点"——目录名逐字节可断言）
MOMENT = datetime(2026, 9, 20, 15, 30, 12)


def _write_manifest(project, **fields) -> None:
    project.mkdir(parents=True, exist_ok=True)
    data = {"version": 1, "platform": PLATFORM_STM32, "slugs": []}
    data.update(fields)
    (project / CONTEXT_MANIFEST_FILENAME).write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 目录命名：形态固定、同秒不覆盖
# ---------------------------------------------------------------------------


def test_output_name_shape_is_platform_plus_timestamp():
    assert hwcheck_output_name(PLATFORM_STM32, MOMENT) == "hwcheck-stm32-20260920-153012"
    assert hwcheck_output_name(PLATFORM_MSPM0, MOMENT) == "hwcheck-mspm0-20260920-153012"
    assert HWCHECK_DIR_PREFIX == "hwcheck"


def test_output_name_rejects_unknown_platform():
    """未知平台在拼目录名之前就大声失败（不许拼出 `hwcheck-nope-…` 这种脏目录）。"""
    with pytest.raises(HwCheckError) as excinfo:
        hwcheck_output_name("nope", MOMENT)
    message = str(excinfo.value)
    assert "nope" in message
    assert PLATFORM_STM32 in message and PLATFORM_MSPM0 in message


def test_parse_roundtrips_own_names():
    name = hwcheck_output_name(PLATFORM_MSPM0, MOMENT)
    assert parse_hwcheck_dir_name(name) == (PLATFORM_MSPM0, "2026-09-20 15:30:12")


@pytest.mark.parametrize(
    "name",
    [
        "2024H_Auto_Car_STM32",  # 赛题工程目录
        "hwcheck",  # 只有前缀
        "hwcheck-stm32",  # 缺时间戳
        "hwcheck-stm32-20260920",  # 缺时分秒
        "hwcheck-nope-20260920-153012",  # 平台不在词表
        "hwcheck-stm32-20261340-153012",  # 月份 13 非法
        "hwcheck-stm32-20260920-256000",  # 小时 25 非法
        "hwcheck-stm32-20260920-153012-2",  # 多余后缀（不是本形态）
        "hwcheck--20260920-153012",
        "",
    ],
)
def test_parse_rejects_foreign_and_malformed_names(name):
    assert parse_hwcheck_dir_name(name) is None


def test_resolve_returns_a_free_new_dir(tmp_path):
    candidate = resolve_hwcheck_output_dir(tmp_path, PLATFORM_STM32, now=MOMENT)
    assert candidate.parent == tmp_path
    assert candidate.name == "hwcheck-stm32-20260920-153012"
    assert not candidate.exists(), "选定阶段不落盘（落盘归生成内核）"


def test_resolve_never_overwrites_when_the_same_second_is_taken(tmp_path):
    """同一秒连点两次：第二次顺延一秒，绝不复用已存在的目录（票面硬要求）。"""
    first = resolve_hwcheck_output_dir(tmp_path, PLATFORM_STM32, now=MOMENT)
    first.mkdir()
    second = resolve_hwcheck_output_dir(tmp_path, PLATFORM_STM32, now=MOMENT)
    assert second != first
    assert second.name == "hwcheck-stm32-20260920-153013"
    assert not second.exists()


def test_resolve_rejects_missing_parent_directory(tmp_path):
    """父目录不存在 = 大声报错：用户把路径打错时，不许静默建出一棵树来。"""
    with pytest.raises(HwCheckError) as excinfo:
        resolve_hwcheck_output_dir(tmp_path / "打错的路径", PLATFORM_STM32, now=MOMENT)
    assert "父目录" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 扫最近几次：只认自己人、新→旧、文件不算
# ---------------------------------------------------------------------------


def test_list_scans_only_hwcheck_project_dirs_newest_first(tmp_path):
    (tmp_path / "2024H_Auto_Car_STM32").mkdir()  # 赛题工程：不进列表
    (tmp_path / "hwcheck-stm32-20260920-101010").mkdir()
    (tmp_path / "hwcheck-mspm0-20260920-120000").mkdir()
    (tmp_path / "hwcheck-stm32-20260920-120000").write_text("同名文件不是工程", encoding="utf-8")
    items = list_hwcheck_projects(tmp_path)
    assert [i.name for i in items] == [
        "hwcheck-mspm0-20260920-120000",
        "hwcheck-stm32-20260920-101010",
    ]
    assert items[0].platform == PLATFORM_MSPM0
    assert items[0].created_at == "2026-09-20 12:00:00"
    assert items[0].dir == tmp_path / "hwcheck-mspm0-20260920-120000"


def test_list_respects_limit_and_tolerates_a_missing_parent(tmp_path):
    for day in range(5):
        (tmp_path / f"hwcheck-stm32-2026092{day}-120000").mkdir()
    assert len(list_hwcheck_projects(tmp_path, limit=2)) == 2
    # 还没检测过 / 父目录还没建 = 空列表，不是错误（"一次都没跑过"是正常状态）
    assert list_hwcheck_projects(tmp_path / "nope") == ()


# ---------------------------------------------------------------------------
# 回读：把一个已有目录读回检测配置（kind 是判据）
# ---------------------------------------------------------------------------


def test_read_project_recovers_platform_and_channels_from_slugs(tmp_path):
    project = tmp_path / "hwcheck-stm32-20260920-153012"
    _write_manifest(
        project,
        kind="hwcheck",
        platform=PLATFORM_STM32,
        slugs=["led", "delay", "debug_uart", "oled"],
    )
    config = read_hwcheck_project(project)
    assert config.platform == PLATFORM_STM32
    assert config.debug_uart is True
    assert config.oled is True


def test_read_project_channel_flags_follow_the_module_set(tmp_path):
    serial_only = tmp_path / "hwcheck-mspm0-20260920-153012"
    _write_manifest(
        serial_only,
        kind="hwcheck",
        platform=PLATFORM_MSPM0,
        slugs=["led", "delay", "debug_uart"],
    )
    config = read_hwcheck_project(serial_only)
    assert (config.platform, config.debug_uart, config.oled) == (PLATFORM_MSPM0, True, False)

    lamp_only = tmp_path / "hwcheck-stm32-20260920-153013"
    _write_manifest(lamp_only, kind="hwcheck", slugs=["led", "delay"])
    config = read_hwcheck_project(lamp_only)
    assert (config.debug_uart, config.oled) == (False, False)


def test_read_project_rejects_a_contest_project(tmp_path):
    """赛题工程（kind=contest，或旧清单缺 kind）不许被当成检测工程——如实拒绝。"""
    contest = tmp_path / "2024H_Auto_Car_STM32"
    _write_manifest(contest, kind="contest", slugs=["led"])
    with pytest.raises(HwCheckError) as excinfo:
        read_hwcheck_project(contest)
    assert "检测工程" in str(excinfo.value)

    legacy = tmp_path / "legacy_project"
    _write_manifest(legacy, slugs=["led"])  # 旧清单：缺 kind = 赛题工程
    with pytest.raises(HwCheckError):
        read_hwcheck_project(legacy)


def test_read_project_rejects_a_dir_without_manifest(tmp_path):
    plain = tmp_path / "hwcheck-stm32-20260920-153012"
    plain.mkdir()
    with pytest.raises(HwCheckError) as excinfo:
        read_hwcheck_project(plain)
    assert "检测工程" in str(excinfo.value)


# ---------------------------------------------------------------------------
# 自建件归档与快照（工单 hwcheck-unknown-device/08）
# ---------------------------------------------------------------------------


def _make_device_entry(root, device_id="mine_gyro", *, draft=True) -> None:
    """数据目录里造一件自建件（定义 + 资料副本 + 抽取草稿）。"""
    from contest_generator.my_devices import DEVICE_JSON, save_device, CustomDevice

    save_device(root, CustomDevice(id=device_id, name="卖家给的六轴模块", bus="i2c", address=0x68))
    entry = root / device_id
    (entry / "materials" / "material.txt").write_text("I2C 地址：0x76", encoding="utf-8")
    if draft:
        (entry / "draft.json").write_text(
            json.dumps({"missing": ["register"], "missing_text": "手册里没找到"}),
            encoding="utf-8",
        )
    assert (entry / DEVICE_JSON).is_file()


def test_archive_copies_definition_material_and_draft_into_the_project(tmp_path):
    """生成后归档：定义快照 + 资料副本 + 抽取草稿原样进工程 `custom_device/<id>/`。"""
    from contest_generator.hwcheck_store import (
        CUSTOM_DEVICE_DIRNAME,
        archive_custom_devices,
    )
    from contest_generator.my_devices import my_devices_dir

    data_root = my_devices_dir(tmp_path / "data")
    _make_device_entry(data_root)
    project = tmp_path / "project"
    project.mkdir()

    archived = archive_custom_devices(project, tmp_path / "data", ("mine_gyro",))

    assert archived == ("mine_gyro",)
    snapshot = project / CUSTOM_DEVICE_DIRNAME / "mine_gyro"
    assert (snapshot / "device.json").is_file()
    assert (snapshot / "materials" / "material.txt").read_text(encoding="utf-8") == "I2C 地址：0x76"
    assert json.loads((snapshot / "draft.json").read_text(encoding="utf-8"))["missing"] == ["register"]


def test_archive_without_devices_creates_nothing(tmp_path):
    """一件自建件都没有 = 不建 `custom_device/` 目录（旧工程的工程树一个字节不多）。"""
    from contest_generator.hwcheck_store import archive_custom_devices

    project = tmp_path / "project"
    project.mkdir()
    archived = archive_custom_devices(project, tmp_path / "data", ())
    assert archived == ()
    assert not (project / "custom_device").exists(), "空归档不许留空目录"


def test_archive_is_loud_when_the_definition_has_vanished(tmp_path):
    """选中的自建件在数据目录里不见了 = 大声报错（工程里调着它的探测函数，
    归档却少了它的定义——静默跳过就是一次悄无声息的少档案）。"""
    from contest_generator.hwcheck_store import archive_custom_devices

    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(HwCheckError) as excinfo:
        archive_custom_devices(project, tmp_path / "data", ("mine_gone",))
    assert "mine_gone" in str(excinfo.value)


def test_read_custom_snapshots_returns_only_existing_entries(tmp_path):
    """读快照：有快照的回定义；没有的（08 之前的工程 / 归档缺失）不在字典里。"""
    from contest_generator.hwcheck_store import (
        CUSTOM_DEVICE_DIRNAME,
        read_custom_snapshots,
    )

    project = tmp_path / "project"
    _make_device_entry(project / CUSTOM_DEVICE_DIRNAME)

    snapshots = read_custom_snapshots(project, ("mine_gyro", "mine_gone"))

    assert set(snapshots) == {"mine_gyro"}
    assert snapshots["mine_gyro"].id == "mine_gyro"
    assert snapshots["mine_gyro"].address == 0x68
