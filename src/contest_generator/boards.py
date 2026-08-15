"""板级引脚配置：板定义数据模型与加载（单源）。

boards/*.json 是板图坐标 / 丝印 / 能力集的唯一数据源（spec 工单
pin-board-config/01）：生成门禁（工单 02 绑定校验）与前端板图（工单 03 SVG）
同吃这份数据——本模块只负责解析、加载、能力判定，不参与生成写侧。

能力 token 格式 = `<角色类型>[:<实例>]`，角色类型词表单源 = manifest.py 的
PIN_ROLE_TYPES（boards 与 manifest pins 声明共用，改词表只改那一处）。

能力集口径：
- stm32 = ml_libs 支持表（实例→引脚写死在功能库内：ml_uart 的 UART_1→
  PA9/10、ml_pwm 的 TIM2_CH1→PA0、ml_exti 的 EXTI_PA0~PC7、ml_adc 的
  Channel→引脚），GPIO 任意；软 I2C 已参数化（ADR 0011 工单 02：引脚宏迁
  pin_config.h，i2c_scl/i2c_sda token 去实例 = 任意 io 脚类型级）；
  enc 实例 = EXTI 线号（motor 的 EXTI2/EXTI4 handler 名绑定线号，v1 换线 =
  遗留候选）——门禁按"默认引脚能力 token 的实例"约束绑定引脚（如 MOTOR_A_ENC
  默认 PA2 → 能力 enc:2 → 只能绑到同线号 PB2）。
- mspm0 = 地猛星引脚图 PDF 每脚复用标注（sources/materials/2026_04_地猛星
  电赛控制题配套资料/00_立创·地猛星MSPM0G3507开发板引脚图.pdf，pdftotext
  提取）——真任意（芯片级过滤），GPIO/enc 任意 io 脚（编码器走 GPIO 组中断，
  无线号约束）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .entry_store import (
    StoreParseError,
    StoreReadError,
    StoreShapeError,
    read_json,
)
from .manifest import PIN_ROLE_TYPES
from .platforms import KNOWN_PLATFORMS

# 板定义文件目录（随包分发，板图/能力集唯一数据源）
BOARDS_DIR = Path(__file__).parent / "boards"

# 引脚种类：io = 可绑定（含板载共享注记），fixed = 排针上有但固定占用不可绑，
# 其余为排针上的供电/复位资源
PIN_KINDS = ("io", "power", "gnd", "reset", "fixed")

# 排针侧（板图坐标列）：left / right 对应双排排针
PIN_SIDES = ("left", "right")

# 板缘地标位置（区分板图上下）：top / bottom / left / right
PIN_EDGES = ("top", "bottom", "left", "right")


class BoardError(ValueError):
    """板定义文件解析或校验失败，message 中说明具体问题。"""


@dataclass(frozen=True)
class BoardPin:
    """板图上的一个排针位（引脚/电源/复位/固定资源）。"""

    name: str  # 引脚名（PA0 / 3V3 / GND / NRST / R）
    kind: str  # PIN_KINDS 之一
    x: int  # 板图网格列（0/1 = 左/右排针）
    y: int  # 板图网格行（0..19，自上而下）
    side: str  # left / right
    capabilities: tuple[str, ...] = ()  # 能力 token（<类型>[:<实例>]）
    notes: str = ""  # 板载共享/固定占用说明（前端展示）

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "x": self.x,
            "y": self.y,
            "side": self.side,
            "capabilities": list(self.capabilities),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class FixedResource:
    """排针之外的固定资源（SWD 排针 / 晶振 / BOOT / 板载器件）。

    occupies 里的引脚可以不在排针上（如 PD0/PD1 晶振），也可以与排针脚
    重叠（如 PC13 板载 LED 共用）——重叠 = 共享资源，绑定校验只认 pins。
    """

    name: str
    occupies: tuple[str, ...]
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "occupies": list(self.occupies), "note": self.note}


@dataclass(frozen=True)
class Landmark:
    """板缘物理地标（区分板图上下）：Type-C 插口 / 4P 弯针排针等。

    edge = 所在板缘（PIN_EDGES 之一）；kind = 地标形状（usb_typec /
    header_4p——前端渲染器只认认识的 kind，未知静默跳过，后端不拦）。
    """

    edge: str
    kind: str
    label: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"edge": self.edge, "kind": self.kind, "label": self.label, "note": self.note}


@dataclass(frozen=True)
class Board:
    """一块开发板的定义：板图坐标 + 能力集 + 固定资源 + 板缘地标。

    pins = 排针位全量有序列表（含 power/gnd 重名位——GND 在双排上多处出现）；
    pin_index = 绑定相关引脚（io/fixed/reset）按名索引（这些名字在板上唯一，
    绑定校验/前端候选高亮只认它）。
    """

    board_id: str
    name: str
    platform: str
    pins: tuple[BoardPin, ...] = ()
    pin_index: dict[str, BoardPin] = field(default_factory=dict)
    fixed: tuple[FixedResource, ...] = ()
    landmarks: tuple[Landmark, ...] = ()
    pcb_color: str = ""  # 板图 PCB 底色（俯视图观感）；空 = 前端默认令牌

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_id": self.board_id,
            "name": self.name,
            "platform": self.platform,
            "pins": [p.to_dict() for p in self.pins],
            "fixed": [f.to_dict() for f in self.fixed],
            "landmarks": [lm.to_dict() for lm in self.landmarks],
            "pcb_color": self.pcb_color,
        }


def board_pin(board: Board, name: str) -> BoardPin | None:
    """按名取排针引脚（绑定相关名字唯一）；不存在（板外脚如 PB4/PB5）返回 None。"""
    return board.pin_index.get(name)


def pin_supports(pin: BoardPin, role_type: str, instance: str = "") -> bool:
    """能力判定：引脚能力集是否含 `<role_type>[:<instance>]`。

    instance 空 = 只查类型（gpio_out/gpio_in/enc 无实例）；非空 = 必须同实例
    （如 uart_tx:UART_1 只认 UART_1）。生成门禁（工单 02）与前端候选高亮
    共用本判定——能力集的唯一消费口。
    """
    token = f"{role_type}:{instance}" if instance else role_type
    return token in pin.capabilities


def pin_capability_instances(pin: BoardPin, role_type: str) -> tuple[str, ...]:
    """引脚能力集中某类型的所有实例（去类型前缀，保序）。

    门禁用它从角色默认引脚推导所需实例（如 MOTOR_A_ENC 默认 PA2 的
    enc:2 → 绑定引脚必须也有 enc:2——v1 限同 EXTI 线号的机械实现）。
    """
    prefix = f"{role_type}:"
    return tuple(
        token[len(prefix) :] for token in pin.capabilities if token.startswith(prefix)
    )


def board_for_platform(platform: str, boards_dir: Path = BOARDS_DIR) -> Board:
    """平台 → 板定义（生成绑定校验 / 写侧用；每平台一块板）。

    该平台无板定义抛 BoardError（板 JSON 是包内静态数据，缺失 = 安装/发布
    坏 → 500 大声失败，与 ManifestError 同政策——errors.py 白名单留痕）。
    """
    for board in load_boards(boards_dir):
        if board.platform == platform:
            return board
    raise BoardError(f"平台 {platform!r} 没有板定义（boards/ 目录下无该平台 JSON）")


def load_boards(boards_dir: Path) -> list[Board]:
    """加载目录下全部 board JSON（按 board_id 排序）；损坏即抛 BoardError。"""
    if not boards_dir.is_dir():
        raise BoardError(f"板定义目录不存在：{boards_dir}")
    boards = [
        load_board(path)
        for path in sorted(boards_dir.glob("*.json"))
    ]
    ids = [b.board_id for b in boards]
    if len(set(ids)) != len(ids):
        raise BoardError(f"板定义 board_id 重复：{ids}")
    return boards


def load_board(path: Path) -> Board:
    """读取单个板定义文件（读盘 / 解析 / 形状走 entry_store 原语）。"""
    try:
        data = read_json(path.parent, path.name)
    except (StoreReadError, StoreParseError) as exc:
        raise BoardError(f"无法读取 {path}: {exc.error}") from exc
    except StoreShapeError:
        raise BoardError(f"{path} 必须是 JSON 对象") from None
    return _parse_board(data, path)


def _parse_board(data: dict[str, Any], path: Path) -> Board:
    if not isinstance(data, dict):
        raise BoardError(f"{path} 必须是 JSON 对象")
    board_id = _require(data, "board_id", str, path)
    name = _require(data, "name", str, path)
    platform = _require(data, "platform", str, path)
    if platform not in KNOWN_PLATFORMS:
        raise BoardError(
            f"{path} 的平台 {platform!r} 不在已知平台 {KNOWN_PLATFORMS} 内"
        )
    if path.stem != board_id:
        raise BoardError(
            f"{path} 的 board_id {board_id!r} 与文件名 {path.stem!r} 不一致"
        )

    raw_pins = _require(data, "pins", list, path)
    pins: list[BoardPin] = []
    pin_index: dict[str, BoardPin] = {}
    for item in raw_pins:
        pin = _parse_pin(item, path)
        pins.append(pin)
        # 绑定相关名字（io/fixed/reset）板上唯一；power/gnd 重名合法
        # （双排多处 GND/3V3/5V——绑定校验只认 io/fixed，不碰电源脚）。
        if pin.kind != "power" and pin.kind != "gnd":
            if pin.name in pin_index:
                raise BoardError(f"{path} 的绑定相关引脚重复：{pin.name}")
            pin_index[pin.name] = pin

    raw_fixed = data.get("fixed", [])
    if not isinstance(raw_fixed, list):
        raise BoardError(f"{path} 的 fixed 必须是数组")
    fixed_names: set[str] = set()
    fixed: list[FixedResource] = []
    for item in raw_fixed:
        resource = _parse_fixed(item, path)
        if resource.name in fixed_names:
            raise BoardError(f"{path} 的固定资源重复：{resource.name}")
        fixed_names.add(resource.name)
        fixed.append(resource)

    raw_landmarks = data.get("landmarks", [])
    if not isinstance(raw_landmarks, list):
        raise BoardError(f"{path} 的 landmarks 必须是数组")
    landmarks: list[Landmark] = []
    for item in raw_landmarks:
        landmarks.append(_parse_landmark(item, path))

    pcb_color = data.get("pcb_color", "")
    if not isinstance(pcb_color, str):
        raise BoardError(f"{path} 的 pcb_color 必须是字符串")

    return Board(
        board_id=board_id,
        name=name,
        platform=platform,
        pins=tuple(pins),
        pin_index=pin_index,
        fixed=tuple(fixed),
        landmarks=tuple(landmarks),
        pcb_color=pcb_color,
    )


def _parse_pin(item: Any, path: Path) -> BoardPin:
    if not isinstance(item, dict):
        raise BoardError(f"{path} 的 pins 条目必须是对象")
    name = _require(item, "name", str, path)
    kind = _require(item, "kind", str, path)
    if kind not in PIN_KINDS:
        raise BoardError(f"{path} 引脚 {name} 的 kind {kind!r} 不在 {PIN_KINDS} 内")
    x = _require(item, "x", int, path)
    y = _require(item, "y", int, path)
    side = _require(item, "side", str, path)
    if side not in PIN_SIDES:
        raise BoardError(f"{path} 引脚 {name} 的 side {side!r} 不在 {PIN_SIDES} 内")
    capabilities = _parse_capabilities(item, path, name)
    notes = item.get("notes", "")
    if not isinstance(notes, str):
        raise BoardError(f"{path} 引脚 {name} 的 notes 必须是字符串")
    return BoardPin(
        name=name,
        kind=kind,
        x=x,
        y=y,
        side=side,
        capabilities=capabilities,
        notes=notes,
    )


def _parse_capabilities(item: dict[str, Any], path: Path, name: str) -> tuple[str, ...]:
    raw = item.get("capabilities", [])
    if not isinstance(raw, list):
        raise BoardError(f"{path} 引脚 {name} 的 capabilities 必须是数组")
    tokens: list[str] = []
    for token in raw:
        if not isinstance(token, str) or not token:
            raise BoardError(f"{path} 引脚 {name} 的能力 token 必须是非空字符串")
        parts = token.split(":")
        if len(parts) > 2 or parts[0] not in PIN_ROLE_TYPES:
            raise BoardError(
                f"{path} 引脚 {name} 的能力 token {token!r} 非法"
                f"（类型须在 PIN_ROLE_TYPES 内，至多一个 :实例）"
            )
        if len(parts) == 2 and not parts[1]:
            raise BoardError(f"{path} 引脚 {name} 的能力 token {token!r} 实例为空")
        tokens.append(token)
    return tuple(tokens)


def _parse_landmark(item: Any, path: Path) -> Landmark:
    if not isinstance(item, dict):
        raise BoardError(f"{path} 的 landmarks 条目必须是对象")
    edge = _require(item, "edge", str, path)
    if edge not in PIN_EDGES:
        raise BoardError(f"{path} 板缘地标的 edge {edge!r} 不在 {PIN_EDGES} 内")
    kind = _require(item, "kind", str, path)
    if not kind:
        raise BoardError(f"{path} 板缘地标的 kind 不能为空")
    label = item.get("label", "")
    note = item.get("note", "")
    if not isinstance(label, str) or not isinstance(note, str):
        raise BoardError(f"{path} 板缘地标的 label/note 必须是字符串")
    return Landmark(edge=edge, kind=kind, label=label, note=note)


def _parse_fixed(item: Any, path: Path) -> FixedResource:
    if not isinstance(item, dict):
        raise BoardError(f"{path} 的 fixed 条目必须是对象")
    name = _require(item, "name", str, path)
    occupies_raw = _require(item, "occupies", list, path)
    occupies: list[str] = []
    for pin in occupies_raw:
        if not isinstance(pin, str) or not pin:
            raise BoardError(f"{path} 固定资源 {name} 的 occupies 必须是非空字符串")
        if pin in occupies:
            raise BoardError(f"{path} 固定资源 {name} 的 occupies 重复：{pin}")
        occupies.append(pin)
    note = item.get("note", "")
    if not isinstance(note, str):
        raise BoardError(f"{path} 固定资源 {name} 的 note 必须是字符串")
    return FixedResource(name=name, occupies=tuple(occupies), note=note)


def _require(data: dict[str, Any], key: str, expected_type: type, path: Path) -> Any:
    if key not in data:
        raise BoardError(f"{path} 缺少必填字段：{key}")
    value = data[key]
    if not isinstance(value, expected_type):
        raise BoardError(
            f"{path} 字段 {key} 必须是 {expected_type.__name__}"
        )
    return value
