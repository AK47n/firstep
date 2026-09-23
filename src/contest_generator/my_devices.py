"""「我的器件」（库外件）的**定义形状 + 数据目录**（工单 hwcheck-unknown-device/02）。

学生手上新到一件器件，它不在模块库里（卖家常卖的某个传感器模块、别人给的模块、
小厂模块）。这一模块让那件东西**在工具里存在**：一条自己的记录——名称 / 总线 /
7 位地址 / 身份寄存器 / 期望值 / 备注——存得住、列得出、改得了、删得掉。

**这一版不生成任何代码**（spec 把"渲染探测小节"留给工单 03–06）：先把"事实"这条
路打通。所以本模块只有三件事：

1. **定义形状与校验**（`CustomDevice` / `.validated()`）：字段全是**事实**，没有
   一项是推导——地址是 7 位（0x08–0x77），寄存器与期望值是 8 位，`expect` 必须与
   `register` 同行（没有寄存器就没有可比的东西）。
2. **数据目录**（`my_devices_dir` / `save_device` / `list_devices` / `delete_device`）：
   `<配置目录>/hwcheck_devices/<id>/device.json`，**目录即数据库**，`materials/`
   预留给用户提供的资料副本（工单 07 用）。
3. **载荷投影**（`read_device_payload`）：把事实 + 派生的地址双向显示拼成页面要的
   形状（7 位值 + 8 位读 / 写形式，手册里 0x68 与 0xD0 两种写法都能对上）。

## 两条刻意的边界

* **不进 `library/`**。那是产品库：写库动作自动 git 提交、随发布包分发到别人手上。
  用户自建的东西混进去就会被别人下载到，也不该出现在 `git status` 里。落点由
  `my_devices_dir(data_dir)` 单源推导，`data_dir` 由调用方给（HTTP 层的
  `AppContext.config_path.parent`，与 `updates/` / `cache/` 同一个数据目录）——
  本模块不 import `webapp`，因此可脱离 TestClient 直测。
* **件与平台无关**。同一件在两个平台上都能测（总线脚由平台决定，地址与寄存器是
  器件的事实），所以定义里**没有** `platform` 字段——切平台不会把器件弄丢。

## 时间戳与幂等更新

`created_at` / `updated_at` 由 `save_device` 在落盘那一刻写（`now` 可注入，判据里
不出现"现在几点"）。按 id 幂等更新时 **`created_at` 不动**——"这件我什么时候建的"
是一条真实的历史事实，改一次名字就把它冲掉是最容易让人不信赖数据的那种坏法。
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from .entry_store import (
    StoreError,
    read_json,
    write_json,
)

__all__ = [
    "BUS_I2C",
    "BUS_LABELS",
    "BUS_VOCABULARY",
    "DEVICE_ID_MAX_CHARS",
    "DEVICE_ID_PATTERN",
    "DEVICE_ID_PREFIX",
    "DEVICE_JSON",
    "DRAFT_FILENAME",
    "MATERIALS_DIRNAME",
    "MATERIAL_TEXT_FILENAME",
    "MY_DEVICES_DIRNAME",
    "NAME_MAX_CHARS",
    "NOTES_MAX_CHARS",
    "CustomDevice",
    "MyDeviceError",
    "address_forms",
    "delete_device",
    "list_devices",
    "load_device",
    "load_device_entry",
    "my_devices_dir",
    "read_device_payload",
    "save_device",
]


class MyDeviceError(Exception):
    """「我的器件」的形状 / 落点错误（登记 errors.py → 400 中文）。

    与 `HwCheckError` 分开一个类，是为了让"库外件的定义不合法"与"检测请求不合法"
    在错误映射表里各自可读；两者对用户是同一个出口（400 + 中文 message + 改一改
    再试），不新开第二条失败通道。
    """


# 数据目录名（= spec 的 `hwcheck_devices/<id>/`）：与 `updates/` / `cache/` 平级，
# 都在配置目录下——改名只改这一处。
MY_DEVICES_DIRNAME = "hwcheck_devices"

# 条目内文件名与资料目录名（工单 07 往 `materials/` 里放用户提供的资料副本）
DEVICE_JSON = "device.json"
MATERIALS_DIRNAME = "materials"

# 资料原文与抽取草稿（工单 08：保存时随定义落进条目，生成时一并归档进工程
# ——"过几天回头看，清楚知道当时凭什么填了那个地址"）
MATERIAL_TEXT_FILENAME = "material.txt"
DRAFT_FILENAME = "draft.json"

# id 前缀：库外件一眼看得出是"我的"（页面也按它区分两类东西）
DEVICE_ID_PREFIX = "mine_"

# id 文法（工单 12 收紧）：`mine_` 前缀 + **C 标识符可用字符**（字母数字下划线，
# **不含连字符**）。原因：id 会被原样拼进检测程序的 C 函数名（`hwcheck_custom` 的
# `CustomSection.func_name` = f"hwcheck_custom_{id}"），`mine_gyro-2` 拼出来是
# `hwcheck_custom_mine_gyro-2`——不是合法 C 标识符，整份工程编不过。这条文法因此
# **不再复用** `entry_store.SLUG_PATTERN`：那是库内键文法（`0-96-iic` 这类带连字符
# 的库内 slug 靠它），而库内 slug 永远不进 C 标识符——两条文法管两件事，判据各自
# 单源（"id 会拼进 C 标识符"的判据全仓库只有这里一处）。前缀以字母开头，所以
# 拼出的 `hwcheck_custom_*` 恒为合法 C 标识符，渲染侧不必再验一遍。
DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

# id 总长上限（工单 12 评审补的长度维）：小节函数是 `static`（内部链接），C99 对
# 内部标识符只保证前 63 个字符有效——`hwcheck_custom_` 前缀占 15 个，id 本体最长
# 48 个字符，再长就有"两个长 id 截断后同名 C 函数"的理论风险（那是票面自己点名
# 过的危害，字符集收紧关不掉它，上限才能）。
DEVICE_ID_MAX_CHARS = 48

# 总线词表（spec 定的那串）+ 展示名。词表外大声失败——`bus` 决定这一版能不能
# 生成探测程序（只有 i2c 能），放一个不认识的词进来等于把它当 I2C 猜。
BUS_I2C = "i2c"
BUS_VOCABULARY = (
    "i2c",
    "spi",
    "uart",
    "onewire",
    "analog",
    "gpio",
    "other",
)
BUS_LABELS: dict[str, str] = {
    "i2c": "I2C",
    "spi": "SPI",
    "uart": "UART",
    "onewire": "单总线",
    "analog": "模拟量",
    "gpio": "普通 IO（电平）",
    "other": "其它 / 不确定",
}

# 7 位地址的合法区间（I2C 规范：0x00–0x07 与 0x78–0x7F 是保留段）
ADDRESS7_MIN = 0x08
ADDRESS7_MAX = 0x77

# 字段长度上限：都是"页面上一行字"，超长粘贴不该把卡片撑爆。上限只防误操作，
# 不防恶意（这是本机单用户工具）——所以给得宽松，只在明显不对时拦。
NAME_MAX_CHARS = 60
NOTES_MAX_CHARS = 1000


@dataclass(frozen=True)
class CustomDevice:
    """一件库外器件的定义（**全是事实**，没有一项推导）。

    `address` 是 **7 位**地址（0x08–0x77）；页面上显示的 8 位读 / 写形式是派生的
    （`address_forms`），不落盘——落盘两份就是两个真相来源。
    """

    id: str
    name: str
    bus: str
    address: int | None = None
    register: int | None = None
    expect: int | None = None
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def echo_only(self) -> bool:
        """有身份寄存器、**没有**期望值 = 板上只回显读到的字节（不判 OK/FAIL）。

        这一档存在的意义（spec）：没有可比的东西就如实说"只回显"——把"读到一个数"
        当成"这件是好的"是这一版最想避免的误读。
        """
        return self.register is not None and self.expect is None

    def validated(self, *, library_slugs: Sequence[str] = ()) -> "CustomDevice":
        """校验并归一，返回**新的**对象（纯函数，不改原对象）。

        `library_slugs` = 库内 slug 全量（`library.list_modules` 的 slug 集）：
        id 撞上其中任何一个就点名要求改名。空 / 不传 = 不查（域层单测与"还没读库"
        的调用方用；路由侧一律传）。
        """
        device_id = _require_device_id(self.id)
        name = _require_text(self.name, "名称", NAME_MAX_CHARS)
        if self.bus not in BUS_VOCABULARY:
            known = "、".join(BUS_VOCABULARY)
            raise MyDeviceError(
                f"总线类型 {self.bus!r} 不在词表里（{known}）——"
                "不确定就选「其它 / 不确定」"
            )
        address = _optional_byte(self.address, "地址", 7)
        register = _optional_byte(self.register, "身份寄存器", 8)
        expect = _optional_byte(self.expect, "期望值", 8)
        notes = _optional_notes(self.notes)

        if self.bus == BUS_I2C:
            if address is None:
                raise MyDeviceError(
                    "I2C 器件必须填地址（手册里的 7 位地址，0x08–0x77）——"
                    "没有地址就没法 ping 它"
                )
            if not ADDRESS7_MIN <= address <= ADDRESS7_MAX:
                raise MyDeviceError(_address_range_message(address))
        elif address is not None:
            raise MyDeviceError(
                f"只有 i2c 才填地址（这件填的是 {self.bus!r}）："
                "地址是 I2C 总线的事实，挂到别的总线上就是填错了行"
            )
        if expect is not None and register is None:
            raise MyDeviceError(
                "填了期望值就必须填身份寄存器——"
                "「期望值」说的是「读哪个寄存器该读回什么」，没有寄存器就没有可比的东西"
            )
        if device_id in set(library_slugs):
            raise MyDeviceError(
                f"器件 id {device_id!r} 与库内模块同名（库内 slug 也叫这个）——"
                "请改名：换成你自己的名字（如 mine_" + device_id[len(DEVICE_ID_PREFIX):]
                + "_v2）再存，id 是这件东西在你工具里的唯一名字"
            )
        return replace(
            self,
            id=device_id,
            name=name,
            address=address,
            register=register,
            expect=expect,
            notes=notes,
        )

    def to_payload(self) -> dict[str, Any]:
        """落盘形态：只写事实（地址 7 位；派生的读写形式不落盘）。"""
        return {
            "id": self.id,
            "name": self.name,
            "bus": self.bus,
            "address": self.address,
            "register": self.register,
            "expect": self.expect,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def my_devices_dir(data_dir: Path | str) -> Path:
    """「我的器件」数据根 = `<配置目录>/hwcheck_devices`（**不是** `library/`）。

    `data_dir` 由调用方给（HTTP 层 = `AppContext.config_path.parent`，与
    `updates/` / `cache/` 同一个数据目录）。本模块不自己去找配置目录——那样就得
    import 配置 / 工具根，纯函数的那条边界就没了。
    """
    return Path(data_dir) / MY_DEVICES_DIRNAME


def save_device(
    root: Path | str,
    device: CustomDevice,
    *,
    library_slugs: Sequence[str] = (),
    now: datetime | None = None,
    material_text: str | None = None,
    draft: Mapping[str, Any] | None = None,
) -> CustomDevice:
    """落盘一件定义（按 id 幂等更新），返回**存下来的**那件（带时间戳）。

    校验**在落盘前**全部做完，且只在**这一处**做一遍：`library_slugs`（库内 slug
    全量）也在这里交给 `validated()`——调用方**不必也不能**先自己校验一次
    （两道校验的下场是第二道白跑、且将来加规则时容易只改一处，这条由
    `test_validated_is_applied_exactly_once_across_the_save_path` 钉住）。

    落盘走「临时目录 + 原子改名」，所以条目目录**一出现就是完整的**
    （`list_devices` 按约定对读不出来的条目大声失败，不该在写入窗口里看到自己
    刚建了一半的目录）。临时目录以 `.` 开头——`list_devices` 与
    `entry_store.iter_entry_dirs` 都跳过点开头的目录。

    `created_at` 语义：已存在且读得回 → **原样保留**；否则 = 本次写入时刻。

    **资料原文与抽取草稿**（工单 08，可选项）：`material_text`（用户贴 / 传的
    资料文本）与 `draft`（抽取草稿载荷）给了就随定义落进条目；**没给就原样
    保留旧的那份**——改个名字不该抹掉"当时凭什么填了那个地址"，这是归档的
    源头（生成时 `hwcheck_store.archive_custom_devices` 把它们一并复制进工程）。
    `material_text` 给了但**只有空白** = 视同没给（两态选一：不存在"给了空白
    却把旧资料悄悄删掉"的第三态）。
    """
    if material_text is not None and not material_text.strip():
        material_text = None
    moment = now or datetime.now()
    stamp = moment.strftime("%Y-%m-%d %H:%M:%S")
    checked = device.validated(library_slugs=library_slugs)
    root_dir = Path(root)
    root_dir.mkdir(parents=True, exist_ok=True)
    entry_dir = root_dir / checked.id
    saved = replace(
        checked,
        created_at=_existing_created_at(entry_dir) or stamp,
        updated_at=stamp,
    )
    staging = root_dir / f".{checked.id}.tmp"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    try:
        (staging / MATERIALS_DIRNAME).mkdir(parents=True)
        write_json(staging, DEVICE_JSON, saved.to_payload())
        if entry_dir.exists():
            _carry_over_provenance(entry_dir, staging, material_text, draft)
            shutil.rmtree(entry_dir)
        if material_text is not None and material_text.strip():
            (staging / MATERIALS_DIRNAME / MATERIAL_TEXT_FILENAME).write_text(
                material_text, encoding="utf-8"
            )
        if draft is not None:
            (staging / DRAFT_FILENAME).write_text(
                json.dumps(dict(draft), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        staging.rename(entry_dir)
    except Exception:
        # 清理失败不掩盖原始错误（照 entry_store.discard_entry_dirs 的口径）
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return saved


def _carry_over_provenance(
    entry_dir: Path,
    staging: Path,
    material_text: str | None,
    draft: Mapping[str, Any] | None,
) -> None:
    """旧条目的资料副本与抽取草稿**原样带进**新条目（没给新的就保留旧的）。

    幂等保存每次都从空暂存目录重写整份条目——不带这一步，改一次名字就会把
    上次的资料与草稿冲掉（归档的源头悄悄丢一半）。
    """
    old_materials = entry_dir / MATERIALS_DIRNAME
    if old_materials.is_dir():
        for item in old_materials.iterdir():
            if item.name == MATERIAL_TEXT_FILENAME and material_text is not None:
                continue  # 这次给了新的资料原文，覆盖旧的
            target = staging / MATERIALS_DIRNAME / item.name
            if target.exists():
                continue
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
    old_draft = entry_dir / DRAFT_FILENAME
    if old_draft.is_file() and draft is None:
        shutil.copy2(old_draft, staging / DRAFT_FILENAME)


def load_device(root: Path | str, device_id: str) -> CustomDevice:
    """读一件定义（不存在 / 坏 JSON / 形状非法都大声点名该条目）。

    **id 先过文法**（`_entry_dir`）：id 是拼进路径的那一段，`..` 这种必须在这里
    就挡掉——读一次不该有写副作用，但"读到了什么"同样不该由 caller 保证。
    """
    return _load_entry(_entry_dir(root, device_id))


def load_device_entry(entry_dir: Path | str) -> CustomDevice:
    """读一个**条目目录**（`hwcheck_store.read_custom_snapshots` 读工程内快照
    与 `load_device` 读数据目录共用同一条解析 + 校验——快照也是"定义"，坏快照
    同样大声点名，不许悄悄变成半截事实）。"""
    return _load_entry(Path(entry_dir))


def list_devices(root: Path | str) -> tuple[CustomDevice, ...]:
    """数据根下的全部定义：`updated_at` 新 → 旧，同刻按 id 码点序（确定性）。

    数据根不存在 / 空 = 空元组（"一件都没建过"是正常状态，不是错误）。
    **坏条目大声失败**（`_load_entry`）：静默跳过会让一件再也读不出来的器件
    从页面上消失，而用户以为它还在。
    """
    directory = Path(root)
    if not directory.is_dir():
        return ()
    devices = [
        _load_entry(entry)
        for entry in directory.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    ]
    # 两级排序：先按 id 升序（确定性兜底），再按 updated_at 降序（主序稳定）
    devices.sort(key=lambda d: d.id)
    devices.sort(key=lambda d: d.updated_at, reverse=True)
    return tuple(devices)


def delete_device(root: Path | str, device_id: str) -> None:
    """删掉一件（连同 `materials/` 里那份资料副本）；查无此条大声失败。

    **id 先过文法**（`_entry_dir`）——这条是路径穿越的正面防线，不是手滑防御：
    `Path(root) / ".."` 就是配置目录（里面装着 config.json / modules / masters），
    直接 `rmtree` 会把整个数据目录删掉。id 从路由段进来时，路由层的路径段语法
    **不保证**拦得住 `..`（`[^/]+` 是能匹配它的），所以每个把 id 拼进路径的函数
    自己挡一次。对照先例：`library.delete_module` 也是先校验 slug 再删。
    """
    shutil.rmtree(_entry_dir(root, device_id))


def _entry_dir(root: Path | str, device_id: str) -> Path:
    """id → 条目目录（**唯一的拼接点**：文法校验与拼接绑在一起，谁也绕不过）。

    所有把 id 变成路径的调用都必须经这里：校验漏一处就是一个 `rmtree` 级的洞。
    "不存在"也在这一处报（读 / 删两条路的文案本来就该是同一句）。
    """
    entry_dir = Path(root) / _require_device_id(device_id)
    if not entry_dir.is_dir():
        raise MyDeviceError(f"没有这件器件：{device_id}")
    return entry_dir


def read_device_payload(device: CustomDevice) -> dict[str, Any]:
    """页面载荷：存下来的事实 + 派生的地址双向显示。

    派生显示（`address_forms`）放在这里而不是落盘：手册里 7 位与 8 位两种写法都
    常见，页面必须两种都给出来（这是填错地址最常见的一处坑），但**真相只有一个**
    ——存下来的 7 位值。
    """
    return {
        "id": device.id,
        "name": device.name,
        "bus": device.bus,
        "bus_label": BUS_LABELS.get(device.bus, device.bus),
        "address": device.address,
        "address_forms": address_forms(device.address),
        "register": device.register,
        "expect": device.expect,
        "echo_only": device.echo_only,
        "notes": device.notes,
        "created_at": device.created_at,
        "updated_at": device.updated_at,
    }


def address_forms(address: int | None) -> dict[str, str]:
    """7 位地址 → {7 位, 8 位读, 8 位写} 三种写法（十六进制，两位大写）。

    8 位形式 = 7 位左移一位 + 读写位（读 1 / 写 0）——手册里的 0x68 与 0xD0
    因此能对上。`None`（非 I2C 件）= 三个空串（不编一个 0x00 出来）。
    """
    if address is None:
        return {"address7": "", "read8": "", "write8": ""}
    value = _optional_byte(address, "地址", 7)
    if value is None or not ADDRESS7_MIN <= value <= ADDRESS7_MAX:
        raise MyDeviceError(_address_range_message(address))
    return {
        "address7": f"0x{value:02X}",
        "read8": f"0x{(value << 1 | 0x01):02X}",
        "write8": f"0x{(value << 1):02X}",
    }


# ---------------------------------------------------------------------------
# 内部：字段级校验（判据都在这里，上面只负责编排）
# ---------------------------------------------------------------------------


def _require_device_id(value: Any) -> str:
    """id 文法 = `mine_` 前缀 + C 标识符可用字符（`DEVICE_ID_PATTERN`，工单 12）。

    目录名 = id，所以这里既挡手滑（空格 / 中文 / 大写 M 开头）也挡路径穿越
    （`mine/../evil` 这种）。**不复用** `entry_store.SLUG_PATTERN`（02 时的决定，
    12 推翻）：那是库内键文法、允许连字符，而 id 要拼进 C 函数名——判据见
    `DEVICE_ID_PATTERN` 那条注释，全仓库只有这一处。
    """
    text = value if isinstance(value, str) else ""
    if len(text) > DEVICE_ID_MAX_CHARS:
        raise MyDeviceError(
            f"器件 id 太长了（{len(text)} 字符，上限 {DEVICE_ID_MAX_CHARS}）——"
            "它是检测程序里 C 函数名的一段（hwcheck_custom_<id>），"
            "换短一点的名字"
        )
    if (
        not text.startswith(DEVICE_ID_PREFIX)
        or len(text) <= len(DEVICE_ID_PREFIX)
        or DEVICE_ID_PATTERN.fullmatch(text) is None
    ):
        raise MyDeviceError(
            f"器件 id {value!r} 不合法：必须是 {DEVICE_ID_PREFIX!r} 开头、"
            "后面只跟字母数字下划线，不能用连字符——id 会原样拼进检测程序的 "
            "C 函数名，连字符拼出来的不是合法 C 标识符（例：mine_gyro）。"
            "带着连字符的旧条目请删掉后用新 id 重建"
        )
    return text

def _require_text(value: Any, what: str, limit: int) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise MyDeviceError(f"请填{what}（必填）")
    if len(text) > limit:
        raise MyDeviceError(f"{what}太长了（{len(text)} 字，上限 {limit} 字）——请精简一下")
    return text


def _optional_byte(value: Any, what: str, bits: int) -> int | None:
    """可选字节字段：None / 空串 = 没填；其余必须是 [0, 2**bits) 的整数。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise MyDeviceError(f"{what}必须是整数（十六进制写法如 0x68 也行）：{value!r}")
    limit = 1 << bits
    if not 0 <= value < limit:
        if bits == 7:
            raise MyDeviceError(_address_range_message(value))
        raise MyDeviceError(f"{what}必须是 8 位（0x00–0xFF）：0x{value:X}")
    return value


