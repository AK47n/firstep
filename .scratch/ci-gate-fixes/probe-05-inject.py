# probe-05-inject.py — 工单 ci-gate-fixes/05：给 webapp.py **临时**注入落点日志，
# 把"红那一轮"的 register / bye / 退出调度**在服务端**逐事件记下来。
#
# 为什么必须这么做（读数是这么逼出来的）：
#   · probe-05-diag3 的现场：第 8 个文档 document-start 后 **21ms** 就发出 fetch register，
#     但 resource timing 记的是 `status 0 / size 0`（连接被拒），同时页面 30 秒超时；
#     而 Node 侧独立通道在 **+4ms 还是 200**、**+218ms 就连不上**。
#   · 也就是说：**register 那一发"发出去即失败"**，浏览器侧看不出是"没到服务端"还是
#     "到了没被处理"。只能到服务端去看。
#
# 注入的东西（全部走 stderr，被夹具的 FIRSTEP_BROWSER_SERVER_LOG 捕获）：
#   [P5] tabs_register / tabs_bye（进锁前后）/ schedule_exit 布防 / 宽限到点真退出
# 探针跑完**逐字节复原**（bytes 读写；本文件的 webapp.py 是 CRLF，锚点按 LF 写、
# 注入前后换算——文本模式会把 CRLF 归一成 LF，造成"复原复核"假红，这一条是本仓既有纪律）。
#
# 跑法：python .scratch/ci-gate-fixes/probe-05-inject.py [--rounds=8] [--suite=12]
import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = REPO / "src" / "contest_generator" / "webapp.py"

# 注入片段：**全部单引号 f-string**，避开与外层双引号的引号冲突。
REG_RECV = (
    '        print(f"[P5] {time.time():.3f} register 收到 tab={tab_id[:8]}"'
    ' f" epoch={payload.get(\'epoch\')} 注册表={len(context.tab_registry)}",'
    " file=sys.stderr, flush=True)"
)
REG_DONE = (
    '        print(f"[P5] {time.time():.3f} register 已登记"'
    ' f" 注册表={len(context.tab_registry)}", file=sys.stderr, flush=True)'
)
BYE_LINE = (
    '        _empty = context.tab_registry.unregister('
    'tab_id, _optional_number(payload, "epoch"))\n'
    '        print(f"[P5] {time.time():.3f} bye 收到 tab={tab_id[:8]}"'
    ' f" epoch={payload.get(\'epoch\')} 注销后空={_empty}",'
    " file=sys.stderr, flush=True)"
)
SCHED = (
    '    _armed = registry.arm_exit()\n'
    '    print(f"[P5] {time.time():.3f} schedule_exit 布防={_armed}",'
    " file=sys.stderr, flush=True)"
)
DELAYED = (
    '    def delayed() -> None:\n'
    '        deadline = time.monotonic() + _EXIT_GRACE\n'
    '        while True:\n'
    '            now = time.monotonic()\n'
    '            if now < deadline:\n'
    '                time.sleep(deadline - now)\n'
    '            _due = registry.exit_if_due(_EXIT, _EXIT_PAGE_GRACE)\n'
    '            _page = registry.page_requested_at()\n'
    '            print(f"[P5] {time.time():.3f} 醒 真退出={_due} page_at={_page:.3f}",'
    " file=sys.stderr, flush=True)\n"
    '            if _due:\n'
    '                return\n'
    '            if _page <= 0 or _page + _EXIT_PAGE_GRACE <= time.monotonic():\n'
    '                return                       # 判据没放行又不是页面在来：不再空转\n'
    '            deadline = _page + _EXIT_PAGE_GRACE'
)

# 退出判据的内部读数（`[P5D]`）：红的那一轮里"页面请求到底记没记上、布防时刻谁前谁后"，
# 只有这里看得见（浏览器侧看不到服务端状态，access log 也只有顺序没有时刻）。
DUE_OLD = (
    '        with self._lock:\n'
    '            if not self._exit_armed or self._tabs:\n'
    '                return False\n'
    '            if page_grace > 0 and self._page_at >= time.monotonic() - page_grace:'
)
DUE_NEW = (
    '        with self._lock:\n'
    '            print(f"[P5D] {time.time():.3f} exit_if_due 布防={self._exit_armed}"'
    ' f" 标签={len(self._tabs)} page_at={self._page_at:.3f}"'
    ' f" page_grace={page_grace}",'
    " file=sys.stderr, flush=True)\n"
    '            if not self._exit_armed or self._tabs:\n'
    '                return False\n'
    '            if page_grace > 0 and self._page_at >= time.monotonic() - page_grace:'
)
PAGE_OLD = (
    '        with self._lock:\n'
    '            self._page_at = time.monotonic()'
)
PAGE_NEW = (
    '        with self._lock:\n'
    '            self._page_at = time.monotonic()\n'
    '            print(f"[P5D] {time.time():.3f} 页面请求已记 page_at={self._page_at:.3f}"'
    ' f" 布防={self._exit_armed}",'
    " file=sys.stderr, flush=True)"
)

