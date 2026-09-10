r"""A11（cli-init-compile-timeout/01）真机探针：首编超时即停。

口径（挂账单 A11）：临时调小 `compile_runner.COMPILE_TIMEOUT_SECONDS` 验证
「首编超时即停」——超时是**终端状态**（`CompileRun.exit_code=None` +
`timed_out=True`），半截输出不作编译报错喂第 1 轮 LLM。

本探针的诚实性边界（写清楚，别拔高）：
- 期望的「真实调用次数 = 0」：超时即停 ⇒ 一次 `/api/fix-errors` 都不该发。
  探针统计真实发生的修复调用次数（`fix_stream` 包装计数），断言 == 0；
  且把「跑了多久」落盘——只有几十毫秒量级才说明它没等到 LLM。
- 超时注入方式：monkeypatch `generate_check.collect_build_log`，在调用真实
  `compile_runner.collect_build_log` 时显式传 `timeout=1.0`（生产默认
  `COMPILE_TIMEOUT_SECONDS=180.0` 不动、仓库文件不改）——被测路径仍是
  check_topic 的真实代码（uv4_build → collect_build_log → CompileRun）。
- dry-run 对照（`--dry-run-timeout`）：同一探针只做「被测构建在 1s 内能不能
  跑完」的判定。若 dry-run 本身 > 1s（例如全量重建 ~4s），则超时是必然。
  dry-run 若 < 1s（增量/极快构建），超时不必然发生 —— 那时改小阈值重跑，
  否则本项验证不成立（如实报告，不硬判 PASS）。

用法：
    $env:PYTHONPATH='src'; python .scratch/cli-init-compile-timeout/probe-16-first-build-timeout.py \
        --out-dir .scratch/real-run/out_2026C_stm32 --platform stm32 --timeout 1.0
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / ".scratch" / "real-run"))

import generate_check as gc  # noqa: E402
from contest_generator import compile_runner  # noqa: E402

EVIDENCE: list[str] = []


def note(line: str) -> None:
    print(line, flush=True)
    EVIDENCE.append(line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--platform", default="stm32", choices=("stm32", "mspm0"))
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--dry-run-timeout", action="store_true")
    parser.add_argument("--evidence", default="")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    if not out_dir.is_dir():
        note(f"✗ 输出目录不存在：{out_dir}")
        return 2

    real_collect = compile_runner.collect_build_log
    budgets: list[float] = []

    def patched_collect(platform, root, *, uv4=None, make=None,
                        timeout=compile_runner.COMPILE_TIMEOUT_SECONDS):
        # 期望值注入点：把生产默认换成探针阈值（生产常量本身不动）
        budgets.append(args.timeout)
        return real_collect(platform, root, uv4=uv4, make=make,
                            timeout=args.timeout)

    gc.collect_build_log = patched_collect

    if args.dry_run_timeout:
        # 对照：直接量一次「不超时」的真实构建耗时（不注入阈值）
        started = time.monotonic()
        build = real_collect(
            args.platform, out_dir,
            uv4=compile_runner.find_uv4("") if args.platform == "stm32" else None,
            make=compile_runner.find_make("") if args.platform == "mspm0" else None,
            timeout=600.0,
        )
        dur = time.monotonic() - started
        note(f"[dry-run] {args.platform} 全量重建耗时 {dur:.2f}s "
             f"（exit={build.run.exit_code} timed_out={build.run.timed_out}）")
        note(f"[dry-run] 阈值 {args.timeout}s ⇒ 超时{'必然发生' if dur > args.timeout else '不必然（需更小阈值）'}")
        return 0

    # 修复调用计数（真实网络调用才计数；停住就不该有任何一次）
    real_fix_stream = gc.fix_stream
    fix_calls = {"n": 0}

    def counting_fix_stream(payload):  # noqa: ANN001
        fix_calls["n"] += 1
        note(f"  !! 发生第 {fix_calls['n']} 次真实 /api/fix-errors 调用（不该有）")
        return real_fix_stream(payload)

    gc.fix_stream = counting_fix_stream

    # 骨架段要真实调用（每次分钟级）——本探针只验「首编超时即停」，
    # 用 --reuse-skeleton 语义：直接喂一份已落盘 main.c，跳过 /api/skeleton。
    main_c = (out_dir / "main.c").read_text(encoding="utf-8", errors="replace")
    real_post = gc.post

    def fake_post(url: str, payload: dict) -> dict:  # noqa: ANN001
        if url == "/api/skeleton":
            note(f"  [骨架] 探针跳过真实调用，复用盘上 main.c（{len(main_c)} 字符）")
            return {"main_c": main_c, "intercepted": []}
        return real_post(url, payload)

    gc.post = fake_post

    note(f"[A11] 阈值注入 collect_build_log timeout={args.timeout}s"
         f"（生产默认 {compile_runner.COMPILE_TIMEOUT_SECONDS}s 未改）")
    note(f"[A11] 输出目录 {out_dir} / 平台 {args.platform}")
    started = time.monotonic()
    try:
        passed, summary, raw, timed_out = (
            gc.uv4_build(out_dir) if args.platform == "stm32"
            else gc.gmake_build(out_dir)
        )
    except Exception as exc:  # noqa: BLE001 - 探针把异常当断言失败报告
        note(f"✗ 构建调用抛异常：{type(exc).__name__}: {exc}")
        return 1
    dur = time.monotonic() - started

    note(f"[A11] uv4_build/gmake_build 返回：passed={passed} timed_out={timed_out}")
    note(f"[A11] 摘要：{summary}")
    note(f"[A11] 原样输出长度 {len(raw)} 字符；构建墙钟 {dur:.2f}s")

    fixes = fix_calls["n"]
    checks = [
        ("注入生效（collect_build_log 收到探针阈值）", budgets == [args.timeout]),
        ("timed_out=True", timed_out is True),
        ("passed 非 True（超时不算通过）", passed is not True),
        ("真实修复调用 0 次（超时即停，未喂第 1 轮）", fixes == 0),
        (f"未等到 LLM（墙钟 {dur:.2f}s < 30s）", dur < 30.0),
    ]
    ok = True
    for name, cond in checks:
        note(("  ✓ " if cond else "  ✗ ") + name)
        ok = ok and bool(cond)
    note(f"A11 首编超时即停：{'PASS' if ok else 'FAIL'}")
    if args.evidence:
        Path(args.evidence).write_text("\n".join(EVIDENCE) + "\n", encoding="utf-8")
        print(f"--> 证据已落盘 {args.evidence}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
