# -*- coding: utf-8 -*-
"""CI 工作流的守卫（工单 commit-gate/04）。

**为什么要有**：CI 配置坏掉同样**静默**——YAML 写错、触发分支漏了 main、或者悄悄把
「不联网」那条约定破了，都不会有人立刻发现，直到某天真的需要它挡一次回归。
这里把「工作流存在、触发条件、跑什么命令、不吃 secret」这些契约钉住。
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    yaml = pytest.importorskip("yaml", reason="CI 契约用 yaml 解析（PyYAML 未装则跳过）")
    assert WORKFLOW.is_file(), ".github/workflows/ci.yml 不存在——远端没有闸门"
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "工作流不是一个映射"
    return data


def test_workflow_triggers_on_push_and_pull_request(workflow):
    """push 到 main 与 PR 都要触发（否则红照样能进 main）。"""
    # `on` 在 YAML 里可能被解析成布尔 True——两种写法都认
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict), f"触发段解析异常：{triggers!r}"
    push = triggers.get("push") or {}
    branches = push.get("branches") or []
    assert "main" in branches, f"push 没盯 main：{branches}"
    assert "pull_request" in triggers, "PR 上不跑 CI"


def test_workflow_runs_the_same_commands_as_local(workflow):
    """判据与本地同一套：`pytest -n auto` 与 `tools/preflight.py`（不另写一套）。"""
    jobs = workflow.get("jobs") or {}
    assert jobs, "工作流没有 job"
    all_runs = "\n".join(
        str(step.get("run", ""))
        for job in jobs.values()
        for step in (job.get("steps") or [])
    )
    assert "python -m pytest" in all_runs, "CI 没跑 pytest"
    assert "tools/preflight.py" in all_runs, "CI 没跑发版自检"
    assert "-n auto" in all_runs, "CI 没并行跑（本机实测并行 2 倍速，串行会拖长）"


def test_workflow_does_not_use_secrets_or_network_steps(workflow):
    """不联网、不吃 secret（仓库既有约定：测试用桩，见 tests/fakes.py）。"""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text, "CI 用了 secret——本仓库测试刻意不联网，不该需要凭据"
    jobs = workflow.get("jobs") or {}
    for job in jobs.values():
        for step in (job.get("steps") or []):
            uses = str(step.get("uses", ""))
            assert uses.startswith(("actions/checkout", "actions/setup-python", "")) or uses == "", (
                f"出现了非预期的第三方 action：{uses}（多一个就多一处供应链面）"
            )


def test_workflow_checks_out_and_installs_dev_extras(workflow):
    """checkout + 装 `.[dev]`（dev 组是仓库自己声明的测试依赖，不许在 CI 里另列一份）。"""
    jobs = workflow.get("jobs") or {}
    assert any(
        any(str(step.get("uses", "")).startswith("actions/checkout")
            for step in (job.get("steps") or []))
        for job in jobs.values()
    ), "没有 checkout 步骤"
    all_runs = "\n".join(
        str(step.get("run", ""))
        for job in jobs.values()
        for step in (job.get("steps") or [])
    )
    assert '.[dev]' in all_runs, "CI 没按 pyproject 的 dev 组装测试依赖"


def test_windows_job_present_for_platform_specific_risks(workflow):
    """必须有 windows-latest：路径长度 / CRLF 字节口径 / .ps1 编码这些风险只在 Windows 暴露。"""
    jobs = workflow.get("jobs") or {}
    runners = [str(job.get("runs-on", "")) for job in jobs.values()]
    assert any("windows" in runner for runner in runners), f"没有 Windows job：{runners}"
    assert any("ubuntu" in runner for runner in runners), f"没有 Linux 快速 job：{runners}"
