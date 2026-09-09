"""tracker 盘点脚本的状态行提取契约（2026-09-09 在途盘点修复）。

**为什么有这个测试**：`.scratch/tracker-audit/census.py` 与 `list_open_tickets.py`
早期各自写了一份「只认粗体 + 全角冒号」的正则，把 301 个半角冒号 / 标题式写法的
工单误算成「无状态行」，并**漏报过两张真正开放的工单**（`code-editor-refine/08`
claimed、`code-page-vscode-overhaul/07` ready-for-agent）。形态单源收敛到
`.scratch/tracker-audit/ticket_status.py` 后，本测试钉住三件事：

1. 三种形态都能提取（含半角/全角冒号、引用行、列表行、标题式）；
2. **全库不变量**：任何工单（非 `pr-body-*.md` 草稿）都必须被提取到状态——
   将来若有人用第四种写法新开工单，这里立刻红；
3. 两个脚本的端到端输出不漏任何 `ticket_status.is_open` 判定的未完成工单。

模块从 `.scratch/tracker-audit/` 经 importlib 加载（照 `tests/test_generate_check_contract.py`
先例：该目录在 gitignore 内但被 force-tracked）。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / ".scratch" / "tracker-audit"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_tracker_{name}", SCRIPT_DIR / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def status():
    return _load("ticket_status")


# ---------------------------------------------------------------------------
# 1. 三形态提取
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# 工单\n\n**Status:** resolved\n", "resolved"),
        ("# 工单\n\n**状态：** ready-for-agent\n", "ready-for-agent"),
        ("# 工单\n\n**Status：** claimed\n", "claimed"),
        ("# 工单\n\nStatus: resolved\n", "resolved"),
        ("# 工单\n\n- Status: resolved\n", "resolved"),
        ("# 工单\n\n> 状态：resolved（双轴评审通过）\n", "resolved"),
        ("# 工单\n\n## 状态\n\nresolved\n", "resolved"),
        ("# 工单\n\n## Status\n\nclaimed\n", "claimed"),
        ("# 工单\n\n没有状态行\n", None),
        # 变体值原样返回（形态归一由 census 分桶负责，不在提取层做判决）
        ("# 工单\n\n**Status:** resolved：2026-08-23\n", "resolved：2026-08-23"),
        ("# 工单\n\n**Status:** 已实施\n", "已实施"),
    ],
)
def test_extract_status_forms(status, text, expected):
    assert status.extract_status(text) == expected


def test_extract_status_prefers_head_over_body(status):
    """状态行按约定在文首：正文里引用别人状态不应盖过顶部真状态。"""
    text = "# 工单\n\n**Status:** claimed\n\n" + ("正文\n" * 60) + "\n**Status:** resolved\n"
    assert status.extract_status(text) == "claimed"


def test_extract_status_falls_back_to_body(status):
    """状态行写在 40 行之后（generate-gate/01 实例）也要认出来。"""
    text = "# 工单\n\n" + ("正文\n" * 60) + "\n**Status:** resolved\n"
    assert status.extract_status(text) == "resolved"


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("claimed", True),
        ("ready-for-agent", True),
        ("ready-for-human", True),
        ("needs-info", True),
        ("resolved", False),
        ("已实施", False),
        ("deferred", False),
        (None, False),
    ],
)
def test_is_open(status, state, expected):
    assert status.is_open(state) is expected


# ---------------------------------------------------------------------------
# 2. 全库不变量
# ---------------------------------------------------------------------------


def test_every_ticket_status_is_detected(status):
    """全库工单（非 pr-body 草稿）都必须能被提取到状态——第四种写法出现即红。"""
    missing = []
    for path in sorted((ROOT / ".scratch").glob("*/issues/*.md")):
        if path.name.startswith("pr-body"):
            continue  # PR body 草稿不是工单
        if status.extract_status(path.read_text(encoding="utf-8", errors="replace")) is None:
            missing.append(str(path.relative_to(ROOT)))
    assert missing == [], f"这些工单的状态行形态未被识别：{missing}"


def test_ascii_colon_tickets_are_detected(status):
    """回归锚点：半角冒号形态的工单必须被提取到（旧正则漏报的实例）。

    锚点用「形态」而非固定值——工单翻牌后状态会变，但形态不该变。
    """
    for rel in (
        ".scratch/code-editor-refine/issues/08-ai-apply-locate-insert.md",
        ".scratch/code-page-vscode-overhaul/issues/07-code-visual-polish.md",
        ".scratch/identity-fields/issues/06-pending-identity-sources-human.md",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        state = status.extract_status(text)
        assert state is not None, f"{rel} 的状态行未被识别"
        assert state in status.STANDARD_STATES, f"{rel} 状态值非标准：{state}"


# ---------------------------------------------------------------------------
# 3. 脚本端到端
# ---------------------------------------------------------------------------


def _run(script: str) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={"PYTHONIOENCODING": "utf-8", "PATH": __import__("os").environ.get("PATH", "")},
        check=True,
    )
    assert "SyntaxWarning" not in result.stderr, result.stderr
    return result.stdout


def test_census_buckets_are_not_all_unknown(status):
    """census 的分桶与提取器一致：resolved（含变体）/ 非标准值 / 无状态行 三桶计数
    等于按 ticket_status 现算的结果——不再把半角冒号形态误算成无状态行。"""
    import re

    expected = {"resolved": 0, "非标准值": 0, "无状态行": 0}
    for path in sorted((ROOT / ".scratch").glob("*/issues/*.md")):
        state = status.extract_status(path.read_text(encoding="utf-8", errors="replace"))
        if state is None:
            expected["无状态行"] += 1
        elif state == "resolved" or state.startswith("resolved"):
            expected["resolved"] += 1
        elif state in status.STANDARD_STATES:
            continue  # claimed / ready-* / needs-* / wontfix 各成一桶
        else:
            expected["非标准值"] += 1

    out = _run("census.py")
    assert "(none)" not in out
    assert f"'resolved': {expected['resolved']}" in out
    assert f"非标准值 {expected['非标准值']} 张" in out
    assert f"无状态行 {expected['无状态行']} 张" in out
    # 无状态行只剩 pr-body 草稿（非工单）
    pr_bodies = len(list((ROOT / ".scratch").glob("*/issues/pr-body-*.md")))
    assert expected["无状态行"] == pr_bodies
    assert re.search(r"resolved 变体形态 \d+ 张", out)


def test_list_open_tickets_covers_every_open_ticket(status):
    """清单脚本的每一张未完成工单都要出现在输出里（不漏报）。"""
    out = _run("list_open_tickets.py")
    expected = []
    for path in sorted((ROOT / ".scratch").glob("*/issues/*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if status.is_open(status.extract_status(text)):
            expected.append(f"{path.parent.parent.name}/{path.name}")
    assert expected, "全库竟无未完成工单——先确认 tracker 是否被误改"
    missing = [rel for rel in expected if rel not in out]
    assert missing == [], f"这些未完成工单未出现在清单输出：{missing}"
