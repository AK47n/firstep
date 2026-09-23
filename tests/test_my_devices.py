# -*- coding: utf-8 -*-
"""「我的器件」（库外件）的定义形状与数据目录（工单 hwcheck-unknown-device/02）。

这一单**不生成任何代码**：先把"事实"这条路打通——学生手上那件不在模块库里的
器件，能有一条自己的记录（名称 / 总线 / 7 位地址 / 身份寄存器 / 期望值 / 备注），
存得住、列得出、改得了、删得掉。

判据重点（都是会静默出错的地方）：

① **落点**：`<配置目录>/hwcheck_devices/<id>/device.json`——目录即数据库，
   与产品库（`library/`，会 git 提交、随发布包分发）**物理分开**；
② **校验**：地址按 **7 位**存（0x08–0x77），寄存器 / 期望值是 8 位，
   `expect` 必须与 `register` 同行（没有寄存器就没有可比的东西）；
③ **id 撞库内 slug**：当场 400 点名要求改名——不静默加后缀（学生会以为自己
   填的 id 生效了，而工程里的 `mine_xxx` 是另一个东西）；
④ **件与平台无关**：同一件在两个平台上都能测，所以定义里**没有** platform 字段。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from contest_generator.entry_store import SLUG_PATTERN
from contest_generator.my_devices import (
    DEVICE_JSON,
    MATERIALS_DIRNAME,
    MY_DEVICES_DIRNAME,
    BUS_I2C,
    BUS_VOCABULARY,
    CustomDevice,
    MyDeviceError,
    address_forms,
    delete_device,
    list_devices,
    load_device,
    my_devices_dir,
    read_device_payload,
    save_device,
)

MOMENT = datetime(2026, 9, 22, 16, 40, 5)


def _device(**overrides) -> CustomDevice:
    """一件合法的自建件（i2c + 7 位地址），用关键字覆盖出各种非法形态。"""
    data = {
        "id": "mine_gyro",
        "name": "卖家给的六轴模块",
        "bus": BUS_I2C,
        "address": 0x68,
        "register": 0x75,
        "expect": 0x68,
        "notes": "卖家页写的 WHO_AM_I",
    }
    data.update(overrides)
    return CustomDevice(**data)


# ---------------------------------------------------------------------------
# 落点：目录即数据库，与产品库物理分开
# ---------------------------------------------------------------------------


def test_data_dir_is_the_configured_data_dir_not_the_product_library():
    """落点判据：`<配置目录>/hwcheck_devices`——**不进 `library/`**。

    用户自建的东西会 git 提交、随发布包分发到别人手上（那是产品库的语义），
    所以这条判据要钉在路径推导本身，而不是"小心别写错"。
    """
    data_dir = Path("/somewhere/.contest_generator")
    assert my_devices_dir(data_dir) == data_dir / MY_DEVICES_DIRNAME
    assert MY_DEVICES_DIRNAME == "hwcheck_devices"
    assert "library" not in MY_DEVICES_DIRNAME


def test_saving_never_touches_the_product_library(tmp_path):
    """反证落点：保存一件之后，库根（`library/`）一个字节都不该多。"""
    library = tmp_path / "library"
    (library / "modules").mkdir(parents=True)
    save_device(my_devices_dir(tmp_path / "data"), _device(), now=MOMENT)
    assert sorted(p.name for p in library.iterdir()) == ["modules"]
    assert not (library / "hwcheck_devices").exists()


def test_save_writes_device_json_and_reserves_materials_dir(tmp_path):
    """一件的定义落 `device.json`，资料副本目录 `materials/` 先预留出来。"""
    root = my_devices_dir(tmp_path / "data")
    saved = save_device(root, _device(), now=MOMENT)
    entry = root / "mine_gyro"
    assert saved.id == "mine_gyro"
    assert saved.created_at == "2026-09-22 16:40:05"
    assert (entry / DEVICE_JSON).is_file()
    assert (entry / MATERIALS_DIRNAME).is_dir()
    assert DEVICE_JSON == "device.json"


def test_roundtrip_keeps_every_fact_and_writes_utf8_json(tmp_path):
    """读回来 == 存进去（字段一个不少），地址以 **7 位整数**落盘。"""
    root = my_devices_dir(tmp_path / "data")
    saved = save_device(root, _device(), now=MOMENT)
    text = (root / "mine_gyro" / DEVICE_JSON).read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["address"] == 0x68, "地址按 7 位存（不是派生出的 8 位读写形式）"
    assert data["bus"] == "i2c"
    assert "卖家给的六轴模块" in text, "中文按原样写（ensure_ascii=False）"
    assert list_devices(root) == (saved,)


def test_saved_entry_dir_is_never_half_written(tmp_path):
    """落盘走临时目录 + 原子改名：条目目录**一出现就是完整的**。

    否则 `list_devices` 会在"目录已建、device.json 还没写"的窗口里看到
    一个读不出来的条目——那正是它按约定要大声失败的那种坏数据。
    """
    root = my_devices_dir(tmp_path / "data")
    save_device(root, _device(), now=MOMENT)
    names = sorted(p.name for p in root.iterdir())
    assert names == ["mine_gyro"], f"不该留下临时目录残渣：{names}"
    assert (root / "mine_gyro" / MATERIALS_DIRNAME).is_dir(), "原子改名要带上 materials/"


def test_created_at_is_kept_and_updated_at_moves_on_upsert(tmp_path):
    """按 id 幂等更新：`created_at` 不动、`updated_at` 前进（"这件我什么时候建的"）。"""
    root = my_devices_dir(tmp_path / "data")
    first = save_device(root, _device(), now=MOMENT)
    later = datetime(2026, 9, 23, 9, 0, 0)
    save_device(root, _device(name="改过的名字"), now=later)
    stored = load_device(root, "mine_gyro")
    assert len(list_devices(root)) == 1, "按 id 幂等更新：不新建第二份"
    assert stored.name == "改过的名字"
    assert stored.created_at == first.created_at, first
    assert stored.updated_at != stored.created_at


def test_list_is_newest_first_with_a_deterministic_tie_break(tmp_path):
    """列表顺序确定（updated_at 新 → 旧，同刻按 id 码点序）——页面刷新不跳行。"""
    root = my_devices_dir(tmp_path / "data")
    save_device(root, _device(id="mine_b"), now=MOMENT)
    save_device(root, _device(id="mine_a"), now=MOMENT)
    save_device(root, _device(id="mine_c"), now=datetime(2026, 9, 22, 17, 0, 0))
    assert [d.id for d in list_devices(root)] == ["mine_c", "mine_a", "mine_b"]


def test_empty_or_missing_dir_is_an_empty_list_not_an_error(tmp_path):
    """"一件都没建过"是正常状态（不是错误），坏条目则大声点名。"""
    root = my_devices_dir(tmp_path / "data")
    assert list_devices(root) == ()
    root.mkdir(parents=True)
    assert list_devices(root) == ()
    (root / "mine_broken").mkdir()
    with pytest.raises(MyDeviceError) as excinfo:
        list_devices(root)
    assert "mine_broken" in str(excinfo.value)


def test_delete_removes_the_whole_entry_and_says_so_when_missing(tmp_path):
    root = my_devices_dir(tmp_path / "data")
    save_device(root, _device(), now=MOMENT)
    delete_device(root, "mine_gyro")
    assert list_devices(root) == ()
    with pytest.raises(MyDeviceError) as excinfo:
        delete_device(root, "mine_gyro")
    assert "mine_gyro" in str(excinfo.value)


@pytest.mark.parametrize("bad_id", ["..", ".", "../..", "mine/../..", "", "mine_x/.."])
def test_delete_and_load_refuse_ids_outside_the_entry_grammar(tmp_path, bad_id):
    """**删 / 读也必须校验 id 文法**——这不是手滑防御，是路径穿越防线本身。

    `delete_device(root, "..")` 会被拼成 `root/..`（= 配置目录，里面装着 config.json /
    modules / masters）然后整棵 `rmtree` 掉。所以判据不能只活在保存那一路：
    **每个把 id 拼进路径的函数都得自己挡一次**（乱码 id 从路由 / 脚本 / 别处进来时
    没人替你挡，路由层的路径段语法也不保证拦得住 `..`）。
    """
    data = tmp_path / "data"
    data.mkdir()
    (data / "config.json").write_text("{}", encoding="utf-8")
    root = my_devices_dir(data)

    for call in (lambda: delete_device(root, bad_id), lambda: load_device(root, bad_id)):
        with pytest.raises(MyDeviceError):
            call()
    assert (data / "config.json").is_file(), "配置目录一个字节都不该被动到"
    assert data.is_dir()


# ---------------------------------------------------------------------------
# 校验：字段全是事实，没有一项推导
# ---------------------------------------------------------------------------


def test_bus_vocabulary_is_the_spec_list():
    """总线词表 = spec 那一串（多一个少一个都算漂移）。"""
    assert BUS_VOCABULARY == (
        "i2c", "spi", "uart", "onewire", "analog", "gpio", "other",
    )
    assert BUS_I2C == "i2c"


@pytest.mark.parametrize(
    "value",
    ["gyro", "mine", "mine gyro", "mine_陀螺仪", "MINE_gyro", "mine/../evil", "..", ""],
)
def test_id_must_be_a_mine_prefixed_slug(value):
    """id 文法 = `mine_` 前缀 + 库内 slug 同一文法（它同时是**目录名**）。

    目录名 = id，所以这里既挡手滑也挡路径穿越（`mine/../evil` 这种）。
    """
    with pytest.raises(MyDeviceError) as excinfo:
        _device(id=value).validated()
    assert "mine_" in str(excinfo.value)
    assert SLUG_PATTERN.fullmatch(value) is None or not value.startswith("mine_")


def test_valid_id_passes_and_its_shape_matches_the_store_key_grammar():
    assert _device().validated().id == "mine_gyro"
    assert SLUG_PATTERN.fullmatch("mine_gyro") is not None


@pytest.mark.parametrize("value", [None, "", "   "])
def test_name_is_required(value):
    with pytest.raises(MyDeviceError) as excinfo:
        _device(name=value).validated()
    assert "名称" in str(excinfo.value)


def test_name_has_a_length_cap():
    """名字是页面上一行字，超长粘贴不该把卡片撑爆。"""
    with pytest.raises(MyDeviceError) as excinfo:
        _device(name="长" * 200).validated()
    assert "名称" in str(excinfo.value)


def test_unknown_bus_is_rejected_with_the_vocabulary():
    with pytest.raises(MyDeviceError) as excinfo:
        _device(bus="can").validated()
    message = str(excinfo.value)
    assert "can" in message
    assert "i2c" in message and "other" in message


@pytest.mark.parametrize("value", [0x07, 0x78, 0x80, 0xD0, -1, 256])
def test_i2c_address_must_be_a_seven_bit_address(value):
    """手册里 0xD0 那种**8 位写法**在这里必须被拒——存的是 7 位（0x08–0x77）。"""
    with pytest.raises(MyDeviceError) as excinfo:
        _device(address=value).validated()
    assert "7 位" in str(excinfo.value) or "地址" in str(excinfo.value)


def test_i2c_requires_an_address():
    with pytest.raises(MyDeviceError) as excinfo:
        _device(address=None).validated()
    assert "地址" in str(excinfo.value)


def test_non_i2c_may_have_no_address_and_keeps_the_bus():
    """非 I2C 的陌生件这一版不生成探测程序，但**照样记得住**（清单与排障要用）。"""
    device = _device(bus="spi", address=None, register=None, expect=None)
    assert device.validated().address is None


def test_non_i2c_with_an_address_is_rejected():
    """地址是 I2C 总线的事实：挂到 spi 上就是填错了行。"""
    with pytest.raises(MyDeviceError) as excinfo:
        _device(bus="spi", address=0x68).validated()
    assert "i2c" in str(excinfo.value)


@pytest.mark.parametrize("value", [-1, 256, 0x1FF])
def test_register_and_expect_are_eight_bit(value):
    with pytest.raises(MyDeviceError):
        _device(register=value).validated()
    with pytest.raises(MyDeviceError):
        _device(expect=value).validated()


def test_expect_without_register_is_rejected():
    """"期望值"是"读哪个寄存器该读回什么"的一半——没有寄存器就没有可比的东西。"""
    with pytest.raises(MyDeviceError) as excinfo:
        _device(register=None, expect=0x68).validated()
    assert "寄存器" in str(excinfo.value)


def test_register_without_expect_is_fine_and_means_echo_only():
    """有寄存器、没期望值 = 只回显那一档（不是错误）。"""
    device = _device(expect=None).validated()
    assert device.register == 0x75 and device.expect is None
    assert device.echo_only is True
    assert _device(register=None, expect=None).validated().echo_only is False


def test_notes_are_optional_and_length_capped():
    assert _device(notes=None).validated().notes == ""
    with pytest.raises(MyDeviceError) as excinfo:
        _device(notes="备" * 5000).validated()
    assert "备注" in str(excinfo.value)


def test_validated_is_applied_exactly_once_across_the_save_path(tmp_path, monkeypatch):
    """全链路只校验**一遍**（判据在 `save_device` 一处，调用方不预先校验）。

    两道校验不是"更保险"：第二道白跑，且将来加一条规则时容易只改一处（改在
    `validated` 里的规则会漏掉路由那道、或反过来）。这条用例把"只跑一次"钉住
    —— 计数是行为判据，不是源码文本判据。
    """
    calls: list[dict] = []
    real = CustomDevice.validated

    def counting(self, **kwargs):
        calls.append(dict(kwargs))
        return real(self, **kwargs)

    monkeypatch.setattr(CustomDevice, "validated", counting)
    root = my_devices_dir(tmp_path / "data")
    save_device(root, _device(), library_slugs=("oled", "led"), now=MOMENT)
    assert len(calls) == 1, f"一次保存应只校验一遍，实际 {len(calls)} 遍：{calls}"
    assert calls[0].get("library_slugs") == ("oled", "led"), (
        "库内 slug 必须由 save_device 一处传进判据（绕开它就等于没查撞名）：" + repr(calls)
    )


def test_save_device_itself_rejects_a_library_clash(tmp_path):
    """撞库内 slug 的判据在 `save_device` 里就成立（不靠调用方记得先校验）。"""
    root = my_devices_dir(tmp_path / "data")
    with pytest.raises(MyDeviceError) as excinfo:
        save_device(root, _device(id="mine_oled"), library_slugs=("oled", "mine_oled"))
    assert "改名" in str(excinfo.value)
    assert not (root / "mine_oled").exists(), "被拒的定义一个字节都不该落盘"


# ---------------------------------------------------------------------------
# 地址双向显示（7 位 + 派生的 8 位读 / 写形式）
# ---------------------------------------------------------------------------


def test_address_forms_derives_read_and_write_from_the_seven_bit_value():
    """手册里 0x68 与 0xD0 两种写法都能对上——这是填错地址最常见的一处坑。"""
    assert address_forms(0x68) == {
        "address7": "0x68", "read8": "0xD1", "write8": "0xD0",
    }
    assert address_forms(0x76) == {
        "address7": "0x76", "read8": "0xED", "write8": "0xEC",
    }
    assert address_forms(0x08)["write8"] == "0x10"
    assert address_forms(0x77)["read8"] == "0xEF"


def test_address_forms_is_empty_without_an_address():
    assert address_forms(None) == {"address7": "", "read8": "", "write8": ""}


@pytest.mark.parametrize("value", [0x07, 0x78, -1])
def test_address_forms_refuses_values_outside_the_seven_bit_range(value):
    with pytest.raises(MyDeviceError):
        address_forms(value)


# ---------------------------------------------------------------------------
# 与库内 slug 的冲突（400 点名要求改名）／载荷形状
# ---------------------------------------------------------------------------


def test_id_clashing_with_a_library_slug_is_named_out_loud():
    """撞库内 slug：**当场点名要求改名**，不静默加后缀。

    静默加后缀是最坏的解法：学生填了 `mine_oled`、页面存成 `mine_oled_2`，
    过两天他照 `mine_oled` 找这件东西就找不到了。
    """
    with pytest.raises(MyDeviceError) as excinfo:
        _device(id="mine_oled").validated(library_slugs=("oled", "mine_oled", "led"))
    message = str(excinfo.value)
    assert "mine_oled" in message
    assert "改名" in message
    assert "库内" in message


def test_id_that_does_not_clash_is_accepted():
    device = _device().validated(library_slugs=("oled", "led", "i2c_probe"))
    assert device.id == "mine_gyro"


def test_payload_carries_facts_plus_the_derived_address_forms():
    """载荷 = 存下来的事实 + 派生的双向显示；**平台不在里面**（件与平台无关）。"""
    payload = read_device_payload(_device())
    assert payload["id"] == "mine_gyro"
    assert payload["name"] == "卖家给的六轴模块"
    assert payload["bus"] == "i2c"
    assert payload["bus_label"] == "I2C"
    assert payload["address"] == 0x68
    assert payload["address_forms"] == {
        "address7": "0x68", "read8": "0xD1", "write8": "0xD0",
    }
    assert payload["register"] == 0x75 and payload["expect"] == 0x68
    assert payload["echo_only"] is False
    assert payload["notes"] == "卖家页写的 WHO_AM_I"
    assert "platform" not in payload


def test_payload_of_an_spi_device_has_empty_address_forms():
    payload = read_device_payload(
        _device(bus="spi", address=None, register=None, expect=None)
    )
    assert payload["address"] is None
    assert payload["address_forms"]["address7"] == ""
    assert payload["bus_label"] == "SPI"