ANCHORS = [
    (
        '        context.tab_registry.register(tab_id, _optional_number(payload, "epoch"))',
        REG_RECV + "\n"
        '        context.tab_registry.register(tab_id, _optional_number(payload, "epoch"))\n'
        + REG_DONE,
    ),
    (
        '        if context.tab_registry.unregister(tab_id, _optional_number(payload, "epoch")):\n'
        '            _schedule_exit_if_idle(context.tab_registry)',
        BYE_LINE + "\n"
        '        if _empty:\n'
        '            _schedule_exit_if_idle(context.tab_registry)',
    ),
    (
        '    if not registry.arm_exit():\n        return',
        SCHED + '\n    if not _armed:\n        return',
    ),
    (
        # 当前（已修）形态的 delayed()：循环体里那两步记一下（醒的时刻 + 判据结果 + page_at）
        '    def delayed() -> None:\n'
        '        deadline = armed_at + _EXIT_GRACE\n'
        '        while True:\n'
        '            now = time.monotonic()\n'
        '            if now < deadline:\n'
        '                time.sleep(deadline - now)\n'
        '            if registry.exit_if_due(_EXIT, _EXIT_PAGE_GRACE):\n'
        '                return\n'
        '            page_at = registry.page_requested_at()\n'
        '            if page_at <= armed_at:\n'
        '                return                       # 没有"布防之后才到的页面"：不再空转（至多一轮）\n'
        '            if page_at + _EXIT_PAGE_GRACE <= time.monotonic():\n'
        '                return\n'
        '            deadline = page_at + _EXIT_PAGE_GRACE',
        DELAYED,
    ),
    (DUE_OLD, DUE_NEW),
    (PAGE_OLD, PAGE_NEW),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--suite", type=int, default=12)
    ap.add_argument("--out", default=str(Path(__file__).with_suffix(".txt")))
    args = ap.parse_args()

    original = TARGET.read_bytes()
    before = digest(TARGET)
    # 本工作树 webapp.py 是 **CRLF**（.gitattributes 只声明 .githooks / *.bat，
    # core.autocrlf=true 的检出形态）——锚点按 LF 写，注入前后各自换算回原形态。
    crlf = original.count(b"\r\n") > 0
    text = original.decode("utf-8").replace("\r\n", "\n")
    if "[P5]" in text:
        print("探针前置干净性检查失败：webapp.py 里已经有 [P5] 注入（上次被强杀了？）")
        return 2
    for old, new in ANCHORS:
        if old not in text:
            print("找不到注入锚点（产品改动过？）：\n" + old[:120])
            return 2
        text = text.replace(old, new, 1)
    if crlf:
        text = text.replace("\n", "\r\n")
    out_path = Path(args.out)
    log = out_path.with_name(out_path.stem + "-server.log")
    p5_path = out_path.with_name(out_path.stem + "-p5.txt")
    try:
        TARGET.write_bytes(text.encode("utf-8"))
        print(f"已注入（原 sha256 {before[:12]}）")
        if log.exists():
            log.unlink()
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
                   FIRSTEP_BROWSER_SERVER_LOG=str(log))
        proc = subprocess.run(
            ["node", "--test", "--test-concurrency=1",
             "tests/browser/launcher-reload.spec.mjs"],
            cwd=str(REPO), env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        out = (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or "")
        out_path.write_text(out, encoding="utf-8")
        p5 = []
        if log.exists():
            p5 = [ln.rstrip() for ln in
                  log.read_text(encoding="utf-8", errors="replace").splitlines()
                  if "[P5]" in ln]
            p5_path.write_text("\n".join(p5), encoding="utf-8")
        # stdout 会被上层重定向，落盘才是给下一轮读的；这里只报计数与关键行
        print(f"探针输出已落盘：{out_path.name}")
        print(f"[P5] 行数 {len(p5)} -> {p5_path.name}")
        for ln in p5[-25:]:
            print("   " + ln)
        print("探针 stdout 尾段：")
        for ln in out.splitlines()[-30:]:
            print("   " + ln)
    finally:
        TARGET.write_bytes(original)
        after = digest(TARGET)
        ok = "逐字节复原 OK" if after == before else "**复原失败**"
        print(f"收尾复核：{ok}（{after[:12]}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
