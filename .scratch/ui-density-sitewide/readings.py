"""readings.py — 本批（hwcheck-hygiene）的**读数落盘**小工具：跑一条闸门命令，把完整输出
（剥 ANSI、UTF-8、带命令/时间/退出码头）写进本目录，并在控制台只回摘要行。

为什么要它（踩过的坑，见 `docs/agents/local-environment.md` 第 2 节）：
  · PowerShell 的 `>` / `Tee-Object` 写 **UTF-16LE**，`read` 工具当二进制拒读；
  · `node --test` 的摘要行在 **stderr** 且带 ANSI，用 PowerShell 抓 stdout 会一行都拿不到；
  · `node … | Select-Object -First N` 会掐断上游（SIGPIPE 把 node 带走，`test.after` 里的
    `server.stop()` 来不及跑 ⇒ 留下孤儿后端）。
本脚本一律 `subprocess.run(capture_output=True)` 收全量，所以三条都不沾。

用法：
    python .scratch/hwcheck-hygiene/readings.py <读数名> -- <命令…>
    python .scratch/hwcheck-hygiene/readings.py <读数名> --out-dir <目录> -- <命令…>
例：
    python .scratch/hwcheck-hygiene/readings.py probe-01-browser -- node --test --test-concurrency=1 "tests/browser/*.spec.mjs"
    python .scratch/hwcheck-hygiene/readings.py probe-01-js -- node --test "tests/js/*.test.mjs"
输出：`<目录>/<读数名>.txt`（**整份**输出 + 头部；默认目录 = 本脚本所在目录，
`--out-dir` 可指到别的批次目录——其他批次不必再抄一份这个脚本）。
"""

from __future__ import annotations

import datetime
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = pathlib.Path(__file__).resolve().parent
ANSI = re.compile(r"\x1b\[[0-9;]*m")
SUMMARY_PREFIX = ("ℹ tests", "ℹ suites", "ℹ pass", "ℹ fail", "ℹ cancelled", "ℹ skipped",
                  "ℹ todo", "ℹ duration_ms", "✖", "FAILED", "ERROR")


def main(argv: list[str]) -> int:
    out_dir = OUT_DIR
    if "--out-dir" in argv:
        at = argv.index("--out-dir")
        if at + 1 >= len(argv):
            print("--out-dir 后面要跟一个目录")
            return 2
        out_dir = pathlib.Path(argv[at + 1]).resolve()
        del argv[at:at + 2]
    if "--" not in argv or len(argv) < 3:
        print(__doc__)
        return 2
    split = argv.index("--")
    name = argv[0]
    cmd = argv[split + 1:]
    started = datetime.datetime.now().astimezone()
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    body = ANSI.sub("", (proc.stdout or "") + (proc.stderr or ""))
    # node 的 spec reporter 用 `\r` 做进度重写（"… ⟩ 名字"那种）——不归一的话整段会挤成一行
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    header = "\n".join([
        f"# 读数：{name}",
        f"# 命令：{' '.join(cmd)}",
        f"# 工作树：{REPO}",
        f"# 开始：{started.isoformat(timespec='seconds')}",
        f"# 退出码：{proc.returncode}",
        "",
    ])
    out = out_dir / f"{name}.txt"
    out.write_text(header + body, encoding="utf-8", newline="")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for line in body.splitlines():
        if line.strip().startswith(SUMMARY_PREFIX):
            print(line.rstrip())
    print(f"\n退出码 {proc.returncode}；完整读数已落盘：{out.relative_to(REPO).as_posix()}")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