def _optional_notes(value: Any) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if len(text) > NOTES_MAX_CHARS:
        raise MyDeviceError(
            f"备注太长了（{len(text)} 字，上限 {NOTES_MAX_CHARS} 字）——"
            "备注会进上板清单与 AI 排障上下文，写关键的那几句就够了"
        )
    return text


def _address_range_message(value: Any) -> str:
    """地址越界的文案：**点明 7 位与 8 位的关系**（这是填错地址最常见的一处坑）。"""
    shown = f"0x{value:02X}" if isinstance(value, int) and not isinstance(value, bool) else repr(value)
    return (
        f"地址 {shown} 不是 7 位地址（合法区间 0x{ADDRESS7_MIN:02X}–0x{ADDRESS7_MAX:02X}）——"
        "手册里常见的是 8 位写法（0xD0 这种），填的时候请填它的 7 位形式（0x68）"
    )


# ---------------------------------------------------------------------------
# 内部：条目读写（统一走 entry_store 原语；域错误在这里翻译）
# ---------------------------------------------------------------------------


def _load_entry(entry_dir: Path) -> CustomDevice:
    """读一个条目目录 → CustomDevice（坏 JSON / 形状非法都点名该条目）。"""
    try:
        data = read_json(entry_dir, DEVICE_JSON)
    except StoreError as exc:
        raise MyDeviceError(
            f"这件器件读不出来（{entry_dir.name}）：{exc} —— "
            f"要么手工修好 {entry_dir / DEVICE_JSON}，要么删掉这个条目重填"
        ) from exc
    return _device_from_payload(data, entry_dir.name)


