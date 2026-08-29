"""接线快照（工单 task-wiring-diagram/01）：生成工程时把「板定义 + 接线行」
快照落盘（.contest_wiring.json）——后续任务推进 / 接线图渲染一次读取全齐，
不再二次请求。接线行与 README「引脚接线表」**同源**（wiring_rows 与
readme._pin_rows 共用 readme._pin_row_items 单一推导）：图上不会出现与
表格矛盾的线。

本模块只做快照生产侧（构建 / 写盘）；读取侧与 wiring 校验协议属工单 02/04
（相应函数按阻塞顺序补入本模块）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from .boards import Board
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
