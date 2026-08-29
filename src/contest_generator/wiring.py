"""接线快照与 wiring 校验（工单 task-wiring-diagram/01 + 02）。

生成工程时把「板定义 + 接线行」快照落盘（.contest_wiring.json）——后续任务
推进 / 接线图渲染一次读取全齐，不再二次请求。接线行与 README「引脚接线表」
**同源**（wiring_rows 与 readme._pin_rows 共用 readme._pin_row_items 单一
推导）：图上不会出现与表格矛盾的线。

数据纪律（项目铁律：AI 输出不可信）：wiring 字段（步骤报告里 AI 给出的
「本步接哪几根线」引用）只允许引用真实名字——pin ∈ 板定义引脚名集合，
target ∈ 模块端子名（声明 id / label）∪ 板载固定资源名 ∪ 引脚名自身；
逐条校验、非法丢弃，全部非法 = 空（前端走退化路径）。本模块与 LLM 层
解耦（llm.py 只在形状提取侧引用 WiringEntry），可纯函数直测。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .boards import Board, board_for_platform
from .readme import _pin_row_items, _row_role_text

# 接线快照输出文件名（生成写侧单源，generator 消费；任务推进读写同此）
WIRING_SNAPSHOT_FILENAME = ".contest_wiring.json"

# 快照 schema 版本：结构变动（字段增删）时 +1；读取侧版本不符按缺失处理
# （向前兼容退化，不 500）。
WIRING_SNAPSHOT_VERSION = 1


def wiring_rows(
    platform: str,
    manifests: Sequence,
    resolved_bindings: Sequence | None = None,
    instance_plans: Mapping[str, Sequence] | None = None,
) -> list[dict]:
    """接线行结构化列表（快照 rows 的原材料）。

    与 README 引脚接线表**同源**：内部调用 readme._pin_row_items（`_pin_rows`
    同一推导），逐条映射为 dict——role = 渲染文本（与 README 行逐字一致，
    供图/表一致性校验与展示）、role_id / role_label = 结构化端子名（供 wiring
    校验与端子匹配：声明 id / label 都是合法 target）；remark = 说明（类型 /
    必接）。未声明 pins 的模块不产生行（与 README 行为一致）。
    """
    return [
        {
            "slug": slug,
            "role": _row_role_text(role_id, role_label),
            "role_id": role_id,
            "role_label": role_label,
            "pin": pin,
            "remark": remark,
        }
        for slug, role_id, role_label, pin, remark in _pin_row_items(
            platform, manifests, resolved_bindings, instance_plans
        )
    ]


def build_wiring_snapshot(
    platform: str,
    board: Board,
    manifests: Sequence,
    resolved_bindings: Sequence | None = None,
    instance_plans: Mapping[str, Sequence] | None = None,
) -> dict:
    """快照内容 = {version, platform, board_id, board（板定义内嵌）, rows}。

    board = 板定义完整 dict（board.to_dict()，与 /api/boards 同平台板一致：
    引脚坐标 / 丝印 / 固定资源 / 地标）——运行期一次读取全齐，不再二次请求。
    rows = wiring_rows 推导（含多实例通道行）。
    """
    return {
        "version": WIRING_SNAPSHOT_VERSION,
        "platform": platform,
        "board_id": board.board_id,
        "board": board.to_dict(),
        "rows": wiring_rows(platform, manifests, resolved_bindings, instance_plans),
    }


def write_wiring_snapshot(output_dir: Path, snapshot: dict) -> Path:
    """快照写盘（工程根 .contest_wiring.json，纯新增文件不碰既有产物）。

    ensure_ascii=False + 尾部换行（与既有生成 JSON 文件写法一致）；写失败
    由生成流程既有 rmtree 兜底，生成原子性不破。
    """
    path = output_dir / WIRING_SNAPSHOT_FILENAME
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def read_wiring_snapshot(output_dir: Path | str) -> dict | None:
    """快照读取（条目级容错）：目录无文件 / 坏 JSON / 非对象 / 版本不符 → None。

    None = 走退化路径（旧目录无快照 = 向后兼容场景；前端空态/资源高亮）。
    绝不抛异常——与既有任务数据读取容错风格一致（不 500）。
    """
    path = Path(output_dir) / WIRING_SNAPSHOT_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("version") != WIRING_SNAPSHOT_VERSION:
        return None
    board = data.get("board")
    if not isinstance(board, dict) or not isinstance(data.get("rows"), list):
        return None
    return data


# ---------------------------------------------------------------------------
# wiring 字段（步骤报告协议扩展，工单 02）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WiringEntry:
    """一条「本步需要接的线」的结构化引用（AI 只给名字，图由数据决定）。

    pin = 板引脚名（板定义 pins name，含 3V3/GND/5V 供电类）；target =
    模块端子名（声明 id / label）∪ 板载固定资源名 ∪ 引脚名自身（板内直连）；
    note = 简短中文说明（如极性注意），可省略。
    """

    pin: str
    target: str
    note: str = ""

    def to_dict(self) -> dict:
        return {"pin": self.pin, "target": self.target, "note": self.note}


def parse_wiring_entries(raw: object) -> tuple[WiringEntry, ...]:
    """形状提取（与 LLM 层解耦的纯函数）：raw = JSON 反序列化后的 wiring 值。

    非 list / None → ()；逐条：非 dict / pin 或 target 非非空字符串 → 丢弃
    （机械形状坏，查表校验也无法救命——宁丢勿猜）；note 非字符串 → 空串。
    本函数只保形状，合法性由 filter_wiring_entries 查表判决。
    """
    if not isinstance(raw, list):
        return ()
    entries: list[WiringEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        pin = item.get("pin")
        target = item.get("target")
        if not isinstance(pin, str) or not pin.strip():
            continue
        if not isinstance(target, str) or not target.strip():
            continue
        note = item.get("note", "")
        if not isinstance(note, str):
            note = ""
        entries.append(
            WiringEntry(pin=pin.strip(), target=target.strip(), note=note.strip())
        )
    return tuple(entries)


def _board_pin_names(board: Mapping) -> frozenset[str]:
    """板定义 dict 的引脚名集合（含 power/gnd/reset 类，供电线用）。"""
    return frozenset(
        pin.get("name") for pin in (board.get("pins") or ())
        if isinstance(pin, Mapping) and isinstance(pin.get("name"), str)
    )


def _board_target_names(board: Mapping) -> frozenset[str]:
    """板侧合法 target：固定资源名 ∪ 引脚名自身（板内直连场景）。"""
    names: set[str] = set(_board_pin_names(board))
    for item in board.get("fixed") or ():
        name = item.get("name") if isinstance(item, Mapping) else ""
        if isinstance(name, str) and name:
            names.add(name)
    return frozenset(names)


def module_target_names(manifests: Sequence, platform: str) -> frozenset[str]:
    """模块侧合法 target：各 manifest 该平台 pins 声明的 id ∪ 非空 label。

    label 解析侧已归一（label==id → 空串），非空 label 即附注形态，与声明
    id 同为端子名（AI 引用哪个都放行）；跳过多平台条目不存在的平台。
    """
    names: set[str] = set()
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for decl in entry.pins:
            names.add(decl.id)
            if decl.label:
                names.add(decl.label)
    return frozenset(names)


def _row_target_names(rows: Sequence[Mapping]) -> set[str]:
    """快照行端子名集合：role_id ∪ 非空 role_label ∪ role（渲染合成串）。

    role = _row_role_text 合成文本（「KEY_START（启动按键）」式，channel 宏行
    label 为空 = role_id 本身）——wiring_summary_text 的角色列与接线图端子
    标签都显示这条合成串，AI 照抄展示值也能过校验（评审整改：白名单只收
    role_id/label 单独值会让照抄列名的合法引用被误滤，协议自我抵消）。
    """
    names: set[str] = set()
    for row in rows:
        role_id = row.get("role_id")
        if isinstance(role_id, str) and role_id:
            names.add(role_id)
        role_label = row.get("role_label")
        if isinstance(role_label, str) and role_label:
            names.add(role_label)
        role = row.get("role")
        if isinstance(role, str) and role:
            names.add(role)
    return names


def filter_wiring_entries(
    entries: Sequence[WiringEntry],
    pins: Sequence[str] | frozenset[str],
    targets: Sequence[str] | frozenset[str],
) -> tuple[WiringEntry, ...]:
    """查表校验（纯函数，可单测）：pin ∈ pins、target ∈ targets 才保留。

    逐条校验：非法条目丢弃、合法保留（保序）；剩余 0 条 = 空元组（前端按
    空处理 → 退化路径）。pins = 板引脚名集合；targets = 模块端子名 ∪ 固定
    资源名 ∪ 引脚名自身（上游拼好）。
    """
    pin_set = frozenset(pins)
    target_set = frozenset(targets)
    return tuple(
        entry
        for entry in entries
        if entry.pin in pin_set and entry.target in target_set
    )


def wiring_source(
    output_dir: Path | str, platform: str, manifests: Sequence
) -> tuple[Mapping | None, list[dict], frozenset[str], frozenset[str]]:
    """wiring 数据单源装配（一次快照读取）：(board, rows, pin_names, target_names)。

    评审整改（wiring_context 与 read_wiring_rows 各自 read_wiring_snapshot
    一次读盘 + rows/target 两处推导 = Duplicated Code）：合并单入口，快照读
    一次、推导一套。快照优先（rows = 落盘行、board = 内嵌板定义）；快照无 /
    板非 dict → 静态板定义（board_for_platform）+ wiring_rows 推导（名字集合
    一致，仍可作引用白名单，ticket 02 备注「快照优先、静态回退」）；板都取
    不到 → board=None、pin_names 空（上游按空 wiring 处理，走退化路径）。
    可能抛 BoardError——调用方（步骤报告降级路径）按「无校验数据」处理。
    """
    snapshot = read_wiring_snapshot(output_dir)
    if snapshot is not None:
        rows = snapshot.get("rows")
        if isinstance(rows, list):
            board = snapshot.get("board")
            if isinstance(board, dict):
                pins = _board_pin_names(board)
                targets = _row_target_names(rows)
                targets |= _board_target_names(board)
                return board, rows, pins, frozenset(targets)
            # 快照存在但板定义缺失：行仍可展示，板侧只从静态板取
            board = board_for_platform(platform).to_dict()
            pins = _board_pin_names(board)
            targets = _row_target_names(rows)
            targets |= _board_target_names(board)
            return board, rows, pins, frozenset(targets)
    board = board_for_platform(platform).to_dict()
    rows = wiring_rows(platform, manifests)
    pins = _board_pin_names(board)
    targets = set(module_target_names(manifests, platform))
    targets |= _board_target_names(board)
    return board, rows, pins, frozenset(targets)


def wiring_context(
    output_dir: Path | str, platform: str, manifests: Sequence
) -> tuple[Mapping | None, frozenset[str], frozenset[str]]:
    """wiring 校验数据源（wiring_source 的校验侧投影）。

    返回 (board, pin_names, target_names)：board = 板定义 dict（快照内嵌板
    定义；无快照 = board_for_platform 静态板；都取不到 = None——上游按空
    wiring 处理）；pin_names = 板引脚名集合（含 3V3/GND/5V 供电类）；
    target_names = 模块端子名（快照行 role_id/label/role；无快照 = manifests
    声明 id/label）∪ 板载固定资源名 ∪ 引脚名自身（板内直连）。可能抛异常
    （board_for_platform 的 BoardError）——调用方按「无校验数据」处理。
    """
    board, _rows, pins, targets = wiring_source(output_dir, platform, manifests)
    return board, pins, targets


def read_wiring_rows(
    output_dir: Path | str, manifests: Sequence, platform: str
) -> list[dict]:
    """接线行读取（wiring_source 的行侧投影）：快照行优先，无快照现场推导。

    快照行 = 落盘值（绑定覆盖 + 实例通道后的最终行，与 README 表同源）；
    无快照 = wiring_rows(manifests) 缺省绑定口径推导（名字集合一致，仍可作
    引用白名单）——校验数据源按 ticket 02 备注「快照优先、静态回退」。
    """
    _board, rows, _pins, _targets = wiring_source(output_dir, platform, manifests)
    return rows


def wiring_summary_text(rows: Sequence[Mapping], board: Mapping | None) -> str:
    """步骤报告 prompt 的「本工程接线数据」段（wiring 字段的引用白名单）。

    表行与 README 引脚接线表**同源**（rows = wiring_rows / 快照行）：AI 只能
    引用这里出现的引脚名与端子名；板载供电 / 固定资源行列出电源类引脚与板载
    资源名（这两类不在接线表内，供电 / 资源线仍可引用）。rows 为空 = 说明
    一句（AI 知道无可引用接线行）；board 缺失 = 只给表行。
    """
    lines = ["【本工程接线数据（wiring 字段只准引用这里的引脚名与端子名）】"]
    if rows:
        lines.append("| 模块 | 角色 | 引脚 | 说明 |")
        for row in rows:
            lines.append(
                f"| {row.get('slug', '')} | {row.get('role', '')} | "
                f"{row.get('pin', '')} | {row.get('remark', '')} |"
            )
    else:
        lines.append("（本工程接线表为空——无已声明引脚接线行）")
    if board:
        power_names: list[str] = []
        fixed_names: list[str] = []
        for pin in board.get("pins") or ():
            if not isinstance(pin, Mapping):
                continue
            name = pin.get("name")
            kind = pin.get("kind")
            if kind in ("power", "gnd", "reset") and isinstance(name, str) and name not in power_names:
                power_names.append(name)
        for item in board.get("fixed") or ():
            name = item.get("name") if isinstance(item, Mapping) else ""
            if isinstance(name, str) and name and name not in fixed_names:
                fixed_names.append(name)
        if power_names or fixed_names:
            lines.append(
                "板载供电/固定资源（wiring 可引用）："
                + "、".join([*power_names, *fixed_names])
            )
    return "\n".join(lines)
