# -*- coding: utf-8 -*-
"""前端测试门禁的守卫（工单 module-hwcheck/01）。

**为什么单独立一套**：`tests/js/` 那 1500 多条用例此前**没有任何自动触发点**——
pytest 面完全看不见它们（不是 `test_*.py`），本地闸门与 CI 都只管 Python。
于是"改了导航忘了同步守卫"、"fx 与 ui 双源漂移"这类错误只能等真机上发现
（2026-09-12「firstep 一打开就卡死」就是同一个盲区）。这道门禁的失效方式
同样是**静默**的：选择器少置一个标志位、CI 少一步、两边 glob 不一致——
都不会报错，只会"少跑了一批用例"，而"少跑"正好长得像"全绿"。

所以这里既测正例（前端落点必须置 js 标志 + pytest 面照旧倒向整套），
也测反例（非前端落点不得白白拖上前端门禁），并把**本地闸门与 CI 用的是
同一条命令、同一个 glob** 钉住。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO / "tools" / "prepush.py"
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


def load_prepush():
    spec = importlib.util.spec_from_file_location("prepush_js_gate", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["prepush_js_gate"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def prepush():
    return load_prepush()


# ---------------------------------------------------------------------------
# 选择器：前端落点必须置 js 标志（且 pytest 面照旧倒向整套）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "src/contest_generator/static/index.html",
        "src/contest_generator/static/js/fx/hwcheck.js",
        "src/contest_generator/static/js/ui/hwcheck.js",
        "src/contest_generator/static/js/app.js",
        "tests/js/nav-tabs-shared.mjs",
        "tests/js/nav-tabs-guard.test.mjs",
        "tests/js/hwcheck.test.mjs",
    ],
)
def test_frontend_paths_turn_on_js_gate(prepush, path):
    """前端落点（static/ 资产 + tests/js/ 用例）→ js=True，pytest 面仍整套。"""
    selection = prepush.select_tests([path])
    assert selection.js is True, f"{path} 应带起前端门禁"
    assert selection.full is True, f"{path} 在 pytest 面仍应倒向整套（认不出对应关系）"
    assert path in selection.reasons


def test_js_gate_glob_points_at_the_real_test_dir(prepush):
    """glob 必须指向真实存在的前端用例目录（改目录名后不会静默跑 0 个用例）。"""
    assert prepush.JS_TESTS_GLOB == "tests/js/*.test.mjs"
    assert (REPO / prepush.JS_TESTS_DIR).is_dir()
    assert list((REPO / "tests" / "js").glob("*.test.mjs")), "tests/js 下应有 *.test.mjs 用例"
    assert prepush.js_test_files(), "展开清单不该为空"


@pytest.mark.parametrize(
    "changed",
    [
        # 回归（评审抓到的真缺陷）：公共面 / 认不出的落点排在**前面**时，
        # 旧实现用 `return Selection(..., js=js)` 提前返回，而 js 还在循环里累加
        # ——那次提前返回把前端门禁整个吞掉。CI 配置按字母序排在改动清单首位，
        # 本单自己的改动集就命中了这一支。
        [".github/workflows/ci.yml", "src/contest_generator/static/index.html"],
        ["src/contest_generator/manifest.py", "src/contest_generator/static/js/ui/hwcheck.js"],
        ["src/contest_generator/static/index.html", ".github/workflows/ci.yml"],
        ["tools/prepush.py", "tests/js/nav-tabs-guard.test.mjs"],
    ],
)
def test_frontend_gate_survives_a_full_fallback_in_the_same_change(prepush, changed):
    """**顺序无关**：同一批改动里只要有前端落点，前端门禁就必须被带起。"""
    selection = prepush.select_tests(list(changed))
    assert selection.full is True, f"{changed} 应倒向整套"
    assert selection.js is True, (
        f"{changed} 里含前端落点，前端门禁却被吞掉了（改动顺序不该影响判据）"
    )


def test_full_fallback_keeps_every_frontend_entry_reason(prepush):
    """提前返回也不许丢理由：每条改动都要能在 reasons 里查到为什么。"""
    changed = [".github/workflows/ci.yml", "src/contest_generator/static/index.html"]
    selection = prepush.select_tests(changed)
    for rel in changed:
        assert rel in selection.reasons


def test_non_frontend_paths_do_not_turn_on_js_gate(prepush):
    """反例：后端 / 库 / 文档落点不得白白拖上前端门禁（门禁要跑得快才有人不绕过）。"""
    for path in (
        "src/contest_generator/changelog.py",
        "library/modules/oled/manifest.json",
        "docs/agents/workflow.md",
        "tests/test_hwcheck.py",
    ):
        assert prepush.select_tests([path]).js is False, f"{path} 不该带起前端门禁"


def test_non_js_file_under_tests_still_falls_back_to_full(prepush):
    """`tests/` 下认不出的非前端文件（老行为）仍倒向整套——本次改动不许松掉它。"""
    selection = prepush.select_tests(
        ["tests/_byte_server.py"],
        tests=frozenset({"tests/test_webapp.py"}),
        wide=frozenset(),
    )
    assert selection.full is True
    assert selection.js is False


def test_describe_mentions_the_js_gate(prepush):
    """闸门自报的那行必须说清"还要跑前端"——不然维护者以为只看 pytest 就够了。"""
    text = prepush.select_tests(["src/contest_generator/static/index.html"]).describe()
    assert "前端门禁" in text
    assert prepush.JS_TESTS_GLOB in text


# ---------------------------------------------------------------------------
# 执行：真红必须拒推；node 缺失按"闸门故障放行"
# ---------------------------------------------------------------------------


def test_run_js_tests_reports_node_missing_as_pass(prepush, monkeypatch, capsys):
    """node 不在 PATH → 打印原因 + 返回 0（不该把维护者堵在门外）。"""
    monkeypatch.setattr(prepush.shutil, "which", lambda name: None)
    assert prepush.run_js_tests() == 0
    out = capsys.readouterr().out
    assert "跳过前端门禁" in out
    assert "node" in out


def test_run_js_tests_propagates_failure(prepush, monkeypatch):
    """node 在、用例红了 → 非 0 原样传出（这是门禁存在的意义，不能被吞）。"""
    monkeypatch.setattr(prepush.shutil, "which", lambda name: "/usr/bin/node")
    monkeypatch.setattr(prepush.subprocess, "run", lambda *a, **k: type("R", (), {"returncode": 1})())
    assert prepush.run_js_tests() == 1


def test_run_js_tests_uses_the_expanded_file_list(prepush, monkeypatch):
    """执行的命令 = `node --test <展开后的每个用例>`（不把 glob 交给 node）。

    为什么不交 glob：`node --test` 的位置参数只有 **Node ≥21** 才支持 glob，
    Node 20 会把它当字面文件名而报 MODULE_NOT_FOUND。清单在 Python 侧展开
    （js_test_files）后传真实路径，任何版本都认——这条用例钉住那个形态。
    """
    seen: dict = {}

    class _Result:
        returncode = 0

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["cwd"] = kwargs.get("cwd")
        return _Result()

    monkeypatch.setattr(prepush.shutil, "which", lambda name: "node")
    monkeypatch.setattr(prepush.subprocess, "run", fake_run)
    assert prepush.run_js_tests() == 0
    files = prepush.js_test_files()
    assert files, "js_test_files() 不该为空"
    assert seen["cmd"] == ["node", "--test", *files]
    assert all(f.startswith("tests/js/") and f.endswith(".test.mjs") for f in files)
    assert Path(seen["cwd"]) == prepush.REPO_ROOT


def test_js_test_files_match_the_contract_glob(prepush):
    """清单与对外契约 `JS_TESTS_GLOB` 必须指向同一批文件（CI / 文档引用的就是它）。"""
    files = prepush.js_test_files()
    assert files == tuple(sorted(files)), "清单应排序（判据确定性）"
    assert set(files) == {
        p.relative_to(prepush.REPO_ROOT).as_posix()
        for p in (prepush.REPO_ROOT / "tests" / "js").glob("*.test.mjs")
    }
    assert prepush.JS_TESTS_GLOB.endswith("*.test.mjs")


def test_run_js_tests_reports_empty_list_as_pass(prepush, monkeypatch, capsys):
    """目录改名 / 清单过期 → 打印原因 + 返回 0（**不许**静默跑 0 个用例装作通过）。"""
    monkeypatch.setattr(prepush.shutil, "which", lambda name: "node")
    monkeypatch.setattr(prepush, "js_test_files", lambda: ())
    called = {"run": False}

    def fake_run(*args, **kwargs):
        called["run"] = True
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(prepush.subprocess, "run", fake_run)
    assert prepush.run_js_tests() == 0
    assert called["run"] is False, "清单为空时不该真起 node"
    out = capsys.readouterr().out
    assert "跳过前端门禁" in out
    assert "没有 *.test.mjs" in out


def test_js_gate_does_not_execute_under_dry_run(prepush, monkeypatch, capsys):
    """--dry-run / --select-only 只说不跑（前端门禁同理不许被真执行）。"""

    def forbidden(*args, **kwargs):
        raise AssertionError("dry-run 不该执行前端门禁")

    monkeypatch.setattr(prepush, "run_js_tests", forbidden)
    monkeypatch.setattr(prepush, "run_pytest", forbidden)
    code = prepush.main(
        ["--changed", "src/contest_generator/static/index.html", "--dry-run"]
    )
    assert code == 0
    assert prepush.JS_TESTS_GLOB in capsys.readouterr().out


def test_main_returns_nonzero_when_js_gate_fails(prepush, monkeypatch):
    """前端门禁红 → main 非 0（git 会因此拒推）。"""
    monkeypatch.setattr(prepush, "run_js_tests", lambda: 1)
    monkeypatch.setattr(prepush, "run_pytest", lambda paths, *, full: 0)
    assert prepush.main(["--changed", "tests/js/hwcheck.test.mjs"]) == 1


def test_full_mode_runs_js_gate_and_pytest(prepush, monkeypatch):
    """--full 两支都跑（发版 / 推 tag 时的口径：前端门禁不许被整套 pytest 顶掉）。"""
    calls: list[str] = []
    monkeypatch.setattr(prepush, "run_js_tests", lambda: calls.append("js") or 0)
    monkeypatch.setattr(prepush, "run_pytest", lambda paths, *, full: calls.append("pytest") or 0)
    assert prepush.main(["--full"]) == 0
    assert calls == ["js", "pytest"]


def test_no_js_flag_skips_the_gate(prepush, monkeypatch):
    """`--no-js` 是明写的例外（给"确知这次不需要前端用例"的场合留门）。"""

    def forbidden(*args, **kwargs):
        raise AssertionError("--no-js 不该跑前端门禁")

    monkeypatch.setattr(prepush, "run_js_tests", forbidden)
    monkeypatch.setattr(prepush, "run_pytest", lambda paths, *, full: 0)
    assert prepush.main(["--changed", "tests/js/hwcheck.test.mjs", "--no-js"]) == 0


# ---------------------------------------------------------------------------
# CI：与本地同一条命令、同一个 glob
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def workflow() -> dict:
    yaml = pytest.importorskip("yaml", reason="CI 契约用 yaml 解析（PyYAML 未装则跳过）")
    assert WORKFLOW.is_file(), ".github/workflows/ci.yml 不存在——远端没有闸门"
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_ci_runs_the_frontend_gate(workflow, prepush):
    """CI 必须跑前端门禁，且用的就是本地那条命令 / 那个 glob。"""
    runs = "\n".join(
        str(step.get("run", ""))
        for job in (workflow.get("jobs") or {}).values()
        for step in (job.get("steps") or [])
    )
    assert f'node --test "{prepush.JS_TESTS_GLOB}"' in runs, (
        "CI 没跑前端门禁（或者用的 glob 与本地闸门不一致——两边必须同一条命令）"
    )


def test_ci_pins_the_node_version(workflow):
    """CI 必须钉 node 版本：glob 位置参数要 Node ≥21，不钉就会随 runner 预装版本飘。"""
    jobs = workflow.get("jobs") or {}
    nodes = [
        step
        for job in jobs.values()
        for step in (job.get("steps") or [])
        if str(step.get("uses", "")).startswith("actions/setup-node")
    ]
    assert nodes, "CI 没有 setup-node 步骤——前端门禁会吃 runner 预装的 node 版本"
    for step in nodes:
        version = str((step.get("with") or {}).get("node-version", ""))
        assert version, "setup-node 没钉版本"
        major = int(re.match(r"\d+", version).group(0)) if re.match(r"\d+", version) else 0
        assert major >= 21, f"node-version={version!r} 太老——glob 位置参数要 ≥21"


def test_ci_frontend_gate_stays_offline_and_secretless(workflow):
    """前端门禁不许引入 secret / 网络步骤（仓库既有约定：两条不变量）。"""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text
    jobs = workflow.get("jobs") or {}
    for job in jobs.values():
        for step in (job.get("steps") or []):
            uses = str(step.get("uses", ""))
            assert uses.startswith(("actions/checkout", "actions/setup-python", "")) or uses == "", (
                f"出现了非预期的第三方 action：{uses}（多一个就多一处供应链面）"
            )


def test_local_gate_and_ci_share_one_glob_source(prepush):
    """两处引用的 glob 逐字相同（判据只有一份，改一处忘另一处 = 假绿）。"""
    ci = WORKFLOW.read_text(encoding="utf-8")
    assert prepush.JS_TESTS_GLOB in ci, "CI 里的 glob 与 tools/prepush.py 的常量不一致"
