"""dump 门禁完整 400 文案（工单 pin-capacity/01 实施期取证件）。"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))
sys.stdout.reconfigure(encoding="utf-8")

import tests.test_generator as t  # noqa: E402
from contest_generator.generator import (  # noqa: E402
    GateContext,
    SyscfgPinConflictError,
    _check_syscfg_pin_conflicts,
)
from contest_generator.patchers import PLATFORM_MSPM0  # noqa: E402

tmp = REPO / ".scratch/pin-capacity/_tmp"
tmp.mkdir(parents=True, exist_ok=True)
cases = (
    ("2026h", t.REAL_2026H_MSPM0_SLUGS, GateContext(board=t._mspm0_board())),
    ("motor_servo", ("motor", "servo"), GateContext(board=t._mspm0_board())),
    ("motor_servo_noboard", ("motor", "servo"), GateContext()),
)
for label, slugs, ctx in cases:
    corpus = t._real_mspm0_syscfg_corpus(tmp)
    manifests = t._real_mspm0_manifests(*slugs)
    try:
        _check_syscfg_pin_conflicts(corpus, manifests, PLATFORM_MSPM0, ctx)
    except SyscfgPinConflictError as exc:
        text = str(exc)
        out = REPO / f".scratch/pin-capacity/msg-{label}.txt"
        out.write_text(text, encoding="utf-8")
        print(f"=== {label} → {out.relative_to(REPO)}")
        print(text)
        print()
