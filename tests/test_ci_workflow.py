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
    """不吃 secret；action 只用 GitHub 官方的那几个（多一个就多一处供应链面）。

    **「不联网」这条约定的真实边界**（工单 ui-dom-contract-gate/03 写明）：
    说的是**测试本身不打网络**——`tests/**` 里的用例走 `tests/fakes.py` 的桩，
    所以 CI 不需要任何凭据。而 CI 的**装依赖步骤本来就要联网**（pip / npm /
    `npx playwright install chromium` 都是下载），那不是"测试联网"，
    也不改变"测试不打网络"这条判据。别把两件事混起来读。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text, "CI 用了 secret——本仓库测试刻意不联网，不该需要凭据"
    jobs = workflow.get("jobs") or {}
    allowed = ("actions/checkout", "actions/setup-python", "actions/setup-node")
    for job in jobs.values():
        for step in (job.get("steps") or []):
            uses = str(step.get("uses", ""))
            assert uses == "" or uses.startswith(allowed), (
                f"出现了非预期的第三方 action：{uses}（只许 GitHub 官方的 checkout / "
                "setup-python / setup-node，多一个就多一处供应链面）"
            )


def test_browser_suite_job_runs_the_same_command_as_local(workflow):
    """浏览器门禁 job（工单 ui-dom-contract-gate/03）：存在、跑**与本地同一条命令**、装齐前置。

    判据是"判据只有一份"——本地 `tools/prepush.py:run_browser_tests` 与 CI 里这条
    必须是同一个 glob、同一串参数（`--test-concurrency=1` 是硬要求：每个 spec 各起
    一个真后端 + 一个真 Chromium，并发跑只会让失败不可归因）。
    """
    jobs = workflow.get("jobs") or {}
    browser_jobs = {name: job for name, job in jobs.items()
                    if any("tests/browser/*.spec.mjs" in str(step.get("run", ""))
                           for step in (job.get("steps") or []))}
    assert browser_jobs, "CI 里没有跑 tests/browser/*.spec.mjs 的 job——浏览器门禁没接上远端"
    runs = "\n".join(
        str(step.get("run", ""))
        for job in browser_jobs.values()
        for step in (job.get("steps") or [])
    )
    assert "node --test --test-concurrency=1" in runs, f"浏览器门禁没串行跑：\n{runs}"
    assert "npx playwright install chromium" in runs, "CI 没装 Chromium——浏览器用例起不来"
    assert "npm install" in runs, "CI 没装 npm 依赖（playwright）"
    runners = [str(job.get("runs-on", "")) for job in browser_jobs.values()]
    assert any("windows" in runner for runner in runners), f"浏览器门禁不在 Windows 上跑：{runners}"


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


def test_checkout_fetches_full_history(workflow):
    """checkout 必须取全历史（`fetch-depth: 0`）。

    2026-09-16 CI 实测：默认 `fetch-depth: 1` 的浅克隆里，`CHANGELOG` 锚点守卫
    查不到那个提交（连 HEAD~1 都没有）→ 在最需要它的地方假红。取全历史才有得查。
    """
    jobs = workflow.get("jobs") or {}
    checkouts = [
        step
        for job in jobs.values()
        for step in (job.get("steps") or [])
        if str(step.get("uses", "")).startswith("actions/checkout")
    ]
    assert checkouts, "没有 checkout 步骤"
    for step in checkouts:
        depth = (step.get("with") or {}).get("fetch-depth")
        assert depth == 0, f"checkout 没取全历史（fetch-depth={depth!r}）——锚点守卫会假红"
