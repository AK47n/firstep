"""launcher 留痕门禁（工单 launcher-failure-reason/01）。

三组断言，只看**外部可观察事实**：

1. `tools/launcher-log.ps1` 的表层行为（真跑它、解析落盘的那一行）；
2. **静态守卫 + 守卫自身的回归测试**：`start-app.bat` 的每一条 `exit /b` 之前必须有一次带
   `-Reason` 的 launcher-log 调用，每个 reason 码必须落在**本文件里的码表**（单源）里，
   且码表里的每个码都被真的用到；守卫的判据用合成 `.bat` 文本正反各跑一遍（防「守卫自己被写坏、
   于是新分支漏留痕也判绿」）；
3. **端口覆盖单源**（`webapp.resolve_port` 与 `start-app.bat` 同口径）+ **真机分支矩阵验收件的在位性**
   （探针脚本、落盘、7 态判读、全 PASS、时间戳新鲜）。

### 硬约束：本文件**不跑任何会弹框的 launcher 分支**

`start-app.bat` 的失败分支用 `WScript.Shell.Popup` 弹**模态**框——没人点「确定」它就不返回。
第一版实现把这些分支直接放进 pytest，后果是：① 用户桌面上真的被弹了一排框（两次截图报障）；
② 测试挂死 9 分钟。**教训：真机矩阵必须先把弹窗宿主变成不可能存在的东西，再谈跑不跑。**

拦框的方案逐条实测过，只有「不在测试里跑失败分支」是稳的：

| 方案 | 结果 |
|---|---|
| PATH/PATHEXT 前置垫片 | ❌ 无效：launcher 调的是**绝对路径** `%SystemRoot%\\System32\\…\\powershell.exe`，cmd 直接 CreateProcess 它 |
| 「假 SystemRoot + 批处理桩 `powershell.exe`」 | ❌ 报「不是有效的 Win32 应用程序」 |
| 「假 SystemRoot + `powershell.cmd`」 | ❌ launcher 命令行带 `.exe` 后缀，`.cmd` 不被查询 |
| 「假 SystemRoot 里不放 powershell」 | ⚠️ 弹框确实不可能出现，但 `launcher.log` 也写不出来（留痕本身要调 powershell）⇒ 断言不了分支码。**因此本文件只拿它当兜底**，不靠它跑失败分支 |
| **交给真机探针跑（第 3 组断言的对象）** | ✅ 探针用真 SystemRoot 跑、自带弹窗清扫线程 + 到点 `taskkill /T`，判读看 `launcher.log` 的 reason 行 |

所以真机分支矩阵的**执行**在
`.scratch/launcher-failure-reason/probe-01-branch-matrix.py`（按需手动跑，约 2 分钟），
本文件只钉住它的**判据与落盘**。
"""

from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_LOG_PS1 = ROOT / "tools" / "launcher-log.ps1"
START_APP_BAT = ROOT / "start-app.bat"
FEATURE_DIR = ROOT / ".scratch" / "launcher-failure-reason"
PROBE = FEATURE_DIR / "probe-01-branch-matrix.py"
PROBE_EVIDENCE = FEATURE_DIR / "verify-01-branch-matrix.txt"

POWERSHELL = (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
              / "WindowsPowerShell" / "v1.0" / "powershell.exe")

REASON_RE = re.compile(r"reason=([a-z][a-z0-9_]*)")
LOG_LINE_RE = re.compile(
    r"^\[(?P<stamp>[^\]]+)\] reason=(?P<reason>[a-z][a-z0-9_]*)(?P<rest>(?: [A-Za-z][A-Za-z0-9_]*=\S+)*)$")
LOGGER_RE = re.compile(r"-Reason\s+([a-z][a-z0-9_]*)")

#: reason 码表单源（spec「reason 码表」一节；改码表必须同时改这里 + launcher + spec 表格）
REASON_CODES = frozenset({
    "updating", "update_left", "no_python", "old_python", "no_deps",
    "port_busy", "timeout", "already_running", "started",
})

#: 真机矩阵要覆盖的形态（探针落盘里必须逐条有判读段）
EXPECTED_BRANCHES = ("updating", "no_python", "started", "already_running",
                     "port_busy", "timeout", "already_running@8000")

