# -*- coding: utf-8 -*-
"""LLM 工作流观测缝（工单 webapp-consolidation/02）：行为直测 + 单源结构守卫。

**为什么单独立一个文件**：这条缝的判据不是某个路由的行为，而是**「预算 + 观测
收集器 + 客户端派发 + 结算」四件事各恰好一处**这条不变量（同款先例：
`tests/test_download_sequence_home.py`）。判据写成纯函数，红证可喂合成片段或
HEAD 版源码，不必手改仓库文件。

缝的语义与「为什么这四件必须一起做对」写在 `webapp.LLMRun` 的类 docstring 里，
此处不重复。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from contest_generator.config import AppConfig
from contest_generator.llm import build_llm
from contest_generator.webapp import AppContext, LLMRun
from tests.fakes import FakeTransport

REPO = Path(__file__).resolve().parents[1]
WEBAPP_PATH = REPO / "src" / "contest_generator" / "webapp.py"


def _context(tmp_path: Path, factory) -> AppContext:
    """最小 AppContext：真配置形状 + 注入的工厂（不碰真配置目录）。"""
    return AppContext(
        config_path=tmp_path / "cfg" / "config.json",
        config=AppConfig(
            api_key="sk-test",
            module_library_dir=tmp_path / "modules",
            masters_dir=tmp_path / "masters",
        ),
        llm_factory=factory,
    )


def _api_response(content: str) -> str:
    """DeepSeek 响应包络（与 tests/test_llm.py 同款）：content 在 choices[0].message.content。"""
    return json.dumps({"choices": [{"message": {"content": content}}]})


# ---------------------------------------------------------------------------
# 行为：缝的 interface（派发 / 只观测 / 结算）
# ---------------------------------------------------------------------------


def test_dispatch_shares_one_budget_and_collector_across_calls(tmp_path):
    """同一趟的多次派发共享同一个预算与收集器对象（既有工厂契约，收口不许改）。

    这正是 `tests/test_webapp.py` 两条 skeleton / recommend 用例钉的语义——那两条
    走 HTTP 端到端，这条把同一判据钉在缝的直测面上。
    """
    seen: list[tuple[object, object]] = []

    def factory(config, retry_budget=None, observation_collector=None):
        seen.append((retry_budget, observation_collector))
        return object()

    context = _context(tmp_path, factory)
    llm_run = LLMRun(context, "unit-test")

    first, second = llm_run.llm(), llm_run.llm()

    assert first is not second, "每次取用都现派发（不缓存同一个客户端）"
    assert len(seen) == 2
    assert seen[0][0] is not None and seen[0][0] is seen[1][0], "预算跨派发同一个对象"
    assert seen[0][1] is not None and seen[0][1] is seen[1][1], "收集器跨派发同一个对象"
    assert seen[0][1] is llm_run.collector
    assert llm_run.collector.workflow_id.startswith("unit-test:")


def test_one_argument_factory_still_works(tmp_path):
    """1 参数工厂照旧（`_llm` 的兼容面不动）：本地路由注入的就是这种。"""
    sentinel = object()
    llm_run = LLMRun(_context(tmp_path, lambda config: sentinel), "unit-test")

    assert llm_run.llm() is sentinel


def test_observation_only_run_builds_no_model(tmp_path):
    """只做观测的工作流（视觉那 5 处）：不碰 `.llm()` 就一个模型都不造。"""
    calls: list[object] = []
    llm_run = LLMRun(
        _context(tmp_path, lambda config: calls.append(config)), "vision-describe"
    )

    assert llm_run.collector.workflow_id.startswith("vision-describe:")
    llm_run.settle()
    assert calls == [], "没取客户端就不该派发工厂"


def test_settle_records_the_workflow_once_and_is_idempotent(tmp_path):
    """结算把这一趟记进 recent_llm_workflows；重复调只记一条（幂等）。"""
    transport = FakeTransport(body=_api_response("Auto_Car"))

    def factory(config, retry_budget=None, observation_collector=None):
        return build_llm(config, retry_budget, observation_collector, transport)

    context = _context(tmp_path, factory)
    llm_run = LLMRun(context, "unit-test")

    assert llm_run.llm().name_topic_english("设计并制作一个自动行驶小车") == "Auto_Car"
    llm_run.settle()
    llm_run.settle()  # 幂等：同一趟不许记两条

    workflows = context.recent_llm_workflows.to_dict()["workflows"]
    assert [item["workflow_name"] for item in workflows] == ["unit-test"]
    assert workflows[0]["call_count"] == 1
    assert workflows[0]["status"] == "success"


def test_settle_leaves_an_empty_run_unrecorded(tmp_path):
    """一次调用都没有的趟不记（`add_completed` 的既有语义：空观测不进面板）。"""
    context = _context(tmp_path, lambda config: object())
    LLMRun(context, "unit-test").settle()

    assert context.recent_llm_workflows.to_dict()["workflows"] == []


def test_llm_run_carries_the_workflow_name_into_the_collector(tmp_path):
    """工作流名由调用方给（观察面板按它分组）——缝不改写它，落在收集器身份里。"""
    llm_run = LLMRun(_context(tmp_path, lambda config: object()), "tasks-plan")
    assert isinstance(llm_run, LLMRun)
    assert llm_run.collector.workflow_id.startswith("tasks-plan:")


# ---------------------------------------------------------------------------
# 单源守卫：四件事各恰好一处，且都落在缝内
# ---------------------------------------------------------------------------


def _called_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


# 判据四条：探针名 → 认哪个调用（`dispatch` 只认**带预算 / 收集器**的派发——
# `_llm(context)` 的裸调用是另一回事，本单不动）
_PROBES = {
    "collector": lambda node: _called_name(node) == "create_llm_observation_collector",
    "budget": lambda node: _called_name(node) == "RetryBudget",
    "dispatch": lambda node: _called_name(node) == "_llm" and len(node.args) >= 2,
    "settle": lambda node: _called_name(node) == "add_completed",
}


def _triple_sites(source: str) -> dict[str, list[str]]:
    """四件事**每一个调用点**落在哪个函数里（形如 `LLMRun.__init__`；判据纯函数）。

    **不按函数去重**：工单判据是"各恰好一处"，同一函数里写两遍也算违规——去重会把
    它放过（评审抓到的判据强度问题）。列表元素数就是调用点数。
    限定名（类名.函数名）而不是裸函数名：`llm` / `settle` 这种名字在别处也可能有。
    """
    sites: dict[str, list[str]] = {name: [] for name in _PROBES}

    def walk(node: ast.AST, stack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(child, [*stack, child.name])
                continue
            if isinstance(child, ast.Call):
                owner = ".".join(stack) or "<module>"
                for probe, matches in _PROBES.items():
                    if matches(child):
                        sites[probe].append(owner)
            walk(child, stack)

    walk(ast.parse(source), [])
    return sites


def test_llm_triple_has_a_single_home():
    """四件事**各恰好一处**，且都落在缝里（webapp 其它地方再出现、或同一处写两遍即红）。"""
    sites = _triple_sites(WEBAPP_PATH.read_text(encoding="utf-8"))
    assert sites == {
        "collector": ["LLMRun.__init__"],
        "budget": ["LLMRun.__init__"],
        "dispatch": ["LLMRun.llm"],
        "settle": ["LLMRun.settle"],
    }, f"三件套散回路由了：{sites}"


def test_llm_triple_guard_is_not_vacuous():
    """红证（合成片段）：在路由里重新长出三件套 → 判据当场认出（守卫不是摆设）。"""
    fake = (
        "def route(ctx):\n"
        "    budget = RetryBudget()\n"
        "    collector = create_llm_observation_collector('recommend')\n"
        "    llm = _llm(ctx, budget, collector)\n"
        "    ctx.recent_llm_workflows.add_completed(collector)\n"
        "    return _llm(ctx)\n"
    )
    sites = _triple_sites(fake)
    assert sites == {
        "collector": ["route"],
        "budget": ["route"],
        "dispatch": ["route"],
        "settle": ["route"],
    }, f"合成片段没被认出来：{sites}"


def test_llm_triple_guard_counts_every_call_site():
    """同一个函数里写两遍也要红（判据**不去重**——"各恰好一处"是字面意思）。"""
    twice = (
        "def route(ctx):\n"
        "    a = create_llm_observation_collector('x')\n"
        "    b = create_llm_observation_collector('y')\n"
        "    ctx.recent_llm_workflows.add_completed(a)\n"
        "    ctx.recent_llm_workflows.add_completed(b)\n"
    )
    sites = _triple_sites(twice)
    assert sites["collector"] == ["route", "route"]
    assert sites["settle"] == ["route", "route"]


def test_bare_llm_call_is_not_a_dispatch():
    """裸 `_llm(ctx)`（7 处低配端点）不算三件套派发——本单不动它们。"""
    assert _triple_sites("def route(ctx):\n    return _llm(ctx)\n")["dispatch"] == []
