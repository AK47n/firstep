"""诊断（临时）：全库累积态对拍暴露的 pair 类分歧——定性 + 定量 + 分类。

背景：工单 03 的「不做」条目记着「全库（84 模块 / 176 角色）枚举已实测暴露
188 条 `pair` 类既有分歧（as32/debug_uart/hc05/zigbee 族的 UART TX/RX 跨角色
成对）」——本脚本把那条线索复现出来，并按**后端拒因**分类，判定它是不是
`_check_paired_role_instances`（成对角色同实例）一类，以及是否只在特定种子下出现。

口径（与 tests/test_bindings_matrix.py 的累积态相逐字一致）：
- 模型放行 = `selectable` 命中 且 `constraint` 谓词求值通过（`_selectable`）；
- 真实提交 = 模型放行的一步改绑并入**累积** bindings（`collectBindings` 形态）；
- 判据 = 整份回验 `resolve_bindings`。

跑法：python .scratch/mspm0-slot-conflict/probe_full_library_accumulated.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import test_bindings_matrix as t  # noqa: E402
from contest_generator.boards import BOARDS_DIR, load_boards  # noqa: E402
from contest_generator.library import list_modules  # noqa: E402
from contest_generator.pin_bindings import (  # noqa: E402
    PinBindingError,
    build_bindings_matrix,
    resolve_bindings,
)

BOARDS = {b.platform: b for b in load_boards(BOARDS_DIR)}
LIBRARY_MODULES = t.LIBRARY_MODULES


def _reason(manifests, platform, board, bindings) -> str:
    try:
        resolve_bindings(manifests, platform, board, bindings)
        return "（后端收）"
    except PinBindingError as exc:
        return str(exc)


def _seed_defaults(manifests, platform, board):
    """种子 = 每个角色显式绑回自己的默认脚（`_default_pin_seed` 的多平台版）。"""
    seed: dict[str, str] = {}
    for manifest in manifests:
        entry = manifest.platforms.get(platform)
        if entry is None:
            continue
        for decl in entry.pins:
            if decl.default and board.pin_index.get(decl.default) is not None:
                seed[f"{manifest.slug}.{decl.id}"] = decl.default
    return seed


def _enumerate(manifests, platform, board, seed, limit=None):
    """逐步 × 全候选枚举假绿/假红。

    ⚠ 判据口径**不在这里重写**：直接吃 `tests/test_bindings_matrix.py` 的
    `_stepwise_false_greens`（`_selectable` / `_constraints` / 读取口径都单源在那边）
    ——脚本自己抄一份求值逻辑，就会和用例各漂各的（本轮 new 的 `constraints` 数组
    就是这么被抄漏的：脚本口径不更新 → 探针报的数与用例不一致）。
    """
    return t._stepwise_false_greens(manifests, platform, board, seed)


def _classify(reason: str) -> str:
    """后端拒因 → 门禁名。"""
    if "必须同实例，请成对绑定" in reason:
        return "pair（_check_paired_role_instances）"
    if "必须绑到同一端口" in reason:
        return "port（_check_mspm0_gpio_port_groups）"
    if "共用同一槽位" in reason:
        return "slot（_check_slot_conflicts）"
    if "两通道必须同实例" in reason:
        return "pwm-pair（_check_mspm0_pwm_channel_pairs）"
    if "不能担任该角色" in reason or "不支持角色类型" in reason:
        return "capability（能力层）"
    return "其他：" + reason[:60]


def main() -> None:
    library = list_modules(LIBRARY_MODULES)
    print(f"全库模块 {len(library)} 个")

    for platform in ("mspm0", "stm32"):
        board = BOARDS[platform]
        manifests = list_modules(LIBRARY_MODULES)
        roles = sum(
            1
            for m in manifests
            if m.platforms.get(platform) is not None
            for _ in m.platforms[platform].pins
        )
        seed = _seed_defaults(manifests, platform, board)
        print(f"\n================ {platform}：{roles} 角色，种子条目 {len(seed)} ================")
        for label, trial_seed in (("空种子", {}), ("默认脚种子", seed)):
            fg, fr, checked = _enumerate(manifests, platform, board, trial_seed)
            kinds = Counter(_classify(r) for _, _, r in fg)
            print(f"\n-- {label}：样本 {checked}，假绿 {len(fg)}，假红 {len(fr)}")
            for kind, count in kinds.most_common():
                print(f"     {count:4d}  {kind}")
            if fg:
                print("     例（前 8）：")
                for role, pin, reason in fg[:8]:
                    print(f"       {role} → {pin}：{reason[:110]}")
            if fr:
                print("     假红例（前 8）：", fr[:8])
            # 分歧涉及的模块族
            slugs = Counter(role.split(".", 1)[0] for role, _, _ in fg)
            print("     涉及模块：", dict(slugs.most_common(12)))


if __name__ == "__main__":
    main()