#: 落盘新鲜度上限（天）：超过就说明是旧证据，真机结论不再可信
EVIDENCE_MAX_AGE_DAYS = 30


def _bat_text(path: Path = START_APP_BAT) -> str:
    """start-app.bat 是 GBK 无 BOM（cmd 按 ANSI 解析），测试按 gbk 读。"""
    return path.read_bytes().decode("gbk", errors="replace")


def _ps1_source() -> str:
    raw = LAUNCHER_LOG_PS1.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "tools/launcher-log.ps1 必须是 UTF-8 with BOM（仓库硬性约定）"
    return raw.decode("utf-8-sig")


# ------------------------------------------------------------ 1. helper 行为

def _write_log(profile: Path, reason: str, fields: list[str] | None = None) -> str:
    """真跑 helper 写一行，返回它写进文件的那一行文本。"""
    cmd = [str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-File", str(LAUNCHER_LOG_PS1), "-Reason", reason]
    cmd.extend(fields or [])
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                          env={**os.environ, "USERPROFILE": str(profile)}, timeout=120)
    assert proc.returncode == 0, f"launcher-log.ps1 退出码 {proc.returncode}：{proc.stderr}"
    log = profile / ".contest_generator" / "launcher.log"
    assert log.is_file(), "launcher-log.ps1 没有写出 launcher.log"
    return log.read_text(encoding="utf-8").splitlines()[-1]


def test_launcher_log_writes_parseable_line(tmp_path: Path):
    """写出来的一行：ISO8601（带时区）+ reason + 附加 key=value，值内无空格。"""
    line = _write_log(tmp_path, "port_busy", ["port=8899"])
    m = LOG_LINE_RE.match(line)
    assert m, f"日志行形态不符：{line!r}"
    assert m.group("reason") == "port_busy"
    assert " port=8899" in m.group("rest")
    stamp = dt.datetime.fromisoformat(m.group("stamp"))
    assert stamp.tzinfo is not None, "时间戳必须带时区偏移"
    assert abs((dt.datetime.now(stamp.tzinfo) - stamp).total_seconds()) < 300


def test_launcher_log_appends_and_creates_dir(tmp_path: Path):
    """追加语义（不是覆盖）+ 目标目录不存在时自动创建 + 文件 UTF-8 无 BOM。"""
    profile = tmp_path / "no-such-home"
    assert not profile.exists()
    _write_log(profile, "no_python")
    _write_log(profile, "started", ["tries=2"])
    log = profile / ".contest_generator" / "launcher.log"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, f"应为追加语义（两行），实得：{lines}"
    assert REASON_RE.search(lines[0]).group(1) == "no_python"
    assert " tries=2" in lines[1]
    assert not log.read_bytes().startswith(b"\xef\xbb\xbf"), "launcher.log 不得带 BOM"


def test_launcher_log_rejects_unusable_input(tmp_path: Path):
    """码表外的 reason / 带空格的字段值都被挡下发错（不给日志写垃圾）。"""
    for reason in ("Port-Busy", "port busy", ""):
        proc = subprocess.run(
            [str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(LAUNCHER_LOG_PS1), "-Reason", reason],
            capture_output=True, text=True, errors="replace",
            env={**os.environ, "USERPROFILE": str(tmp_path)}, timeout=120,
        )
        assert proc.returncode != 0, f"reason={reason!r} 应被拒绝"
    proc = subprocess.run(
        [str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(LAUNCHER_LOG_PS1), "-Reason", "started", "tries=2 3"],
        capture_output=True, text=True, errors="replace",
        env={**os.environ, "USERPROFILE": str(tmp_path)}, timeout=120,
    )
    assert proc.returncode != 0, "字段值含空格应被拒绝"
    assert not (tmp_path / ".contest_generator" / "launcher.log").exists(), "被拒绝时不得留下日志"


# ------------------------------------------------------------ 2. 静态守卫（含守卫自身回归）

