"""C3（fix-request-budget/01）真机探针：超大中文上下文打 /api/fix-errors 不再「请求体过大」。

背景（工单）：修复请求体有硬上限（`llm.MAX_REQUEST_BYTES = 128 * 1024`，按
json.dumps ensure_ascii 序列化字节计——中文 6 字节/字符）。旧口径按字符记账，
全中文最坏 ≈295KB 直接撞墙，报的就是「请求体过大」。修法是各段 wire 预算
（`budget.FIX_CONTEXT_TOTAL_BYTES = 23000` 等）+ 段级截断标注。

本探针构造**最坏形态输入**（全中文、每段都顶到上限）打真端点，判据：
① 不出现「请求体过大」；② 终态 done（不是 error）；③ 事件流以 parse_done →
fix_start 起头（与 events.py 词表同源比对）；④ 报告各段实际截断情况（有没
被点名 / dropped 清单）——超预算不发送要**点名**（防静默丢失）。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/fix-request-budget/probe-16-huge-context.py \
        --out-dir .scratch/real-run/out_2026C_stm32
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from contest_generator import events as ev  # noqa: E402

BASE = "http://127.0.0.1:8000"
OUT = REPO / ".scratch" / "fix-request-budget"

# 最坏形态各段：全中文、超长（远超各段上限，用于触发截断路径）
HUGE_CN_ERRORS = (
    "Rebuild target 'Target 1'\n"
    + "".join(
        f'..\\modules\\mod{i:02d}\\code\\impl{i:02d}.c({i}): error:  '
        f'#20: identifier "变量名{i:02d}" is undefined '
        f'（这是超长中文报错说明，用来把报错段顶到上限：'
        + "中文填充" * 40 + "）\n"
        for i in range(1, 61)
    )
    + '".\\Objects\\Project.axf" - 60 Error(s), 0 Warning(s).\n'
)
HUGE_CN_PROBLEM = "（赛题原文·超长中文）" + "本题要求设计并制作一套系统，能够完成测量、控制与显示功能。" * 260
HUGE_CN_MAIN = (
    "/* 超长中文注释 main.c：用来把 main.c 段顶到上限 */\n"
    + "".join(f"/* 第 {i} 行中文注释：填充填充填充填充填充填充填充填充 */\n"
              for i in range(1, 500))
    + "int main(void) { while (1) {} }\n"
)
HUGE_PREVIOUS = [
    {"file": f"modules/mod{i:02d}/code/impl{i:02d}.c", "line": i,
     "status": "applied",
     "reason": "（上一轮修复理由·超长中文）" + "理由填充" * 30}
    for i in range(1, 41)
]


def sse(url: str, payload: dict, timeout: float = 1800.0):
    req = urllib.request.Request(
        BASE + url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    order: list[str] = []
    terminal = None
    body_bytes = len(json.dumps(payload).encode("utf-8"))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        buf = ""
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buf:
                frame, buf = buf.split("\n\n", 1)
                etype = data = None
                for line in frame.splitlines():
                    if line.startswith("event:"):
                        etype = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                if not etype:
                    continue
                order.append(etype)
                if etype in (ev.EVENT_DONE, ev.EVENT_ERROR):
                    terminal = (etype, json.loads(data) if data else {})
    return body_bytes, order, (terminal or ("", {}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=".scratch/real-run/out_2026C_stm32")
    args = parser.parse_args()
    out_dir = (REPO / args.out_dir).resolve()
    lines: list[str] = []

    def note(t: str) -> None:
        print(t, flush=True)
        lines.append(t)

    payload = {
        "output_dir": str(out_dir),
        "error_text": HUGE_CN_ERRORS,
        "problem_text": HUGE_CN_PROBLEM,
        "platform": "stm32",
        "slugs": ["led"],
        "main_c": HUGE_CN_MAIN,
        "previous_fixes": HUGE_PREVIOUS,
    }
    seg = {k: len(json.dumps(v).encode("utf-8")) for k, v in payload.items()}
    note(f"[构造] 各段 wire 字节：{json.dumps(seg, ensure_ascii=False)}")
    note(f"[构造] 客户端请求体合计 ≈ {sum(seg.values())} 字节"
         f"（LLM 侧另有系统提示词 + JSON 壳）")

    t0 = time.monotonic()
    try:
        body_bytes, order, (kind, data) = sse("/api/fix-errors", payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        note(f"✗ HTTP {exc.code}：{body[:400]}")
        note("C3 超大上下文修复：FAIL（端点直接拒绝）")
        return 1
    dur = time.monotonic() - t0
    note(f"[事件流] {' → '.join(order)}（{dur:.1f}s）")
    note(f"[终态] {kind}")

    msg = json.dumps(data, ensure_ascii=False)
    too_big = "请求体过大" in msg
    checks = [
        ("未出现「请求体过大」", not too_big),
        ("终态 done（非 error）", kind == ev.EVENT_DONE),
        ("事件流以 parse_done → fix_start 起头",
         order[:2] == [ev.EVENT_PARSE_DONE, ev.EVENT_FIX_START]),
    ]
    fixes = data.get("fixes") or []
    note(f"[done] fixes={len(fixes)} degraded={data.get('degraded')} "
         f"file_count={data.get('file_count')} error_count={data.get('error_count')}")
    for f in fixes[:6]:
        note(f"   - {f.get('file')}:{f.get('line')} [{f.get('status')}] "
             f"{str(f.get('reason'))[:80]}")
    note(f"[截断可见性] 报告文本前 400 字：{msg[:400]}")
    ok = all(c for _, c in checks)
    note("")
    for name, cond in checks:
        note(("  ✓ " if cond else "  ✗ ") + name)
    note(f"\nC3 超大上下文修复真机：{'PASS' if ok else 'FAIL'}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verify-16-huge-context.txt").write_text("\n".join(lines) + "\n",
                                                    encoding="utf-8")
    (OUT / "verify-16-huge-context.json").write_text(json.dumps(
        {"segments": seg, "client_body_bytes": body_bytes, "event_order": order,
         "terminal": kind, "done": data, "duration_s": round(dur, 1),
         "checks": {n: bool(c) for n, c in checks}}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("--> 落盘 .scratch/fix-request-budget/verify-16-huge-context.{txt,json}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
