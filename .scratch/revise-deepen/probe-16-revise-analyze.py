r"""B24（revise-deepen/05）真机段一：直接消费 `/api/revise/analyze` SSE + 回填结果。

为什么要拆两段（诚实边界写在最前）：
- 浏览器整链跑（页面点「分析影响」→ 等 SSE → 渲染）在本轮**三次尝试都在分析阶段挂住**
  （页面状态行停在「AI 影响分析中…」，之后 `Runtime.evaluate` 不再返回——
  与 `.scratch/code-editor-cdp-hang/` 记录过的「渲染进程无响应」同族现象）；
  而服务端遥测显示 `analyze_impact` 调用**成功**（12.7~25.6s，200）。
  即：**服务端链路是好的，卡的是浏览器侧的 SSE 消费/渲染这一段**，本轮不能靠它下结论。
- 本探针走服务端真链（真 LLM、真端点、真事件流），把 done 载荷落盘；
  浏览器侧的渲染另由 `.scratch/revise-deepen/verify-16-revise-render.mjs` 用**这份真实载荷**
  喂产品自己的渲染函数（`ui/generate-revise.js` 的导出面）取证——两段拼起来 = 完整判据，
  且每段都可单独复跑，不再被渲染进程挂死拖累。

用法：
    $env:PYTHONIOENCODING='utf-8'; python .scratch/revise-deepen/probe-16-revise-analyze.py
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
OUT = REPO / ".scratch" / "revise-deepen"

QA = (
    "问：小车的无线通信是否限定为已有的 Zigbee 模块？\n"
    "答：就用现有 Zigbee DL-20 透传（115200），不额外加别的无线模块。\n"
    "\n"
    "问：开锁动作是继电器还是只用 LED 指示？\n"
    "答：以 LED 指示为准，继电器只做演示联动，不做硬性要求。\n"
)


def sse(url: str, payload: dict, timeout: float = 1800.0):
    """消费 SSE：返回 (事件序, 每次事件载荷列表, 终态 kind, 终态 data)。"""
    req = urllib.request.Request(
        BASE + url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    order: list[str] = []
    payloads: list[dict] = []
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
                parsed = json.loads(data) if data else {}
                payloads.append({"event": etype, "data": parsed})
                if etype in (ev.EVENT_DONE, ev.EVENT_ERROR):
                    terminal = (etype, parsed)
    return order, payloads, (terminal[0] if terminal else ""), (terminal[1] if terminal else {})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=".scratch/real-run/out_2026C_stm32")
    parser.add_argument("--topic", default="2026C")
    args = parser.parse_args()
    out_dir = (REPO / args.out_dir).resolve()
    problem = (REPO / "library" / "topics" / args.topic / "topic.md").read_text(
        encoding="utf-8")

    lines: list[str] = []

    def note(t: str) -> None:
        print(t, flush=True)
        lines.append(t)

    qa_count = sum(1 for blk in QA.split("\n\n") if blk.strip())
    body = {
        "output_dir": str(out_dir),
        "new_qa_text": QA,
        "qa_count": qa_count,
        "problem_text": problem,   # 清单里题面为空 → 走「补题面」覆盖路径（原验收场景）
    }
    note(f"[请求] POST /api/revise/analyze  output_dir={out_dir}")
    note(f"[请求] 新 Q&A {qa_count} 段 / {len(QA)} 字符；补题面 {len(problem)} 字符")
    t0 = time.monotonic()
    order, payloads, kind, data = sse("/api/revise/analyze", body)
    dur = time.monotonic() - t0
    note(f"[事件流] {' → '.join(order)}（{dur:.1f}s）")
    note(f"[终态] {kind}")

    impacts = data.get("impacts") or []
    diff = data.get("diff") or {}
    warns = data.get("warnings") or []
    suggested = data.get("suggested_slugs") or []
    note(f"[done] impacts={len(impacts)} diff={{added:{len(diff.get('added') or [])},"
         f" removed:{len(diff.get('removed') or [])},"
         f" unchanged:{len(diff.get('unchanged') or [])}}}"
         f" warnings={len(warns)} suggested_slugs={len(suggested)}")
    for im in impacts[:5]:
        note(f"   - Q&A#{im.get('qa_index')} {str(im.get('reason'))[:100]}")
        if im.get("add") or im.get("remove"):
            note(f"     +{im.get('add')} −{im.get('remove')}")

    checks = [
        ("事件流含 impact_analyzing（分析阶段事件）",
         ev.EVENT_IMPACT_ANALYZING in order),
        ("事件流含 diff_ready（diff 就绪事件）", ev.EVENT_DIFF_READY in order),
        ("终态 done", kind == ev.EVENT_DONE),
        ("done 带 impacts（逐条影响结论）", len(impacts) >= 1),
        ("done 带 diff 三键（added/removed/unchanged）",
         all(k in diff for k in ("added", "removed", "unchanged"))),
        ("done 带 suggested_slugs（可编辑确认集）", isinstance(suggested, list)),
        ("每段 Q&A 都有影响结论（逐条不漏）", len(impacts) == qa_count),
    ]
    note("")
    ok = True
    for name, cond in checks:
        note(("  ✓ " if cond else "  ✗ ") + name)
        ok = ok and bool(cond)
    note(f"\nB24 段一（真机 SSE + 载荷形状）：{'PASS' if ok else 'FAIL'}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verify-16-revise-analyze.txt").write_text("\n".join(lines) + "\n",
                                                      encoding="utf-8")
    (OUT / "verify-16-revise-analyze.json").write_text(json.dumps(
        {"event_order": order, "events": payloads, "terminal": kind, "done": data,
         "duration_s": round(dur, 1),
         "checks": {n: bool(c) for n, c in checks}}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("--> 落盘 .scratch/revise-deepen/verify-16-revise-analyze.{txt,json}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