def _exit_lines(text: str) -> list[int]:
    out = []
    for i, line in enumerate(text.splitlines()):
        s = line.strip()
        if s.startswith("rem ") or s.startswith("::"):
            continue
        if re.match(r"^exit\s+/b\b", s, re.IGNORECASE):
            out.append(i)
    return out


def _log_call_lines(text: str) -> list[int]:
    """真正「写一行日志」的调用行 = 带 `-Reason <码>` 的那些（`set LAUNCHER_LOG_PS1=…` 不算）。"""
    out = []
    for i, line in enumerate(text.splitlines()):
        s = line.strip()
        if s.startswith("rem ") or s.startswith("::"):
            continue
        if LOGGER_RE.search(s):
            out.append(i)
    return out


def _guard_violations(text: str, codes: frozenset[str] = REASON_CODES) -> list[str]:
    """守卫判据单源（拆出来是为了能拿合成文本正反各跑一遍）。

    返回违规清单；空清单 = 通过。判据三条：
      ① 每条 `exit /b` 之前必须有一次留痕调用，且紧邻（≤5 行，容忍中间夹几条 rem）；
      ② 留痕调用数与退出分支数一一对应；
      ③ 出现的 reason 码集合必须**恰好等于**码表（漏引用 / 表外新码都算违规）。
    """
    lines = text.splitlines()
    exits = _exit_lines(text)
    calls = _log_call_lines(text)
    problems: list[str] = []
    seen: list[str] = []
    for idx in exits:
        preceding = [c for c in calls if c < idx]
        if not preceding:
            problems.append(f"第 {idx + 1} 行的 exit /b 之前没有留痕调用")
            continue
        gap = idx - preceding[-1]
        if gap > 5:
            problems.append(f"第 {idx + 1} 行与它前面的留痕调用隔了 {gap} 行（疑似贴错分支）")
        m = LOGGER_RE.search(lines[preceding[-1]])
        if not m:
            problems.append(f"留痕调用缺少 -Reason：{lines[preceding[-1]]!r}")
            continue
        seen.append(m.group(1))
    if len(calls) != len(exits):
        problems.append(f"留痕调用 {len(calls)} 处、退出分支 {len(exits)} 处，应一一对应")
    if set(seen) != set(codes):
        problems.append(f"reason 码与码表不一致：分支={sorted(set(seen))} 码表={sorted(codes)}")
    return problems


def test_every_exit_branch_logs_reason():
    """真文件的守卫断言：每条 `exit /b` 前必有一次带 -Reason 的留痕调用，码与码表一致。"""
    text = _bat_text()
    assert len(_exit_lines(text)) >= 9, f"start-app.bat 退出分支数异常：{len(_exit_lines(text))}"
    assert _guard_violations(text) == []


def test_guard_catches_regressions_on_synthetic_bat():
    """守卫自身回归：合成文本上**必须**能抓住三类违规（否则守卫是摆设）。"""
    ok = (
        "@echo off\r\n"
        ":a\r\nrem launcher-log\r\n"
        '"ps" -File "x.ps1" -Reason updating\r\n'
        "exit /b 1\r\n"
        ":b\r\nrem launcher-log\r\n"
        '"ps" -File "x.ps1" -Reason started\r\n'
        "exit /b 0\r\n"
    )
    codes = frozenset({"updating", "started"})
    assert _guard_violations(ok, codes) == [], "正例被误判"

    no_log = ok.replace('"ps" -File "x.ps1" -Reason started\r\n', "")
    hits = _guard_violations(no_log, codes)
    assert any("没有留痕调用" in p or "一一对应" in p for p in hits), f"漏留痕没抓住：{hits}"

    stray_code = ok.replace("-Reason started", "-Reason whatever")
    hits = _guard_violations(stray_code, codes)
    assert any("码与码表不一致" in p for p in hits), f"表外新码没抓住：{hits}"

    duplicated = ok.replace("-Reason started", "-Reason updating")
    hits = _guard_violations(duplicated, codes)
    assert any("码与码表不一致" in p for p in hits), f"重复用码没抓住：{hits}"

    far_away = ok.replace("rem launcher-log\r\n", "") + ("\r\n" * 8) + ":c\r\nexit /b 1\r\n"
    hits = _guard_violations(far_away, codes)
    assert any("疑似贴错分支" in p or "没有留痕调用" in p for p in hits), f"隔太远没抓住：{hits}"


