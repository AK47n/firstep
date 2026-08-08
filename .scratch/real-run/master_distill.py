"""母版重提炼真机运行：scan → distill(SSE) → confirm，一次跑完。

用法：python master_distill.py [--skip-distill] [--confirm-only]
依赖：服务在 127.0.0.1:8000 运行。
"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
PROJECTS = ["C:/Users/luoji/Desktop/2026C", "C:/Users/luoji/Desktop/2021F/21F"]
PLATFORM = "stm32"
REPORT_FILE = Path(__file__).parent / "distill_report.json"


def post(url: str, payload: dict, stream: bool = False):
    req = urllib.request.Request(
        BASE + url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(req)


def scan() -> None:
    with post("/api/masters/scan", {"project_dirs": PROJECTS}) as r:
        for s in json.loads(r.read()):
            print(f"[scan] {s['name']}: {s['platform']} {len(s['files'])} 文件 "
                  f"config={s['config_summary']}")


def distill() -> dict:
    print("[distill] 开始（SSE），约 10-20 分钟……")
    with post("/api/masters/distill", {"platform": PLATFORM, "project_dirs": PROJECTS}) as r:
        buf = ""
        report = None
        while True:
            chunk = r.read(4096)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buf:
                frame, buf = buf.split("\n\n", 1)
                event = data = None
                for line in frame.splitlines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:].strip()
                if not data:
                    continue
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if event == "progress":
                    p = payload
                    print(f"  [进度] {p.get('stage','?')} {p.get('current',0)}/{p.get('total','?')}")
                elif event == "done":
                    report = payload
                    print(f"[done] 报告 {len(json.dumps(payload))} 字符")
                elif event == "error":
                    print(f"[error] {payload.get('message')}")
                    sys.exit(1)
        if report is None:
            print("[!] 流结束但没有 done 事件")
            sys.exit(2)
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[distill] 报告已存 {REPORT_FILE}")
    return report


def confirm() -> None:
    report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    report["project_dirs"] = PROJECTS
    payload = {k: v for k, v in report.items()}
    print(f"[confirm] 提交（{len(json.dumps(payload))} 字符）……")
    with post("/api/masters/confirm", payload) as r:
        print("[confirm] OK:", json.loads(r.read()))


if __name__ == "__main__":
    skip_distill = "--skip-distill" in sys.argv
    confirm_only = "--confirm-only" in sys.argv
    if not confirm_only:
        scan()
    if not skip_distill:
        distill()
    confirm()