def _device_from_payload(data: dict[str, Any], entry_name: str) -> CustomDevice:
    """载荷 → CustomDevice（校验 + 归一；错一律点名是哪个条目）。

    读侧也跑一遍 `validated()`：手工编辑过的 `device.json`（或旧版本写的形状）
    不该悄悄变成一件"半截事实"的器件混进检测计划。
    """
    try:
        device = CustomDevice(
            id=_str_field(data, "id"),
            name=_str_field(data, "name"),
            bus=_str_field(data, "bus"),
            address=data.get("address"),
            register=data.get("register"),
            expect=data.get("expect"),
            notes=data.get("notes") or "",
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        ).validated()
    except MyDeviceError as exc:
        raise MyDeviceError(
            f"这件器件的定义不合法（{entry_name}）：{exc} —— "
            f"要么手工修好 hwcheck_devices/{entry_name}/{DEVICE_JSON}，"
            "要么删掉这个条目重填"
        ) from exc
    if device.id != entry_name:
        raise MyDeviceError(
            f"条目目录名与里面的 id 不一致（目录 {entry_name!r} / 文件 {device.id!r}）："
            "目录名就是这件东西的身份，请把两边改成一致"
        )
    return device


def _str_field(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise MyDeviceError(f"缺少必填字段：{key}")
    return value


def _existing_created_at(entry_dir: Path) -> str:
    """已存在条目的 `created_at`（读不回来 / 还没有 = 空串 → 调用方用当前时刻）。

    刻意**不让坏条目挡住保存**：用户就是想改一件坏掉的器件，读不回来也该能存进去
    （覆盖成好的）；坏条目的"大声失败"发生在 `list_devices`（浏览侧）。
    """
    path = entry_dir / DEVICE_JSON
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    value = data.get("created_at") if isinstance(data, dict) else None
    return value if isinstance(value, str) else ""