def test_reason_code_table_matches_spec_table():
    """码表单源与 spec 的码表表格必须逐条对齐（表涨了忘了改代码 = 在这里红）。

    spec 里码表是紧跟在一行「- **reason 码表**（…）：」之后、以**空行**收尾的表；
    这里只取该段里的表格行，避免把 spec 别处的代码块当条目。
    """
    spec = (FEATURE_DIR / "spec.md").read_text(encoding="utf-8")
    header = re.search(r"\*\*reason 码表\*\*", spec)
    assert header, "spec 里找不到「reason 码表」标题"
    # 标题行之后就是表格（中间可能空一行）：取「连续的以 | 开头的行」，直到表格结束
    rows: list[str] = []
    for line in spec[header.end():].splitlines():
        if line.strip().startswith("|"):
            rows.append(line)
        elif rows:
            break
    assert rows, "spec 码表段里一行表格都没解析到"
    table_codes = set(re.findall(r"^\s*\|\s*`([a-z][a-z0-9_]*)`\s*\|", "\n".join(rows), re.MULTILINE))
    assert table_codes, f"spec 码表段里没有解析到条目：{rows[:3]!r}"
    assert table_codes == set(REASON_CODES), (
        f"spec 码表与测试码表不一致：spec 独有={sorted(table_codes - set(REASON_CODES))} "
        f"测试独有={sorted(set(REASON_CODES) - table_codes)}")


def test_bat_keeps_ansi_encoding_and_crlf():
    """改 .bat 不得引入 UTF-8 BOM / 裸 LF；新增的留痕注释行保持 ASCII。"""
    raw = START_APP_BAT.read_bytes()
    assert raw[:3] != b"\xef\xbb\xbf", "start-app.bat 不得是 UTF-8 BOM"
    assert b"\r\n" in raw
    assert len(re.findall(rb"(?<!\r)\n", raw)) == 0, "start-app.bat 出现裸 LF"
    for line in _bat_text().splitlines():
        if line.strip() == "rem launcher-log":
            assert line.isascii(), "新增的留痕注释行不得引入非 ASCII"


def test_launcher_log_ps1_is_single_source():
    """格式单源在 helper：.bat 不得自己拼日志写入。"""
    src = _ps1_source()
    assert "AppendAllText" in src, "helper 应使用 .NET 追加（Add-Content 首写会带 BOM）"
    assert "UTF8Encoding($false)" in src, "helper 必须显式写 UTF-8 无 BOM"
    assert "AppendAllText" in src and "Add-Content" not in _bat_text(), "start-app.bat 不得自己拼日志写入"


def test_poll_sleep_is_stdin_safe():
    """轮询里的「睡一秒」不得用 `timeout /t`。

    `timeout.exe` 在 stdin 被重定向（无控制台输入）时会**立刻**报错退出（实测「不支持输入重新定向，
    立即退出此进程」）⇒ 20 次轮询预算瞬间烧光、把「服务没起来」误判成「启动超时」。
    改用 `ping` 是本次有意偏离工单「不改控制流」之处，已记进 spec/工单的「实施记录」。
    """
    text = _bat_text()
    assert not re.search(r"(?m)^\s*timeout\s+/t\s", text), "轮询不得用 timeout /t（stdin 重定向会立刻失败）"
    assert "ping.exe" in text, "轮询应使用 ping 作为可移植的「睡一秒」"


# ------------------------------------------------------------ 3. 端口覆盖 + 验收件

def test_resolve_port_reads_env_override(monkeypatch: pytest.MonkeyPatch):
    """端口覆盖单源：`FIRSTEP_LAUNCHER_PORT` 合法才生效，非法/缺省一律回 8000。"""
    from contest_generator.webapp import DEFAULT_PORT, LAUNCHER_PORT_ENV, resolve_port

    assert DEFAULT_PORT == 8000
    monkeypatch.delenv(LAUNCHER_PORT_ENV, raising=False)
    assert resolve_port() == 8000
    for raw in ("8899", " 8899 ", "1", "65535"):
        monkeypatch.setenv(LAUNCHER_PORT_ENV, raw)
        assert resolve_port() == int(raw.strip()), raw
    for raw in ("", "abc", "0", "65536", "-1", "80.5"):
        monkeypatch.setenv(LAUNCHER_PORT_ENV, raw)
        assert resolve_port() == 8000, raw


