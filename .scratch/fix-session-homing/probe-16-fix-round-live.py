"""C4（fix-session-homing/01）真机探针：贴文本修复一次真实调用 + 事件流 + 回滚一致。

判据（机器可判部分，全程走产品真代码真端点）：
1. 事件流序：`/api/fix-errors` SSE 帧序 = parse_done → fix_start → apply_result* →
   llm_telemetry* → done（词表单源 events.py，脚本按 events.py 现读比对，不写死字符串）；
2. done 载荷字段：fixes 数组（file/line/status/reason）+ backup_id 非空；
3. 真修复：注入到 main.c 的那处错误被 AI 改掉（文件内容确实变了）；
4. 回滚一致：`POST /api/fix-errors/rollback {output_dir, backup_id}` → 文件内容
   逐字节回到修复前（sha256 比对）+ 返回 restored 列表非空。

用法：
    $env:PYTHONPATH='src'; python .scratch/fix-session-homing/probe-16-fix-round-live.py \
        --out-dir .scratch/real-run/out_2026C_stm32
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
import sys  # noqa: E402

sys.path.insert(0, str(REPO / "src"))
from contest_generator import events as ev  # noqa: E402

BASE = "http://127.0.0.1:8000"
OUT = REPO / ".scratch" / "fix-session-homing"

# 注入的编译报错（形态与真机 UV4 一致：路径(行号): error: #N: 消息）
INJECT_LINE = "    int unused_probe_c4 = 1;   /* C4 贴文本探针：未引用变量 */"
ERROR_TEXT = (
    "Rebuild target 'Target 1'\n"
    "compiling main.c...\n"
    '..\\main.c(23): warning:  #177-D: variable "unused_probe_c4" was declared '
    "but never referenced\n"
    '..\\main.c: 0 warnings, 1 error\n'
    '".\\Objects\\Project.axf" - 1 Error(s), 1 Warning(s).\n'
    "Target not created.\n"
    "Build Time Elapsed:  00:00:02\n"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sse(url: str, payload: dict, timeout: float = 1800.0):
    """消费 SSE，返回 (事件序, 终态kind, 终态data)。"""
    req = urllib.request.Request(
        BASE + url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    order: list[str] = []
    terminal = None
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
    return order, (terminal[0] if terminal else ""), (terminal[1] if terminal else {})


def post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"__http_error__": exc.code,
                "detail": exc.read().decode("utf-8", errors="replace")[:400]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=".scratch/real-run/out_2026C_stm32")
    parser.add_argument("--no-inject", action="store_true",
                        help="不注入假报错，直接用现成 main.c（真错误文本由 --error-file 给）")
    parser.add_argument("--error-file", default="")
    args = parser.parse_args()

    out_dir = (REPO / args.out_dir).resolve()
    main_c = out_dir / "main.c"
    if not main_c.is_file():
        print(f"✗ 缺 main.c：{main_c}")
        return 2

    lines: list[str] = []

    def note(t: str) -> None:
        print(t, flush=True)
        lines.append(t)

    before_text = main_c.read_text(encoding="utf-8")
    if args.no_inject:
        error_text = Path(args.error_file).read_text(encoding="utf-8") \
            if args.error_file else ERROR_TEXT
    else:
        src_lines = before_text.split("\n")
        idx = next(i for i, l in enumerate(src_lines) if l.startswith("int main("))
        src_lines.insert(idx + 2, INJECT_LINE)
        main_c.write_text("\n".join(src_lines), encoding="utf-8")
        error_text = ERROR_TEXT
        note(f"[注入] main.c 第 {idx + 3} 行插入未引用变量：{INJECT_LINE.strip()}")
    # 基线 = **注入之后、修复之前**的磁盘状态（回滚语义 = 恢复到修复写回前，
    # 首版把基线取在注入前，于是「回滚成功」被误判成 sha 不复原——脚本自身口径错）
    before_sha = sha(main_c)
    before_text = main_c.read_text(encoding="utf-8")
    note(f"[修复前] main.c sha256={before_sha[:16]}… 行数={len(before_text.splitlines())}")

    payload = {
        "output_dir": str(out_dir),
        "error_text": error_text,
        "platform": "stm32",
        "problem_text": "（C4 贴文本探针：修复中心贴文本模式）",
        "slugs": ["led"],
        "main_c": main_c.read_text(encoding="utf-8"),
    }
    note(f"[请求] POST /api/fix-errors output_dir={out_dir} error_text={len(error_text)} 字符")
    t0 = time.monotonic()
    order, kind, data = sse("/api/fix-errors", payload)
    dur = time.monotonic() - t0
    note(f"[事件流] {' → '.join(order)}（{dur:.1f}s）")
    note(f"[终态] {kind}")

    # 事件词表比对（events.py 现读，不写死）
    expected_prefix = [ev.EVENT_PARSE_DONE, ev.EVENT_FIX_START]
    ok_order = order[:2] == expected_prefix and order[-1] in (
        ev.EVENT_DONE, ev.EVENT_ERROR
    )
    note(f"  事件序判据（events.py 词表）：{'PASS' if ok_order else 'FAIL'}"
         f" 期望前缀 {expected_prefix}")

    fixes = data.get("fixes") or []
    backup_id = data.get("backup_id") or ""
    note(f"[done] fixes={len(fixes)} backup_id={backup_id!r} degraded={data.get('degraded')}")
    for f in fixes:
        note(f"   - {f.get('file')}:{f.get('line')} [{f.get('status')}] {f.get('reason')}")

    applied = [f for f in fixes if f.get("status") == "applied"]
    after_text = main_c.read_text(encoding="utf-8")
    changed = after_text != before_text
    note(f"[修复后] 文件内容变化={changed}；注入行是否仍在="
         f"{'unused_probe_c4' in after_text}")

    ok_fix = kind == ev.EVENT_DONE and bool(fixes) and bool(backup_id)
    note(f"  修复调用判据：{'PASS' if ok_fix else 'FAIL'}（done + fixes 非空 + backup_id 非空）")

    rollback = {}
    if backup_id:
        rollback = post("/api/fix-errors/rollback",
                        {"output_dir": str(out_dir), "backup_id": backup_id})
        note(f"[回滚] 响应：{json.dumps(rollback, ensure_ascii=False)[:300]}")
        restored = rollback.get("restored") or []
        back_sha = sha(main_c)
        ok_rb = bool(restored) and back_sha == before_sha
        note(f"  回滚一致判据：{'PASS' if ok_rb else 'FAIL'}"
             f"（restored={len(restored)} 项；sha 复原={back_sha == before_sha}）")
    else:
        ok_rb = False
        note("  回滚一致判据：FAIL（无 backup_id，无法回滚）")

    ok = ok_order and ok_fix and ok_rb
    note(f"\nC4 贴文本修复真机：{'PASS' if ok else 'FAIL'}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verify-16-fix-round-live.txt").write_text("\n".join(lines) + "\n",
                                                      encoding="utf-8")
    (OUT / "verify-16-fix-round-live.json").write_text(
        json.dumps({"event_order": order, "terminal": kind, "fixes": fixes,
                    "backup_id": backup_id, "rollback": rollback,
                    "file_changed": changed,
                    "sha_before": before_sha, "sha_after": sha(main_c),
                    "ok": {"order": ok_order, "fix": ok_fix, "rollback": ok_rb}},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print("--> 落盘 .scratch/fix-session-homing/verify-16-fix-round-live.{txt,json}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