def test_launcher_bat_validates_same_port_env():
    """launcher 侧必须与 `resolve_port` **同口径**地校验端口。

    只查「变量名出现次数」是不够的：两侧口径不一致时会出现「launcher 轮询坏端口、服务绑 8000」
    的假超时（探针实测误判过 `started`）。所以这里要求 `.bat` 里有数字形态校验 + 上界回落。
    """
    from contest_generator.webapp import LAUNCHER_PORT_ENV

    text = _bat_text()
    assert LAUNCHER_PORT_ENV in text, f"start-app.bat 未使用 {LAUNCHER_PORT_ENV}"
    assert text.count(f"%{LAUNCHER_PORT_ENV}%") >= 5, "launcher 里端口变量用得比预期少（漏改一处？）"
    assert re.search(r"findstr /r \"\^\[1-9\]\[0-9\]\*\$\"", text), "缺少数字形态校验"
    assert "gtr 65535" in text, "缺少上界（65535）回落 8000"


def test_probe_artifact_and_wiring():
    """真机分支矩阵的**执行者是探针**：判据、落盘、7 态判读、全 PASS、证据新鲜。

    探针会真跑 launcher（含会弹框的 `port_busy` / `timeout`，以及真起一次服务的 `started`），
    自带弹窗清扫 + 浏览器抑制 + `taskkill /T`，耗时约 2 分钟，所以不进默认测试套，按需手动跑：

        $env:PYTHONIOENCODING='utf-8'; python .scratch/launcher-failure-reason/probe-01-branch-matrix.py

    说明（如实记账）：这条测试是**静态闸**，不重跑探针——手写一份「看起来很对」的落盘就能骗过它
    （评审已指出）。真正的证据是落盘本身（逐态 `reason` 行 + 退出码 + 耗时），外加新鲜度上限；
    要更强的绑定需要把探针跑进 CI，那是另一件事（本单范围外）。
    """
    assert PROBE.is_file(), f"缺少真机探针 {PROBE}"
    script = PROBE.read_text(encoding="utf-8")
    for branch in ("updating", "no_python", "started", "already_running", "port_busy", "timeout"):
        assert f'"{branch}"' in script, f"探针没有覆盖分支 {branch}"
    assert "taskkill" in script, "探针必须能连弹框宿主一起收干净（taskkill /T）"
    assert "弹窗清扫" in script, "探针必须带弹窗清扫（框不许留在用户桌面）"
    assert "suppress_browser" in script, "探针必须带浏览器抑制（不许反复真开浏览器）"

    assert PROBE_EVIDENCE.is_file(), f"缺少落盘证据 {PROBE_EVIDENCE}（先跑一次探针）"
    age_days = (dt.datetime.now().timestamp() - PROBE_EVIDENCE.stat().st_mtime) / 86400
    assert age_days <= EVIDENCE_MAX_AGE_DAYS, (
        f"落盘证据已过期（{age_days:.0f} 天 > {EVIDENCE_MAX_AGE_DAYS} 天），请重跑探针")
    evidence = PROBE_EVIDENCE.read_text(encoding="utf-8")
    assert "FAIL" not in evidence, "探针落盘里出现 FAIL，需重新取证"
    for branch in EXPECTED_BRANCHES:
        assert re.search(rf"\[{re.escape(branch)}\]\s*期望", evidence), f"落盘里缺少 {branch} 的判读段"
    m = re.search(r"合计：(\d+)/(\d+) PASS", evidence)
    assert m, "落盘里缺少合计判读行"
    got, total = int(m.group(1)), int(m.group(2))
    assert got == total == len(EXPECTED_BRANCHES), f"合计 {got}/{total} 与期望 {len(EXPECTED_BRANCHES)} 态不符"
    assert "已复原=True" in evidence, "落盘里缺少浏览器抑制的复原确认"
